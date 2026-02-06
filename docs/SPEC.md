# Human Execution Protocol (HXP) — Specification v0.1

## Abstract

The Human Execution Protocol (HXP) is an open protocol enabling AI agents to invoke human actions through a standardized interface. It defines a request/receipt model where agents emit structured execution requests, humans perform bounded actions, and agents receive machine-readable receipts to continue execution.

The protocol is transport-agnostic but provides an HTTP-based reference binding. It is designed to complement existing agent protocols (x402 for payments, MCP for tools, A2A for agent communication) by standardizing the agent-to-human execution layer.

## 1. Terminology

- **Agent**: An autonomous software system that encounters a boundary requiring human execution.
- **HXP Server**: A service that receives agent requests, routes them to humans, and returns receipts.
- **Human Client**: An interface (web, mobile, CLI, chat) through which a human executes requests.
- **Execution Request**: A structured message from an agent describing what human action is needed.
- **Execution Receipt**: A structured response confirming a human has acted, including the result and evidence.
- **Role**: A classification determining which human should handle an execution request.
- **Action**: A finite, well-defined type of human execution (e.g., DECIDE, APPROVE, PROVIDE).

## 2. Actions

HXP v0.1 defines three core actions. Additional actions may be added in future versions through an RFC process.

### 2.1 DECIDE

The agent presents a question with predefined options. The human selects one.

**Use cases**: Pricing approval, strategy choices, go/no-go decisions, configuration selection.

**Required fields**:
- `question` (string): The decision to be made
- `options` (array of strings, 2-6 items): The available choices

**Optional fields**:
- `context` (string, max 500 chars): Background information
- `default_option` (string): Pre-selected option if timeout occurs

**Receipt result**: The selected option (string, must match one of the provided options)

### 2.2 APPROVE

The agent presents an item or action for binary approval. The human approves or rejects.

**Use cases**: Expense approval, content review, deployment gates, contract signing.

**Required fields**:
- `item` (string): Description of what needs approval
- `details` (object): Structured data about the item

**Optional fields**:
- `context` (string, max 500 chars): Why approval is needed
- `reject_requires_reason` (boolean, default false): Whether rejection must include a reason

**Receipt result**: `"approved"` or `"rejected"` with optional `reason` field.

### 2.3 PROVIDE

The agent needs information only a human can supply.

**Use cases**: API keys, passwords, configuration values, creative input, physical-world observations.

**Required fields**:
- `prompt` (string): What information is needed
- `input_type` (enum): `text`, `number`, `url`, `email`, `file`, `selection`

**Optional fields**:
- `context` (string, max 500 chars): Why this information is needed
- `validation` (object): Constraints on the input (regex, min/max, allowed values)
- `placeholder` (string): Example of expected input

**Receipt result**: The provided value (type matches `input_type`).

## 3. Request Object

### 3.1 Schema

```json
{
  "request_id": "string (server-generated UUID)",
  "action": "DECIDE | APPROVE | PROVIDE",
  "role": "owner | delegate | pool",
  "priority": "low | normal | high | critical",
  "timeout_seconds": "integer (0 = no timeout)",
  "fallback": "pause | fail | default",
  "agent_id": "string (identifies the requesting agent)",
  "project_id": "string (optional, groups related requests)",
  "metadata": {
    "agent_framework": "string (e.g., 'langraph', 'crewai')",
    "agent_task": "string (what the agent is working on)"
  },
  "created_at": "ISO 8601 timestamp",
  "expires_at": "ISO 8601 timestamp or null",
  "payload": {
    // Action-specific fields (see Section 2)
  }
}
```

### 3.2 Priority Levels

| Priority | Description | Expected resolution |
|----------|------------|-------------------|
| `low` | Nice to have, agent can wait | Hours to days |
| `normal` | Standard request | Minutes to hours |
| `high` | Blocking critical path | Minutes |
| `critical` | Urgent, time-sensitive | Immediate notification |

### 3.3 Fallback Behaviors

| Fallback | On timeout |
|----------|-----------|
| `pause` | Agent pauses, request stays open indefinitely |
| `fail` | Agent receives a failure receipt |
| `default` | Agent receives receipt with `default_option` (DECIDE only) |

## 4. Receipt Object

### 4.1 Schema

```json
{
  "request_id": "string (matches the request)",
  "status": "completed | expired | failed | cancelled",
  "result": "varies by action type (see Section 2)",
  "reason": "string (optional, for rejections or failures)",
  "completed_by": "string (human identifier, anonymized if pool)",
  "completed_at": "ISO 8601 timestamp",
  "duration_seconds": "integer (time from assignment to completion)",
  "evidence_hash": "string (SHA-256 of request + result + timestamp)"
}
```

### 4.2 Evidence Hash

The evidence hash provides tamper-detection for receipts:

```
evidence_hash = SHA-256(request_id + result + completed_at + server_secret)
```

This allows agents to verify receipts were issued by a trusted HXP server.

## 5. HTTP Binding

### 5.1 Endpoints

#### Create Request
```
POST /hxp/v1/requests
Content-Type: application/json
Authorization: Bearer {agent_api_key}

{
  "action": "DECIDE",
  "role": "owner",
  "priority": "normal",
  "timeout_seconds": 3600,
  "fallback": "pause",
  "agent_id": "agent_alpha_01",
  "project_id": "project_alpha",
  "payload": {
    "question": "Approve $99/mo Stripe plan?",
    "options": ["Approve", "Deny"],
    "context": "Required for payment processing in Project Alpha."
  }
}

Response: 201 Created
{
  "request_id": "hxp_abc123",
  "status": "pending",
  "created_at": "2026-02-06T10:00:00Z",
  "expires_at": "2026-02-06T11:00:00Z",
  "poll_url": "/hxp/v1/requests/hxp_abc123",
  "ws_url": "wss://server/hxp/ws/hx_abc123"
}
```

#### Poll Request Status
```
GET /hxp/v1/requests/{request_id}
Authorization: Bearer {agent_api_key}

Response: 200 OK
{
  "request_id": "hxp_abc123",
  "status": "completed",
  "receipt": { ... }
}
```

#### List Pending Requests (Human Client)
```
GET /hxp/v1/inbox
Authorization: Bearer {human_token}
Query: ?status=pending&priority=high

Response: 200 OK
{
  "requests": [ ... ],
  "total": 6,
  "unresolved": 3
}
```

#### Resolve Request (Human Client)
```
POST /hxp/v1/requests/{request_id}/resolve
Authorization: Bearer {human_token}
Content-Type: application/json

{
  "result": "Approve",
  "reason": null
}

Response: 200 OK
{
  "receipt": { ... }
}
```

### 5.2 WebSocket Binding

Agents can subscribe to real-time updates instead of polling:

```
WSS /hxp/ws/{request_id}

Server sends:
{ "event": "assigned", "assigned_to": "user_456" }
{ "event": "completed", "receipt": { ... } }
{ "event": "expired" }
```

### 5.3 Error Codes

| HTTP Status | Meaning |
|-------------|---------|
| 201 | Request created successfully |
| 200 | Request retrieved / resolved |
| 400 | Invalid request (bad action, missing fields) |
| 401 | Invalid API key or token |
| 404 | Request not found |
| 409 | Request already resolved |
| 422 | Invalid resolution (result doesn't match options) |
| 408 | Request timed out |

## 6. Roles and Routing

### 6.1 Resolution Order

When a request arrives, the server resolves the target human:

1. **owner**: Route to the agent's registered owner
2. **delegate**: Check delegation rules (role → user mapping)
3. **pool**: Route to first available qualified human (future)

### 6.2 Delegation Rules

Owners can configure delegation:

```json
{
  "rules": [
    { "action": "APPROVE", "tag": "finance", "delegate_to": "user_789" },
    { "action": "DECIDE", "project_id": "project_beta", "delegate_to": "user_012" }
  ]
}
```

## 7. Security Considerations

- All communication MUST use TLS.
- Agent API keys are scoped per agent or per project.
- Human tokens use standard OAuth 2.0 / JWT.
- Receipts include evidence hashes for tamper detection.
- Context fields are bounded (max 500 chars) to prevent information leakage.
- Humans always see that they are resolving an agent request (transparency requirement).

## 8. Relationship to Other Protocols

- **x402**: HXP does not handle payments. If an agent needs to pay, use x402. If it needs human execution, use HXP. Both can coexist.
- **MCP**: An MCP tool can internally raise HXP requests when human input is needed.
- **A2A**: An agent receiving an A2A task may raise HXP requests to complete parts that require human involvement.
- **CIBA**: HXP's APPROVE action overlaps with CIBA for authorization, but HXP generalizes to any bounded human action.

## 9. Future Extensions (Planned)

- `SIGN`: Digital or physical signature with document hash
- `CALL`: Guided phone call with script and recording
- `VERIFY`: Human verification of a claim or artifact
- `APPEAR`: Physical presence at a location with evidence
- Webhook delivery for receipts
- Cryptographic receipt signatures (beyond SHA-256 hash)
- Multi-human consensus (require N-of-M approvals)
- Request chaining (output of one request feeds into another)

## 10. Versioning

The protocol uses semantic versioning. The version is included in the URL path:

```
POST /hxp/v1/requests
```

Breaking changes increment the major version. New actions or optional fields increment the minor version.

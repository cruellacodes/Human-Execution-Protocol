# HXP — Human Execution Protocol

> *The open standard for human execution in agentic systems.*

## What is HXP?

The **Human Execution Protocol** (HXP) is a lightweight, open protocol that lets AI agents invoke human actions — decisions, approvals, signatures, verifications — through a standardized, machine-readable interface.

When an agent hits a boundary it can't cross alone, it raises an **HXP execution request**. A human executes. The agent gets a **receipt** and continues.

```
Agent ──▶ HXP Server ──▶ Human Client
  ◀── receipt ◀── execution ◀──
```

Think of it as **HTTP callbacks, but the callback is a person.**

## Why HXP?

Every agent framework handles human-in-the-loop differently. LangGraph uses `interrupt()`. AutoGen has approval patterns. Custom agents send Slack messages. There's no standard.

HXP provides:

- **A universal request format** — any agent framework can emit HXP requests
- **A universal receipt format** — machine-readable proof that a human acted
- **Blocking semantics** — agents wait for human completion, like `await`
- **Role-based routing** — requests go to the right human (owner, delegate, or pool)
- **Timeout & fallback** — built-in handling when humans are unavailable

## How It Works

HXP is built on top of standard HTTP. Agents make POST requests. Humans resolve them through any client. Agents poll or subscribe via WebSocket for the result. Every response includes an `HXP-Status` header signaling the execution state.

```
1. Agent hits a boundary it can't cross alone
2. Agent sends POST /hxp/v1/requests with a structured execution request
3. Server queues it, routes to the right human, returns HXP-Status: pending
4. Human sees the request in their client (web, mobile, Slack, CLI)
5. Human executes (taps a button, signs, provides info)
6. Server returns HXP-Status: completed with a signed receipt
7. Agent gets the receipt and continues autonomously
```

The protocol uses three custom headers:

| Header | Purpose |
|--------|---------|
| `HXP-Status` | Execution state: `pending`, `assigned`, `completed`, `expired` |
| `HXP-Request-Id` | Unique execution request identifier (e.g. `hxp_abc123`) |
| `Authorization` | Standard Bearer token for agents and humans |

## Quick Start

### 1. Start the server

```bash
git clone https://github.com/cruellacodes/Human-Execution-Protocol.git
cd Human-Execution-Protocol/server
npm install
cp .env.example .env
npm start
```

Server runs at `http://localhost:3402`. Verify with:

```bash
curl http://localhost:3402/hxp
```

### 2. Open the human client

Open `client/index.html` in a browser. Click **Connect**. This is where you'll see and execute requests from your agents.

### 3. Seed sample requests

```bash
pip install httpx
python demo.py
```

Switch to the browser — 7 sample requests appear. Tap through them to see the full flow.

### 4. Use in your own agent (Python SDK)

```bash
pip install httpx websockets
```

```python
from hxp import HXPClient

client = HXPClient(server="http://localhost:3402", api_key="dev-agent-key")

# Agent needs a decision — blocks until human responds
receipt = client.decide(
    question="Approve $99/mo Stripe plan for Project Alpha?",
    options=["Approve", "Deny"],
    context="Required for payment processing. Monthly cost within budget.",
)

if receipt.result == "Approve":
    setup_stripe_plan()
else:
    pause_project()
```

### 5. Run the full agent example

```bash
python examples/agent_builds_saas.py
```

Watch an agent build a SaaS product end-to-end, pausing for your input only when it hits a boundary. Resolve each request in the browser as they appear.

## Core Concepts

### Actions (v0.1)

| Action | Description | Human sees |
|--------|------------|------------|
| `DECIDE` | Choose between options | Buttons with clear choices |
| `APPROVE` | Yes/no gate on a specific item | Item details + Approve/Reject |
| `PROVIDE` | Supply information the agent needs | Structured input form |

### Request Lifecycle

```
PENDING → ASSIGNED → COMPLETED
                  → EXPIRED (timeout)
                  → FAILED
```

### Roles

| Role | Who | When |
|------|-----|------|
| `owner` | The person who deployed the agent | Default — your decisions |
| `delegate` | Someone assigned to a capability | "Design questions go to Sarah" |
| `pool` | Anonymous qualified humans | Scale mode (future) |

### Receipts

Every completed request returns a signed receipt:

```json
{
  "request_id": "hx_abc123",
  "status": "completed",
  "result": "Approve",
  "completed_by": "user_456",
  "completed_at": "2026-02-06T14:30:00Z",
  "evidence_hash": "sha256:9f86d08..."
}
```

Receipts are the proof layer. Agents can verify, log, and audit every human action.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│  Agent        │────▶│  HXP Server       │────▶│  Human Client │
│  (any         │     │                   │     │  (web/mobile/  │
│   framework)  │◀────│  • Request queue   │◀────│   slack/cli)   │
│              │     │  • Role routing    │     │               │
│              │     │  • Receipt store   │     │               │
└──────────────┘     └──────────────────┘     └───────────────┘
     POST /request        WebSocket/SSE           Push/Poll
     GET  /receipt         notifications           renders UI
```

## Repository Structure

```
hxp/
├── docs/
│   └── SPEC.md              # Full protocol specification
├── server/                   # Reference Node.js server
│   ├── package.json
│   ├── server.js
│   └── .env.example
├── sdk-python/              # Python SDK for agents
│   ├── hxp/
│   │   ├── __init__.py
│   │   └── client.py
│   └── setup.py
├── client/                  # Web-based human client
│   └── index.html
├── openapi.yaml             # OpenAPI 3.0 specification
└── README.md
```

## Comparison with Existing Protocols

| Protocol | What it standardizes | HXP complement |
|----------|---------------------|-----------------|
| **x402** | Agent→service payments | HXP handles non-payment human actions |
| **MCP** | Agent→tool connections | HXP is invoked when tools need human input |
| **A2A** | Agent→agent communication | HXP handles the agent→human leg |
| **AG-UI** | Agent→frontend transport | HXP defines the request *semantics*, AG-UI could be a transport |
| **CIBA** | Async authorization | HXP generalizes beyond auth to any human action |

## Design Principles

1. **Agents don't hire humans. They invoke them.** The protocol treats human actions as side effects — deterministic, bounded, and machine-verifiable.

2. **Humans execute, they don't interpret.** No ambiguity. Bounded context. Clear options. Constrained interfaces. This is what makes human output reliable at scale.

3. **Receipts make humans auditable.** Every execution returns a signed receipt with evidence hash. This is what lets agents trust the physical world.

4. **Transparent by default.** Humans always know they're executing for an agent. Trust comes from clarity, not obscurity.

5. **Start simple, extend later.** Three actions today. More when the community proves they're needed.

## Roadmap

- [x] Protocol spec v0.1 (DECIDE, APPROVE, PROVIDE)
- [x] OpenAPI specification
- [x] Reference server (Node.js)
- [x] Python SDK
- [x] Web client
- [ ] TypeScript SDK
- [ ] Go SDK
- [ ] LangGraph integration
- [ ] CrewAI integration
- [ ] Slack/Discord adapter
- [ ] Mobile client
- [ ] Delegated roles & routing rules
- [ ] Human pool marketplace
- [ ] Webhook delivery
- [ ] Receipt signatures (cryptographic)

## Contributing

HXP is open source under MIT. We welcome:

- New action type proposals (open an RFC issue)
- SDK implementations in other languages
- Agent framework integrations
- Human client adapters (Slack, Discord, Telegram, CLI)
- Security audits

## License

MIT — use it, fork it, build on it.

---

*Humans are the last API.*
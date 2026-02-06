/**
 * Human Execution Protocol — Reference Server
 * 
 * A minimal, in-memory implementation of the Human Execution Protocol (HXP).
 * For production use, replace the in-memory store with a database.
 * 
 * Usage:
 *   cp .env.example .env
 *   npm install
 *   npm start
 */

const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const crypto = require('crypto');
const { WebSocketServer } = require('ws');
const http = require('http');

const app = express();
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: '/hxp/ws' });

app.use(cors());
app.use(express.json());

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const PORT = process.env.PORT || 3402;
const SERVER_SECRET = process.env.SERVER_SECRET || 'hxp-dev-secret-change-me';
const AGENT_API_KEYS = new Set((process.env.AGENT_API_KEYS || 'dev-agent-key').split(','));
const HUMAN_TOKENS = new Set((process.env.HUMAN_TOKENS || 'dev-human-token').split(','));

// ---------------------------------------------------------------------------
// In-Memory Store (replace with DB for production)
// ---------------------------------------------------------------------------
const requests = new Map();       // request_id -> request object
const delegationRules = [];       // delegation rules
const wsSubscriptions = new Map(); // request_id -> Set<ws>

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const VALID_ACTIONS = ['DECIDE', 'APPROVE', 'PROVIDE'];
const VALID_ROLES = ['owner', 'delegate', 'pool'];
const VALID_PRIORITIES = ['low', 'normal', 'high', 'critical'];
const VALID_FALLBACKS = ['pause', 'fail', 'default'];

function generateEvidenceHash(requestId, result, completedAt) {
  const data = `${requestId}:${JSON.stringify(result)}:${completedAt}:${SERVER_SECRET}`;
  return crypto.createHash('sha256').update(data).digest('hex');
}

function validatePayload(action, payload) {
  switch (action) {
    case 'DECIDE':
      if (!payload.question || typeof payload.question !== 'string') {
        return 'DECIDE requires a "question" string in payload';
      }
      if (!Array.isArray(payload.options) || payload.options.length < 2 || payload.options.length > 6) {
        return 'DECIDE requires "options" array with 2-6 items';
      }
      break;
    case 'APPROVE':
      if (!payload.item || typeof payload.item !== 'string') {
        return 'APPROVE requires an "item" string in payload';
      }
      break;
    case 'PROVIDE':
      if (!payload.prompt || typeof payload.prompt !== 'string') {
        return 'PROVIDE requires a "prompt" string in payload';
      }
      if (!payload.input_type) {
        return 'PROVIDE requires an "input_type" in payload';
      }
      break;
    default:
      return `Unknown action: ${action}`;
  }
  return null;
}

function validateResult(request, result) {
  switch (request.action) {
    case 'DECIDE':
      if (!request.payload.options.includes(result)) {
        return `Result must be one of: ${request.payload.options.join(', ')}`;
      }
      break;
    case 'APPROVE':
      if (!['approved', 'rejected'].includes(result)) {
        return 'Result must be "approved" or "rejected"';
      }
      break;
    case 'PROVIDE':
      if (result === null || result === undefined || result === '') {
        return 'PROVIDE result cannot be empty';
      }
      break;
  }
  return null;
}

function notifySubscribers(requestId, event) {
  const subs = wsSubscriptions.get(requestId);
  if (subs) {
    const message = JSON.stringify(event);
    for (const ws of subs) {
      if (ws.readyState === 1) { // OPEN
        ws.send(message);
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Auth middleware
// ---------------------------------------------------------------------------
function requireAgentAuth(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'unauthorized', message: 'Missing Bearer token' });
  }
  const token = auth.slice(7);
  if (!AGENT_API_KEYS.has(token)) {
    return res.status(401).json({ error: 'unauthorized', message: 'Invalid agent API key' });
  }
  req.agentKey = token;
  next();
}

function requireHumanAuth(req, res, next) {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'unauthorized', message: 'Missing Bearer token' });
  }
  const token = auth.slice(7);
  if (!HUMAN_TOKENS.has(token)) {
    return res.status(401).json({ error: 'unauthorized', message: 'Invalid human token' });
  }
  req.humanId = token; // In production, decode JWT to get user ID
  next();
}

// ---------------------------------------------------------------------------
// Agent API Routes
// ---------------------------------------------------------------------------

// POST /hxp/v1/requests — Create a human action request
app.post('/hxp/v1/requests', requireAgentAuth, (req, res) => {
  const {
    action,
    role = 'owner',
    priority = 'normal',
    timeout_seconds = 0,
    fallback = 'pause',
    agent_id,
    project_id,
    metadata = {},
    payload = {}
  } = req.body;

  // Validate action
  if (!VALID_ACTIONS.includes(action)) {
    return res.status(400).json({
      error: 'invalid_action',
      message: `Action must be one of: ${VALID_ACTIONS.join(', ')}`
    });
  }

  // Validate role
  if (!VALID_ROLES.includes(role)) {
    return res.status(400).json({
      error: 'invalid_role',
      message: `Role must be one of: ${VALID_ROLES.join(', ')}`
    });
  }

  // Validate payload
  const payloadError = validatePayload(action, payload);
  if (payloadError) {
    return res.status(400).json({ error: 'invalid_payload', message: payloadError });
  }

  const now = new Date().toISOString();
  const requestId = `hxp_${uuidv4().replace(/-/g, '').slice(0, 12)}`;
  const expiresAt = timeout_seconds > 0
    ? new Date(Date.now() + timeout_seconds * 1000).toISOString()
    : null;

  const request = {
    request_id: requestId,
    action,
    role,
    priority,
    timeout_seconds,
    fallback,
    agent_id: agent_id || 'unknown',
    project_id: project_id || null,
    metadata,
    payload,
    status: 'pending',
    created_at: now,
    expires_at: expiresAt,
    receipt: null
  };

  requests.set(requestId, request);

  // Set up timeout if applicable
  if (timeout_seconds > 0) {
    setTimeout(() => {
      const req = requests.get(requestId);
      if (req && req.status === 'pending') {
        req.status = 'expired';
        if (fallback === 'default' && action === 'DECIDE' && payload.default_option) {
          req.status = 'completed';
          req.receipt = {
            request_id: requestId,
            status: 'completed',
            result: payload.default_option,
            reason: 'Timeout — default option applied',
            completed_by: 'system',
            completed_at: new Date().toISOString(),
            duration_seconds: timeout_seconds,
            evidence_hash: generateEvidenceHash(requestId, payload.default_option, new Date().toISOString())
          };
        }
        notifySubscribers(requestId, {
          event: req.status,
          receipt: req.receipt
        });
      }
    }, timeout_seconds * 1000);
  }

  console.log(`[HXP] New ${action} request: ${requestId} (priority: ${priority})`);

  res.status(201)
    .header('HXP-Status', 'pending')
    .header('HXP-Request-Id', requestId)
    .json({
    request_id: requestId,
    status: 'pending',
    created_at: now,
    expires_at: expiresAt,
    poll_url: `/hxp/v1/requests/${requestId}`,
    ws_url: `ws://localhost:${PORT}/hxp/ws?request_id=${requestId}`
  });
});

// GET /hxp/v1/requests — List requests for an agent
app.get('/hxp/v1/requests', requireAgentAuth, (req, res) => {
  const { agent_id, project_id, status, limit = 20 } = req.query;

  let results = Array.from(requests.values());

  if (agent_id) results = results.filter(r => r.agent_id === agent_id);
  if (project_id) results = results.filter(r => r.project_id === project_id);
  if (status) results = results.filter(r => r.status === status);

  results.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  results = results.slice(0, parseInt(limit));

  res.json({ requests: results, total: results.length });
});

// GET /hxp/v1/requests/:id — Get request status
app.get('/hxp/v1/requests/:id', requireAgentAuth, (req, res) => {
  const request = requests.get(req.params.id);
  if (!request) {
    return res.status(404).json({ error: 'not_found', message: 'Request not found' });
  }
  res.status(200)
    .header('HXP-Status', request.status)
    .header('HXP-Request-Id', req.params.id)
    .json(request);
});

// POST /hxp/v1/requests/:id/cancel — Cancel a request
app.post('/hxp/v1/requests/:id/cancel', requireAgentAuth, (req, res) => {
  const request = requests.get(req.params.id);
  if (!request) {
    return res.status(404).json({ error: 'not_found', message: 'Request not found' });
  }
  if (request.status !== 'pending' && request.status !== 'assigned') {
    return res.status(409).json({ error: 'conflict', message: 'Request already resolved' });
  }
  request.status = 'cancelled';
  notifySubscribers(req.params.id, { event: 'cancelled' });
  res.json({ request_id: req.params.id, status: 'cancelled' });
});

// ---------------------------------------------------------------------------
// Human API Routes
// ---------------------------------------------------------------------------

// GET /hxp/v1/inbox — Get pending requests for a human
app.get('/hxp/v1/inbox', requireHumanAuth, (req, res) => {
  const { status = 'pending', priority, action } = req.query;

  let results = Array.from(requests.values())
    .filter(r => r.status === status || r.status === 'assigned');

  if (priority) results = results.filter(r => r.priority === priority);
  if (action) results = results.filter(r => r.action === action);

  // Sort: critical first, then by creation time
  const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 };
  results.sort((a, b) => {
    const pDiff = (priorityOrder[a.priority] || 2) - (priorityOrder[b.priority] || 2);
    if (pDiff !== 0) return pDiff;
    return new Date(b.created_at) - new Date(a.created_at);
  });

  res.json({
    requests: results,
    total: results.length,
    unresolved: results.filter(r => r.status === 'pending').length
  });
});

// POST /hxp/v1/requests/:id/resolve — Human resolves a request
app.post('/hxp/v1/requests/:id/resolve', requireHumanAuth, (req, res) => {
  const request = requests.get(req.params.id);
  if (!request) {
    return res.status(404).json({ error: 'not_found', message: 'Request not found' });
  }
  if (request.status === 'completed' || request.status === 'cancelled') {
    return res.status(409).json({ error: 'conflict', message: 'Request already resolved' });
  }
  if (request.status === 'expired') {
    return res.status(409).json({ error: 'expired', message: 'Request has expired' });
  }

  const { result, reason } = req.body;

  if (result === undefined || result === null) {
    return res.status(400).json({ error: 'missing_result', message: 'Result is required' });
  }

  // Validate result matches action constraints
  const resultError = validateResult(request, result);
  if (resultError) {
    return res.status(422).json({ error: 'invalid_result', message: resultError });
  }

  // Check if rejection requires reason
  if (request.action === 'APPROVE' && result === 'rejected' &&
      request.payload.reject_requires_reason && !reason) {
    return res.status(422).json({
      error: 'reason_required',
      message: 'A reason is required when rejecting this request'
    });
  }

  const completedAt = new Date().toISOString();
  const durationSeconds = Math.round(
    (new Date(completedAt) - new Date(request.created_at)) / 1000
  );

  const receipt = {
    request_id: req.params.id,
    status: 'completed',
    result,
    reason: reason || null,
    completed_by: req.humanId,
    completed_at: completedAt,
    duration_seconds: durationSeconds,
    evidence_hash: generateEvidenceHash(req.params.id, result, completedAt)
  };

  request.status = 'completed';
  request.receipt = receipt;

  // Notify WebSocket subscribers
  notifySubscribers(req.params.id, { event: 'completed', receipt });

  console.log(`[HXP] Resolved ${request.action} request: ${req.params.id} → ${result}`);

  res.status(200)
    .header('HXP-Status', 'completed')
    .header('HXP-Request-Id', req.params.id)
    .json({ receipt });
});

// ---------------------------------------------------------------------------
// Admin API Routes
// ---------------------------------------------------------------------------

// GET /hxp/v1/delegation/rules
app.get('/hxp/v1/delegation/rules', requireHumanAuth, (req, res) => {
  res.json({ rules: delegationRules });
});

// POST /hxp/v1/delegation/rules
app.post('/hxp/v1/delegation/rules', requireHumanAuth, (req, res) => {
  const rule = req.body;
  delegationRules.push(rule);
  res.status(201).json(rule);
});

// ---------------------------------------------------------------------------
// Health & Info
// ---------------------------------------------------------------------------
app.get('/hxp', (req, res) => {
  res.json({
    protocol: 'hxp',
    name: 'Human Execution Protocol',
    version: '0.1.0',
    description: 'An open protocol for agents to execute humans',
    actions: VALID_ACTIONS,
    endpoints: {
      agent: '/hxp/v1/requests',
      human: '/hxp/v1/inbox',
      admin: '/hxp/v1/delegation/rules'
    }
  });
});

// Stats endpoint for the dashboard
app.get('/hxp/v1/stats', (req, res) => {
  const all = Array.from(requests.values());
  res.json({
    total: all.length,
    pending: all.filter(r => r.status === 'pending').length,
    completed: all.filter(r => r.status === 'completed').length,
    expired: all.filter(r => r.status === 'expired').length,
    failed: all.filter(r => r.status === 'failed').length,
    avg_duration_seconds: all.filter(r => r.receipt)
      .reduce((sum, r) => sum + r.receipt.duration_seconds, 0) /
      (all.filter(r => r.receipt).length || 1)
  });
});

// ---------------------------------------------------------------------------
// WebSocket Handling
// ---------------------------------------------------------------------------
wss.on('connection', (ws, req) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const requestId = url.searchParams.get('request_id');

  if (requestId) {
    if (!wsSubscriptions.has(requestId)) {
      wsSubscriptions.set(requestId, new Set());
    }
    wsSubscriptions.get(requestId).add(ws);

    ws.on('close', () => {
      const subs = wsSubscriptions.get(requestId);
      if (subs) {
        subs.delete(ws);
        if (subs.size === 0) wsSubscriptions.delete(requestId);
      }
    });

    // If request is already resolved, send immediately
    const request = requests.get(requestId);
    if (request && request.receipt) {
      ws.send(JSON.stringify({ event: 'completed', receipt: request.receipt }));
    }
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
server.listen(PORT, () => {
  console.log(`
  ╔═══════════════════════════════════════╗
  ║  Human Execution Protocol (HXP)      ║
  ║  Reference Server v0.1.0             ║
  ║                                       ║
  ║  API:  http://localhost:${PORT}/hxp    ║
  ║  Docs: http://localhost:${PORT}/hxp    ║
  ║  WS:   ws://localhost:${PORT}/hxp/ws   ║
  ╚═══════════════════════════════════════╝
  `);
});

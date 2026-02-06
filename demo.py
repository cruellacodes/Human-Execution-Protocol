#!/usr/bin/env python3
"""
Human Execution Protocol — Demo

Seeds sample requests to showcase the protocol.

Run the server first:
  cd server && npm install && npm start

Then run this demo:
  pip install httpx
  python demo.py

Then open client/index.html in a browser and click "Connect" to see
the requests and execute them.
"""

import httpx
import time
import sys

SERVER = "http://localhost:3402"
API_KEY = "dev-agent-key"

headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def create_request(body):
    resp = httpx.post(f"{SERVER}/hxp/v1/requests", json=body, headers=headers)
    data = resp.json()
    if resp.status_code == 201:
        print(f"  ✓ Created {body['action']} request: {data['request_id']}")
    else:
        print(f"  ✗ Failed: {data}")
    return data


def main():
    print("\n╔════════════════════════════════════════════════╗")
    print("║  Human Execution Protocol — Seeding requests   ║")
    print("╚════════════════════════════════════════════════╝\n")

    # Check server is running
    try:
        resp = httpx.get(f"{SERVER}/hxp")
        print(f"Server: {resp.json()['name']} v{resp.json()['version']}\n")
    except Exception:
        print("Error: HXP server not running. Start it with:")
        print("  cd server && npm install && npm start\n")
        sys.exit(1)

    # --- DECIDE requests ---
    print("Creating DECIDE requests...")

    create_request({
        "action": "DECIDE",
        "role": "owner",
        "priority": "high",
        "agent_id": "agent-alpha",
        "project_id": "saas-mvp",
        "timeout_seconds": 3600,
        "fallback": "pause",
        "payload": {
            "question": "Approve $99/mo Stripe plan for SaaS MVP?",
            "options": ["Approve", "Deny"],
            "context": "Required for payment processing. This is the standard plan — "
                       "supports up to 10,000 transactions/month."
        }
    })

    create_request({
        "action": "DECIDE",
        "role": "owner",
        "priority": "normal",
        "agent_id": "agent-beta",
        "project_id": "landing-page",
        "payload": {
            "question": "Which domain should we use for the landing page?",
            "options": ["getwidget.io", "widgetapp.com", "trywidget.dev", "widget.tools"],
            "context": "All domains available. Prices range from $12-18/year."
        }
    })

    create_request({
        "action": "DECIDE",
        "role": "owner",
        "priority": "critical",
        "agent_id": "agent-gamma",
        "project_id": "api-service",
        "timeout_seconds": 1800,
        "fallback": "fail",
        "payload": {
            "question": "Database is at 92% capacity. Scale up now?",
            "options": ["Scale up ($50/mo increase)", "Wait and monitor", "Archive old data first"],
            "context": "Current: 2GB RDS instance. At current growth rate, "
                       "will hit 100% in ~3 days."
        }
    })

    print()

    # --- APPROVE requests ---
    print("Creating APPROVE requests...")

    create_request({
        "action": "APPROVE",
        "role": "owner",
        "priority": "normal",
        "agent_id": "agent-alpha",
        "project_id": "saas-mvp",
        "payload": {
            "item": "Deploy v1.0.0 to production",
            "details": {
                "version": "1.0.0",
                "changes": 23,
                "tests_passing": True,
                "ci_status": "green",
                "preview_url": "https://preview.example.com"
            },
            "context": "All CI checks passed. 23 changes including auth flow, "
                       "dashboard, and billing integration."
        }
    })

    create_request({
        "action": "APPROVE",
        "role": "owner",
        "priority": "high",
        "agent_id": "agent-delta",
        "project_id": "marketing",
        "payload": {
            "item": "Send email campaign to 2,400 subscribers",
            "details": {
                "subject": "Introducing Widget — built for teams",
                "recipients": 2400,
                "estimated_cost": "$4.80"
            },
            "context": "First marketing email. List built from waitlist signups. "
                       "Includes unsubscribe link and CAN-SPAM compliance.",
            "reject_requires_reason": True
        }
    })

    print()

    # --- PROVIDE requests ---
    print("Creating PROVIDE requests...")

    create_request({
        "action": "PROVIDE",
        "role": "owner",
        "priority": "normal",
        "agent_id": "agent-alpha",
        "project_id": "saas-mvp",
        "payload": {
            "prompt": "Stripe API secret key (production)",
            "input_type": "text",
            "context": "Needed to configure payment processing for SaaS MVP. "
                       "This will be stored encrypted.",
            "placeholder": "sk_live_..."
        }
    })

    create_request({
        "action": "PROVIDE",
        "role": "owner",
        "priority": "normal",
        "agent_id": "agent-beta",
        "project_id": "landing-page",
        "payload": {
            "prompt": "Company tagline for the landing page hero section",
            "input_type": "text",
            "context": "This will appear as the main headline. Keep it under 10 words.",
            "placeholder": "Build faster with Widget"
        }
    })

    print()
    print("═══════════════════════════════════════════")
    print(f"  Done! Created 7 sample requests.")
    print(f"  Open client/index.html and click Connect")
    print(f"  to see and resolve them.")
    print("═══════════════════════════════════════════\n")


if __name__ == "__main__":
    main()

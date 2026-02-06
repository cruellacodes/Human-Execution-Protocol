#!/usr/bin/env python3
"""
Example: AI Agent using Human Execution Protocol to build a SaaS product.

This shows what a real autonomous agent looks like when it uses HXP
to handle decisions, approvals, and information it can't resolve alone.

Usage:
  1. Start the HXP server: cd server && npm start
  2. Open client/index.html in a browser
  3. Run this agent: python examples/agent_builds_saas.py
  4. Execute requests in the browser as the agent pauses on each one
"""

import asyncio
import sys
import os

# Add parent directory to path for local development
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk-python'))

from hxp import HXPAsyncClient


async def build_saas():
    """Simulate an autonomous agent building a SaaS product."""

    async with HXPAsyncClient(
        server="http://localhost:3402",
        api_key="dev-agent-key",
        agent_id="saas-builder-agent",
        project_id="widget-saas",
    ) as h:

        print("\n🤖 Agent: Starting SaaS build for 'Widget'...\n")

        # ---------------------------------------------------------------
        # Step 1: Agent needs a product name decision
        # ---------------------------------------------------------------
        print("🤖 Agent: I've researched the market and have 3 name candidates.")
        print("   → Raising HXP DECIDE request...\n")

        receipt = await h.decide(
            question="Which product name should we go with?",
            options=["Widget Pro", "WidgetHQ", "Widgetly"],
            context="Based on domain availability, SEO competition, and "
                    "brand memorability analysis. All .com domains available.",
            priority="high",
        )

        product_name = receipt.result
        print(f"✅ Human decided: {product_name}")
        print(f"   Receipt: {receipt.evidence_hash[:16]}...\n")

        # ---------------------------------------------------------------
        # Step 2: Agent builds the product, then needs deployment approval
        # ---------------------------------------------------------------
        print(f"🤖 Agent: Building {product_name}...")
        print("   → Setting up Next.js project...")
        print("   → Implementing auth, dashboard, billing...")
        print("   → Running test suite... 47/47 passing")
        print("   → Generating preview deployment...")
        await asyncio.sleep(2)

        print("\n🤖 Agent: Build complete. Need approval to deploy.")
        print("   → Raising HXP APPROVE request...\n")

        receipt = await h.approve(
            item=f"Deploy {product_name} v1.0 to production",
            details={
                "framework": "Next.js 15",
                "features": ["Auth", "Dashboard", "Billing", "API"],
                "tests": "47/47 passing",
                "lighthouse_score": 94,
                "preview_url": "https://preview.widget.example.com",
            },
            context="All tests green. Lighthouse score 94. Preview link included.",
            priority="high",
        )

        if receipt.is_approved:
            print(f"✅ Human approved deployment!")
        else:
            print(f"❌ Human rejected: {receipt.reason}")
            print("🤖 Agent: Pausing project. Will address feedback.")
            return

        # ---------------------------------------------------------------
        # Step 3: Agent needs Stripe key to set up payments
        # ---------------------------------------------------------------
        print(f"\n🤖 Agent: Deploying {product_name} to production...")
        await asyncio.sleep(1)
        print("   → Deployed! Now setting up payment processing.")
        print("   → I need the Stripe API key to continue.")
        print("   → Raising HXP PROVIDE request...\n")

        receipt = await h.provide(
            prompt="Stripe secret key for production",
            input_type="text",
            context=f"Needed to configure billing for {product_name}. "
                    "Will be stored encrypted in environment variables.",
            placeholder="sk_live_...",
            priority="normal",
        )

        stripe_key = receipt.result
        print(f"✅ Human provided Stripe key: {stripe_key[:12]}...")
        print(f"🤖 Agent: Configuring Stripe...\n")

        # ---------------------------------------------------------------
        # Step 4: Agent sets up pricing, needs approval
        # ---------------------------------------------------------------
        print("🤖 Agent: I've analyzed competitor pricing and recommend:")
        print("   → Free tier: 100 requests/month")
        print("   → Pro: $29/mo for 10,000 requests")
        print("   → Enterprise: $99/mo unlimited")
        print("   → Raising HXP APPROVE request...\n")

        receipt = await h.approve(
            item="Launch with recommended pricing tiers",
            details={
                "free": {"price": 0, "requests": 100},
                "pro": {"price": 29, "requests": 10000},
                "enterprise": {"price": 99, "requests": "unlimited"},
            },
            context="Based on analysis of 12 competitors. Pro tier targets "
                    "the $25-35 sweet spot where most SaaS tools compete.",
        )

        if receipt.is_approved:
            print("✅ Pricing approved!")
        else:
            print(f"❌ Pricing rejected: {receipt.reason}")
            print("🤖 Agent: Will revise pricing strategy.")
            return

        # ---------------------------------------------------------------
        # Done
        # ---------------------------------------------------------------
        print(f"\n{'='*50}")
        print(f"🎉 {product_name} is LIVE!")
        print(f"   URL: https://{product_name.lower().replace(' ', '')}.com")
        print(f"   Pricing: Free / $29 / $99")
        print(f"   Status: Accepting customers")
        print(f"\n   HXP requests executed: 4")
        print(f"   Total human time: ~2 minutes")
        print(f"   Total agent time: autonomous")
        print(f"{'='*50}\n")


if __name__ == "__main__":
    asyncio.run(build_saas())

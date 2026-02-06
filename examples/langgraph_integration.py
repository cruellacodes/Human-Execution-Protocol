"""
Example: HXP + LangGraph Integration

This shows how HXP replaces LangGraph's built-in interrupt() with
a standardized, cross-framework protocol.

Before HXP (LangGraph-specific):
    def review_node(state):
        human_review = interrupt({"question": "approve?"})
        # Only works inside LangGraph

After HXP (any framework):
    async def review_node(state):
        receipt = await HXP.approve("Deploy to production?")
        # Works with any framework, any human client
"""

# This is pseudocode showing the integration pattern.
# Actual LangGraph code would use langgraph's StateGraph.

from hxp import HXPAsyncClient


# ---------------------------------------------------------------
# Option A: Direct usage in a LangGraph node
# ---------------------------------------------------------------

async def build_node(state):
    """Agent builds something."""
    # ... agent does work ...
    state["built"] = True
    return state


async def review_node(state):
    """
    Instead of LangGraph's interrupt(), use HXP.
    
    This means:
    - The review request goes to the HXP server
    - Any human client can resolve it (not just LangGraph's UI)
    - The receipt is standardized and auditable
    - Works the same if you later migrate to CrewAI, AutoGen, etc.
    """
    async with HXPAsyncClient(
        server="http://localhost:3402",
        agent_id="langgraph-agent",
        project_id=state.get("project_id", "default"),
    ) as HXP:
        receipt = await HXP.approve(
            item=f"Deploy {state['project_name']} to production",
            details={
                "version": state.get("version", "1.0"),
                "tests_passing": state.get("tests_passing", True),
            },
            context="All checks passed. Ready for production.",
            priority="high",
        )

    state["approved"] = receipt.is_approved
    state["review_receipt"] = receipt.evidence_hash
    return state


async def deploy_node(state):
    """Deploy if approved."""
    if state.get("approved"):
        # ... deploy ...
        state["deployed"] = True
    return state


# ---------------------------------------------------------------
# Option B: HXP as a LangGraph tool
# ---------------------------------------------------------------

def create_HXP_tools(HXP_client):
    """
    Create LangChain-compatible tools from hxp actions.
    
    This lets the LLM itself decide when to ask a human,
    rather than hardcoding it into the graph.
    """
    from langchain_core.tools import tool

    @tool
    async def ask_human_decision(question: str, options: str) -> str:
        """Ask the human owner to choose between options. 
        Use this when you need a decision you can't make autonomously.
        options should be comma-separated."""
        option_list = [o.strip() for o in options.split(",")]
        receipt = await HXP_client.decide(
            question=question,
            options=option_list,
        )
        return f"Human decided: {receipt.result}"

    @tool
    async def ask_human_approval(item: str, context: str) -> str:
        """Ask the human to approve or reject something.
        Use this before deploying, sending emails, or spending money."""
        receipt = await HXP_client.approve(
            item=item,
            context=context,
        )
        if receipt.is_approved:
            return "Human approved."
        else:
            return f"Human rejected. Reason: {receipt.reason or 'none given'}"

    @tool
    async def ask_human_for_info(prompt: str, context: str) -> str:
        """Ask the human to provide information you don't have.
        Use this for API keys, passwords, preferences, or creative input."""
        receipt = await HXP_client.provide(
            prompt=prompt,
            context=context,
        )
        return f"Human provided: {receipt.result}"

    return [ask_human_decision, ask_human_approval, ask_human_for_info]


# ---------------------------------------------------------------
# The key insight
# ---------------------------------------------------------------

"""
Why this matters:

1. PORTABILITY: Your human-in-the-loop logic isn't locked to LangGraph.
   Move to CrewAI? AutoGen? Custom framework? HXP works everywhere.

2. ROUTING: LangGraph's interrupt() only works within the LangGraph UI.
   HXP routes to any client: web, mobile, Slack, CLI, email.

3. RECEIPTS: Every human action returns a signed receipt.
   LangGraph's interrupt() returns unstructured data.

4. ASYNC: HXP is async by default. The agent can wait hours for
   a human to respond without holding compute resources.

5. AUDITABLE: Every human decision has an evidence hash.
   Required for compliance, debugging, and trust.
"""

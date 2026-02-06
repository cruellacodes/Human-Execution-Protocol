"""
Human Execution Protocol (HXP)

Python SDK for agents to invoke human actions.

Usage:
    from hxp import HXPClient

    client = HXPClient(server="http://localhost:3402")

    # Synchronous
    receipt = client.decide(
        question="Approve deployment?",
        options=["Yes", "No"]
    )

    # Async
    receipt = await client.async_decide(
        question="Approve deployment?",
        options=["Yes", "No"]
    )
"""

from hxp.client import HXPClient, HXPAsyncClient, HXPReceipt, HXPError, HXPTimeoutError

__version__ = "0.1.0"
__all__ = ["HXPClient", "HXPAsyncClient", "HXPReceipt", "HXPError", "HXPTimeoutError"]

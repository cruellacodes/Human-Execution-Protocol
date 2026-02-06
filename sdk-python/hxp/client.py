"""
Human Execution Protocol — Python SDK Client

Provides both synchronous and asynchronous clients for agents
to invoke human actions via the Human Execution Protocol.
"""

import time
import json
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
from enum import Enum

import httpx


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class Action(str, Enum):
    DECIDE = "DECIDE"
    APPROVE = "APPROVE"
    PROVIDE = "PROVIDE"


class Role(str, Enum):
    OWNER = "owner"
    DELEGATE = "delegate"
    POOL = "pool"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Fallback(str, Enum):
    PAUSE = "pause"
    FAIL = "fail"
    DEFAULT = "default"


class Status(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class HXPReceipt:
    """Receipt returned when a human completes an HXP request."""
    request_id: str
    status: str
    result: Any
    reason: Optional[str] = None
    completed_by: Optional[str] = None
    completed_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    evidence_hash: Optional[str] = None

    @property
    def is_approved(self) -> bool:
        """For APPROVE actions: True if approved."""
        return self.result == "approved"

    @property
    def is_rejected(self) -> bool:
        """For APPROVE actions: True if rejected."""
        return self.result == "rejected"

    def __repr__(self):
        return f"HXPReceipt(id={self.request_id}, status={self.status}, result={self.result})"


class HXPError(Exception):
    """Base error for HXP operations."""
    def __init__(self, message: str, status_code: int = None, details: dict = None):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class HXPTimeoutError(HXPError):
    """Raised when a request times out waiting for human action."""
    pass


# ---------------------------------------------------------------------------
# Synchronous Client
# ---------------------------------------------------------------------------

class HXPClient:
    """
    Synchronous HXP client for agents.

    Usage:
        client = HXPClient(server="http://localhost:3402", api_key="your-key")

        # Quick decision
        receipt = client.decide("Approve $99 plan?", ["Approve", "Deny"])

        # Quick approval
        receipt = client.approve("Deploy v2.1 to production", details={"version": "2.1"})

        # Request information
        receipt = client.provide("Stripe API key", input_type="text")

        # Low-level: any action
        receipt = client.require(
            action="DECIDE",
            payload={"question": "...", "options": [...]},
            role="owner",
            timeout_seconds=3600
        )
    """

    def __init__(
        self,
        server: str = "http://localhost:3402",
        api_key: str = "dev-agent-key",
        agent_id: str = "default-agent",
        project_id: Optional[str] = None,
        default_timeout: int = 0,
        poll_interval: float = 2.0,
        max_poll_time: float = 86400,
    ):
        self.server = server.rstrip("/")
        self.api_key = api_key
        self.agent_id = agent_id
        self.project_id = project_id
        self.default_timeout = default_timeout
        self.poll_interval = poll_interval
        self.max_poll_time = max_poll_time
        self._client = httpx.Client(
            base_url=f"{self.server}/hxp/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    def require(
        self,
        action: str,
        payload: dict,
        role: str = "owner",
        priority: str = "normal",
        timeout_seconds: int = None,
        fallback: str = "pause",
        agent_id: str = None,
        project_id: str = None,
        metadata: dict = None,
        wait: bool = True,
    ) -> HXPReceipt:
        """
        Create an HXP execution request and optionally wait for the human receipt.

        Args:
            action: DECIDE, APPROVE, or PROVIDE
            payload: Action-specific data
            role: owner, delegate, or pool
            priority: low, normal, high, or critical
            timeout_seconds: Override default timeout
            fallback: pause, fail, or default
            agent_id: Override default agent_id
            project_id: Override default project_id
            metadata: Optional metadata
            wait: If True (default), blocks until human responds

        Returns:
            HXPReceipt with the human's response
        """
        body = {
            "action": action,
            "role": role,
            "priority": priority,
            "timeout_seconds": timeout_seconds if timeout_seconds is not None else self.default_timeout,
            "fallback": fallback,
            "agent_id": agent_id or self.agent_id,
            "payload": payload,
        }
        if project_id or self.project_id:
            body["project_id"] = project_id or self.project_id
        if metadata:
            body["metadata"] = metadata

        # Create the request
        response = self._client.post("/requests", json=body)
        if response.status_code != 201:
            data = response.json()
            raise HXPError(
                data.get("message", "Request creation failed"),
                status_code=response.status_code,
                details=data,
            )

        created = response.json()
        request_id = created["request_id"]

        if not wait:
            return HXPReceipt(request_id=request_id, status="pending", result=None)

        # Poll for completion
        return self._poll(request_id)

    def _poll(self, request_id: str) -> HXPReceipt:
        """Poll until request is resolved or max_poll_time exceeded."""
        start = time.time()
        while True:
            elapsed = time.time() - start
            if elapsed > self.max_poll_time:
                raise HXPTimeoutError(
                    f"Polling timeout after {self.max_poll_time}s for request {request_id}"
                )

            response = self._client.get(f"/requests/{request_id}")
            if response.status_code != 200:
                raise HXPError(f"Failed to poll request {request_id}")

            data = response.json()
            status = data["status"]

            if status == "completed":
                receipt_data = data.get("receipt", {})
                return HXPReceipt(
                    request_id=receipt_data.get("request_id", request_id),
                    status=receipt_data.get("status", "completed"),
                    result=receipt_data.get("result"),
                    reason=receipt_data.get("reason"),
                    completed_by=receipt_data.get("completed_by"),
                    completed_at=receipt_data.get("completed_at"),
                    duration_seconds=receipt_data.get("duration_seconds"),
                    evidence_hash=receipt_data.get("evidence_hash"),
                )
            elif status in ("expired", "failed", "cancelled"):
                if status == "expired":
                    # Check if there's a default receipt (from fallback=default)
                    if data.get("receipt"):
                        rd = data["receipt"]
                        return HXPReceipt(
                            request_id=rd.get("request_id", request_id),
                            status="completed",
                            result=rd.get("result"),
                            reason=rd.get("reason"),
                        )
                    raise HXPTimeoutError(f"Request {request_id} expired")
                raise HXPError(f"Request {request_id} {status}")

            time.sleep(self.poll_interval)

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def decide(
        self,
        question: str,
        options: List[str],
        context: str = None,
        default_option: str = None,
        priority: str = "normal",
        timeout_seconds: int = None,
        **kwargs,
    ) -> HXPReceipt:
        """
        Ask a human to choose between options.

        Args:
            question: The decision to be made
            options: 2-6 choices
            context: Optional background info
            default_option: Option to use if timeout (requires fallback="default")

        Returns:
            HXPReceipt — receipt.result is the selected option string
        """
        payload = {"question": question, "options": options}
        if context:
            payload["context"] = context
        if default_option:
            payload["default_option"] = default_option

        return self.require(
            action="DECIDE",
            payload=payload,
            priority=priority,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    def approve(
        self,
        item: str,
        details: dict = None,
        context: str = None,
        reject_requires_reason: bool = False,
        priority: str = "normal",
        timeout_seconds: int = None,
        **kwargs,
    ) -> HXPReceipt:
        """
        Ask a human to approve or reject something.

        Args:
            item: What needs approval
            details: Structured data about the item
            context: Why approval is needed

        Returns:
            HXPReceipt — receipt.result is "approved" or "rejected"
        """
        payload = {"item": item}
        if details:
            payload["details"] = details
        if context:
            payload["context"] = context
        if reject_requires_reason:
            payload["reject_requires_reason"] = True

        return self.require(
            action="APPROVE",
            payload=payload,
            priority=priority,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    def provide(
        self,
        prompt: str,
        input_type: str = "text",
        context: str = None,
        placeholder: str = None,
        validation: dict = None,
        priority: str = "normal",
        timeout_seconds: int = None,
        **kwargs,
    ) -> HXPReceipt:
        """
        Ask a human to supply information.

        Args:
            prompt: What information is needed
            input_type: text, number, url, email, file, selection
            context: Why this information is needed

        Returns:
            HXPReceipt — receipt.result is the provided value
        """
        payload = {"prompt": prompt, "input_type": input_type}
        if context:
            payload["context"] = context
        if placeholder:
            payload["placeholder"] = placeholder
        if validation:
            payload["validation"] = validation

        return self.require(
            action="PROVIDE",
            payload=payload,
            priority=priority,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# ---------------------------------------------------------------------------
# Async Client
# ---------------------------------------------------------------------------

class HXPAsyncClient:
    """
    Async HXP client for agents. Same API as HXPClient but async.

    Usage:
        async with HXPAsyncClient(server="http://localhost:3402") as client:
            receipt = await client.decide("Approve?", ["Yes", "No"])
    """

    def __init__(self, **kwargs):
        self.poll_interval = kwargs.pop("poll_interval", 2.0)
        self.max_poll_time = kwargs.pop("max_poll_time", 86400)
        self.agent_id = kwargs.pop("agent_id", "default-agent")
        self.project_id = kwargs.pop("project_id", None)
        self.default_timeout = kwargs.pop("default_timeout", 0)

        server = kwargs.pop("server", "http://localhost:3402").rstrip("/")
        api_key = kwargs.pop("api_key", "dev-agent-key")

        self._client = httpx.AsyncClient(
            base_url=f"{server}/hxp/v1",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def require(self, action, payload, role="owner", priority="normal",
                      timeout_seconds=None, fallback="pause", agent_id=None,
                      project_id=None, metadata=None, wait=True) -> HXPReceipt:
        body = {
            "action": action,
            "role": role,
            "priority": priority,
            "timeout_seconds": timeout_seconds if timeout_seconds is not None else self.default_timeout,
            "fallback": fallback,
            "agent_id": agent_id or self.agent_id,
            "payload": payload,
        }
        if project_id or self.project_id:
            body["project_id"] = project_id or self.project_id
        if metadata:
            body["metadata"] = metadata

        response = await self._client.post("/requests", json=body)
        if response.status_code != 201:
            data = response.json()
            raise HXPError(data.get("message", "Failed"), response.status_code, data)

        request_id = response.json()["request_id"]
        if not wait:
            return HXPReceipt(request_id=request_id, status="pending", result=None)

        return await self._poll(request_id)

    async def _poll(self, request_id: str) -> HXPReceipt:
        import asyncio
        start = time.time()
        while True:
            if time.time() - start > self.max_poll_time:
                raise HXPTimeoutError(f"Polling timeout for {request_id}")

            response = await self._client.get(f"/requests/{request_id}")
            data = response.json()

            if data["status"] == "completed":
                rd = data.get("receipt", {})
                return HXPReceipt(
                    request_id=rd.get("request_id", request_id),
                    status="completed",
                    result=rd.get("result"),
                    reason=rd.get("reason"),
                    completed_by=rd.get("completed_by"),
                    completed_at=rd.get("completed_at"),
                    duration_seconds=rd.get("duration_seconds"),
                    evidence_hash=rd.get("evidence_hash"),
                )
            elif data["status"] in ("expired", "failed", "cancelled"):
                raise HXPError(f"Request {request_id} {data['status']}")

            await asyncio.sleep(self.poll_interval)

    async def decide(self, question, options, context=None, **kwargs):
        payload = {"question": question, "options": options}
        if context:
            payload["context"] = context
        return await self.require(action="DECIDE", payload=payload, **kwargs)

    async def approve(self, item, details=None, context=None, **kwargs):
        payload = {"item": item}
        if details:
            payload["details"] = details
        if context:
            payload["context"] = context
        return await self.require(action="APPROVE", payload=payload, **kwargs)

    async def provide(self, prompt, input_type="text", context=None, placeholder=None, validation=None, **kwargs):
        payload = {"prompt": prompt, "input_type": input_type}
        if context:
            payload["context"] = context
        if placeholder:
            payload["placeholder"] = placeholder
        if validation:
            payload["validation"] = validation
        return await self.require(action="PROVIDE", payload=payload, **kwargs)

    async def close(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

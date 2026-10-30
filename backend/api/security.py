"""Discovery Engine - Security middleware and authentication utilities (Phase 7, P7.8)."""

from __future__ import annotations

import hmac
import json
import os
from typing import TYPE_CHECKING

from starlette.datastructures import Headers

from api.errors import PayloadTooLargeError

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BODY_BYTES = 1_048_576  # 1MB
EXEMPT_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})


def verify_api_key_bytes(raw_header: bytes | str | None, expected_key: str | None) -> bool:
    """Compare API key in constant time on encoded bytes (hmac.compare_digest).

    Safely handles non-ASCII characters, surrogates, or arbitrary byte sequences
    without raising exceptions.
    """
    if not expected_key:
        return True
    if raw_header is None:
        return False

    try:
        if isinstance(raw_header, str):
            raw_bytes = raw_header.encode("utf-8", errors="replace")
        else:
            raw_bytes = raw_header

        expected_bytes = expected_key.encode("utf-8")
        return hmac.compare_digest(raw_bytes, expected_bytes)
    except Exception:
        return False


async def _send_json_error(
    send: Send,
    status_code: int,
    code: str,
    message: str,
) -> None:
    """Send standard JSON error envelope directly via ASGI send."""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": None,
        }
    }
    body = json.dumps(payload).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": body,
            "more_body": False,
        }
    )


class SecurityMiddleware:
    """Pure ASGI security middleware enforcing API key authentication and body size limits."""

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int = MAX_REQUEST_BODY_BYTES,
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "")

        # 1. CORS Preflight (OPTIONS) is always exempt from API key check
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # 2. API Key Authentication (when RECOMMENDER_API_KEY is configured in env)
        expected_key = os.environ.get("RECOMMENDER_API_KEY")
        if expected_key and path not in EXEMPT_PATHS:
            raw_header_val: bytes | None = None
            for name, val in scope.get("headers", []):
                if name.lower() == b"x-api-key":
                    raw_header_val = val
                    break

            if raw_header_val is None:
                await _send_json_error(
                    send,
                    status_code=401,
                    code="unauthorized",
                    message="Missing API key header 'X-API-Key'.",
                )
                return

            if not verify_api_key_bytes(raw_header_val, expected_key):
                await _send_json_error(
                    send,
                    status_code=401,
                    code="unauthorized",
                    message="Invalid API key provided.",
                )
                return

        # 3. Request body size limit check via Content-Length header
        headers = Headers(raw=scope.get("headers", []))
        content_length_str = headers.get("content-length")
        if content_length_str:
            try:
                content_length = int(content_length_str)
                if content_length > self.max_body_bytes:
                    await _send_json_error(
                        send,
                        status_code=413,
                        code="payload_too_large",
                        message=f"Request body exceeds maximum allowed size ({self.max_body_bytes} bytes).",
                    )
                    return
            except ValueError:
                pass

        # 4. Streamed / chunked body size limiter
        received_bytes = 0
        payload_too_large = False

        async def limited_receive() -> Message:
            nonlocal received_bytes, payload_too_large
            message = await receive()
            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                received_bytes += len(chunk)
                if received_bytes > self.max_body_bytes:
                    payload_too_large = True
                    raise PayloadTooLargeError(
                        f"Request body exceeds maximum allowed size ({self.max_body_bytes} bytes)."
                    )
            return message

        async def tracking_send(message: Message) -> None:
            if payload_too_large:
                # Intercept downstream error responses (e.g. FastAPI wrapping body parse failure into 400)
                return
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except PayloadTooLargeError:
            payload_too_large = True

        if payload_too_large:
            await _send_json_error(
                send,
                status_code=413,
                code="payload_too_large",
                message=f"Request body exceeds maximum allowed size ({self.max_body_bytes} bytes).",
            )

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Optional


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))


def create_download_token(*, task_id: str, owner_id: str, secret: str, ttl_seconds: int = 600) -> str:
    exp = int(time.time()) + int(ttl_seconds)
    payload = {"task_id": task_id, "owner_id": owner_id, "exp": exp}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64url_encode(payload_bytes)}.{_b64url_encode(sig)}"


def verify_download_token(*, token: str, secret: str) -> Optional[dict[str, Any]]:
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload_bytes = _b64url_decode(payload_b64)
        sig = _b64url_decode(sig_b64)

        expected_sig = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected_sig):
            return None

        payload = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(payload, dict):
            return None

        exp = payload.get("exp")
        if not isinstance(exp, int):
            return None
        if int(time.time()) > exp:
            return None

        task_id = payload.get("task_id")
        owner_id = payload.get("owner_id")
        if not isinstance(task_id, str) or not isinstance(owner_id, str):
            return None

        return payload
    except Exception:
        return None

from __future__ import annotations

import re

_INVALID_FILENAME_CHARS = re.compile(r"[<>:\"/\\|?*]")


def sanitize_filename(name: str, *, max_len: int = 200) -> str:
    """Sanitize a user/provider-provided name for filesystem usage.

    Keeps behavior consistent across backend modules.
    """

    cleaned = _INVALID_FILENAME_CHARS.sub("", name or "").strip()
    if not cleaned:
        return "untitled"
    return cleaned[:max_len]

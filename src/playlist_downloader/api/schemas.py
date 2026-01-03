from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InitRequest(BaseModel):
    url: str
    options: Optional[Dict[str, Any]] = None


class StartRequest(BaseModel):
    selected_indices: Optional[List[int]] = None


class SearchRequest(BaseModel):
    query: str
    providers: List[str] = ["spotify", "youtube", "soundcloud"]

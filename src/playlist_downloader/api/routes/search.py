from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Request

from ..schemas import SearchRequest
from ...services.search_service import build_suggestions, relevance_score

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/suggestions")
async def get_suggestions(request: Request, q: str):
    return build_suggestions(
        query=q,
        spotify_client=request.app.state.spotify_client,
        search_manager=request.app.state.search_manager,
    )


@router.post("/search")
async def search_media(request: Request, req: SearchRequest):
    tasks = []
    search_manager = request.app.state.search_manager

    if "spotify" in req.providers:
        tasks.append(search_manager.search_spotify(req.query))
    if "youtube" in req.providers:
        tasks.append(search_manager.search_youtube(req.query))
    if "soundcloud" in req.providers:
        tasks.append(search_manager.search_soundcloud(req.query))

    results_list = await asyncio.gather(*tasks)

    final_results: List[Dict[str, Any]] = []
    for r in results_list:
        final_results.extend(r)

    final_results.sort(
        key=lambda it: (
            relevance_score(it, req.query),
            (it.get("title", "") or "").strip().lower(),
        ),
        reverse=True,
    )
    return final_results

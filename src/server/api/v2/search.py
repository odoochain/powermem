"""
Memory search API routes (v2) — per-request config.
"""

from fastapi import APIRouter, Depends, Request

from ...models.request_v2 import V2SearchRequest
from ...models.response import APIResponse
from ...services.search_service import SearchService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config
from ..shared.search import do_search

router_v2 = APIRouter(prefix="/memories", tags=["search-v2"])


@router_v2.post(
    "/search",
    response_model=APIResponse,
    summary="Search memories",
    description="Search memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def search_memories_v2(
    request: Request,
    body: V2SearchRequest,
    api_key: str = Depends(verify_api_key),
):
    service = SearchService(config=resolve_config(body.config))
    return do_search(service, body.query, body.user_id, body.agent_id, body.run_id, body.filters, body.limit)

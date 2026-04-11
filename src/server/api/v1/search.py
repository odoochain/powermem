"""
Memory search API routes (v1 + v2)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...models.request import SearchRequest, V2SearchRequest
from ...models.response import APIResponse, SearchResponse, SearchResult
from ...services.search_service import SearchService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.converters import search_result_to_response
from ...utils.config_resolver import resolve_config

router = APIRouter(prefix="/memories", tags=["search"])
router_v2 = APIRouter(prefix="/memories", tags=["search-v2"])


def get_search_service(request: Request) -> SearchService:
    """Dependency to get search service singleton from app state"""
    service = request.app.state.search_service
    if service is None:
        from ...models.errors import ErrorCode, APIError
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Search service unavailable: storage backend initialization failed",
            status_code=503,
        )
    return service


# ===================================================================
# Shared business logic
# ===================================================================

def _do_search(
    service: SearchService,
    query: str,
    user_id: Optional[str],
    agent_id: Optional[str],
    run_id: Optional[str],
    filters: Optional[dict],
    limit: int,
):
    results = service.search_memories(
        query=query,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        filters=filters,
        limit=limit,
    )
    search_results = [
        search_result_to_response(r) for r in results.get("results", [])
    ]
    response_data = SearchResponse(
        results=search_results,
        total=len(search_results),
        query=query,
    )
    return APIResponse(
        success=True,
        data=response_data.model_dump(mode='json'),
        message="Search completed successfully",
    )


# ===================================================================
# v1 handlers
# ===================================================================

@router.post(
    "/search",
    response_model=APIResponse,
    summary="Search memories",
    description="Search memories using semantic search with optional filters",
)
@limiter.limit(get_rate_limit_string())
async def search_memories_post(
    request: Request,
    body: SearchRequest,
    api_key: str = Depends(verify_api_key),
    service: SearchService = Depends(get_search_service),
):
    """Search memories (POST method)"""
    return _do_search(service, body.query, body.user_id, body.agent_id, body.run_id, body.filters, body.limit)


@router.get(
    "/search",
    response_model=APIResponse,
    summary="Search memories (GET)",
    description="Search memories using query parameters",
)
@limiter.limit(get_rate_limit_string())
async def search_memories_get(
    request: Request,
    query: str = Query(..., description="Search query"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    limit: int = Query(30, ge=1, le=100, description="Maximum number of results"),
    api_key: str = Depends(verify_api_key),
    service: SearchService = Depends(get_search_service),
):
    """Search memories (GET method)"""
    return _do_search(service, query, user_id, agent_id, run_id, None, limit)


# ===================================================================
# v2 handler
# ===================================================================

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
    return _do_search(service, body.query, body.user_id, body.agent_id, body.run_id, body.filters, body.limit)

"""
Memory search API routes (v1)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request

from ...models.request import SearchRequest
from ...models.response import APIResponse
from ...services.search_service import SearchService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ..shared.search import do_search

router = APIRouter(prefix="/memories", tags=["search"])


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
    return do_search(service, body.query, body.user_id, body.agent_id, body.run_id, body.filters, body.limit)


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
    return do_search(service, query, user_id, agent_id, run_id, None, limit)

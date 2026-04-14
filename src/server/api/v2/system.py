"""
System management API routes (v2) — per-request config.
"""

from fastapi import APIRouter, Depends, Request

from ...models.request_v2 import V2DeleteAllRequest
from ...models.response import APIResponse, HealthResponse
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config

router_v2 = APIRouter(prefix="/system", tags=["system-v2"])


@router_v2.get(
    "/health",
    response_model=APIResponse,
    summary="Health check",
    description="Health check (public, no config needed)",
)
async def health_check_v2():
    """Health check endpoint (v2)"""
    health = HealthResponse(status="healthy")
    return APIResponse(
        success=True,
        data=health.model_dump(mode='json'),
        message="Service is healthy",
    )


@router_v2.post(
    "/delete-all-memories",
    response_model=APIResponse,
    summary="Delete all memories",
    description="Delete all memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def delete_all_memories_v2(
    request: Request,
    body: V2DeleteAllRequest,
    api_key: str = Depends(verify_api_key),
):
    """Delete all memories with per-request config"""
    from powermem import Memory
    from ...models.errors import ErrorCode, APIError

    try:
        resolved = resolve_config(body.config)
        memory = Memory(config=resolved)
        result = memory.delete_all(
            user_id=body.user_id,
            agent_id=body.agent_id,
            run_id=body.run_id,
        )

        filters = {}
        if body.user_id:
            filters["user_id"] = body.user_id
        if body.agent_id:
            filters["agent_id"] = body.agent_id
        if body.run_id:
            filters["run_id"] = body.run_id

        filter_desc = f" with filters: {filters}" if filters else ""

        return APIResponse(
            success=True,
            data={"deleted": result, "filters": filters},
            message=f"All memories{filter_desc} deleted successfully",
        )
    except Exception as e:
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Failed to delete all memories: {str(e)}",
            status_code=500,
        )

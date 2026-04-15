"""
System management API routes (v2) — per-request config.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request, Response

from ...models.request_v2 import V2DeleteAllRequest, V2SystemStatusRequest
from ...models.response import APIResponse, HealthResponse, StatusResponse
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config
from ...utils.metrics import get_metrics_collector
from ...utils.health_check import check_all_dependencies
from ...state import SERVER_START_TIME
from powermem.version import __version__ as powermem_version

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
    "/status",
    response_model=APIResponse,
    summary="System status",
    description="Get system status and configuration information with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_status_v2(
    request: Request,
    body: V2SystemStatusRequest,
    api_key: str = Depends(verify_api_key),
):
    try:
        resolved = resolve_config(body.config)
        storage_type = None
        llm_provider = None

        if isinstance(resolved, dict):
            vector_store = resolved.get("vector_store") or resolved.get("database", {})
            storage_type = vector_store.get("provider") if isinstance(vector_store, dict) else None

            llm = resolved.get("llm", {})
            llm_provider = llm.get("provider") if isinstance(llm, dict) else None
        else:
            if hasattr(resolved, "vector_store") and resolved.vector_store:
                storage_type = resolved.vector_store.provider
            if hasattr(resolved, "llm") and resolved.llm:
                llm_provider = resolved.llm.provider

        now = datetime.now(timezone.utc)
        uptime_seconds = (now - SERVER_START_TIME).total_seconds()

        dependencies = await check_all_dependencies()

        system_status = "operational"
        degraded_count = sum(1 for dep in dependencies.values() if dep.status == "degraded")
        unavailable_count = sum(1 for dep in dependencies.values() if dep.status == "unavailable")

        if unavailable_count > 0:
            system_status = "down"
        elif degraded_count > 0:
            system_status = "degraded"

        dependencies_dict = {
            name: dep.model_dump(mode="json")
            for name, dep in dependencies.items()
        }

        status_data = StatusResponse(
            status=system_status,
            version=powermem_version,
            storage_type=storage_type,
            llm_provider=llm_provider,
            uptime_seconds=uptime_seconds,
            started_at=SERVER_START_TIME,
            dependencies=dependencies_dict,
        )

        return APIResponse(
            success=True,
            data=status_data.model_dump(mode="json"),
            message="System status retrieved successfully",
        )
    except Exception as e:
        now = datetime.now(timezone.utc)
        uptime_seconds = (now - SERVER_START_TIME).total_seconds()

        status_data = StatusResponse(
            status="degraded",
            version=powermem_version,
            storage_type=None,
            llm_provider=None,
            uptime_seconds=uptime_seconds,
            started_at=SERVER_START_TIME,
            dependencies={},
        )

        return APIResponse(
            success=True,
            data=status_data.model_dump(mode="json"),
            message=f"System status retrieved with errors: {str(e)[:100]}",
        )


@router_v2.get(
    "/metrics",
    summary="Prometheus metrics",
    description="Get Prometheus format metrics",
)
@limiter.limit(get_rate_limit_string())
async def get_metrics_v2(
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    metrics_collector = get_metrics_collector()
    metrics_text = metrics_collector.get_metrics()

    return Response(
        content=metrics_text,
        media_type="text/plain; version=0.0.4; charset=utf-8",
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

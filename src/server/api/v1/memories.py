"""
Memory management API routes (v1 + v2)
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from ...models.request import (
    MemoryCreateRequest,
    MemoryBatchCreateRequest,
    MemoryUpdateRequest,
    MemoryBatchUpdateRequest,
    BulkDeleteRequest,
    V2MemoryCreateRequest,
    V2MemoryBatchCreateRequest,
    V2MemoryUpdateRequest,
    V2MemoryBatchUpdateRequest,
    V2BulkDeleteRequest,
    V2MemoryGetRequest,
    V2MemoryListRequest,
    V2MemoryDeleteRequest,
    V2MemoryStatsRequest,
    V2MemoryQualityRequest,
)
from ...models.response import (
    APIResponse,
    MemoryListResponse,
)
from ...services.memory_service import MemoryService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.converters import memory_dict_to_response
from ...utils.config_resolver import resolve_config

logger = logging.getLogger("server")

router = APIRouter(prefix="/memories", tags=["memories"])
router_v2 = APIRouter(prefix="/memories", tags=["memories-v2"])


# ---------------------------------------------------------------------------
# v1 dependency — singleton from app state
# ---------------------------------------------------------------------------

def get_memory_service(request: Request) -> MemoryService:
    """Dependency to get memory service singleton from app state"""
    service = request.app.state.memory_service
    if service is None:
        from ...models.errors import ErrorCode, APIError
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Memory service unavailable: storage backend initialization failed",
            status_code=503,
        )
    return service


# ===================================================================
# Shared business logic (called by both v1 and v2 handlers)
# ===================================================================

def _do_create_memory(service: MemoryService, body: MemoryCreateRequest):
    results = service.create_memory(
        content=body.content,
        user_id=body.user_id,
        agent_id=body.agent_id,
        run_id=body.run_id,
        metadata=body.metadata,
        filters=body.filters,
        scope=body.scope,
        memory_type=body.memory_type,
        infer=body.infer,
    )
    memory_responses = [memory_dict_to_response(m) for m in results]
    if len(memory_responses) == 0:
        message = "No memories were created (likely duplicates detected or no facts extracted)"
    elif len(memory_responses) == 1:
        message = "Memory created successfully"
    else:
        message = f"Created {len(memory_responses)} memories successfully"
    return APIResponse(
        success=True,
        data=[m.model_dump(mode='json', exclude_none=True) for m in memory_responses],
        message=message,
    )


def _do_batch_create(service: MemoryService, body: MemoryBatchCreateRequest):
    memories_data = [
        {
            "content": item.content,
            "metadata": item.metadata,
            "filters": item.filters,
            "scope": item.scope,
            "memory_type": item.memory_type,
        }
        for item in body.memories
    ]
    result = service.batch_create_memories(
        memories=memories_data,
        user_id=body.user_id,
        agent_id=body.agent_id,
        run_id=body.run_id,
        infer=body.infer,
    )
    created_memories = []
    for item in result["created"]:
        try:
            memory = service.get_memory(
                memory_id=item["memory_id"],
                user_id=body.user_id,
                agent_id=body.agent_id,
            )
            created_memories.append(memory_dict_to_response(memory).model_dump(mode='json'))
        except Exception as e:
            logger.warning(f"Failed to retrieve created memory {item['memory_id']}: {e}")
            created_memories.append({
                "memory_id": item["memory_id"],
                "content": item["content"],
            })
    response_data = {
        "memories": created_memories,
        "total": result["total"],
        "created_count": result["created_count"],
        "failed_count": result["failed_count"],
    }
    if result["failed_count"] > 0:
        response_data["failed"] = result["failed"]
    return APIResponse(
        success=True,
        data=response_data,
        message=f"Created {result['created_count']} out of {result['total']} memories",
    )


def _do_list_memories(
    service: MemoryService,
    user_id: Optional[str],
    agent_id: Optional[str],
    limit: int,
    offset: int,
    sort_by: Optional[str],
    order: str,
):
    total_count = service.count_memories(user_id=user_id, agent_id=agent_id)
    memories = service.list_memories(
        user_id=user_id,
        agent_id=agent_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        order=order,
    )
    memory_responses = [memory_dict_to_response(m) for m in memories]
    response_data = MemoryListResponse(
        memories=memory_responses,
        total=total_count,
        limit=limit,
        offset=offset,
    )
    return APIResponse(
        success=True,
        data=response_data.model_dump(mode='json'),
        message="Memories retrieved successfully",
    )


def _do_get_memory(
    service: MemoryService,
    memory_id: str,
    user_id: Optional[str],
    agent_id: Optional[str],
):
    memory = service.get_memory(
        memory_id=int(memory_id),
        user_id=user_id,
        agent_id=agent_id,
    )
    memory_response = memory_dict_to_response(memory)
    return APIResponse(
        success=True,
        data=memory_response.model_dump(mode='json'),
        message="Memory retrieved successfully",
    )


def _do_update_memory(
    service: MemoryService,
    memory_id: str,
    body: MemoryUpdateRequest,
    user_id: Optional[str],
    agent_id: Optional[str],
):
    if body.content is None and body.metadata is None:
        from ...models.errors import ErrorCode, APIError
        raise APIError(
            code=ErrorCode.INVALID_REQUEST,
            message="At least one of content or metadata must be provided",
            status_code=400,
        )
    result = service.update_memory(
        memory_id=int(memory_id),
        content=body.content,
        user_id=user_id,
        agent_id=agent_id,
        metadata=body.metadata,
    )
    memory_response = memory_dict_to_response(result)
    return APIResponse(
        success=True,
        data=memory_response.model_dump(mode='json'),
        message="Memory updated successfully",
    )


def _do_batch_update(service: MemoryService, body: MemoryBatchUpdateRequest):
    updates_data = [
        {
            "memory_id": item.memory_id,
            "content": item.content,
            "metadata": item.metadata,
        }
        for item in body.updates
    ]
    result = service.batch_update_memories(
        updates=updates_data,
        user_id=body.user_id,
        agent_id=body.agent_id,
    )
    updated_memories = []
    for item in result["updated"]:
        try:
            memory = service.get_memory(
                memory_id=item["memory_id"],
                user_id=body.user_id,
                agent_id=body.agent_id,
            )
            updated_memories.append(memory_dict_to_response(memory).model_dump(mode='json'))
        except Exception as e:
            logger.warning(f"Failed to retrieve updated memory {item['memory_id']}: {e}")
            updated_memories.append({"memory_id": item["memory_id"]})
    response_data = {
        "memories": updated_memories,
        "total": result["total"],
        "updated_count": result["updated_count"],
        "failed_count": result["failed_count"],
    }
    if result["failed_count"] > 0:
        response_data["failed"] = result["failed"]
    return APIResponse(
        success=True,
        data=response_data,
        message=f"Updated {result['updated_count']} out of {result['total']} memories",
    )


def _do_bulk_delete(
    service: MemoryService,
    memory_ids: List[int],
    user_id: Optional[str],
    agent_id: Optional[str],
):
    result = service.bulk_delete_memories(
        memory_ids=memory_ids,
        user_id=user_id,
        agent_id=agent_id,
    )
    return APIResponse(
        success=True,
        data=result,
        message=f"Deleted {result['deleted_count']} memories",
    )


def _do_delete_memory(
    service: MemoryService,
    memory_id: str,
    user_id: Optional[str],
    agent_id: Optional[str],
):
    service.delete_memory(
        memory_id=int(memory_id),
        user_id=user_id,
        agent_id=agent_id,
    )
    return APIResponse(
        success=True,
        data={"memory_id": memory_id},
        message="Memory deleted successfully",
    )


def _do_get_stats(
    service: MemoryService,
    user_id: Optional[str],
    agent_id: Optional[str],
    time_range: Optional[str],
):
    cutoff_date = None
    if time_range and time_range != "all":
        days = int(time_range[:-1])
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    stats = service.get_statistics(
        user_id=user_id,
        agent_id=agent_id,
        cutoff_date=cutoff_date,
    )
    return APIResponse(success=True, data=stats, message="Statistics retrieved successfully")


async def _do_get_quality(
    service: MemoryService,
    user_id: Optional[str],
    agent_id: Optional[str],
    time_range: Optional[str],
):
    cutoff_date = None
    if time_range and time_range != "all":
        days = int(time_range[:-1])
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    quality_metrics = await service.analyze_memory_quality(
        user_id=user_id,
        agent_id=agent_id,
        cutoff_date=cutoff_date,
    )
    return APIResponse(success=True, data=quality_metrics, message="Quality metrics retrieved successfully")


def _do_get_users(service: MemoryService):
    users = service.get_users()
    return APIResponse(success=True, data=users, message="Users retrieved successfully")


# ===================================================================
# v1 handlers
# ===================================================================

@router.post(
    "",
    response_model=APIResponse,
    summary="Create a memory",
    description="Create a new memory with optional user_id, agent_id, and metadata",
)
@limiter.limit(get_rate_limit_string())
async def create_memory(
    request: Request,
    body: MemoryCreateRequest,
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Create a new memory"""
    return _do_create_memory(service, body)


@router.post(
    "/batch",
    response_model=APIResponse,
    summary="Create multiple memories",
    description="Create multiple memories in a single request (batch operation)",
)
@limiter.limit(get_rate_limit_string())
async def batch_create_memories(
    request: Request,
    body: MemoryBatchCreateRequest,
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Create multiple memories in batch"""
    return _do_batch_create(service, body)


@router.get(
    "",
    response_model=APIResponse,
    summary="List memories",
    description="Get a list of memories with optional filtering, pagination, and sorting",
)
@limiter.limit(get_rate_limit_string())
async def list_memories(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(None, description="Field to sort by: 'created_at', 'updated_at', 'id'"),
    order: str = Query("desc", description="Sort order: 'desc' (descending) or 'asc' (ascending)"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """List memories with pagination and sorting"""
    return _do_list_memories(service, user_id, agent_id, limit, offset, sort_by, order)


@router.get(
    "/stats",
    response_model=APIResponse,
    summary="Get memory statistics",
    description="Get statistics about memories for a user or agent",
)
@limiter.limit(get_rate_limit_string())
async def get_memory_stats(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    time_range: Optional[str] = Query(
        None,
        pattern="^(7d|30d|90d|all)$",
        description="Time range filter: 7d, 30d, 90d, or all"
    ),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Get memory statistics"""
    return _do_get_stats(service, user_id, agent_id, time_range)


@router.get(
    "/quality",
    response_model=APIResponse,
    summary="Get memory quality metrics",
    description="Analyze memory quality and identify potential issues",
)
@limiter.limit(get_rate_limit_string())
async def get_memory_quality(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    time_range: Optional[str] = Query(
        None,
        pattern="^(7d|30d|90d|all)$",
        description="Time range filter: 7d, 30d, 90d, or all"
    ),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Get memory quality metrics"""
    return await _do_get_quality(service, user_id, agent_id, time_range)


@router.get(
    "/users",
    response_model=APIResponse,
    summary="Get unique users",
    description="Get a list of unique user IDs who have memories stored",
)
@limiter.limit(get_rate_limit_string())
async def get_unique_users(
    request: Request,
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Get unique users"""
    return _do_get_users(service)


@router.get(
    "/{memory_id}",
    response_model=APIResponse,
    summary="Get a memory",
    description="Get a specific memory by ID",
)
@limiter.limit(get_rate_limit_string())
async def get_memory(
    request: Request,
    memory_id: str,
    user_id: Optional[str] = Query(None, description="User ID for access control"),
    agent_id: Optional[str] = Query(None, description="Agent ID for access control"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Get a memory by ID"""
    return _do_get_memory(service, memory_id, user_id, agent_id)


@router.put(
    "/batch",
    response_model=APIResponse,
    summary="Batch update memories",
    description="Update multiple memories in a single request (batch operation)",
)
@limiter.limit(get_rate_limit_string())
async def batch_update_memories(
    request: Request,
    body: MemoryBatchUpdateRequest,
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Update multiple memories in batch"""
    return _do_batch_update(service, body)


@router.put(
    "/{memory_id}",
    response_model=APIResponse,
    summary="Update a memory",
    description="Update an existing memory",
)
@limiter.limit(get_rate_limit_string())
async def update_memory(
    request: Request,
    memory_id: str,
    body: MemoryUpdateRequest,
    user_id: Optional[str] = Query(None, description="User ID for access control"),
    agent_id: Optional[str] = Query(None, description="Agent ID for access control"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Update a memory"""
    return _do_update_memory(service, memory_id, body, user_id, agent_id)


@router.delete(
    "/batch",
    response_model=APIResponse,
    summary="Bulk delete memories",
    description="Delete multiple memories at once",
)
@limiter.limit(get_rate_limit_string())
async def bulk_delete_memories(
    request: Request,
    body: BulkDeleteRequest,
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Bulk delete memories"""
    return _do_bulk_delete(service, body.memory_ids, body.user_id, body.agent_id)


@router.delete(
    "/{memory_id}",
    response_model=APIResponse,
    summary="Delete a memory",
    description="Delete a specific memory by ID",
)
@limiter.limit(get_rate_limit_string())
async def delete_memory(
    request: Request,
    memory_id: str,
    user_id: Optional[str] = Query(None, description="User ID for access control"),
    agent_id: Optional[str] = Query(None, description="Agent ID for access control"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Delete a memory"""
    return _do_delete_memory(service, memory_id, user_id, agent_id)


@router.get(
    "/export",
    summary="Export memories",
    description="Export memories to JSON or CSV file",
)
@limiter.limit(get_rate_limit_string())
async def export_memories(
    request: Request,
    format: str = Query("json", description="Export format (json/csv)"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    run_id: Optional[str] = Query(None, description="Filter by run ID"),
    limit: int = Query(1000, ge=1, le=10000, description="Max memories to export"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Export memories"""
    content = service.memory.export_memories(
        format=format,
        user_id=user_id,
        agent_id=agent_id,
        run_id=run_id,
        limit=limit,
    )
    media_type = "application/json" if format.lower() == "json" else "text/csv"
    filename = f"memories_export.{format.lower()}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post(
    "/import",
    response_model=APIResponse,
    summary="Import memories",
    description="Import memories from JSON or CSV file",
)
@limiter.limit(get_rate_limit_string())
async def import_memories(
    request: Request,
    file: UploadFile = File(...),
    user_id: Optional[str] = Query(None, description="Override user ID"),
    agent_id: Optional[str] = Query(None, description="Override agent ID"),
    api_key: str = Depends(verify_api_key),
    service: MemoryService = Depends(get_memory_service),
):
    """Import memories"""
    content = (await file.read()).decode("utf-8")
    filename = file.filename or "import.json"
    fmt = "json"
    if filename.lower().endswith(".csv"):
        fmt = "csv"
    elif filename.lower().endswith(".json"):
        fmt = "json"
    result = service.memory.import_memories(
        source=content,
        format=fmt,
        is_file=False,
        user_id=user_id,
        agent_id=agent_id,
    )
    return APIResponse(
        success=True,
        data=result,
        message=f"Import completed: {result['success']} success, {result['failed']} failed",
    )


# ===================================================================
# v2 handlers — per-request config, all POST
# ===================================================================

@router_v2.post(
    "",
    response_model=APIResponse,
    summary="Create a memory",
    description="Create a new memory with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def create_memory_v2(
    request: Request,
    body: V2MemoryCreateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_create_memory(service, body)


@router_v2.post(
    "/batch",
    response_model=APIResponse,
    summary="Create multiple memories",
    description="Batch create memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def batch_create_memories_v2(
    request: Request,
    body: V2MemoryBatchCreateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_batch_create(service, body)


@router_v2.post(
    "/list",
    response_model=APIResponse,
    summary="List memories",
    description="List memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def list_memories_v2(
    request: Request,
    body: V2MemoryListRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_list_memories(
        service, body.user_id, body.agent_id,
        body.limit, body.offset, body.sort_by, body.order,
    )


@router_v2.post(
    "/stats",
    response_model=APIResponse,
    summary="Get memory statistics",
    description="Get memory statistics with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_memory_stats_v2(
    request: Request,
    body: V2MemoryStatsRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_get_stats(service, body.user_id, body.agent_id, body.time_range)


@router_v2.post(
    "/quality",
    response_model=APIResponse,
    summary="Get memory quality metrics",
    description="Analyze memory quality with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_memory_quality_v2(
    request: Request,
    body: V2MemoryQualityRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return await _do_get_quality(service, body.user_id, body.agent_id, body.time_range)


@router_v2.post(
    "/users",
    response_model=APIResponse,
    summary="Get unique users",
    description="Get unique users with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_unique_users_v2(
    request: Request,
    body: V2MemoryGetRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_get_users(service)


@router_v2.post(
    "/get/{memory_id}",
    response_model=APIResponse,
    summary="Get a memory",
    description="Get a specific memory by ID with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_memory_v2(
    request: Request,
    memory_id: str,
    body: V2MemoryGetRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_get_memory(service, memory_id, body.user_id, body.agent_id)


@router_v2.post(
    "/update/{memory_id}",
    response_model=APIResponse,
    summary="Update a memory",
    description="Update a memory with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def update_memory_v2(
    request: Request,
    memory_id: str,
    body: V2MemoryUpdateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_update_memory(service, memory_id, body, body.user_id, body.agent_id)


@router_v2.post(
    "/batch-update",
    response_model=APIResponse,
    summary="Batch update memories",
    description="Batch update memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def batch_update_memories_v2(
    request: Request,
    body: V2MemoryBatchUpdateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_batch_update(service, body)


@router_v2.post(
    "/delete/{memory_id}",
    response_model=APIResponse,
    summary="Delete a memory",
    description="Delete a memory with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def delete_memory_v2(
    request: Request,
    memory_id: str,
    body: V2MemoryDeleteRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_delete_memory(service, memory_id, body.user_id, body.agent_id)


@router_v2.post(
    "/batch-delete",
    response_model=APIResponse,
    summary="Bulk delete memories",
    description="Bulk delete memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def bulk_delete_memories_v2(
    request: Request,
    body: V2BulkDeleteRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    return _do_bulk_delete(service, body.memory_ids, body.user_id, body.agent_id)

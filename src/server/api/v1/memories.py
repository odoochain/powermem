"""
Memory management API routes (v1)
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from fastapi.responses import Response

from ...models.request import (
    MemoryCreateRequest,
    MemoryBatchCreateRequest,
    MemoryUpdateRequest,
    MemoryBatchUpdateRequest,
    BulkDeleteRequest,
)
from ...models.response import APIResponse
from ...services.memory_service import MemoryService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ..shared.memories import (
    do_create_memory,
    do_batch_create,
    do_list_memories,
    do_get_memory,
    do_update_memory,
    do_batch_update,
    do_bulk_delete,
    do_delete_memory,
    do_get_stats,
    do_get_quality,
    do_get_users,
)

logger = logging.getLogger("server")

router = APIRouter(prefix="/memories", tags=["memories"])


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
    return do_create_memory(service, body)


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
    return do_batch_create(service, body)


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
    return do_list_memories(service, user_id, agent_id, limit, offset, sort_by, order)


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
    return do_get_stats(service, user_id, agent_id, time_range)


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
    return await do_get_quality(service, user_id, agent_id, time_range)


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
    return do_get_users(service)


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
    return do_get_memory(service, memory_id, user_id, agent_id)


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
    return do_batch_update(service, body)


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
    return do_update_memory(service, memory_id, body, user_id, agent_id)


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
    return do_bulk_delete(service, body.memory_ids, body.user_id, body.agent_id)


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
    return do_delete_memory(service, memory_id, user_id, agent_id)


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

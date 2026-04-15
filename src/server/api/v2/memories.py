"""
Memory management API routes (v2) — per-request config, all POST.
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, Request, UploadFile, File, Form

from ...models.request_v2 import (
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
    V2MemoryExportRequest,
    V2MemoryImportRequest,
    PowermemConfig,
)
from ...models.response import APIResponse
from ...services.memory_service import MemoryService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config
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
from fastapi.responses import Response

router_v2 = APIRouter(prefix="/memories", tags=["memories-v2"])


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
    return do_create_memory(service, body)


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
    return do_batch_create(service, body)


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
    return do_list_memories(
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
    return do_get_stats(service, body.user_id, body.agent_id, body.time_range)


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
    return await do_get_quality(service, body.user_id, body.agent_id, body.time_range)


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
    return do_get_users(service)


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
    return do_get_memory(service, memory_id, body.user_id, body.agent_id)


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
    return do_update_memory(service, memory_id, body, body.user_id, body.agent_id)


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
    return do_batch_update(service, body)


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
    return do_delete_memory(service, memory_id, body.user_id, body.agent_id)


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
    return do_bulk_delete(service, body.memory_ids, body.user_id, body.agent_id)


@router_v2.post(
    "/export",
    summary="Export memories",
    description="Export memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def export_memories_v2(
    request: Request,
    body: V2MemoryExportRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    content = service.memory.export_memories(
        format=body.format,
        user_id=body.user_id,
        agent_id=body.agent_id,
        run_id=body.run_id,
        limit=body.limit,
    )
    media_type = "application/json" if body.format.lower() == "json" else "text/csv"
    filename = f"memories_export.{body.format.lower()}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router_v2.post(
    "/import",
    response_model=APIResponse,
    summary="Import memories",
    description="Import memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def import_memories_v2(
    request: Request,
    body: V2MemoryImportRequest,
    api_key: str = Depends(verify_api_key),
):
    service = MemoryService(config=resolve_config(body.config))
    result = service.memory.import_memories(
        source=body.source,
        format=body.format,
        user_id=body.user_id,
        agent_id=body.agent_id,
    )
    return APIResponse(
        success=True,
        data=result,
        message=f"Import completed: {result['success']} success, {result['failed']} failed",
    )


@router_v2.post(
    "/import-file",
    response_model=APIResponse,
    summary="Import memories (multipart)",
    description="Import memories via multipart file upload with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def import_memories_file_v2(
    request: Request,
    file: UploadFile = File(...),
    config: Optional[str] = Form(None, description="JSON string of per-request config"),
    format: Optional[str] = Form(None, description="Import format: json/csv"),
    user_id: Optional[str] = Form(None, description="Override user ID"),
    agent_id: Optional[str] = Form(None, description="Override agent ID"),
    api_key: str = Depends(verify_api_key),
):
    powermem_config = None
    if config:
        powermem_config = PowermemConfig.model_validate(json.loads(config))
    service = MemoryService(config=resolve_config(powermem_config))
    content = (await file.read()).decode("utf-8")
    filename = file.filename or "import.json"
    fmt = format or "json"
    if format is None:
        if filename.lower().endswith(".csv"):
            fmt = "csv"
        elif filename.lower().endswith(".json"):
            fmt = "json"
    result = service.memory.import_memories(
        source=content,
        format=fmt,
        user_id=user_id,
        agent_id=agent_id,
    )
    return APIResponse(
        success=True,
        data=result,
        message=f"Import completed: {result['success']} success, {result['failed']} failed",
    )

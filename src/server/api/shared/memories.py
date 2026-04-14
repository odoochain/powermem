"""
Shared memory business logic (v1 + v2).
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from ...models.request import (
    MemoryCreateRequest,
    MemoryBatchCreateRequest,
    MemoryUpdateRequest,
    MemoryBatchUpdateRequest,
)
from ...models.response import APIResponse, MemoryListResponse
from ...services.memory_service import MemoryService
from ...utils.converters import memory_dict_to_response

logger = logging.getLogger("server")


def do_create_memory(service: MemoryService, body: MemoryCreateRequest):
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


def do_batch_create(service: MemoryService, body: MemoryBatchCreateRequest):
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


def do_list_memories(
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


def do_get_memory(
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


def do_update_memory(
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


def do_batch_update(service: MemoryService, body: MemoryBatchUpdateRequest):
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


def do_bulk_delete(
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


def do_delete_memory(
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


def do_get_stats(
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


async def do_get_quality(
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


def do_get_users(service: MemoryService):
    users = service.get_users()
    return APIResponse(success=True, data=users, message="Users retrieved successfully")

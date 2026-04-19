"""
Shared agent memory business logic (v1 + v2).
"""

from typing import Optional

from ...models.request import AgentMemoryCreateRequest, AgentMemoryShareRequest
from ...models.response import APIResponse, MemoryListResponse
from ...services.agent_service import AgentService
from ...utils.converters import memory_dict_to_response


def do_get_agent_memories(service: AgentService, agent_id: str, limit: int, offset: int):
    memories = service.get_agent_memories(agent_id=agent_id, limit=limit, offset=offset)
    memory_responses = [memory_dict_to_response(m) for m in memories]
    response_data = MemoryListResponse(
        memories=memory_responses,
        total=len(memory_responses),
        limit=limit,
        offset=offset,
    )
    return APIResponse(
        success=True,
        data=response_data.model_dump(mode='json'),
        message="Agent memories retrieved successfully",
    )


def do_create_agent_memory(service: AgentService, agent_id: str, body: AgentMemoryCreateRequest):
    result = service.create_agent_memory(
        agent_id=agent_id,
        content=body.content,
        user_id=body.user_id,
        run_id=body.run_id,
    )
    memory_response = memory_dict_to_response(result)
    return APIResponse(
        success=True,
        data=memory_response.model_dump(mode='json'),
        message="Agent memory created successfully",
    )


def do_share_memories(service: AgentService, agent_id: str, body: AgentMemoryShareRequest):
    result = service.share_memories(
        agent_id=agent_id,
        target_agent_id=body.target_agent_id,
        memory_ids=body.memory_ids,
    )
    return APIResponse(
        success=True,
        data=result,
        message=f"Shared {result['shared_count']} memories successfully",
    )


def do_get_shared_memories(
    service: AgentService,
    agent_id: str,
    limit: int,
    offset: int,
    user_id: Optional[str] = None,
):
    memories = service.get_shared_memories(
        agent_id=agent_id,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )
    memory_responses = [memory_dict_to_response(m) for m in memories]
    response_data = MemoryListResponse(
        memories=memory_responses,
        total=len(memory_responses),
        limit=limit,
        offset=offset,
    )
    return APIResponse(
        success=True,
        data=response_data.model_dump(mode='json'),
        message="Shared memories retrieved successfully",
    )

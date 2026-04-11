"""
Agent memory API routes (v1 + v2)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter

from ...models.request import (
    AgentMemoryCreateRequest,
    AgentMemoryShareRequest,
    V2AgentMemoryCreateRequest,
    V2AgentMemoryShareRequest,
    V2AgentMemoriesRequest,
)
from ...models.response import APIResponse, MemoryListResponse
from ...services.agent_service import AgentService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.converters import memory_dict_to_response
from ...utils.config_resolver import resolve_config

router = APIRouter(prefix="/agents", tags=["agents"])
router_v2 = APIRouter(prefix="/agents", tags=["agents-v2"])


def get_agent_service(request: Request) -> AgentService:
    """Dependency to get agent service singleton from app state"""
    service = request.app.state.agent_service
    if service is None:
        from ...models.errors import ErrorCode, APIError
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="Agent service unavailable: storage backend initialization failed",
            status_code=503,
        )
    return service


# ===================================================================
# Shared business logic
# ===================================================================

def _do_get_agent_memories(service: AgentService, agent_id: str, limit: int, offset: int):
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


def _do_create_agent_memory(service: AgentService, agent_id: str, body: AgentMemoryCreateRequest):
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


def _do_share_memories(service: AgentService, agent_id: str, body: AgentMemoryShareRequest):
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


def _do_get_shared_memories(service: AgentService, agent_id: str, limit: int, offset: int):
    memories = service.get_shared_memories(agent_id=agent_id, limit=limit, offset=offset)
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


# ===================================================================
# v1 handlers
# ===================================================================

@router.get(
    "/{agent_id}/memories",
    response_model=APIResponse,
    summary="Get agent memories",
    description="Get all memories for a specific agent",
)
@limiter.limit(get_rate_limit_string())
async def get_agent_memories(
    request: Request,
    agent_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    api_key: str = Depends(verify_api_key),
    service: AgentService = Depends(get_agent_service),
):
    """Get all memories for an agent"""
    return _do_get_agent_memories(service, agent_id, limit, offset)


@router.post(
    "/{agent_id}/memories",
    response_model=APIResponse,
    summary="Create agent memory",
    description="Create a new memory for a specific agent",
)
@limiter.limit(get_rate_limit_string())
async def create_agent_memory(
    request: Request,
    agent_id: str,
    body: AgentMemoryCreateRequest,
    api_key: str = Depends(verify_api_key),
    service: AgentService = Depends(get_agent_service),
):
    """Create a memory for an agent"""
    return _do_create_agent_memory(service, agent_id, body)


@router.post(
    "/{agent_id}/memories/share",
    response_model=APIResponse,
    summary="Share agent memories",
    description="Share memories from one agent to another",
)
@limiter.limit(get_rate_limit_string())
async def share_agent_memories(
    request: Request,
    agent_id: str,
    body: AgentMemoryShareRequest,
    api_key: str = Depends(verify_api_key),
    service: AgentService = Depends(get_agent_service),
):
    """Share memories between agents"""
    return _do_share_memories(service, agent_id, body)


@router.get(
    "/{agent_id}/memories/share",
    response_model=APIResponse,
    summary="Get shared memories",
    description="Get shared memories for an agent",
)
@limiter.limit(get_rate_limit_string())
async def get_shared_memories(
    request: Request,
    agent_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    api_key: str = Depends(verify_api_key),
    service: AgentService = Depends(get_agent_service),
):
    """Get shared memories for an agent"""
    return _do_get_shared_memories(service, agent_id, limit, offset)


# ===================================================================
# v2 handlers
# ===================================================================

@router_v2.post(
    "/{agent_id}/memories/list",
    response_model=APIResponse,
    summary="Get agent memories",
    description="Get agent memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_agent_memories_v2(
    request: Request,
    agent_id: str,
    body: V2AgentMemoriesRequest,
    api_key: str = Depends(verify_api_key),
):
    service = AgentService(config=resolve_config(body.config))
    return _do_get_agent_memories(service, agent_id, body.limit, body.offset)


@router_v2.post(
    "/{agent_id}/memories",
    response_model=APIResponse,
    summary="Create agent memory",
    description="Create agent memory with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def create_agent_memory_v2(
    request: Request,
    agent_id: str,
    body: V2AgentMemoryCreateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = AgentService(config=resolve_config(body.config))
    return _do_create_agent_memory(service, agent_id, body)


@router_v2.post(
    "/{agent_id}/memories/share",
    response_model=APIResponse,
    summary="Share agent memories",
    description="Share agent memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def share_agent_memories_v2(
    request: Request,
    agent_id: str,
    body: V2AgentMemoryShareRequest,
    api_key: str = Depends(verify_api_key),
):
    service = AgentService(config=resolve_config(body.config))
    return _do_share_memories(service, agent_id, body)


@router_v2.post(
    "/{agent_id}/memories/shared",
    response_model=APIResponse,
    summary="Get shared memories",
    description="Get shared memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_shared_memories_v2(
    request: Request,
    agent_id: str,
    body: V2AgentMemoriesRequest,
    api_key: str = Depends(verify_api_key),
):
    service = AgentService(config=resolve_config(body.config))
    return _do_get_shared_memories(service, agent_id, body.limit, body.offset)

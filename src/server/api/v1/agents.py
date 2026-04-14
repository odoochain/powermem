"""
Agent memory API routes (v1)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request

from ...models.request import AgentMemoryCreateRequest, AgentMemoryShareRequest
from ...models.response import APIResponse
from ...services.agent_service import AgentService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ..shared.agents import (
    do_get_agent_memories,
    do_create_agent_memory,
    do_share_memories,
    do_get_shared_memories,
)

router = APIRouter(prefix="/agents", tags=["agents"])


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
    return do_get_agent_memories(service, agent_id, limit, offset)


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
    return do_create_agent_memory(service, agent_id, body)


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
    return do_share_memories(service, agent_id, body)


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
    return do_get_shared_memories(service, agent_id, limit, offset)

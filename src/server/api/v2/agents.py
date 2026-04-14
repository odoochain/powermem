"""
Agent memory API routes (v2) — per-request config, all POST.
"""

from fastapi import APIRouter, Depends, Request

from ...models.request_v2 import (
    V2AgentMemoryCreateRequest,
    V2AgentMemoryShareRequest,
    V2AgentMemoriesRequest,
)
from ...models.response import APIResponse
from ...services.agent_service import AgentService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config
from ..shared.agents import (
    do_get_agent_memories,
    do_create_agent_memory,
    do_share_memories,
    do_get_shared_memories,
)

router_v2 = APIRouter(prefix="/agents", tags=["agents-v2"])


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
    return do_get_agent_memories(service, agent_id, body.limit, body.offset)


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
    return do_create_agent_memory(service, agent_id, body)


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
    return do_share_memories(service, agent_id, body)


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
    return do_get_shared_memories(service, agent_id, body.limit, body.offset)

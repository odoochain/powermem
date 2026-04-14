"""
User profile API routes (v2) — per-request config, all POST.
"""

from fastapi import APIRouter, Depends, Request

from ...models.request_v2 import (
    V2UserProfileAddRequest,
    V2UserProfileGetRequest,
    V2UserProfileUpdateRequest,
    V2UserMemoriesRequest,
    V2UserDeleteRequest,
    V2UserProfilesRequest,
)
from ...models.response import APIResponse
from ...services.user_service import UserService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.config_resolver import resolve_config
from ..shared.users import (
    do_get_profile,
    do_add_profile,
    do_update_user_memory,
    do_get_user_memories,
    do_delete_profile,
    do_delete_user_memories,
    do_get_all_profiles,
)

router_v2 = APIRouter(prefix="/users", tags=["users-v2"])


@router_v2.post(
    "/{user_id}/profile/get",
    response_model=APIResponse,
    summary="Get user profile",
    description="Get user profile with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_user_profile_v2(
    request: Request,
    user_id: str,
    body: V2UserProfileGetRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_get_profile(service, user_id)


@router_v2.post(
    "/{user_id}/profile",
    response_model=APIResponse,
    summary="Add messages and extract user profile",
    description="Add user profile with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def add_user_profile_v2(
    request: Request,
    user_id: str,
    body: V2UserProfileAddRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_add_profile(service, user_id, body)


@router_v2.post(
    "/{user_id}/memories/update/{memory_id}",
    response_model=APIResponse,
    summary="Update user memory",
    description="Update user memory with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def update_user_memory_v2(
    request: Request,
    user_id: str,
    memory_id: int,
    body: V2UserProfileUpdateRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_update_user_memory(service, user_id, memory_id, body)


@router_v2.post(
    "/{user_id}/memories",
    response_model=APIResponse,
    summary="Get user memories",
    description="Get user memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_user_memories_v2(
    request: Request,
    user_id: str,
    body: V2UserMemoriesRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_get_user_memories(service, user_id, body.limit, body.offset)


@router_v2.post(
    "/{user_id}/profile/delete",
    response_model=APIResponse,
    summary="Delete user profile",
    description="Delete user profile with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def delete_user_profile_v2(
    request: Request,
    user_id: str,
    body: V2UserDeleteRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_delete_profile(service, user_id)


@router_v2.post(
    "/{user_id}/memories/delete",
    response_model=APIResponse,
    summary="Delete user memories",
    description="Delete user memories with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def delete_user_memories_v2(
    request: Request,
    user_id: str,
    body: V2UserDeleteRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_delete_user_memories(service, user_id)


@router_v2.post(
    "/profiles",
    response_model=APIResponse,
    summary="Get all user profiles",
    description="Get all user profiles with per-request config",
)
@limiter.limit(get_rate_limit_string())
async def get_all_user_profiles_v2(
    request: Request,
    body: V2UserProfilesRequest,
    api_key: str = Depends(verify_api_key),
):
    service = UserService(config=resolve_config(body.config))
    return do_get_all_profiles(service, body.user_id, body.fuzzy, body.limit, body.offset)

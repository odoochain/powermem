"""
User profile API routes (v1 + v2)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from slowapi import Limiter

from ...models.request import (
    UserProfileAddRequest,
    UserProfileUpdateRequest,
    V2UserProfileAddRequest,
    V2UserProfileGetRequest,
    V2UserProfileUpdateRequest,
    V2UserMemoriesRequest,
    V2UserDeleteRequest,
    V2UserProfilesRequest,
)
from ...models.response import APIResponse, UserProfileResponse, MemoryListResponse
from ...services.user_service import UserService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ...utils.converters import user_profile_to_response, memory_dict_to_response
from ...utils.config_resolver import resolve_config

router = APIRouter(prefix="/users", tags=["users"])
router_v2 = APIRouter(prefix="/users", tags=["users-v2"])


def get_user_service(request: Request) -> UserService:
    """Dependency to get user service singleton from app state"""
    service = request.app.state.user_service
    if service is None:
        from ...models.errors import ErrorCode, APIError
        raise APIError(
            code=ErrorCode.INTERNAL_ERROR,
            message="User service unavailable: storage backend initialization failed",
            status_code=503,
        )
    return service


# ===================================================================
# Shared business logic
# ===================================================================

def _do_get_profile(service: UserService, user_id: str):
    profile = service.get_user_profile(user_id)
    profile_response = user_profile_to_response(user_id, profile)
    return APIResponse(
        success=True,
        data=profile_response.model_dump(mode='json'),
        message="User profile retrieved successfully",
    )


def _do_add_profile(service: UserService, user_id: str, body: UserProfileAddRequest):
    result = service.add_user_profile(
        user_id=user_id,
        messages=body.messages,
        agent_id=body.agent_id,
        run_id=body.run_id,
        metadata=body.metadata,
        filters=body.filters,
        scope=body.scope,
        memory_type=body.memory_type,
        prompt=body.prompt,
        infer=body.infer,
        profile_type=body.profile_type,
        custom_topics=body.custom_topics,
        strict_mode=body.strict_mode,
        include_roles=body.include_roles,
        exclude_roles=body.exclude_roles,
        native_language=body.native_language,
    )
    return APIResponse(
        success=True,
        data=result,
        message="Messages added and profile extracted successfully",
    )


def _do_update_user_memory(
    service: UserService,
    user_id: str,
    memory_id: int,
    body: UserProfileUpdateRequest,
):
    result = service.update_user_memory(
        user_id=user_id,
        memory_id=memory_id,
        content=body.content,
        agent_id=body.agent_id,
        metadata=body.metadata,
    )
    memory_response = memory_dict_to_response(result)
    return APIResponse(
        success=True,
        data=memory_response.model_dump(mode='json'),
        message="Memory updated successfully",
    )


def _do_get_user_memories(service: UserService, user_id: str, limit: int, offset: int):
    memories = service.get_user_memories(user_id=user_id, limit=limit, offset=offset)
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
        message="User memories retrieved successfully",
    )


def _do_delete_profile(service: UserService, user_id: str):
    result = service.delete_user_profile(user_id=user_id)
    return APIResponse(
        success=True,
        data=result,
        message=f"User profile for {user_id} deleted successfully",
    )


def _do_delete_user_memories(service: UserService, user_id: str):
    result = service.delete_user_memories(user_id=user_id)
    return APIResponse(
        success=True,
        data=result,
        message=f"Deleted {result['deleted_count']} memories for user {user_id}",
    )


def _do_get_all_profiles(
    service: UserService,
    user_id: Optional[str],
    fuzzy: bool,
    limit: int,
    offset: int,
):
    total_count = service.count_profiles(user_id=user_id, fuzzy=fuzzy)
    profiles = service.get_all_profiles(user_id=user_id, fuzzy=fuzzy, limit=limit, offset=offset)
    return APIResponse(
        success=True,
        data={
            "profiles": profiles,
            "total": total_count,
            "limit": limit,
            "offset": offset,
        },
        message="User profiles retrieved successfully",
    )


# ===================================================================
# v1 handlers
# ===================================================================

@router.get(
    "/{user_id}/profile",
    response_model=APIResponse,
    summary="Get user profile",
    description="Get the user profile for a specific user",
)
@limiter.limit(get_rate_limit_string())
async def get_user_profile(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Get user profile"""
    return _do_get_profile(service, user_id)


@router.post(
    "/{user_id}/profile",
    response_model=APIResponse,
    summary="Add messages and extract user profile",
    description="Add conversation messages and extract user profile information",
)
@limiter.limit(get_rate_limit_string())
async def add_user_profile(
    request: Request,
    user_id: str,
    body: UserProfileAddRequest,
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Add messages and extract user profile"""
    return _do_add_profile(service, user_id, body)


@router.put(
    "/{user_id}/memories/{memory_id}",
    response_model=APIResponse,
    summary="Update user memory",
    description="Update an existing memory for a specific user",
)
@limiter.limit(get_rate_limit_string())
async def update_user_memory(
    request: Request,
    user_id: str,
    memory_id: int,
    body: UserProfileUpdateRequest,
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Update user memory"""
    return _do_update_user_memory(service, user_id, memory_id, body)


@router.get(
    "/{user_id}/memories",
    response_model=APIResponse,
    summary="Get user memories",
    description="Get all memories for a specific user",
)
@limiter.limit(get_rate_limit_string())
async def get_user_memories(
    request: Request,
    user_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Get all memories for a user"""
    return _do_get_user_memories(service, user_id, limit, offset)


@router.delete(
    "/{user_id}/profile",
    response_model=APIResponse,
    summary="Delete user profile",
    description="Delete the user profile for a specific user",
)
@limiter.limit(get_rate_limit_string())
async def delete_user_profile(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Delete user profile"""
    return _do_delete_profile(service, user_id)


@router.delete(
    "/{user_id}/memories",
    response_model=APIResponse,
    summary="Delete user memories",
    description="Delete all memories for a specific user (user profile deletion)",
)
@limiter.limit(get_rate_limit_string())
async def delete_user_memories(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Delete all memories for a user"""
    return _do_delete_user_memories(service, user_id)


@router.get(
    "/profiles",
    response_model=APIResponse,
    summary="Get all user profiles",
    description="Get all user profiles with optional filtering and pagination",
)
@limiter.limit(get_rate_limit_string())
async def get_all_user_profiles(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    fuzzy: bool = Query(False, description="Use fuzzy match for user ID"),
    limit: int = Query(20, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    api_key: str = Depends(verify_api_key),
    service: UserService = Depends(get_user_service),
):
    """Get all user profiles with pagination"""
    return _do_get_all_profiles(service, user_id, fuzzy, limit, offset)


# ===================================================================
# v2 handlers
# ===================================================================

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
    return _do_get_profile(service, user_id)


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
    return _do_add_profile(service, user_id, body)


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
    return _do_update_user_memory(service, user_id, memory_id, body)


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
    return _do_get_user_memories(service, user_id, body.limit, body.offset)


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
    return _do_delete_profile(service, user_id)


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
    return _do_delete_user_memories(service, user_id)


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
    return _do_get_all_profiles(service, body.user_id, body.fuzzy, body.limit, body.offset)

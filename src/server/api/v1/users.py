"""
User profile API routes (v1)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request

from ...models.request import UserProfileAddRequest, UserProfileUpdateRequest
from ...models.response import APIResponse
from ...services.user_service import UserService
from ...middleware.auth import verify_api_key
from ...middleware.rate_limit import limiter, get_rate_limit_string
from ..shared.users import (
    do_get_profile,
    do_add_profile,
    do_update_user_memory,
    do_get_user_memories,
    do_delete_profile,
    do_delete_user_memories,
    do_get_all_profiles,
)

router = APIRouter(prefix="/users", tags=["users"])


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
    return do_get_profile(service, user_id)


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
    return do_add_profile(service, user_id, body)


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
    return do_update_user_memory(service, user_id, memory_id, body)


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
    return do_get_user_memories(service, user_id, limit, offset)


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
    return do_delete_profile(service, user_id)


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
    return do_delete_user_memories(service, user_id)


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
    return do_get_all_profiles(service, user_id, fuzzy, limit, offset)

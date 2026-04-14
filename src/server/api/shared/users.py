"""
Shared user profile business logic (v1 + v2).
"""

from typing import Optional

from ...models.request import UserProfileAddRequest, UserProfileUpdateRequest
from ...models.response import APIResponse, MemoryListResponse
from ...services.user_service import UserService
from ...utils.converters import user_profile_to_response, memory_dict_to_response


def do_get_profile(service: UserService, user_id: str):
    profile = service.get_user_profile(user_id)
    profile_response = user_profile_to_response(user_id, profile)
    return APIResponse(
        success=True,
        data=profile_response.model_dump(mode='json'),
        message="User profile retrieved successfully",
    )


def do_add_profile(service: UserService, user_id: str, body: UserProfileAddRequest):
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


def do_update_user_memory(
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


def do_get_user_memories(service: UserService, user_id: str, limit: int, offset: int):
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


def do_delete_profile(service: UserService, user_id: str):
    result = service.delete_user_profile(user_id=user_id)
    return APIResponse(
        success=True,
        data=result,
        message=f"User profile for {user_id} deleted successfully",
    )


def do_delete_user_memories(service: UserService, user_id: str):
    result = service.delete_user_memories(user_id=user_id)
    return APIResponse(
        success=True,
        data=result,
        message=f"Deleted {result['deleted_count']} memories for user {user_id}",
    )


def do_get_all_profiles(
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

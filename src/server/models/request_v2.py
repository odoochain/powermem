"""
v2 request models — per-request config support.

Inherit v1 base models and add an optional ``config`` field.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from .request import (
    MemoryCreateRequest,
    MemoryBatchCreateRequest,
    MemoryUpdateRequest,
    MemoryBatchUpdateRequest,
    BulkDeleteRequest,
    SearchRequest,
    UserProfileAddRequest,
    UserProfileUpdateRequest,
    AgentMemoryCreateRequest,
    AgentMemoryShareRequest,
)


# ---------------------------------------------------------------------------
# Config models
# ---------------------------------------------------------------------------

class ProviderConfig(BaseModel):
    """Provider + config pair (e.g. llm, embedder, vector_store)"""
    provider: str = Field(..., description="Provider name (e.g. 'qwen', 'openai', 'oceanbase')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")


class PowermemConfig(BaseModel):
    """SDK-level configuration carried in v2 requests.

    Mirrors the dict returned by ``auto_config()``.  Every field is optional;
    missing fields fall back to the server-side defaults (env / .env).
    """
    vector_store: Optional[ProviderConfig] = Field(None, description="Vector store / database config")
    llm: Optional[ProviderConfig] = Field(None, description="LLM provider config")
    embedder: Optional[ProviderConfig] = Field(None, description="Embedding provider config")
    graph_store: Optional[Dict[str, Any]] = Field(None, description="Graph store config")
    reranker: Optional[Dict[str, Any]] = Field(None, description="Reranker config")
    sparse_embedder: Optional[Dict[str, Any]] = Field(None, description="Sparse embedder config")
    intelligent_memory: Optional[Dict[str, Any]] = Field(None, description="Intelligent memory config")
    agent_memory: Optional[Dict[str, Any]] = Field(None, description="Agent memory config")
    query_rewrite: Optional[Dict[str, Any]] = Field(None, description="Query rewrite config")
    timezone: Optional[Dict[str, Any]] = Field(None, description="Timezone config")


# ---------------------------------------------------------------------------
# v2 request models
# ---------------------------------------------------------------------------

class V2MemoryCreateRequest(MemoryCreateRequest):
    """v2: create memory with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2MemoryBatchCreateRequest(MemoryBatchCreateRequest):
    """v2: batch create with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2MemoryUpdateRequest(MemoryUpdateRequest):
    """v2: update memory with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="User ID for access control")
    agent_id: Optional[str] = Field(None, description="Agent ID for access control")


class V2MemoryBatchUpdateRequest(MemoryBatchUpdateRequest):
    """v2: batch update with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2MemoryGetRequest(BaseModel):
    """v2: get memory (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="User ID for access control")
    agent_id: Optional[str] = Field(None, description="Agent ID for access control")


class V2MemoryListRequest(BaseModel):
    """v2: list memories (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
    sort_by: Optional[str] = Field(None, description="Field to sort by: 'created_at', 'updated_at', 'id'")
    order: str = Field("desc", description="Sort order: 'desc' or 'asc'")


class V2MemoryDeleteRequest(BaseModel):
    """v2: delete memory (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="User ID for access control")
    agent_id: Optional[str] = Field(None, description="Agent ID for access control")


class V2BulkDeleteRequest(BulkDeleteRequest):
    """v2: bulk delete with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2SearchRequest(SearchRequest):
    """v2: search with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2UserProfileAddRequest(UserProfileAddRequest):
    """v2: add user profile with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2UserProfileGetRequest(BaseModel):
    """v2: get user profile (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2UserProfileUpdateRequest(UserProfileUpdateRequest):
    """v2: update user memory with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2UserMemoriesRequest(BaseModel):
    """v2: get user memories (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")


class V2UserDeleteRequest(BaseModel):
    """v2: delete user profile/memories (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2AgentMemoryCreateRequest(AgentMemoryCreateRequest):
    """v2: create agent memory with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2AgentMemoryShareRequest(AgentMemoryShareRequest):
    """v2: share agent memories with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")


class V2AgentMemoriesRequest(BaseModel):
    """v2: get agent memories (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")


class V2DeleteAllRequest(BaseModel):
    """v2: delete all memories with per-request config"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    run_id: Optional[str] = Field(None, description="Filter by run ID")


class V2MemoryStatsRequest(BaseModel):
    """v2: get memory stats (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    time_range: Optional[str] = Field(None, description="Time range: 7d, 30d, 90d, or all")


class V2MemoryQualityRequest(BaseModel):
    """v2: get memory quality (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    time_range: Optional[str] = Field(None, description="Time range: 7d, 30d, 90d, or all")


class V2UserProfilesRequest(BaseModel):
    """v2: get all user profiles (POST with config)"""
    config: Optional[PowermemConfig] = Field(None, description="Per-request PowerMem configuration")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    fuzzy: bool = Field(False, description="Use fuzzy match for user ID")
    limit: int = Field(20, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")

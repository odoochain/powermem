"""
Request models for PowerMem API
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# v2 Config models — passed per-request instead of loaded from .env
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
# v1 request models
# ---------------------------------------------------------------------------

class MemoryCreateRequest(BaseModel):
    """Request model for creating a memory"""
    
    content: str = Field(..., description="Memory content (string, dict, or list of dicts)")
    user_id: Optional[str] = Field(None, description="User identifier")
    agent_id: Optional[str] = Field(None, description="Agent identifier")
    run_id: Optional[str] = Field(None, description="Run/conversation identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter metadata for advanced filtering")
    scope: Optional[str] = Field(None, description="Memory scope (e.g., 'user', 'agent', 'session')")
    memory_type: Optional[str] = Field(None, description="Memory type classification")
    infer: bool = Field(True, description="Enable intelligent memory processing")


class MemoryItem(BaseModel):
    """Single memory item for batch creation"""
    
    content: str = Field(..., description="Memory content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for this memory")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter metadata for this memory")
    scope: Optional[str] = Field(None, description="Memory scope")
    memory_type: Optional[str] = Field(None, description="Memory type classification")


class MemoryBatchCreateRequest(BaseModel):
    """Request model for creating multiple memories in batch"""
    
    memories: List[MemoryItem] = Field(..., description="List of memories to create", min_length=1, max_length=100)
    user_id: Optional[str] = Field(None, description="User identifier (applied to all memories)")
    agent_id: Optional[str] = Field(None, description="Agent identifier (applied to all memories)")
    run_id: Optional[str] = Field(None, description="Run/conversation identifier (applied to all memories)")
    infer: bool = Field(True, description="Enable intelligent memory processing")


class MemoryUpdateRequest(BaseModel):
    """Request model for updating a memory"""
    
    content: Optional[str] = Field(None, description="New content for the memory")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class MemoryUpdateItem(BaseModel):
    """Single memory update item for batch update"""
    
    memory_id: int = Field(..., description="Memory ID to update")
    content: Optional[str] = Field(None, description="New content for the memory (optional)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata (optional)")


class MemoryBatchUpdateRequest(BaseModel):
    """Request model for updating multiple memories in batch"""
    
    updates: List[MemoryUpdateItem] = Field(..., description="List of memory updates", min_length=1, max_length=100)
    user_id: Optional[str] = Field(None, description="User ID for access control")
    agent_id: Optional[str] = Field(None, description="Agent ID for access control")


class SearchRequest(BaseModel):
    """Request model for searching memories"""
    
    query: str = Field(..., description="Search query")
    user_id: Optional[str] = Field(None, description="Filter by user ID")
    agent_id: Optional[str] = Field(None, description="Filter by agent ID")
    run_id: Optional[str] = Field(None, description="Filter by run ID")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")
    limit: int = Field(default=30, ge=1, le=100, description="Maximum number of results")


class UserProfileAddRequest(BaseModel):
    """Request model for adding messages and extracting user profile"""
    
    messages: Any = Field(..., description="Conversation messages (str, dict, or list[dict])")
    agent_id: Optional[str] = Field(None, description="Agent identifier")
    run_id: Optional[str] = Field(None, description="Run/session identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    filters: Optional[Dict[str, Any]] = Field(None, description="Filter metadata for advanced filtering")
    scope: Optional[str] = Field(None, description="Memory scope")
    memory_type: Optional[str] = Field(None, description="Memory type classification")
    prompt: Optional[str] = Field(None, description="Custom prompt for intelligent processing")
    infer: bool = Field(True, description="Enable intelligent memory processing")
    profile_type: str = Field("content", description="Profile extraction type: 'content' or 'topics'")
    custom_topics: Optional[str] = Field(None, description="Custom topics JSON string for structured extraction (only used when profile_type='topics')")
    strict_mode: bool = Field(False, description="Only output topics from provided list (only used when profile_type='topics')")
    include_roles: Optional[List[str]] = Field(["user"], description="Roles to include when filtering messages. Default: ['user']. Set to None or [] to disable.")
    exclude_roles: Optional[List[str]] = Field(["assistant"], description="Roles to exclude when filtering messages. Default: ['assistant']. Set to None or [] to disable.")
    native_language: Optional[str] = Field(None, description="ISO 639-1 language code (e.g., 'zh', 'en') for profile extraction. If specified, profile will be extracted in this language.")


class UserProfileUpdateRequest(BaseModel):
    """Request model for updating a user memory"""
    
    content: str = Field(..., description="New content for the memory")
    agent_id: Optional[str] = Field(None, description="Agent identifier for access control")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Updated metadata")


class AgentMemoryCreateRequest(BaseModel):
    """Request model for creating agent memory"""
    
    content: str = Field(..., description="Memory content")
    user_id: Optional[str] = Field(None, description="User ID")
    run_id: Optional[str] = Field(None, description="Run ID")


class AgentMemoryShareRequest(BaseModel):
    """Request model for sharing memories between agents"""
    
    target_agent_id: str = Field(..., description="Target agent ID to share with")
    memory_ids: Optional[List[int]] = Field(None, description="Specific memory IDs to share (None for all)")


class BulkDeleteRequest(BaseModel):
    """Request model for bulk deleting memories"""
    
    memory_ids: List[int] = Field(..., description="List of memory IDs to delete", min_length=1, max_length=100)
    user_id: Optional[str] = Field(None, description="User ID for access control")
    agent_id: Optional[str] = Field(None, description="Agent ID for access control")


# ---------------------------------------------------------------------------
# v2 request models — inherit v1 models and add ``config`` field
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

"""Configuration for Apache AGE graph store provider."""

from typing import Any, Optional

from pydantic import AliasChoices, Field, field_validator

from powermem.settings import settings_config
from powermem.storage.config.base import BaseGraphStoreConfig


class AGEGraphConfig(BaseGraphStoreConfig):
    """Configuration for Apache AGE graph store.

    Apache AGE is a PostgreSQL extension that provides graph database
    capabilities via openCypher. This config connects to a PostgreSQL
    instance with the AGE extension installed.

    Environment variable priority (via AliasChoices):
    1. GRAPH_STORE_* (highest priority, inherited)
    2. AGE_* / POSTGRES_* (fallback)
    3. Default values
    """

    _provider_name = "age"
    _class_path = "powermem.storage.age.age_graph.AGEGraphStore"

    model_config = settings_config("GRAPH_STORE_", extra="forbid", env_file=None)

    # PostgreSQL connection parameters (override OceanBase defaults)
    host: str = Field(
        default="localhost",
        validation_alias=AliasChoices(
            "host",
            "GRAPH_STORE_HOST",
            "AGE_HOST",
            "POSTGRES_HOST",
        ),
        description="PostgreSQL server host",
    )

    port: str = Field(
        default="5432",
        validation_alias=AliasChoices(
            "port",
            "GRAPH_STORE_PORT",
            "AGE_PORT",
            "POSTGRES_PORT",
        ),
        description="PostgreSQL server port",
    )

    @field_validator("port", mode="before")
    @classmethod
    def _coerce_port_to_str(cls, value: Any) -> Any:
        if isinstance(value, int):
            return str(value)
        return value

    user: str = Field(
        default="postgres",
        validation_alias=AliasChoices(
            "GRAPH_STORE_USER",
            "AGE_USER",
            "POSTGRES_USER",
            "user",
        ),
        description="PostgreSQL username",
    )

    password: str = Field(
        default="",
        validation_alias=AliasChoices(
            "password",
            "GRAPH_STORE_PASSWORD",
            "AGE_PASSWORD",
            "POSTGRES_PASSWORD",
        ),
        description="PostgreSQL password",
    )

    db_name: str = Field(
        default="postgres",
        validation_alias=AliasChoices(
            "db_name",
            "GRAPH_STORE_DB_NAME",
            "AGE_DATABASE",
            "POSTGRES_DATABASE",
        ),
        description="PostgreSQL database name",
    )

    graph_name: str = Field(
        default="powermem_graph",
        validation_alias=AliasChoices(
            "graph_name",
            "AGE_GRAPH_NAME",
        ),
        description="Name of the AGE graph to use for storing entities and relationships",
    )

    embedding_model_dims: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices(
            "embedding_model_dims",
            "GRAPH_STORE_EMBEDDING_MODEL_DIMS",
            "AGE_EMBEDDING_MODEL_DIMS",
            "POSTGRES_EMBEDDING_MODEL_DIMS",
        ),
        description="Dimension of embedding vectors for entity similarity search",
    )

    max_hops: int = Field(
        default=3,
        validation_alias=AliasChoices(
            "max_hops",
            "GRAPH_STORE_MAX_HOPS",
            "AGE_MAX_HOPS",
        ),
        description="Maximum number of hops for multi-hop graph traversal",
    )

    # LLM and custom prompt fields inherited from BaseGraphStoreConfig
    llm: Optional[Any] = Field(
        default=None,
        description="LLM configuration for entity/relation extraction (overrides global LLM)",
    )
    custom_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt to fetch entities from the given text",
    )
    custom_extract_relations_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt for extracting relations from text",
    )
    custom_update_graph_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt for updating graph memories",
    )
    custom_delete_relations_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt for deleting relations",
    )

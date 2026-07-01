"""
Apache AGE graph storage implementation.

This module provides graph memory storage backed by Apache AGE (A Graph Extension)
for PostgreSQL. It uses openCypher query language via the AGE Python driver.

Apache AGE coexists with pgvector on the same PostgreSQL instance, enabling
both vector search (via PGVectorStore) and graph search (via AGEGraphStore)
without a separate database service.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from powermem.storage.base import GraphStoreBase

logger = logging.getLogger(__name__)


def _escape_cypher_string(value: str) -> str:
    """Escape a string for safe embedding in a Cypher query literal.

    Cypher uses single quotes for string literals. Single quotes inside
    the string are escaped by doubling them. Backslashes are preserved
    literally (Cypher does not interpret backslash escapes in the same
    way as Python).
    """
    if value is None:
        return ""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_filter_properties(filters: Dict[str, Any]) -> str:
    """Build a Cypher property map string from filter dict.

    Example: {"user_id": "alice", "agent_id": "agent1"}
    -> "{user_id: 'alice', agent_id: 'agent1'}"
    """
    parts = []
    for key, value in filters.items():
        if value is not None:
            escaped = _escape_cypher_string(str(value))
            parts.append(f"{key}: '{escaped}'")
    return "{" + ", ".join(parts) + "}"


def _build_filter_conditions(filters: Dict[str, Any], var: str = "n") -> str:
    """Build Cypher WHERE conditions from filter dict.

    Example: {"user_id": "alice", "agent_id": "agent1"}, var="n"
    -> "n.user_id = 'alice' AND n.agent_id = 'agent1'"
    """
    conditions = []
    for key, value in filters.items():
        if value is not None:
            escaped = _escape_cypher_string(str(value))
            conditions.append(f"{var}.{key} = '{escaped}'")
    return " AND ".join(conditions)


class AGEGraphStore(GraphStoreBase):
    """Apache AGE-based graph memory storage implementation.

    Uses openCypher queries via the AGE Python driver to store and retrieve
    entities and relationships. Entities are stored as nodes with labels
    and properties; relationships are stored as edges with types and properties.

    Requires:
        - PostgreSQL with Apache AGE extension installed
        - The `age` Python driver (from drivers/python/ in the AGE source)
        - An LLM and embedder for entity extraction and similarity search
    """

    def __init__(self, config: Any) -> None:
        """Initialize AGE graph memory.

        Args:
            config: Memory configuration containing graph_store, embedder,
                    and llm configs. The graph_store should be an AGEGraphConfig
                    or dict with connection parameters.

        Raises:
            ValueError: If required configuration is missing.
            ImportError: If the age driver is not available.
        """
        self.config = config

        # Extract AGE config from the memory config
        if self.config.graph_store:
            if hasattr(self.config.graph_store, "config"):
                age_config = self.config.graph_store.config
            elif hasattr(self.config.graph_store, "model_dump"):
                age_config = self.config.graph_store
            else:
                age_config = self.config.graph_store
        else:
            age_config = {}

        def get_config_value(key: str, default: Any = None) -> Any:
            if isinstance(age_config, dict):
                return age_config.get(key, default)
            return getattr(age_config, key, default)

        # Connection parameters
        self.host = get_config_value("host", "localhost")
        self.port = get_config_value("port", "5432")
        self.user = get_config_value("user", "postgres")
        self.password = get_config_value("password", "")
        self.db_name = get_config_value("db_name", "postgres")
        self.graph_name = get_config_value("graph_name", "powermem_graph")

        # Graph search parameters
        self.max_hops = get_config_value("max_hops", 3)

        # Embedding dimensions (required for vector similarity on entities)
        embedding_model_dims = get_config_value("embedding_model_dims")
        if embedding_model_dims is None:
            raise ValueError(
                "embedding_model_dims is required for AGE graph operations. "
                "Please configure embedding_model_dims in your AGEGraphConfig."
            )
        self.embedding_dims = embedding_model_dims

        # Initialize embedding model
        from powermem.integrations import EmbedderFactory

        self.embedding_model = EmbedderFactory.create(
            self.config.embedder.provider,
            self.config.embedder.config,
            self.config.vector_store.config,
        )

        # Initialize AGE connection
        self._connect_age()

        # Initialize LLM
        from powermem.integrations import LLMFactory
        from powermem.prompts import GraphPrompts, GraphToolsPrompts

        self.llm_provider = self._get_llm_provider()
        llm_config = self._get_llm_config()
        self.llm = LLMFactory.create(self.llm_provider, llm_config)

        # Initialize prompts
        graph_config = {}
        if self.config.graph_store:
            if hasattr(self.config.graph_store, "model_dump"):
                graph_config = self.config.graph_store.model_dump()
            elif isinstance(self.config.graph_store, dict):
                graph_config = self.config.graph_store

        prompts_config = {"graph_store": graph_config}
        if isinstance(self.config, dict):
            prompts_config.update(self.config)

        self.graph_prompts = GraphPrompts(prompts_config)
        self.graph_tools_prompts = GraphToolsPrompts(prompts_config)

    def _connect_age(self) -> None:
        """Connect to PostgreSQL with AGE extension and create graph if needed."""
        try:
            import age
        except ImportError as e:
            raise ImportError(
                f"The 'age' Python driver is required for AGEGraphStore. "
                f"Install it from the AGE source tree: {e}"
            ) from e

        dsn = f"host={self.host} port={self.port} dbname={self.db_name} user={self.user}"
        if self.password:
            dsn += f" password={self.password}"

        self.ag = age.connect(
            graph=self.graph_name,
            dsn=dsn,
        )
        logger.info(
            "Connected to AGE graph '%s' on %s:%s/%s",
            self.graph_name, self.host, self.port, self.db_name,
        )

    def _get_llm_provider(self) -> str:
        """Get LLM provider from configuration with fallback."""
        gs = self.config.graph_store
        if gs:
            llm_cfg = gs.get("llm") if isinstance(gs, dict) else getattr(gs, "llm", None)
            if llm_cfg:
                provider = llm_cfg.get("provider") if isinstance(llm_cfg, dict) else getattr(llm_cfg, "provider", None)
                if provider:
                    return provider
        if self.config.llm and self.config.llm.provider:
            return self.config.llm.provider
        return "openai"

    def _get_llm_config(self) -> Optional[Any]:
        """Get LLM config from configuration."""
        gs = self.config.graph_store
        if gs:
            llm_cfg = gs.get("llm") if isinstance(gs, dict) else getattr(gs, "llm", None)
            if llm_cfg:
                if isinstance(llm_cfg, dict):
                    return llm_cfg.get("config")
                return getattr(llm_cfg, "config", None)
        if hasattr(self.config.llm, "config"):
            return self.config.llm.config
        return None

    # ----------------------------------------------------------------------
    # Entity / relation extraction (shared logic with OceanBase graph)
    # ----------------------------------------------------------------------

    @staticmethod
    def _coerce_tool_response_to_dict(response: Any) -> Dict[str, Any]:
        """Ensure LLM tool response is a dict."""
        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
        return {}

    def _retrieve_nodes_from_data(
        self, data: str, filters: Dict[str, Any]
    ) -> Dict[str, str]:
        """Extract entities from text using LLM tool calls."""
        _tools = [
            self.graph_tools_prompts.get_extract_entities_tool(),
            self.graph_tools_prompts.get_noop_tool(),
        ]

        search_results = self.llm.generate_response(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are a smart assistant who understands entities and their types in a given text. "
                        f"If user message contains self reference such as 'I', 'me', 'my' etc. "
                        f"then use {filters['user_id']} as the source entity. "
                        f"Extract all the entities from the text. "
                        f"***DO NOT*** answer the question itself if the given text is a question."
                    ),
                },
                {"role": "user", "content": data},
            ],
            tools=_tools,
        )
        search_results = self._coerce_tool_response_to_dict(search_results)

        entity_type_map = {}
        try:
            for tool_call in search_results.get("tool_calls", []):
                if tool_call["name"] != "extract_entities":
                    continue
                for item in tool_call["arguments"]["entities"]:
                    entity_type_map[item["entity"]] = item["entity_type"]
        except Exception as e:
            logger.exception("Error extracting entities: %s", e)

        entity_type_map = {
            k.lower().replace(" ", "_"): v.lower().replace(" ", "_")
            for k, v in entity_type_map.items()
        }
        return entity_type_map

    def _establish_nodes_relations_from_data(
        self, data: str, filters: Dict[str, Any], entity_type_map: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Establish relations among extracted nodes using LLM."""
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"
        if filters.get("run_id"):
            user_identity += f", run_id: {filters['run_id']}"

        system_content = self.graph_prompts.get_system_prompt("extract_relations")
        system_content = system_content.replace("USER_ID", user_identity)

        custom_prompt = None
        gs = self.config.graph_store
        if gs:
            custom_prompt = gs.get("custom_prompt") if isinstance(gs, dict) else getattr(gs, "custom_prompt", None)
        if custom_prompt:
            system_content = system_content.replace(
                "CUSTOM_PROMPT", f"4. {custom_prompt}"
            )

        messages = [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": f"List of entities: {list(entity_type_map.keys())}. \n\nText: {data}",
            },
        ]

        _tools = [
            self.graph_tools_prompts.get_relations_tool(),
            self.graph_tools_prompts.get_noop_tool(),
        ]

        extracted = self.llm.generate_response(messages=messages, tools=_tools)
        extracted = self._coerce_tool_response_to_dict(extracted)

        entities = []
        if extracted.get("tool_calls"):
            first_call = extracted["tool_calls"][0] if extracted["tool_calls"] else {}
            entities = first_call.get("arguments", {}).get("entities", [])

        entities = self._remove_spaces_from_entities(entities)
        return entities

    @staticmethod
    def _remove_spaces_from_entities(entities: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Normalize entity names by replacing spaces with underscores."""
        result = []
        for item in entities:
            normalized = {}
            for key, value in item.items():
                if isinstance(value, str):
                    normalized[key] = value.lower().replace(" ", "_")
                else:
                    normalized[key] = value
            result.append(normalized)
        return result

    # ----------------------------------------------------------------------
    # Cypher execution helpers
    # ----------------------------------------------------------------------

    def _exec_cypher(self, cypher_stmt: str, cols: list = None) -> Any:
        """Execute a Cypher statement and return the cursor."""
        return self.ag.execCypher(cypher_stmt, cols=cols)

    def _commit(self) -> None:
        """Commit the current transaction."""
        self.ag.commit()

    # ----------------------------------------------------------------------
    # GraphStoreBase interface implementation
    # ----------------------------------------------------------------------

    def add(self, data: str, filters: Dict[str, Any]) -> Dict[str, Any]:
        """Add data to the graph.

        Extracts entities and relationships from text via LLM, then creates
        or updates nodes and edges in the AGE graph using Cypher MERGE.

        Args:
            data: The text to add to the graph.
            filters: Dictionary containing user_id, agent_id, run_id.

        Returns:
            Dictionary with deleted_entities and added_entities counts.
        """
        entity_type_map = self._retrieve_nodes_from_data(data, filters)
        to_be_added = self._establish_nodes_relations_from_data(
            data, filters, entity_type_map
        )

        # Search for existing entities to determine deletions
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters
        )
        to_be_deleted = self._get_delete_entities_from_search_output(
            search_output, data, filters
        )

        deleted_count = self._delete_entities(to_be_deleted, filters)
        added_count = self._add_entities(to_be_added, filters, entity_type_map)

        self._commit()

        logger.debug(
            "Deleted entities: %d, Added entities: %d", deleted_count, added_count
        )
        return {
            "deleted_entities": deleted_count,
            "added_entities": added_count,
        }

    def search(
        self, query: str, filters: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for memories and related graph data.

        Extracts entities from the query, finds matching nodes via embedding
        similarity, traverses relationships up to max_hops, and reranks
        results using BM25.

        Args:
            query: Query text to search for.
            filters: Dictionary containing user_id, agent_id, run_id.
            limit: Maximum number of results.

        Returns:
            List of dicts with source, relationship, destination, and score.
        """
        entity_type_map = self._retrieve_nodes_from_data(query, filters)
        search_output = self._search_graph_db(
            node_list=list(entity_type_map.keys()), filters=filters, limit=limit
        )

        if not search_output:
            return []

        # BM25 reranking (same as OceanBase implementation)
        try:
            from rank_bm25 import BM25Okapi
        except ImportError:
            # No BM25 available — return raw results
            return [
                {
                    "source": item["source"],
                    "relationship": item["relationship"],
                    "destination": item["destination"],
                    "score": 0.0,
                }
                for item in search_output[:limit]
            ]

        search_outputs_sequence = []
        for item in search_output:
            combined_text = f"{item['source']} {item['relationship']} {item['destination']}"
            search_outputs_sequence.append(self._tokenize_text(combined_text))

        bm25 = BM25Okapi(search_outputs_sequence)
        tokenized_query = self._tokenize_text(query)
        scores = bm25.get_scores(tokenized_query)
        sorted_indices = sorted(
            range(len(scores)), key=lambda i: scores[i], reverse=True
        )

        results = []
        for idx in sorted_indices[:limit]:
            if idx < len(search_output):
                item = search_output[idx]
                results.append(
                    {
                        "source": item["source"],
                        "relationship": item["relationship"],
                        "destination": item["destination"],
                        "score": float(scores[idx]),
                    }
                )
        return results

    def delete_all(self, filters: Dict[str, Any]) -> None:
        """Delete all graph data for the given filters.

        Uses Cypher MATCH to find all nodes matching the filter properties,
        detaches and deletes them along with their relationships.
        """
        filter_props = _build_filter_properties(filters)
        cypher = (
            f"MATCH (n {filter_props}) "
            f"DETACH DELETE n"
        )
        try:
            self._exec_cypher(cypher)
            self._commit()
            logger.info("Deleted all graph data for filters: %s", filters)
        except Exception as e:
            logger.warning("Error deleting graph data: %s", e)
            self.ag.rollback()

    def get_all(
        self, filters: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, str]]:
        """Retrieve all nodes and relationships from the graph database.

        Args:
            filters: Dictionary containing user_id, agent_id, run_id.
            limit: Maximum number of relationships to retrieve.

        Returns:
            List of dicts with source, relationship, and target.
        """
        filter_props = _build_filter_properties(filters)
        cypher = (
            f"MATCH (n {filter_props})-[r]->(m) "
            f"RETURN n.name AS source, type(r) AS relationship, m.name AS target "
            f"LIMIT {limit}"
        )
        try:
            cursor = self._exec_cypher(cypher, cols=["source", "relationship", "target"])
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning("Error retrieving graph data: %s", e)
            return []

        results = []
        for row in rows:
            source = row[0] if row[0] else ""
            relationship = row[1] if row[1] else ""
            target = row[2] if row[2] else ""
            results.append(
                {
                    "source": str(source),
                    "relationship": str(relationship),
                    "target": str(target),
                }
            )
        logger.info("Retrieved %d relationships", len(results))
        return results

    def reset(self) -> None:
        """Reset the graph by dropping and recreating it."""
        from age import deleteGraph, checkGraphCreated

        try:
            deleteGraph(self.ag.connection, self.graph_name)
        except Exception:
            pass

        checkGraphCreated(self.ag.connection, self.graph_name)
        logger.info("Graph '%s' has been reset", self.graph_name)

    def get_statistics(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get statistics for the graph data."""
        filter_props = _build_filter_properties(filters) if filters else "{}"

        stats = {
            "total_nodes": 0,
            "total_relationships": 0,
            "by_type": {},
        }

        # Count nodes
        try:
            cypher = f"MATCH (n {filter_props}) RETURN count(n) AS cnt"
            cursor = self._exec_cypher(cypher, cols=["cnt"])
            row = cursor.fetchone()
            if row:
                stats["total_nodes"] = int(row[0])
        except Exception as e:
            logger.warning("Error counting nodes: %s", e)

        # Count relationships
        try:
            cypher = f"MATCH (n {filter_props})-[r]->() RETURN count(r) AS cnt"
            cursor = self._exec_cypher(cypher, cols=["cnt"])
            row = cursor.fetchone()
            if row:
                stats["total_relationships"] = int(row[0])
        except Exception as e:
            logger.warning("Error counting relationships: %s", e)

        # Count by entity label
        try:
            cypher = (
                f"MATCH (n {filter_props}) "
                f"RETURN labels(n) AS labels, count(n) AS cnt"
            )
            cursor = self._exec_cypher(cypher, cols=["labels", "cnt"])
            for row in cursor.fetchall():
                labels = row[0]
                count = int(row[1])
                if labels:
                    label_str = ",".join(labels) if isinstance(labels, list) else str(labels)
                    stats["by_type"][label_str] = count
        except Exception as e:
            logger.warning("Error counting by type: %s", e)

        return stats

    def get_unique_users(self) -> List[str]:
        """Get a list of unique user IDs from the graph."""
        try:
            cypher = "MATCH (n) WHERE n.user_id IS NOT NULL RETURN DISTINCT n.user_id AS uid"
            cursor = self._exec_cypher(cypher, cols=["uid"])
            rows = cursor.fetchall()
            return [str(row[0]) for row in rows if row[0] is not None]
        except Exception as e:
            logger.warning("Error getting unique users: %s", e)
            return []

    # ----------------------------------------------------------------------
    # Internal graph operations
    # ----------------------------------------------------------------------

    def _search_graph_db(
        self, node_list: List[str], filters: Dict[str, Any], limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for nodes by embedding similarity and traverse relationships.

        For each node name, generates an embedding, queries AGE for similar
        entities, then performs multi-hop traversal via Cypher.
        """
        result_relations = []
        seen_relations = set()
        filter_props = _build_filter_properties(filters)

        for node_name in node_list:
            # Generate embedding for the node name
            n_embedding = self.embedding_model.embed(node_name)

            # Search for similar entities by name (exact match first, then
            # embedding similarity would require pgvector integration on
            # the entity table — for now, use name matching as the primary
            # lookup since AGE nodes store entity names as properties)
            entities = self._search_node_by_name(node_name, filters)
            if not entities:
                continue

            entity_ids = [e.get("id") for e in entities if e.get("id")]

            # Multi-hop traversal
            multi_hop_results = self._multi_hop_search(entity_ids, filters, limit)
            for relation in multi_hop_results:
                relation_key = (
                    relation.get("source"),
                    relation.get("relationship"),
                    relation.get("destination"),
                )
                if relation_key in seen_relations:
                    continue
                seen_relations.add(relation_key)
                result_relations.append(relation)

        return result_relations

    def _search_node_by_name(
        self, node_name: str, filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for entities by name in the AGE graph."""
        filter_props = _build_filter_properties(filters)
        escaped_name = _escape_cypher_string(node_name)
        cypher = f"MATCH (n {filter_props}) WHERE n.name = '{escaped_name}' RETURN id(n) AS id, n.name AS name LIMIT 10"
        try:
            cursor = self._exec_cypher(cypher, cols=["id", "name"])
            rows = cursor.fetchall()
            return [{"id": row[0], "name": row[1]} for row in rows]
        except Exception as e:
            logger.warning("Error searching node '%s': %s", node_name, e)
            return []

    def _multi_hop_search(
        self, entity_ids: List[Any], filters: Dict[str, Any], limit: int
    ) -> List[Dict[str, Any]]:
        """Perform multi-hop graph traversal using Cypher.

        Uses Cypher's variable-length path pattern (1..N hops) to find
        all reachable relationships from the seed entities.
        """
        if not entity_ids:
            return []

        filter_props = _build_filter_properties(filters)
        max_hops = self.max_hops

        # Build a Cypher query for multi-hop traversal
        # MATCH (n {user_id: 'alice'})-[r*1..3]-(m) RETURN ...
        id_list = ", ".join(str(eid) for eid in entity_ids)
        cypher = (
            f"MATCH (n {filter_props})-[r*1..{max_hops}]-(m) "
            f"WHERE id(n) IN [{id_list}] "
            f"UNWIND r AS rel "
            f"MATCH (a)-[rel]->(b) "
            f"RETURN a.name AS source, type(rel) AS relationship, b.name AS destination "
            f"LIMIT {limit}"
        )

        try:
            cursor = self._exec_cypher(
                cypher, cols=["source", "relationship", "destination"]
            )
            rows = cursor.fetchall()
        except Exception as e:
            logger.warning("Multi-hop search failed, trying single-hop: %s", e)
            # Fallback to single-hop
            cypher = (
                f"MATCH (n {filter_props})-[r]->(m) "
                f"WHERE id(n) IN [{id_list}] "
                f"RETURN n.name AS source, type(r) AS relationship, m.name AS destination "
                f"LIMIT {limit}"
            )
            try:
                cursor = self._exec_cypher(
                    cypher, cols=["source", "relationship", "destination"]
                )
                rows = cursor.fetchall()
            except Exception as e2:
                logger.warning("Single-hop fallback also failed: %s", e2)
                return []

        results = []
        for row in rows:
            source = row[0] if row[0] else ""
            relationship = row[1] if row[1] else ""
            destination = row[2] if row[2] else ""
            results.append(
                {
                    "source": str(source),
                    "relationship": str(relationship),
                    "destination": str(destination),
                }
            )
        return results

    def _get_delete_entities_from_search_output(
        self,
        search_output: List[Dict[str, Any]],
        data: str,
        filters: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Use LLM to determine which existing relationships to delete."""
        from powermem.utils.utils import format_entities

        search_output_string = format_entities(search_output)
        user_identity = f"user_id: {filters['user_id']}"
        if filters.get("agent_id"):
            user_identity += f", agent_id: {filters['agent_id']}"

        system_prompt, user_prompt = self.graph_prompts.get_delete_relations_prompt(
            search_output_string, data, user_identity
        )

        _tools = [self.graph_tools_prompts.get_delete_tool()]

        memory_updates = self.llm.generate_response(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=_tools,
        )
        memory_updates = self._coerce_tool_response_to_dict(memory_updates)

        to_be_deleted = []
        for item in memory_updates.get("tool_calls", []):
            if item.get("name") == "delete_graph_memory":
                to_be_deleted.append(item.get("arguments"))

        to_be_deleted = self._remove_spaces_from_entities(to_be_deleted)
        return to_be_deleted

    def _delete_entities(
        self, to_be_deleted: List[Dict[str, str]], filters: Dict[str, Any]
    ) -> int:
        """Delete specified relationships from the graph.

        Returns the count of deleted relationships.
        """
        if not to_be_deleted:
            return 0

        filter_props = _build_filter_properties(filters)
        deleted_count = 0

        for item in to_be_deleted:
            source = _escape_cypher_string(item.get("source", ""))
            relationship = _escape_cypher_string(item.get("relationship", ""))
            destination = _escape_cypher_string(item.get("destination", ""))

            cypher = (
                f"MATCH (a {filter_props})-[r]->(b {filter_props}) "
                f"WHERE a.name = '{source}' "
                f"AND type(r) = '{relationship}' "
                f"AND b.name = '{destination}' "
                f"DELETE r"
            )
            try:
                self._exec_cypher(cypher)
                deleted_count += 1
            except Exception as e:
                logger.warning("Failed to delete relationship %s: %s", item, e)

        return deleted_count

    def _add_entities(
        self,
        to_be_added: List[Dict[str, str]],
        filters: Dict[str, Any],
        entity_type_map: Dict[str, str],
    ) -> int:
        """Add entities and relationships to the graph using Cypher MERGE.

        Returns the count of added relationships.
        """
        if not to_be_added:
            return 0

        filter_props = _build_filter_properties(filters)
        added_count = 0

        for item in to_be_added:
            source = item.get("source", "")
            destination = item.get("destination", "")
            relationship = item.get("relationship", "")

            if not source or not destination:
                continue

            source_escaped = _escape_cypher_string(source)
            dest_escaped = _escape_cypher_string(destination)
            rel_escaped = _escape_cypher_string(relationship)

            source_label = entity_type_map.get(source, "Entity")
            dest_label = entity_type_map.get(destination, "Entity")

            # Sanitize labels (Cypher labels can't have spaces or special chars)
            source_label = re.sub(r"[^a-zA-Z0-9_]", "", source_label) or "Entity"
            dest_label = re.sub(r"[^a-zA-Z0-9_]", "", dest_label) or "Entity"

            # MERGE source node
            cypher = (
                f"MERGE (a:{source_label} {filter_props} {{name: '{source_escaped}'}})"
            )
            try:
                self._exec_cypher(cypher)
            except Exception as e:
                logger.warning("Failed to merge source node '%s': %s", source, e)
                continue

            # MERGE destination node
            cypher = (
                f"MERGE (b:{dest_label} {filter_props} {{name: '{dest_escaped}'}})"
            )
            try:
                self._exec_cypher(cypher)
            except Exception as e:
                logger.warning("Failed to merge dest node '%s': %s", destination, e)
                continue

            # MERGE relationship
            cypher = (
                f"MATCH (a:{source_label} {filter_props} {{name: '{source_escaped}'}}), "
                f"(b:{dest_label} {filter_props} {{name: '{dest_escaped}'}}) "
                f"MERGE (a)-[r:`{rel_escaped}`]->(b)"
            )
            try:
                self._exec_cypher(cypher)
                added_count += 1
            except Exception as e:
                logger.warning("Failed to merge relationship '%s': %s", relationship, e)

        return added_count

    @staticmethod
    def _tokenize_text(text: str) -> List[str]:
        """Tokenize text for BM25 scoring.

        Uses jieba for Chinese text if available, otherwise simple split.
        """
        try:
            import jieba
            tokens = list(jieba.cut(text.lower()))
            return [t for t in tokens if t.strip()]
        except ImportError:
            return text.lower().split()

    def close(self) -> None:
        """Close the AGE connection."""
        if hasattr(self, "ag") and self.ag.connection:
            try:
                self.ag.close()
            except Exception:
                pass

    def __del__(self):
        """Clean up connection on deletion."""
        self.close()

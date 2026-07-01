"""Tests for AGEGraphStore and AGEGraphConfig."""

import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure a clean 'age' module slot — individual tests will patch it as needed
sys.modules.pop("age", None)


class TestAGEGraphConfig(unittest.TestCase):
    """Tests for AGEGraphConfig configuration."""

    def test_config_registers_as_provider(self):
        """AGEGraphConfig auto-registers with the 'age' provider name."""
        from powermem.storage.config.base import BaseGraphStoreConfig
        from powermem.storage.config.age import AGEGraphConfig

        self.assertTrue(BaseGraphStoreConfig.has_provider("age"))
        cls = BaseGraphStoreConfig.get_provider_config_cls("age")
        self.assertIs(cls, AGEGraphConfig)

    def test_config_class_path(self):
        """AGEGraphConfig registers the correct class path."""
        from powermem.storage.config.base import BaseGraphStoreConfig

        path = BaseGraphStoreConfig.get_provider_class_path("age")
        self.assertEqual(path, "powermem.storage.age.age_graph.AGEGraphStore")

    def test_config_defaults(self):
        """AGEGraphConfig has sensible PostgreSQL defaults."""
        from powermem.storage.config.age import AGEGraphConfig

        config = AGEGraphConfig(
            embedding_model_dims=384,
            password="secret",
        )
        self.assertEqual(config.host, "localhost")
        self.assertEqual(config.port, "5432")
        self.assertEqual(config.user, "postgres")
        self.assertEqual(config.db_name, "postgres")
        self.assertEqual(config.graph_name, "powermem_graph")
        self.assertEqual(config.max_hops, 3)
        self.assertEqual(config.embedding_model_dims, 384)

    def test_config_port_coercion(self):
        """AGEGraphConfig coerces integer port to string."""
        from powermem.storage.config.age import AGEGraphConfig

        config = AGEGraphConfig(
            embedding_model_dims=384,
            port=5432,
            password="secret",
        )
        self.assertEqual(config.port, "5432")
        self.assertIsInstance(config.port, str)

    def test_config_custom_graph_name(self):
        """AGEGraphConfig accepts a custom graph name."""
        from powermem.storage.config.age import AGEGraphConfig

        config = AGEGraphConfig(
            embedding_model_dims=384,
            graph_name="my_custom_graph",
            password="secret",
        )
        self.assertEqual(config.graph_name, "my_custom_graph")


class TestAGEGraphStoreHelpers(unittest.TestCase):
    """Tests for AGEGraphStore static helper methods."""

    def test_escape_cypher_string_simple(self):
        from powermem.storage.age.age_graph import _escape_cypher_string
        self.assertEqual(_escape_cypher_string("hello"), "hello")

    def test_escape_cypher_string_single_quote(self):
        from powermem.storage.age.age_graph import _escape_cypher_string
        self.assertEqual(_escape_cypher_string("it's"), "it\\'s")

    def test_escape_cypher_string_backslash(self):
        from powermem.storage.age.age_graph import _escape_cypher_string
        self.assertEqual(_escape_cypher_string("path\\to"), "path\\\\to")

    def test_escape_cypher_string_none(self):
        from powermem.storage.age.age_graph import _escape_cypher_string
        self.assertEqual(_escape_cypher_string(None), "")

    def test_build_filter_properties_basic(self):
        from powermem.storage.age.age_graph import _build_filter_properties
        result = _build_filter_properties({"user_id": "alice", "agent_id": "agent1"})
        self.assertIn("user_id: 'alice'", result)
        self.assertIn("agent_id: 'agent1'", result)
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))

    def test_build_filter_properties_empty(self):
        from powermem.storage.age.age_graph import _build_filter_properties
        self.assertEqual(_build_filter_properties({}), "{}")

    def test_build_filter_properties_none_value(self):
        from powermem.storage.age.age_graph import _build_filter_properties
        result = _build_filter_properties({"user_id": "alice", "agent_id": None})
        self.assertIn("user_id: 'alice'", result)
        self.assertNotIn("agent_id", result)

    def test_build_filter_conditions_basic(self):
        from powermem.storage.age.age_graph import _build_filter_conditions
        result = _build_filter_conditions({"user_id": "alice"}, var="n")
        self.assertEqual(result, "n.user_id = 'alice'")

    def test_build_filter_conditions_multiple(self):
        from powermem.storage.age.age_graph import _build_filter_conditions
        result = _build_filter_conditions(
            {"user_id": "alice", "agent_id": "agent1"}, var="m"
        )
        self.assertIn("m.user_id = 'alice'", result)
        self.assertIn("m.agent_id = 'agent1'", result)
        self.assertIn("AND", result)


class TestAGEGraphStoreEntityNormalization(unittest.TestCase):
    """Tests for entity normalization."""

    def test_remove_spaces_basic(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        entities = [
            {"source": "New York", "destination": "Los Angeles", "relationship": "connected to"},
        ]
        result = AGEGraphStore._remove_spaces_from_entities(entities)
        self.assertEqual(result[0]["source"], "new_york")
        self.assertEqual(result[0]["destination"], "los_angeles")
        self.assertEqual(result[0]["relationship"], "connected_to")

    def test_remove_spaces_empty(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        self.assertEqual(AGEGraphStore._remove_spaces_from_entities([]), [])

    def test_remove_spaces_preserves_non_string(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        entities = [{"source": "entity1", "count": 5}]
        result = AGEGraphStore._remove_spaces_from_entities(entities)
        self.assertEqual(result[0]["count"], 5)


class TestAGEGraphStoreCoerceResponse(unittest.TestCase):
    """Tests for LLM response coercion."""

    def test_coerce_dict_passthrough(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        d = {"tool_calls": [{"name": "test"}]}
        self.assertEqual(AGEGraphStore._coerce_tool_response_to_dict(d), d)

    def test_coerce_json_string(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        s = '{"tool_calls": [{"name": "test"}]}'
        result = AGEGraphStore._coerce_tool_response_to_dict(s)
        self.assertEqual(result["tool_calls"][0]["name"], "test")

    def test_coerce_invalid_string_returns_empty(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        self.assertEqual(AGEGraphStore._coerce_tool_response_to_dict("not json"), {})

    def test_coerce_none_returns_empty(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        self.assertEqual(AGEGraphStore._coerce_tool_response_to_dict(None), {})


class TestAGEGraphStoreTokenize(unittest.TestCase):
    """Tests for text tokenization."""

    def test_tokenize_simple(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        with patch.dict('sys.modules', {'jieba': None}):
            result = AGEGraphStore._tokenize_text("hello world foo")
            self.assertEqual(result, ["hello", "world", "foo"])

    def test_tokenize_lowercases(self):
        from powermem.storage.age.age_graph import AGEGraphStore
        with patch.dict('sys.modules', {'jieba': None}):
            result = AGEGraphStore._tokenize_text("Hello WORLD")
            self.assertEqual(result, ["hello", "world"])


class TestAGEGraphStoreFactoryRegistration(unittest.TestCase):
    """Tests that AGE is discoverable via GraphStoreFactory."""

    def test_factory_lists_age_provider(self):
        from powermem.storage.factory import GraphStoreFactory
        providers = GraphStoreFactory.get_supported_providers()
        self.assertIn("age", providers)


def _make_mock_config(**overrides):
    """Create a mock config object for AGEGraphStore.__init__.

    Uses a plain dict for graph_store so the get_config_value() helper
    in age_graph.py picks up values via dict.get() instead of returning
    MagicMock auto-attributes.
    """
    graph_store_dict = {
        "host": overrides.get("host", "localhost"),
        "port": overrides.get("port", "5432"),
        "user": overrides.get("user", "postgres"),
        "password": overrides.get("password", "secret"),
        "db_name": overrides.get("db_name", "postgres"),
        "graph_name": overrides.get("graph_name", "powermem_graph"),
        "max_hops": overrides.get("max_hops", 3),
        "embedding_model_dims": overrides.get("embedding_model_dims", 384),
        "llm": None,
        "custom_prompt": None,
    }

    config = MagicMock()
    # graph_store is a plain dict — age_graph.py checks isinstance(dict)
    config.graph_store = graph_store_dict

    config.embedder = MagicMock()
    config.embedder.provider = "openai"
    config.embedder.config = MagicMock()
    config.vector_store = MagicMock()
    config.vector_store.config = MagicMock()
    config.llm = MagicMock()
    config.llm.provider = "openai"
    config.llm.config = MagicMock()
    return config


class TestAGEGraphStoreInit(unittest.TestCase):
    """Tests for AGEGraphStore initialization."""

    @patch.dict('sys.modules', {'age': MagicMock()})
    @patch("powermem.integrations.EmbedderFactory")
    @patch("powermem.integrations.LLMFactory")
    def test_init_connects_to_age(self, mock_llm_factory, mock_embedder_factory):
        """AGEGraphStore.__init__ connects to AGE with correct DSN."""
        mock_age_mod = sys.modules['age']
        mock_ag = MagicMock()
        mock_age_mod.connect.return_value = mock_ag
        mock_embedder_factory.create.return_value = MagicMock()
        mock_llm_factory.create.return_value = MagicMock()

        from powermem.storage.age.age_graph import AGEGraphStore
        config = _make_mock_config()
        store = AGEGraphStore(config)

        mock_age_mod.connect.assert_called_once()
        call_kwargs = mock_age_mod.connect.call_args
        dsn_arg = call_kwargs.kwargs.get("dsn") or call_kwargs[1].get("dsn")
        self.assertIn("host=localhost", dsn_arg)
        self.assertIn("port=5432", dsn_arg)
        self.assertIn("dbname=postgres", dsn_arg)
        graph_arg = call_kwargs.kwargs.get("graph") or call_kwargs[1].get("graph")
        self.assertEqual(graph_arg, "powermem_graph")

    @patch.dict('sys.modules', {'age': MagicMock()})
    @patch("powermem.integrations.EmbedderFactory")
    @patch("powermem.integrations.LLMFactory")
    def test_init_raises_without_embedding_dims(self, mock_llm_factory, mock_embedder_factory):
        """AGEGraphStore.__init__ raises ValueError if embedding_model_dims is None."""
        from powermem.storage.age.age_graph import AGEGraphStore

        config = _make_mock_config(embedding_model_dims=None)

        with self.assertRaises(ValueError) as ctx:
            AGEGraphStore(config)
        self.assertIn("embedding_model_dims", str(ctx.exception))

    @patch("powermem.integrations.EmbedderFactory")
    @patch("powermem.integrations.LLMFactory")
    def test_init_raises_without_age_driver(self, mock_llm_factory, mock_embedder_factory):
        """AGEGraphStore.__init__ raises ImportError if age driver is missing."""
        original = sys.modules.pop("age", None)
        # Insert None to simulate the module not being importable
        sys.modules["age"] = None
        try:
            from powermem.storage.age.age_graph import AGEGraphStore
            config = _make_mock_config()
            with self.assertRaises((ImportError, TypeError)):
                AGEGraphStore(config)
        finally:
            sys.modules.pop("age", None)
            if original is not None:
                sys.modules["age"] = original


def _make_store():
    """Create an AGEGraphStore instance with all dependencies mocked.

    Uses __new__ to bypass __init__, then sets required attributes manually.
    """
    from powermem.storage.age.age_graph import AGEGraphStore

    store = AGEGraphStore.__new__(AGEGraphStore)
    store.ag = MagicMock()
    store.graph_name = "test_graph"
    store.max_hops = 3
    store.embedding_dims = 384
    store.llm = MagicMock()
    store.embedding_model = MagicMock()
    store.config = MagicMock()
    store.config.graph_store = MagicMock()
    store.config.graph_store.custom_prompt = None
    store.graph_prompts = MagicMock()
    store.graph_tools_prompts = MagicMock()
    return store


class TestAGEGraphStoreOperations(unittest.TestCase):
    """Tests for AGEGraphStore graph operations."""

    def test_delete_all_executes_cypher(self):
        """delete_all executes DETACH DELETE on matching nodes."""
        store = _make_store()
        store.delete_all({"user_id": "alice"})

        calls = store.ag.execCypher.call_args_list
        self.assertTrue(len(calls) > 0)
        cypher_str = str(calls[0])
        self.assertIn("DETACH DELETE", cypher_str)
        self.assertIn("alice", cypher_str)

    def test_delete_all_rollback_on_error(self):
        """delete_all rolls back on exception."""
        store = _make_store()
        store.ag.execCypher.side_effect = Exception("Cypher error")

        store.delete_all({"user_id": "alice"})
        store.ag.rollback.assert_called_once()

    def test_get_all_returns_relationships(self):
        """get_all returns source/relationship/target from Cypher results."""
        store = _make_store()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("alice", "knows", "bob"),
            ("alice", "works_with", "charlie"),
        ]
        store.ag.execCypher.return_value = mock_cursor

        results = store.get_all({"user_id": "alice"}, limit=10)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["source"], "alice")
        self.assertEqual(results[0]["relationship"], "knows")
        self.assertEqual(results[0]["target"], "bob")

    def test_get_all_empty_results(self):
        """get_all returns empty list when no data."""
        store = _make_store()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        store.ag.execCypher.return_value = mock_cursor

        results = store.get_all({"user_id": "alice"})
        self.assertEqual(results, [])

    def test_get_all_handles_error(self):
        """get_all returns empty list on Cypher error."""
        store = _make_store()
        store.ag.execCypher.side_effect = Exception("Cypher error")

        results = store.get_all({"user_id": "alice"})
        self.assertEqual(results, [])

    def test_get_unique_users_returns_list(self):
        """get_unique_users returns distinct user IDs."""
        store = _make_store()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ("alice",),
            ("bob",),
            (None,),
        ]
        store.ag.execCypher.return_value = mock_cursor

        users = store.get_unique_users()
        self.assertEqual(users, ["alice", "bob"])

    def test_get_unique_users_handles_error(self):
        """get_unique_users returns empty list on error."""
        store = _make_store()
        store.ag.execCypher.side_effect = Exception("error")
        self.assertEqual(store.get_unique_users(), [])

    def test_get_statistics_returns_counts(self):
        """get_statistics returns node and relationship counts."""
        store = _make_store()

        cursor1 = MagicMock()
        cursor1.fetchone.return_value = (42,)
        cursor2 = MagicMock()
        cursor2.fetchone.return_value = (15,)
        cursor3 = MagicMock()
        cursor3.fetchall.return_value = [(["Person"], 30), (["Organization"], 12)]

        store.ag.execCypher.side_effect = [cursor1, cursor2, cursor3]

        stats = store.get_statistics({"user_id": "alice"})

        self.assertEqual(stats["total_nodes"], 42)
        self.assertEqual(stats["total_relationships"], 15)
        self.assertIn("Person", stats["by_type"])
        self.assertEqual(stats["by_type"]["Person"], 30)

    def test_commit_calls_ag_commit(self):
        """_commit() calls ag.commit()."""
        store = _make_store()
        store._commit()
        store.ag.commit.assert_called_once()

    def test_close_closes_connection(self):
        """close() calls ag.close()."""
        store = _make_store()
        store.close()
        store.ag.close.assert_called_once()


class TestAGEGraphStoreSearchNode(unittest.TestCase):
    """Tests for _search_node_by_name."""

    def test_search_node_by_name_returns_entities(self):
        """_search_node_by_name returns matching entities."""
        store = _make_store()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            (1, "alice"),
            (2, "alice"),
        ]
        store.ag.execCypher.return_value = mock_cursor

        results = store._search_node_by_name("alice", {"user_id": "alice"})
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], 1)
        self.assertEqual(results[0]["name"], "alice")

    def test_search_node_by_name_handles_error(self):
        """_search_node_by_name returns empty list on error."""
        store = _make_store()
        store.ag.execCypher.side_effect = Exception("error")

        results = store._search_node_by_name("alice", {"user_id": "alice"})
        self.assertEqual(results, [])


class TestAGEGraphStoreDeleteEntities(unittest.TestCase):
    """Tests for _delete_entities."""

    def test_delete_entities_empty_returns_zero(self):
        """_delete_entities returns 0 for empty list."""
        store = _make_store()
        count = store._delete_entities([], {"user_id": "alice"})
        self.assertEqual(count, 0)

    def test_delete_entities_executes_cypher(self):
        """_delete_entities executes DELETE Cypher for each relationship."""
        store = _make_store()
        to_delete = [
            {"source": "alice", "relationship": "knows", "destination": "bob"},
        ]
        count = store._delete_entities(to_delete, {"user_id": "alice"})
        self.assertEqual(count, 1)
        store.ag.execCypher.assert_called_once()
        cypher_str = str(store.ag.execCypher.call_args)
        self.assertIn("DELETE", cypher_str)

    def test_delete_entities_handles_error(self):
        """_delete_entities continues on error and returns partial count."""
        store = _make_store()
        store.ag.execCypher.side_effect = Exception("error")

        to_delete = [
            {"source": "alice", "relationship": "knows", "destination": "bob"},
        ]
        count = store._delete_entities(to_delete, {"user_id": "alice"})
        self.assertEqual(count, 0)


class TestAGEGraphStoreAddEntities(unittest.TestCase):
    """Tests for _add_entities."""

    def test_add_entities_empty_returns_zero(self):
        """_add_entities returns 0 for empty list."""
        store = _make_store()
        count = store._add_entities([], {"user_id": "alice"}, {})
        self.assertEqual(count, 0)

    def test_add_entities_executes_merger(self):
        """_add_entities executes MERGE Cypher for nodes and relationships."""
        store = _make_store()
        to_add = [
            {"source": "alice", "relationship": "knows", "destination": "bob"},
        ]
        entity_type_map = {"alice": "Person", "bob": "Person"}

        count = store._add_entities(to_add, {"user_id": "alice"}, entity_type_map)
        self.assertEqual(count, 1)
        # Should have called execCypher at least 3 times (source MERGE, dest MERGE, rel MERGE)
        self.assertGreaterEqual(store.ag.execCypher.call_count, 3)

    def test_add_entities_skips_missing_source(self):
        """_add_entities skips entries with missing source."""
        store = _make_store()
        to_add = [
            {"source": "", "relationship": "knows", "destination": "bob"},
        ]
        count = store._add_entities(to_add, {"user_id": "alice"}, {})
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()

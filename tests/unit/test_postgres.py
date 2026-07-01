import importlib
import sys
import unittest
import uuid
from unittest.mock import MagicMock, patch

# Mock psycopg and psycopg2 modules before importing PostgresVectorStore
# Make psycopg3 unavailable to force fallback to psycopg2
sys.modules['psycopg'] = None
sys.modules['psycopg_pool'] = None
sys.modules['psycopg.types.json'] = None

# Set up psycopg2 mocks
mock_psycopg2_extras = MagicMock()
mock_psycopg2_pool = MagicMock()
mock_psycopg2_sql = MagicMock()

# Set up mock functions
mock_execute_values = MagicMock()
mock_json = MagicMock()
mock_threaded_connection_pool = MagicMock()

# Configure mocks
mock_psycopg2_extras.execute_values = mock_execute_values
mock_psycopg2_extras.Json = mock_json
mock_psycopg2_pool.ThreadedConnectionPool = mock_threaded_connection_pool

# Note: We don't mock psycopg2 modules in sys.modules here to avoid import issues
# Instead, we'll patch them in individual tests

# Import PGVectorStore - we'll patch its dependencies in tests
try:
    from powermem.storage.pgvector.pgvector import PGVectorStore
except ImportError:
    # If import fails due to missing dependencies, we'll handle it in tests
    PGVectorStore = None


class TestPGVector(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_conn.cursor.return_value = self.mock_cursor
        
        # Mock connection pool
        self.mock_pool_psycopg2 = MagicMock()
        self.mock_pool_psycopg2.getconn.return_value = self.mock_conn

        self.mock_pool_psycopg = MagicMock()
        self.mock_pool_psycopg.connection.return_value = self.mock_conn
        
        self.mock_get_cursor = MagicMock()
        self.mock_get_cursor.return_value = self.mock_cursor

        # Mock connection string
        self.connection_string = "postgresql://user:pass@host:5432/db"
        
        # Test data
        self.test_vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        self.test_payloads = [{"key": "value1"}, {"key": "value2"}]
        self.test_ids = [1, 2]  # Use integer IDs instead of UUID strings

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    def test_init_with_individual_params_psycopg3(self, mock_psycopg_pool):
        """Test initialization with individual parameters using psycopg3."""
        # Mock psycopg3 to be available
        mock_psycopg_pool.return_value = self.mock_pool_psycopg
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
        )

        mock_psycopg_pool.assert_called_once_with(
            conninfo="postgresql://test_user:test_pass@localhost:5432/test_db",
            min_size=1,
            max_size=4,
            open=True,
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    def test_init_with_individual_params_psycopg2(self, mock_pcycopg2_pool):
        """Test initialization with individual parameters using psycopg2."""
        mock_pcycopg2_pool.return_value = self.mock_pool_psycopg2
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
        )
        
        mock_pcycopg2_pool.assert_called_once_with(
            minconn=1,
            maxconn=4,
            dsn="postgresql://test_user:test_pass@localhost:5432/test_db",
        )

        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_psycopg3_with_explicit_pool(self, mock_get_cursor, mock_connection_pool):
        """
        Test collection creation with psycopg3 when an explicit psycopg_pool.ConnectionPool is provided.
        This ensures that PostgresVectorStore uses the provided pool and still performs collection creation logic.
        """
        # Set up a real (mocked) psycopg_pool.ConnectionPool instance
        explicit_pool = MagicMock(name="ExplicitPsycopgPool")
        # The patch for ConnectionPool should not be used in this case, but we patch it for isolation
        mock_connection_pool.return_value = MagicMock(name="ShouldNotBeUsed")

        # Configure the _get_cursor mock to return our mock cursor as a context manager
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        # Simulate no existing collections in the database
        self.mock_cursor.fetchall.return_value = []

        # Pass the explicit pool to PostgresVectorStore
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            connection_pool=explicit_pool
        )

        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        mock_connection_pool.assert_not_called()


        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)

        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        # Ensure the pool used is the explicit one
        self.assertIs(pgvector.connection_pool, explicit_pool)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_psycopg2_with_explicit_pool(self, mock_get_cursor, mock_connection_pool):
        """
        Test collection creation with psycopg2 when an explicit psycopg2 ThreadedConnectionPool is provided.
        This ensures that PostgresVectorStore uses the provided pool and still performs collection creation logic.
        """
        # Set up a real (mocked) psycopg2 ThreadedConnectionPool instance
        explicit_pool = MagicMock(name="ExplicitPsycopg2Pool")
        # The patch for ConnectionPool should not be used in this case, but we patch it for isolation
        mock_connection_pool.return_value = MagicMock(name="ShouldNotBeUsed")

        # Configure the _get_cursor mock to return our mock cursor as a context manager
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        # Simulate no existing collections in the database
        self.mock_cursor.fetchall.return_value = []

        # Pass the explicit pool to PostgresVectorStore
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            connection_pool=explicit_pool
        )

        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        mock_connection_pool.assert_not_called()

        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)

        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        # Ensure the pool used is the explicit one
        self.assertIs(pgvector.connection_pool, explicit_pool)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify vector extension and table creation
        self.mock_cursor.execute.assert_any_call("CREATE EXTENSION IF NOT EXISTS vector")
        table_creation_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "CREATE TABLE IF NOT EXISTS test_collection" in str(call)]
        self.assertTrue(len(table_creation_calls) > 0)
        
        # Verify pgvector instance properties
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch('powermem.storage.pgvector.pgvector.generate_snowflake_id')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_insert_psycopg3(self, mock_get_cursor, mock_generate_snowflake_id, mock_connection_pool):
        """Test vector insertion with psycopg3."""
        # Set up mock pool and cursor
        mock_connection_pool.return_value = self.mock_pool_psycopg
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        # Mock Snowflake ID generation to return test IDs
        mock_generate_snowflake_id.side_effect = self.test_ids
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        result_ids = pgvector.insert(self.test_vectors, self.test_payloads)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify insert query was executed (psycopg3 uses executemany)
        insert_calls = [call for call in self.mock_cursor.executemany.call_args_list 
                       if "INSERT INTO test_collection" in str(call)]
        self.assertTrue(len(insert_calls) > 0)
        
        # Verify data format (should include IDs, vector, payload, and fulltext_content - 4 elements per tuple)
        call_args = self.mock_cursor.executemany.call_args
        data_arg = call_args[0][1]
        self.assertEqual(len(data_arg), 2)  # 2 vectors
        # Each tuple should have 4 elements: (id, vector, payload, fulltext_content)
        self.assertEqual(len(data_arg[0]), 4)
        # Verify returned IDs match the generated Snowflake IDs
        self.assertEqual(result_ids, self.test_ids)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch('powermem.storage.pgvector.pgvector.generate_snowflake_id')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_insert_psycopg2(self, mock_get_cursor, mock_generate_snowflake_id, mock_connection_pool):
        """
        Test vector insertion with psycopg2.
        This test ensures that PostgresVectorStore.insert uses psycopg2.extras.execute_values for batch inserts
        and that the data passed to execute_values is correctly formatted.
        """
        # --- Setup mocks for psycopg2 and its submodules ---
        # Use the global mock_execute_values from the top of the file
        mock_pool = MagicMock()

        # Mock psycopg2.extras with execute_values
        mock_psycopg2_extras = MagicMock()
        mock_psycopg2_extras.execute_values = mock_execute_values

        mock_psycopg2_pool = MagicMock()
        mock_psycopg2_pool.ThreadedConnectionPool = mock_pool

        # Mock psycopg2 root module
        mock_psycopg2 = MagicMock()
        mock_psycopg2.extras = mock_psycopg2_extras
        mock_psycopg2.pool = mock_psycopg2_pool

        # Mock psycopg2.sql module
        mock_psycopg2_sql = MagicMock()
        
        # Patch sys.modules so that imports in PostgresVectorStore use our mocks
        with patch.dict('sys.modules', {
            'psycopg': None,  # Ensure psycopg3 is not available
            'psycopg_pool': None,
            'psycopg.types.json': None,
            'psycopg2': mock_psycopg2,
            'psycopg2.extras': mock_psycopg2_extras,
            'psycopg2.pool': mock_psycopg2_pool,
            'psycopg2.sql': mock_psycopg2_sql
        }):
            # Force reload of PostgresVectorStore to pick up the mocked modules
            if 'powermem.storage.pgvector.pgvector' in sys.modules:
                importlib.reload(sys.modules['powermem.storage.pgvector.pgvector'])
                # Re-apply the mock after reload
                sys.modules['powermem.storage.pgvector.pgvector'].generate_snowflake_id = mock_generate_snowflake_id

            mock_connection_pool.return_value = self.mock_pool_psycopg
            mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
            mock_get_cursor.return_value.__exit__.return_value = None
            self.mock_cursor.fetchall.return_value = []

            # Mock Snowflake ID generation to return test IDs
            mock_generate_snowflake_id.side_effect = self.test_ids

            pgvector = PGVectorStore(
                dbname="test_db",
                collection_name="test_collection",
                embedding_model_dims=3,
                user="test_user",
                password="test_pass",
                host="localhost",
                port=5432,
                diskann=False,
                hnsw=False,
                minconn=1,
                maxconn=4
            )
            
            result_ids = pgvector.insert(self.test_vectors, self.test_payloads)

            mock_get_cursor.assert_called()
            mock_execute_values.assert_called_once()
            call_args = mock_execute_values.call_args

            self.assertIn("INSERT INTO test_collection", call_args[0][1])
            # Note: Current implementation generates IDs upfront, so no RETURNING id clause
            # The data argument should be a list of tuples, one per vector (with IDs, vector, payload, fulltext_content)
            data_arg = call_args[0][2]
            self.assertEqual(len(data_arg), 2)  # 2 vectors
            # Each tuple should have 4 elements: (id, vector, payload, fulltext_content)
            self.assertEqual(len(data_arg[0]), 4)
            # Verify returned IDs match the generated Snowflake IDs
            self.assertEqual(result_ids, self.test_ids)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results — distance is converted to similarity: max(1 - d/2, 0)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)  # 1 - 0.1/2
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertAlmostEqual(results[1].score, 0.9)   # 1 - 0.2/2

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool

        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )

        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2)

        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()

        # Verify search query was executed
        search_calls = [call for call in self.mock_cursor.execute.call_args_list
                       if "SELECT id, vector <=" in str(call)]
        self.assertTrue(len(search_calls) > 0)

        # Verify results — distance is converted to similarity: max(1 - d/2, 0)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)  # 1 - 0.1/2
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertAlmostEqual(results[1].score, 0.9)   # 1 - 0.2/2

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_delete_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test delete with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_delete_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test delete with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DELETE FROM test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_update_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test update with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_update_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test update with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        updated_vector = [0.5, 0.6, 0.7]
        updated_payload = {"updated": "value"}
        
        pgvector.update(self.test_ids[0], vector=updated_vector, payload=updated_payload)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify update queries were executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_get_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test get with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"})
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_get_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test get with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"})
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        result = pgvector.get(self.test_ids[0])
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify get query was executed
        get_calls = [call for call in self.mock_cursor.execute.call_args_list 
                    if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(get_calls) > 0)
        
        # Verify result
        self.assertIsNotNone(result)
        self.assertEqual(result.id, self.test_ids[0])
        self.assertEqual(result.payload, {"key": "value1"})

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_cols_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list_cols with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [("test_collection",), ("other_table",)]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        collections = pgvector.list_cols()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_cols_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list_cols with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [("test_collection",), ("other_table",)]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        collections = pgvector.list_cols()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list_cols query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name FROM information_schema.tables" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(collections, ["test_collection", "other_table"])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_delete_col_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test delete_col with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete_col()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_delete_col_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test delete_col with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.delete_col()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify delete_col query was executed
        delete_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "DROP TABLE IF EXISTS test_collection" in str(call)]
        self.assertTrue(len(delete_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_col_info_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test col_info with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = ("test_collection", 100, "1 MB")
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        info = pgvector.col_info()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_col_info_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test col_info with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = ("test_collection", 100, "1 MB")
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        info = pgvector.col_info()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify col_info query was executed
        info_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT table_name" in str(call)]
        self.assertTrue(len(info_calls) > 0)
        
        # Verify result
        self.assertEqual(info["name"], "test_collection")
        self.assertEqual(info["count"], 100)
        self.assertEqual(info["size"], "1 MB")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(len(results), 2)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[1].id, self.test_ids[1])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify result
        self.assertEqual(len(results), 2)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[1].id, self.test_ids[1])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed with filters
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed with filters
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")
        self.assertEqual(results[0].payload["run_id"], "run1")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_single_filter_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with single filter using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed with single filter
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_single_filter_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with single filter using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"user_id": "alice"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=filters)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed with single filter
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_no_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test search with no filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed without WHERE clause
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertAlmostEqual(results[1].score, 0.9)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_with_no_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test search with no filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], 0.1, {"key": "value1"}),
            (self.test_ids[1], 0.2, {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )
        
        results = pgvector.search("test query", [0.1, 0.2, 0.3], limit=2, filters=None)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify search query was executed without WHERE clause
        search_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "SELECT id, vector <=" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(search_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertAlmostEqual(results[0].score, 0.95)
        self.assertEqual(results[1].id, self.test_ids[1])
        self.assertAlmostEqual(results[1].score, 0.9)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice", "agent_id": "agent1"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed with filters
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice", "agent_id": "agent1"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice", "agent_id": "agent1"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed with filters
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].payload["user_id"], "alice")
        self.assertEqual(results[0].payload["agent_id"], "agent1")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_single_filter_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with single filter using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed with single filter
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_single_filter_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with single filter using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"user_id": "alice"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        filters = {"user_id": "alice"}
        results = pgvector.list(filters=filters, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed with single filter
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 1)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[0].payload["user_id"], "alice")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_no_filters_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test list with no filters using psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed without WHERE clause
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[1].id, self.test_ids[1])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_list_with_no_filters_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test list with no filters using psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = [
            (self.test_ids[0], [0.1, 0.2, 0.3], {"key": "value1"}),
            (self.test_ids[1], [0.4, 0.5, 0.6], {"key": "value2"}),
        ]
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        results = pgvector.list(filters=None, limit=2)
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify list query was executed without WHERE clause
        list_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "SELECT id, vector, payload" in str(call) and "WHERE" not in str(call)]
        self.assertTrue(len(list_calls) > 0)
        
        # Verify results
        self.assertEqual(len(results), 2)  # Returns list of OutputData objects
        self.assertEqual(results[0].id, self.test_ids[0])
        self.assertEqual(results[1].id, self.test_ids[1])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_reset_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test reset with psycopg3."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.reset()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_reset_psycopg2(self, mock_get_cursor, mock_connection_pool):
        """Test reset with psycopg2."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        pgvector.reset()
        
        # Verify the _get_cursor context manager was called
        mock_get_cursor.assert_called()
        
        # Verify reset operations were executed
        drop_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "DROP TABLE IF EXISTS" in str(call)]
        create_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "CREATE TABLE IF NOT EXISTS" in str(call)]
        self.assertTrue(len(drop_calls) > 0)
        self.assertTrue(len(create_calls) > 0)

    # Enhanced Tests for JSON Serialization
    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    @patch('powermem.storage.pgvector.pgvector.Json')
    def test_update_payload_psycopg3_json_handling(self, mock_json, mock_get_cursor, mock_connection_pool):
        """Test that psycopg3 update uses Json() wrapper for payload serialization."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_payload = {"test": "data", "number": 42}
        pgvector.update("test-id-123", payload=test_payload)
        
        # Verify Json() wrapper was used for psycopg3
        mock_json.assert_called_once_with(test_payload)
        
        # Verify the update query was executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection SET payload" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    @patch('powermem.storage.pgvector.pgvector.Json')
    def test_update_payload_psycopg2_json_handling(self, mock_json, mock_get_cursor, mock_connection_pool):
        """Test that psycopg2 update uses psycopg2.extras.Json() wrapper for payload serialization."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_payload = {"test": "data", "number": 42}
        pgvector.update("test-id-123", payload=test_payload)
        
        # Verify psycopg2.extras.Json() wrapper was used
        mock_json.assert_called_once_with(test_payload)
        
        # Verify the update query was executed
        update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                       if "UPDATE test_collection SET payload" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    def test_transaction_rollback_on_error_psycopg2(self, mock_connection_pool):
        """Test that psycopg2 properly rolls back transactions on errors."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool

        # Set up mock connection that will raise an error only on delete
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn

        # Only raise exception on the delete operation, not during setup
        def execute_side_effect(*args, **kwargs):
            if args and "DELETE FROM" in str(args[0]):
                raise Exception("Database error")
            return MagicMock()
        mock_cursor.execute.side_effect = execute_side_effect
        self.mock_cursor.fetchall.return_value = []  # No existing collections initially

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )

        # Attempt an operation that will fail
        with self.assertRaises(Exception) as context:
            pgvector.delete("test-id")

        self.assertIn("Database error", str(context.exception))
        # Verify rollback was called
        mock_conn.rollback.assert_called()
        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_with(mock_conn)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    def test_commit_on_success_psycopg2(self, mock_connection_pool):
        """Test that psycopg2 properly commits transactions on success."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Set up mock connection for successful operation
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool.getconn.return_value = mock_conn
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections initially
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Perform an operation that requires commit
        pgvector.delete("test-id")
        
        # Verify commit was called
        mock_conn.commit.assert_called()
        # Verify connection was returned to pool
        mock_pool.putconn.assert_called_with(mock_conn)

    # Enhanced Tests for Error Handling
    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_pool_connection_error_handling(self, mock_get_cursor, mock_connection_pool):
        """Test handling of connection pool errors."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool

        # Use a flag to only raise the exception after PostgresVectorStore is initialized
        raise_on_search = {'active': False}
        def get_cursor_side_effect(*args, **kwargs):
            if raise_on_search['active']:
                raise Exception("Connection pool exhausted")
            return self.mock_cursor

        mock_get_cursor.side_effect = get_cursor_side_effect
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            hybrid_search=False,
        )

        # Activate the exception for search only
        raise_on_search['active'] = True
        with self.assertRaises(Exception) as context:
            pgvector.search("test query", [0.1, 0.2, 0.3])

        self.assertIn("Connection pool exhausted", str(context.exception))

    # Enhanced Tests for Vector and Payload Update Combinations
    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_update_vector_only_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test updating only vector without payload."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_vector = [0.1, 0.2, 0.3]
        pgvector.update("test-id", vector=test_vector)
        
        # Verify only vector update query was executed (not payload)
        vector_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "UPDATE test_collection SET vector" in str(call) and "payload" not in str(call)]
        payload_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                               if "UPDATE test_collection SET payload" in str(call)]
        
        self.assertTrue(len(vector_update_calls) > 0)
        self.assertEqual(len(payload_update_calls), 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_update_both_vector_and_payload_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test updating both vector and payload."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        test_vector = [0.1, 0.2, 0.3]
        test_payload = {"updated": True}
        pgvector.update("test-id", vector=test_vector, payload=test_payload)
        
        # Verify both vector and payload update queries were executed
        vector_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                              if "UPDATE test_collection SET vector" in str(call)]
        payload_update_calls = [call for call in self.mock_cursor.execute.call_args_list 
                               if "UPDATE test_collection SET payload" in str(call)]
        
        self.assertTrue(len(vector_update_calls) > 0)
        self.assertTrue(len(payload_update_calls) > 0)

    # Enhanced Tests for Connection String Handling
    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    def test_connection_string_with_sslmode_psycopg3(self, mock_connection_pool):
        """Test connection string handling with SSL mode."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        connection_string = "postgresql://user:pass@localhost:5432/db"
        
        pgvector = PGVectorStore(
            dbname="test_db",  # Will be overridden by connection_string
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            minconn=1,
            maxconn=4,
            sslmode="require",
            connection_string=connection_string
        )
        
        # Verify ConnectionPool was called with the connection string including sslmode
        expected_conn_string = f"{connection_string} sslmode=require"
        mock_connection_pool.assert_called_with(
            conninfo=expected_conn_string,
            min_size=1,
            max_size=4,
            open=True
        )
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    # Enhanced Test for Index Creation with DiskANN
    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_with_diskann_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with DiskANN index."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        # Mock vectorscale extension as available
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        self.mock_cursor.fetchone.return_value = ("vectorscale",)  # Extension exists
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=True,  # Enable DiskANN
            hnsw=False,
            minconn=1,
            maxconn=4
        )
        
        # Verify DiskANN index creation query was executed
        diskann_calls = [call for call in self.mock_cursor.execute.call_args_list 
                        if "USING diskann" in str(call)]
        self.assertTrue(len(diskann_calls) > 0)
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)
        

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_with_hnsw_psycopg3(self, mock_get_cursor, mock_connection_pool):
        """Test collection creation with HNSW index."""
        # Set up mock pool and cursor
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        
        # Configure the _get_cursor mock to return our mock cursor
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        
        self.mock_cursor.fetchall.return_value = []  # No existing collections
        
        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=True,  # Enable HNSW
            minconn=1,
            maxconn=4
        )
        
        # Verify HNSW index creation query was executed
        hnsw_calls = [call for call in self.mock_cursor.execute.call_args_list 
                     if "USING hnsw" in str(call)]
        self.assertTrue(len(hnsw_calls) > 0)
        self.assertEqual(pgvector.collection_name, "test_collection")
        self.assertEqual(pgvector.embedding_model_dims, 3)

    # Enhanced Test for Pool Cleanup
    def test_pool_cleanup_psycopg3(self):
        """Test that psycopg3 pool is properly closed on object deletion."""
        with patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3), \
             patch('powermem.storage.pgvector.pgvector.ConnectionPool') as mock_connection_pool:
            
            mock_pool = MagicMock()
            mock_connection_pool.return_value = mock_pool
            self.mock_cursor.fetchall.return_value = []  # No existing collections
            
            pgvector = PGVectorStore(
                dbname="test_db",
                collection_name="test_collection",
                embedding_model_dims=3,
                user="test_user",
                password="test_pass",
                host="localhost",
                port=5432,
                diskann=False,
                hnsw=False,
                minconn=1,
                maxconn=4
            )
            
            # Trigger __del__ method
            del pgvector
            
            # Verify pool.close() was called
            mock_pool.close.assert_called()

    def test_pool_cleanup_psycopg2(self):
        """Test that psycopg2 pool is properly closed on object deletion."""
        with patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 2), \
             patch('powermem.storage.pgvector.pgvector.ConnectionPool') as mock_connection_pool:
            
            mock_pool = MagicMock()
            mock_connection_pool.return_value = mock_pool
            self.mock_cursor.fetchall.return_value = []  # No existing collections
            
            pgvector = PGVectorStore(
                dbname="test_db",
                collection_name="test_collection",
                embedding_model_dims=3,
                user="test_user",
                password="test_pass",
                host="localhost",
                port=5432,
                diskann=False,
                hnsw=False,
                minconn=1,
                maxconn=4
            )
            
            # Trigger __del__ method
            del pgvector
            
            # Verify pool.closeall() was called
            mock_pool.closeall.assert_called()

    # ========================
    # Hybrid Search Tests
    # ========================

    def test_extract_fulltext_content_from_data_key(self):
        """_extract_fulltext_content pulls text from 'data' key."""
        payload = {"data": "hello world", "other": "ignored"}
        result = PGVectorStore._extract_fulltext_content(payload)
        self.assertEqual(result, "hello world")

    def test_extract_fulltext_content_from_fulltext_content_key(self):
        """_extract_fulltext_content prefers 'fulltext_content' key."""
        payload = {"fulltext_content": "priority text", "data": "fallback"}
        result = PGVectorStore._extract_fulltext_content(payload)
        self.assertEqual(result, "priority text")

    def test_extract_fulltext_content_from_content_key(self):
        """_extract_fulltext_content falls back to 'content' key."""
        payload = {"content": "content text"}
        result = PGVectorStore._extract_fulltext_content(payload)
        self.assertEqual(result, "content text")

    def test_extract_fulltext_content_empty_payload(self):
        """_extract_fulltext_content returns empty string for empty payload."""
        self.assertEqual(PGVectorStore._extract_fulltext_content({}), "")
        self.assertEqual(PGVectorStore._extract_fulltext_content(None), "")

    def test_extract_fulltext_content_ignores_non_string(self):
        """_extract_fulltext_content ignores non-string values."""
        payload = {"data": 123, "content": "real text"}
        result = PGVectorStore._extract_fulltext_content(payload)
        self.assertEqual(result, "real text")

    def test_sanitize_fts_query_simple_words(self):
        """_sanitize_fts_query wraps words in single quotes joined by &."""
        result = PGVectorStore._sanitize_fts_query("hello world")
        self.assertEqual(result, "'hello' & 'world'")

    def test_sanitize_fts_query_empty(self):
        """_sanitize_fts_query returns empty for blank input."""
        self.assertEqual(PGVectorStore._sanitize_fts_query(""), "")
        self.assertEqual(PGVectorStore._sanitize_fts_query("   "), "")
        self.assertEqual(PGVectorStore._sanitize_fts_query(None), "")

    def test_sanitize_fts_query_strips_punctuation(self):
        """_sanitize_fts_query strips punctuation and extracts word tokens."""
        result = PGVectorStore._sanitize_fts_query("hello, world! foo.bar")
        self.assertEqual(result, "'hello' & 'world' & 'foo' & 'bar'")

    def test_sanitize_fts_query_handles_unicode(self):
        """_sanitize_fts_query handles unicode word characters."""
        result = PGVectorStore._sanitize_fts_query("你好 world")
        self.assertIn("'你好'", result)
        self.assertIn("'world'", result)

    def test_sanitize_fts_query_no_word_tokens(self):
        """_sanitize_fts_query returns empty when input has no word tokens."""
        result = PGVectorStore._sanitize_fts_query("!!! ??? @@@")
        self.assertEqual(result, "")

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_get_returns_none_when_not_found(self, mock_get_cursor, mock_connection_pool):
        """get() returns None when no row matches the ID."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []
        self.mock_cursor.fetchone.return_value = None

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )
        result = pgvector.get(999)
        self.assertIsNone(result)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_with_dotted_key_filter(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search uses string_to_array filter for dotted keys."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, '{"data": "match"}', 0.7),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._fulltext_search("hello", limit=5, filters={"metadata.type": "doc"})
        self.assertEqual(len(results), 1)
        # Verify the dotted-key filter SQL was used
        dotted_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "string_to_array" in str(call)]
        self.assertTrue(len(dotted_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_returns_empty_for_punctuation_only(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search returns empty list when query sanitizes to empty."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._fulltext_search("!!! ???", limit=5)
        self.assertEqual(results, [])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_hybrid_search_init_defaults(self, mock_get_cursor, mock_connection_pool):
        """PGVectorStore initializes with hybrid_search enabled by default."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )
        self.assertTrue(pgvector.hybrid_search)
        self.assertEqual(pgvector.fulltext_language, "english")
        self.assertAlmostEqual(pgvector.vector_weight, 0.5)
        self.assertAlmostEqual(pgvector.fts_weight, 0.5)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_hybrid_search_init_disabled(self, mock_get_cursor, mock_connection_pool):
        """PGVectorStore can disable hybrid search."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            hybrid_search=False,
        )
        self.assertFalse(pgvector.hybrid_search)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_creates_fts_gin_index(self, mock_get_cursor, mock_connection_pool):
        """create_col creates a GIN index for fulltext search when hybrid is enabled."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            hybrid_search=True,
        )

        gin_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "USING GIN" in str(call) and "to_tsvector" in str(call)]
        self.assertTrue(len(gin_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_no_gin_index_when_hybrid_disabled(self, mock_get_cursor, mock_connection_pool):
        """create_col does not create GIN index when hybrid_search is False."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            hybrid_search=False,
        )

        gin_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "USING GIN" in str(call)]
        self.assertEqual(len(gin_calls), 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_insert_includes_fulltext_content(self, mock_get_cursor, mock_connection_pool):
        """insert writes fulltext_content extracted from payload alongside vector."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        vectors = [[0.1, 0.2, 0.3]]
        payloads = [{"data": "hello world"}]
        pgvector.insert(vectors, payloads)

        # Verify INSERT includes fulltext_content column
        insert_calls = [call for call in self.mock_cursor.executemany.call_args_list
                        if "INSERT INTO test_collection" in str(call)]
        self.assertTrue(len(insert_calls) > 0)
        sql_str = str(insert_calls[0])
        self.assertIn("fulltext_content", sql_str)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_update_includes_fulltext_content(self, mock_get_cursor, mock_connection_pool):
        """update writes fulltext_content when payload is provided."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        pgvector.update(1, payload={"data": "updated text"})

        update_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "UPDATE test_collection" in str(call) and "fulltext_content" in str(call)]
        self.assertTrue(len(update_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_executes_tsquery(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search executes a query with ts_rank and to_tsquery."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, '{"data": "match"}', 0.5),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._fulltext_search("hello world", limit=5)

        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call) and "ts_rank" in str(call)]
        self.assertTrue(len(fts_calls) > 0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, 1)
        self.assertIn("_fts_score", results[0].payload)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_empty_query_returns_empty(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search returns empty list for empty query."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._fulltext_search("", limit=5)
        self.assertEqual(results, [])
        results = pgvector._fulltext_search("   ", limit=5)
        self.assertEqual(results, [])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_with_filters(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search applies JSONB filters alongside FTS."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, '{"data": "match", "user_id": "alice"}', 0.8),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._fulltext_search("hello", limit=5, filters={"user_id": "alice"})

        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call) and "payload->>" in str(call)]
        self.assertTrue(len(fts_calls) > 0)
        self.assertEqual(len(results), 1)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_fts_mode_calls_fulltext_only(self, mock_get_cursor, mock_connection_pool):
        """search with retrieval_mode='fts' only calls _fulltext_search."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, '{"data": "match"}', 0.9),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector.search("hello", [0.1, 0.2, 0.3], limit=5, retrieval_mode="fts")

        # Should contain to_tsquery calls (FTS) but not vector distance calls
        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call)]
        vector_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "vector <=> " in str(call)]
        self.assertTrue(len(fts_calls) > 0)
        self.assertEqual(len(vector_calls), 0)
        self.assertEqual(len(results), 1)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_vector_mode_calls_vector_only(self, mock_get_cursor, mock_connection_pool):
        """search with retrieval_mode='vector' only calls _vector_search."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, 0.1, {"data": "match"}),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector.search("hello", [0.1, 0.2, 0.3], limit=5, retrieval_mode="vector")

        vector_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "vector <=> " in str(call)]
        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call)]
        self.assertTrue(len(vector_calls) > 0)
        self.assertEqual(len(fts_calls), 0)
        self.assertEqual(len(results), 1)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_hybrid_disabled_falls_back_to_vector(self, mock_get_cursor, mock_connection_pool):
        """search with hybrid_search=False falls back to vector-only even with query."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, 0.1, {"data": "match"}),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            hybrid_search=False,
        )

        results = pgvector.search("hello", [0.1, 0.2, 0.3], limit=5)

        vector_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "vector <=> " in str(call)]
        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call)]
        self.assertTrue(len(vector_calls) > 0)
        self.assertEqual(len(fts_calls), 0)

    def test_rrf_fusion_combines_vector_and_fts(self):
        """_rrf_fusion merges vector and FTS results, boosting overlapping docs."""
        from powermem.storage.base import OutputData

        # Create a bare instance without calling __init__ (avoids DB deps)
        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        vector_results = [
            OutputData(id=1, score=0.9, payload={"data": "doc1"}),
            OutputData(id=2, score=0.8, payload={"data": "doc2"}),
        ]
        fts_results = [
            OutputData(id=2, score=0.5, payload={"data": "doc2", "_fts_score": 0.5}),
            OutputData(id=3, score=0.3, payload={"data": "doc3", "_fts_score": 0.3}),
        ]

        fused = pgvector._rrf_fusion(vector_results, fts_results, limit=10, k=60)

        # 3 unique docs
        self.assertEqual(len(fused), 3)
        # Doc 2 appears in both, should have higher RRF score than docs in only one
        ids_to_scores = {r.id: r.score for r in fused}
        self.assertGreater(ids_to_scores[2], ids_to_scores[1])
        self.assertGreater(ids_to_scores[2], ids_to_scores[3])
        # Fusion metadata present
        for r in fused:
            self.assertIn("_fusion_score", r.payload)
            self.assertIn("_fusion_info", r.payload)
            self.assertEqual(r.payload["_fusion_info"]["fusion_method"], "rrf")

    def test_rrf_fusion_respects_limit(self):
        """_rrf_fusion truncates results to limit."""
        from powermem.storage.base import OutputData

        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        vector_results = [OutputData(id=i, score=0.9, payload={}) for i in range(10)]
        fts_results = [OutputData(id=i, score=0.5, payload={}) for i in range(10, 20)]

        fused = pgvector._rrf_fusion(vector_results, fts_results, limit=5, k=60)
        self.assertEqual(len(fused), 5)

    def test_rrf_fusion_empty_inputs(self):
        """_rrf_fusion returns empty list for empty inputs."""
        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        fused = pgvector._rrf_fusion([], [], limit=5, k=60)
        self.assertEqual(fused, [])

    def test_rrf_fusion_vector_only(self):
        """_rrf_fusion handles vector-only results."""
        from powermem.storage.base import OutputData

        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        vector_results = [
            OutputData(id=1, score=0.9, payload={}),
            OutputData(id=2, score=0.8, payload={}),
        ]
        fused = pgvector._rrf_fusion(vector_results, [], limit=5, k=60)
        self.assertEqual(len(fused), 2)

    def test_rrf_fusion_fts_only(self):
        """_rrf_fusion handles FTS-only results."""
        from powermem.storage.base import OutputData

        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        fts_results = [
            OutputData(id=1, score=0.5, payload={"_fts_score": 0.5}),
        ]
        fused = pgvector._rrf_fusion([], fts_results, limit=5, k=60)
        self.assertEqual(len(fused), 1)

    def test_rrf_fusion_custom_weights(self):
        """_rrf_fusion applies custom weights."""
        from powermem.storage.base import OutputData

        pgvector = PGVectorStore.__new__(PGVectorStore)
        pgvector.vector_weight = 0.5
        pgvector.fts_weight = 0.5

        vector_results = [OutputData(id=1, score=0.9, payload={})]
        fts_results = [OutputData(id=2, score=0.5, payload={"_fts_score": 0.5})]

        # Heavy vector weight
        fused_v = pgvector._rrf_fusion(
            vector_results, fts_results, limit=2, k=60,
            vector_weight=0.9, fts_weight=0.1,
        )
        # Heavy FTS weight
        fused_f = pgvector._rrf_fusion(
            vector_results, fts_results, limit=2, k=60,
            vector_weight=0.1, fts_weight=0.9,
        )

        # With heavy vector weight, doc 1 (from vector) should rank first
        self.assertEqual(fused_v[0].id, 1)
        # With heavy FTS weight, doc 2 (from FTS) should rank first
        self.assertEqual(fused_f[0].id, 2)

    def test_weighted_fusion_normalizes_scores(self):
        """_weighted_fusion min-max normalizes scores before weighting."""
        from powermem.storage.base import OutputData

        vector_results = [
            OutputData(id=1, score=1.0, payload={}),
            OutputData(id=2, score=0.0, payload={}),
        ]
        fts_results = [
            OutputData(id=1, score=0.8, payload={"_fts_score": 0.8}),
        ]

        fused = PGVectorStore._weighted_fusion(
            vector_results, fts_results, limit=5,
            vector_weight=0.5, fts_weight=0.5,
        )

        self.assertEqual(len(fused), 2)
        # Doc 1 appears in both, should rank higher
        self.assertEqual(fused[0].id, 1)
        self.assertIn("_fusion_info", fused[0].payload)
        self.assertEqual(fused[0].payload["_fusion_info"]["fusion_method"], "weighted")

    def test_weighted_fusion_single_source(self):
        """_weighted_fusion handles only vector results."""
        from powermem.storage.base import OutputData

        vector_results = [
            OutputData(id=1, score=0.9, payload={}),
            OutputData(id=2, score=0.5, payload={}),
        ]
        fused = PGVectorStore._weighted_fusion(
            vector_results, [], limit=5,
            vector_weight=0.5, fts_weight=0.5,
        )
        self.assertEqual(len(fused), 2)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_hybrid_mode_fuses_results(self, mock_get_cursor, mock_connection_pool):
        """search in hybrid mode (auto with both query and vectors) fuses results."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        # First call: list_cols returns empty (during __init__)
        # Subsequent calls alternate: vector search then FTS search
        # Each search does fetchall, so we need to return different data per call
        call_count = [0]

        def fetchall_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                # list_cols during __init__
                return []
            elif call_count[0] == 2:
                # vector search result
                return [(1, 0.1, {"data": "doc1"})]
            else:
                # FTS search result
                return [(2, '{"data": "doc2", "_fts_score": 0.5}', 0.5)]

        self.mock_cursor.fetchall.side_effect = fetchall_side_effect

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector.search("hello", [0.1, 0.2, 0.3], limit=5, retrieval_mode="hybrid")

        # Should have results from both paths fused
        self.assertGreater(len(results), 0)
        # Verify both vector and FTS queries were executed
        vector_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "vector <=> " in str(call)]
        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call)]
        self.assertTrue(len(vector_calls) > 0)
        self.assertTrue(len(fts_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_threshold_filters_results(self, mock_get_cursor, mock_connection_pool):
        """search with threshold filters out low-quality results."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        call_count = [0]

        def fetchall_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return []
            elif call_count[0] == 2:
                return [(1, 0.1, {"data": "doc1"})]
            else:
                return [(2, '{"data": "doc2"}', 0.5)]

        self.mock_cursor.fetchall.side_effect = fetchall_side_effect

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        # With a very high threshold, results should be filtered out
        results = pgvector.search(
            "hello", [0.1, 0.2, 0.3], limit=5,
            retrieval_mode="hybrid", threshold=0.99,
        )
        # With threshold 0.99, quality scores (0.0-1.0) below 0.99 are filtered
        for r in results:
            self.assertGreaterEqual(r.payload.get("_quality_score", r.score), 0.99)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_weighted_fusion_mode(self, mock_get_cursor, mock_connection_pool):
        """search with fusion='weighted' uses _weighted_fusion."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        call_count = [0]

        def fetchall_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return []
            elif call_count[0] == 2:
                return [(1, 0.1, {"data": "doc1"})]
            else:
                return [(2, '{"data": "doc2"}', 0.5)]

        self.mock_cursor.fetchall.side_effect = fetchall_side_effect

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector.search(
            "hello", [0.1, 0.2, 0.3], limit=5,
            retrieval_mode="hybrid", fusion="weighted",
        )

        self.assertGreater(len(results), 0)
        for r in results:
            if "_fusion_info" in r.payload:
                self.assertEqual(
                    r.payload["_fusion_info"]["fusion_method"], "weighted"
                )

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_no_query_falls_back_to_vector(self, mock_get_cursor, mock_connection_pool):
        """search with empty query but valid vectors falls back to vector search."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, 0.1, {"data": "doc1"}),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector.search("", [0.1, 0.2, 0.3], limit=5)

        vector_calls = [call for call in self.mock_cursor.execute.call_args_list
                        if "vector <=> " in str(call)]
        fts_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "to_tsquery" in str(call)]
        self.assertTrue(len(vector_calls) > 0)
        self.assertEqual(len(fts_calls), 0)
        self.assertEqual(len(results), 1)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_search_candidate_limit_passed_to_subsearches(self, mock_get_cursor, mock_connection_pool):
        """search passes candidate_limit as search_limit to sub-searches."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None

        call_count = [0]

        def fetchall_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return []
            elif call_count[0] == 2:
                return [(1, 0.1, {"data": "doc1"})]
            else:
                return [(2, '{"data": "doc2"}', 0.5)]

        self.mock_cursor.fetchall.side_effect = fetchall_side_effect

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        pgvector.search(
            "hello", [0.1, 0.2, 0.3], limit=3,
            retrieval_mode="hybrid", candidate_limit=10,
        )

        # Verify LIMIT 10 appears in both vector and FTS queries
        all_sql = [str(call) for call in self.mock_cursor.execute.call_args_list]
        vector_sql = [s for s in all_sql if "vector <=> " in s]
        fts_sql = [s for s in all_sql if "to_tsquery" in s]
        if vector_sql:
            self.assertIn("10", vector_sql[0])
        if fts_sql:
            self.assertIn("10", fts_sql[0])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_vector_search_returns_similarity_in_payload(self, mock_get_cursor, mock_connection_pool):
        """_vector_search stores _vector_similarity in payload metadata."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = [
            (1, 0.1, {"data": "doc1"}),
        ]

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        results = pgvector._vector_search([0.1, 0.2, 0.3], limit=5)
        self.assertEqual(len(results), 1)
        self.assertIn("_vector_similarity", results[0].payload)
        # distance 0.1 -> similarity = max(1 - 0.1/2, 0) = 0.95
        self.assertAlmostEqual(results[0].payload["_vector_similarity"], 0.95)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_create_col_adds_fulltext_content_column_for_existing_tables(self, mock_get_cursor, mock_connection_pool):
        """create_col migrates existing tables by adding fulltext_content column."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        # Verify migration DO $$ block for fulltext_content column
        migration_calls = [call for call in self.mock_cursor.execute.call_args_list
                           if "fulltext_content" in str(call) and "DO $$" in str(call)]
        self.assertTrue(len(migration_calls) > 0)

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_fulltext_search_graceful_failure(self, mock_get_cursor, mock_connection_pool):
        """_fulltext_search returns empty list on database error instead of raising."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
        )

        # Set execute to raise for the FTS search (after __init__ completed)
        self.mock_cursor.execute.side_effect = Exception("FTS query failed")
        results = pgvector._fulltext_search("hello", limit=5)
        self.assertEqual(results, [])

    @patch('powermem.storage.pgvector.pgvector.PSYCOPG_VERSION', 3)
    @patch('powermem.storage.pgvector.pgvector.ConnectionPool')
    @patch.object(PGVectorStore, '_get_cursor')
    def test_custom_fulltext_language(self, mock_get_cursor, mock_connection_pool):
        """PGVectorStore accepts and uses a custom fulltext_language."""
        mock_pool = MagicMock()
        mock_connection_pool.return_value = mock_pool
        mock_get_cursor.return_value.__enter__.return_value = self.mock_cursor
        mock_get_cursor.return_value.__exit__.return_value = None
        self.mock_cursor.fetchall.return_value = []

        pgvector = PGVectorStore(
            dbname="test_db",
            collection_name="test_collection",
            embedding_model_dims=3,
            user="test_user",
            password="test_pass",
            host="localhost",
            port=5432,
            diskann=False,
            hnsw=False,
            fulltext_language="chinese",
        )
        self.assertEqual(pgvector.fulltext_language, "chinese")

        # Verify GIN index uses the specified language
        gin_calls = [call for call in self.mock_cursor.execute.call_args_list
                     if "USING GIN" in str(call)]
        self.assertTrue(len(gin_calls) > 0)
        self.assertIn("chinese", str(gin_calls[0]))

    def tearDown(self):
        """Clean up after each test."""
        pass

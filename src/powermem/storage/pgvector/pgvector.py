import json
import logging
import math
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

from powermem.storage.base import VectorStoreBase, OutputData
from powermem.utils.utils import generate_snowflake_id

# Try to import psycopg (psycopg3) first, then fall back to psycopg2
try:
    from psycopg.types.json import Json
    from psycopg_pool import ConnectionPool
    PSYCOPG_VERSION = 3
    logger = logging.getLogger(__name__)
    logger.info("Using psycopg (psycopg3) with ConnectionPool for PostgreSQL connections")
except ImportError:
    try:
        from psycopg2.extras import Json, execute_values
        from psycopg2.pool import ThreadedConnectionPool as ConnectionPool
        PSYCOPG_VERSION = 2
        logger = logging.getLogger(__name__)
        logger.info("Using psycopg2 with ThreadedConnectionPool for PostgreSQL connections")
    except ImportError:
        raise ImportError(
            "Neither 'psycopg' nor 'psycopg2' library is available. "
            "Please install one of them using 'pip install psycopg[pool]' or 'pip install psycopg2'"
        )

logger = logging.getLogger(__name__)

class PGVectorStore(VectorStoreBase):
    def __init__(
        self,
        dbname,
        collection_name,
        embedding_model_dims,
        user,
        password,
        host,
        port,
        diskann,
        hnsw,
        minconn=1,
        maxconn=5,
        sslmode=None,
        connection_string=None,
        connection_pool=None,
        hybrid_search: bool = True,
        fulltext_language: str = "english",
        vector_weight: float = 0.5,
        fts_weight: float = 0.5,
    ):
        """
        Initialize the PGVector database.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str, optional): Database host
            port (int, optional): Database port
            diskann (bool, optional): Use DiskANN for faster search
            hnsw (bool, optional): Use HNSW for faster search
            minconn (int): Minimum number of connections to keep in the connection pool
            maxconn (int): Maximum number of connections allowed in the connection pool
            sslmode (str, optional): SSL mode for PostgreSQL connection (e.g., 'require', 'prefer', 'disable')
            connection_string (str, optional): PostgreSQL connection string (overrides individual connection parameters)
            connection_pool (Any, optional): psycopg2 connection pool object (overrides connection string and individual parameters)
        """
        self.collection_name = collection_name
        self.use_diskann = diskann
        self.use_hnsw = hnsw
        self.embedding_model_dims = embedding_model_dims
        self.connection_pool = None
        self.hybrid_search = hybrid_search
        self.fulltext_language = fulltext_language
        self.vector_weight = vector_weight
        self.fts_weight = fts_weight
        self._lock = threading.Lock()

        # Connection setup with priority: connection_pool > connection_string > individual parameters
        if connection_pool is not None:
            # Use provided connection pool
            self.connection_pool = connection_pool
        elif connection_string:
            if sslmode:
                # Append sslmode to connection string if provided
                if 'sslmode=' in connection_string:
                    # Replace existing sslmode
                    import re
                    connection_string = re.sub(r'sslmode=[^ ]*', f'sslmode={sslmode}', connection_string)
                else:
                    # Add sslmode to connection string
                    connection_string = f"{connection_string} sslmode={sslmode}"
        else:
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            if sslmode:
                connection_string = f"{connection_string} sslmode={sslmode}"
        
        if self.connection_pool is None:
            if PSYCOPG_VERSION == 3:
                # psycopg3 ConnectionPool
                self.connection_pool = ConnectionPool(conninfo=connection_string, min_size=minconn, max_size=maxconn, open=True)
            else:
                # psycopg2 ThreadedConnectionPool
                self.connection_pool = ConnectionPool(minconn=minconn, maxconn=maxconn, dsn=connection_string)

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col()

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        """
        Unified context manager to get a cursor from the appropriate pool.
        Auto-commits or rolls back based on exception, and returns the connection to the pool.
        """
        if PSYCOPG_VERSION == 3:
            # psycopg3 auto-manages commit/rollback and pool return
            with self.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    try:
                        yield cur
                        if commit:
                            conn.commit()
                    except Exception:
                        conn.rollback()
                        logger.error("Error in cursor context (psycopg3)", exc_info=True)
                        raise
        else:
            # psycopg2 manual getconn/putconn
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            try:
                yield cur
                if commit:
                    conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.error(f"Error occurred: {exc}")
                raise exc
            finally:
                cur.close()
                self.connection_pool.putconn(conn)

    def create_col(self, name=None, vector_size=None, distance=None) -> None:
        """
        Create a new collection (table in PostgreSQL).
        Will also initialize vector search index if specified.
        """
        with self._get_cursor(commit=True) as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    id BIGINT PRIMARY KEY,
                    vector vector({self.embedding_model_dims}),
                    payload JSONB,
                    fulltext_content TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            
            # Add created_at column if it doesn't exist (for existing tables)
            cur.execute(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='{self.collection_name}' AND column_name='created_at') THEN
                        ALTER TABLE {self.collection_name} ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
                    END IF;
                END $$;
                """
            )

            # Add fulltext_content column if it doesn't exist (for existing tables)
            cur.execute(
                f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                   WHERE table_name='{self.collection_name}' AND column_name='fulltext_content') THEN
                        ALTER TABLE {self.collection_name} ADD COLUMN fulltext_content TEXT DEFAULT '';
                    END IF;
                END $$;
                """
            )

            # Create GIN index for fulltext search if hybrid search is enabled
            if self.hybrid_search:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_fts_idx
                    ON {self.collection_name}
                    USING GIN (to_tsvector('{self.fulltext_language}', fulltext_content));
                    """
                )

            if self.use_diskann and self.embedding_model_dims < 2000:
                cur.execute("SELECT * FROM pg_extension WHERE extname = 'vectorscale'")
                if cur.fetchone():
                    # Create DiskANN index if extension is installed for faster search
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS {self.collection_name}_diskann_idx
                        ON {self.collection_name}
                        USING diskann (vector);
                        """
                    )
            elif self.use_hnsw:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_hnsw_idx
                    ON {self.collection_name}
                    USING hnsw (vector vector_cosine_ops)
                    """
                )

    def insert(self, vectors: list[list[float]], payloads=None, ids=None) -> list[int]:
        """
        Insert vectors into the collection.

        Args:
            vectors: List of vectors to insert
            payloads: List of payload dictionaries
            ids: Deprecated parameter (ignored), IDs are now generated using Snowflake algorithm

        Returns:
            List[int]: List of generated Snowflake IDs
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        if not vectors:
            return []

        # Generate Snowflake IDs for each vector
        generated_ids = [generate_snowflake_id() for _ in range(len(vectors))]

        json_payloads = [json.dumps(payload) for payload in payloads]
        # Extract fulltext content from payloads for FTS indexing
        fulltext_contents = [self._extract_fulltext_content(payload) for payload in payloads]
        # Include the generated Snowflake ID and fulltext content in the data
        data = [(vector_id, vector, payload, ft_content)
                for vector_id, vector, payload, ft_content
                in zip(generated_ids, vectors, json_payloads, fulltext_contents)]
        
        if PSYCOPG_VERSION == 3:
            with self._get_cursor(commit=True) as cur:
                # Insert with explicit IDs and fulltext content
                cur.executemany(
                    f"INSERT INTO {self.collection_name} (id, vector, payload, fulltext_content) VALUES (%s, %s, %s, %s)",
                    data,
                )
        else:
            with self._get_cursor(commit=True) as cur:
                # psycopg2: use execute_values
                execute_values(
                    cur,
                    f"INSERT INTO {self.collection_name} (id, vector, payload, fulltext_content) VALUES %s",
                    data,
                )
        
        logger.debug(f"Successfully inserted {len(vectors)} vectors, generated Snowflake IDs: {generated_ids}")
        return generated_ids

    def search(
        self,
        query: str,
        vectors: list[float],
        limit: Optional[int] = 5,
        filters: Optional[dict] = None,
        retrieval_mode: str = "auto",
        fusion: str = "rrf",
        vector_weight: Optional[float] = None,
        fts_weight: Optional[float] = None,
        rrf_k: int = 60,
        candidate_limit: Optional[int] = None,
        threshold: Optional[float] = None,
        include_explanation: bool = False,
    ) -> List[OutputData]:
        """
        Search for similar vectors with optional hybrid search.

        Args:
            query (str): Text query for fulltext search.
            vectors (List[float]): Query vector for vector search.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.
            retrieval_mode (str): "auto", "fts", "vector", or "hybrid".
            fusion (str): "rrf" or "weighted".
            vector_weight (float, optional): Weight for vector search in fusion.
            fts_weight (float, optional): Weight for FTS search in fusion.
            rrf_k (int): RRF constant (default 60).
            candidate_limit (int, optional): Candidate limit before final truncation.
            threshold (float, optional): Minimum score threshold.
            include_explanation (bool): Whether to include explanation in results.

        Returns:
            list: Search results.
        """
        mode = (retrieval_mode or "auto").lower()
        fusion_method = (fusion or "rrf").lower()
        search_limit = candidate_limit if candidate_limit is not None else limit

        has_vectors = vectors is not None and (
            (isinstance(vectors, list) and len(vectors) > 0 and isinstance(vectors[0], (int, float)))
            or (isinstance(vectors, list) and len(vectors) > 0 and isinstance(vectors[0], list))
        )
        has_query = isinstance(query, str) and query.strip() != ""

        # Normalize query vector
        query_vector = None
        if has_vectors:
            if isinstance(vectors[0], (int, float)):
                query_vector = vectors
            else:
                query_vector = vectors[0]

        # Pure FTS mode
        if mode == "fts":
            return self._fulltext_search(query, search_limit, filters)[:limit]

        # Pure vector mode or no hybrid search capability
        if mode == "vector" or not self.hybrid_search or not has_query:
            return self._vector_search(query_vector, search_limit, filters)[:limit]

        # Hybrid mode: both vector and FTS
        if has_vectors and has_query:
            # Run searches concurrently
            vector_results = []
            fts_results = []

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_vector = executor.submit(
                    self._vector_search, query_vector, search_limit, filters
                )
                future_fts = executor.submit(
                    self._fulltext_search, query, search_limit, filters
                )
                for future in as_completed([future_vector, future_fts]):
                    try:
                        result = future.result()
                        if future is future_vector:
                            vector_results = result
                        else:
                            fts_results = result
                    except Exception as e:
                        logger.warning(f"Search failed: {e}")

            # Fuse results
            if fusion_method == "weighted":
                final = self._weighted_fusion(
                    vector_results, fts_results, limit,
                    vector_weight=vector_weight, fts_weight=fts_weight,
                )
            else:
                final = self._rrf_fusion(
                    vector_results, fts_results, limit, k=rrf_k,
                    vector_weight=vector_weight, fts_weight=fts_weight,
                )

            # Apply threshold
            if threshold is not None:
                final = [r for r in final if r.payload.get("_quality_score", r.score) >= threshold]

            return final

        # Fallback: only vectors available
        if has_vectors:
            return self._vector_search(query_vector, search_limit, filters)[:limit]

        # Fallback: only query available
        return self._fulltext_search(query, search_limit, filters)[:limit]

    def _vector_search(
        self, query_vector: List[float], limit: int = 5, filters: Optional[dict] = None
    ) -> List[OutputData]:
        """Pure vector cosine similarity search."""
        if query_vector is None:
            return []

        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                if "." in k:
                    filter_conditions.append(
                        "payload #>> string_to_array(%s, '.') = %s"
                    )
                else:
                    filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT id, vector <=> %s::vector AS distance, payload
                FROM {self.collection_name}
                {filter_clause}
                ORDER BY distance
                LIMIT %s
                """,
                (query_vector, *filter_params, limit),
            )

            results = cur.fetchall()

        output = []
        for r in results:
            distance = float(r[1])
            similarity = max(1.0 - distance / 2.0, 0.0)
            payload = r[2] if isinstance(r[2], dict) else json.loads(r[2])
            payload['_vector_similarity'] = similarity
            output.append(OutputData(id=r[0], score=similarity, payload=payload))
        return output

    @staticmethod
    def _weighted_fusion(
        vector_results: List[OutputData],
        fts_results: List[OutputData],
        limit: int,
        vector_weight: Optional[float] = None,
        fts_weight: Optional[float] = None,
    ) -> List[OutputData]:
        """Weighted fusion using per-path min-max normalized scores."""
        vw = vector_weight if vector_weight is not None else 0.5
        fw = fts_weight if fts_weight is not None else 0.5

        def normalized_scores(results: List[OutputData]) -> Dict[int, float]:
            if not results:
                return {}
            scores = [float(r.score or 0.0) for r in results]
            min_s, max_s = min(scores), max(scores)
            if max_s == min_s:
                return {r.id: 1.0 for r in results}
            return {r.id: (float(r.score or 0.0) - min_s) / (max_s - min_s) for r in results}

        vec_scores = normalized_scores(vector_results)
        fts_scores = normalized_scores(fts_results)
        all_docs: Dict[int, dict] = {}

        for rank, result in enumerate(vector_results, 1):
            all_docs[result.id] = {
                "result": result,
                "vector_rank": rank,
                "fts_rank": None,
                "weighted_score": vw * vec_scores.get(result.id, 0.0),
            }

        for rank, result in enumerate(fts_results, 1):
            ws = fw * fts_scores.get(result.id, 0.0)
            if result.id in all_docs:
                all_docs[result.id]["fts_rank"] = rank
                all_docs[result.id]["weighted_score"] += ws
                all_docs[result.id]["result"].payload["_fts_score"] = result.payload.get("_fts_score")
            else:
                all_docs[result.id] = {
                    "result": result,
                    "vector_rank": None,
                    "fts_rank": rank,
                    "weighted_score": ws,
                }

        sorted_docs = sorted(all_docs.values(), key=lambda d: d["weighted_score"], reverse=True)

        final_results = []
        for doc_data in sorted_docs[:limit]:
            result = doc_data["result"]
            score = doc_data["weighted_score"]
            quality_score = (
                1.0
                if doc_data["fts_rank"] is not None
                else result.payload.get("_vector_similarity", score)
            )
            result.score = score
            result.payload["_fusion_score"] = score
            result.payload["_quality_score"] = quality_score
            result.payload["_fusion_info"] = {
                "vector_rank": doc_data["vector_rank"],
                "fts_rank": doc_data["fts_rank"],
                "weighted_score": score,
                "fusion_method": "weighted",
                "vector_weight": vw,
                "fts_weight": fw,
            }
            final_results.append(result)

        return final_results

    def delete(self, vector_id: int) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (int): ID of the vector to delete.
        """
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DELETE FROM {self.collection_name} WHERE id = %s", (vector_id,))

    def update(
        self,
        vector_id: int,
        vector: Optional[list[float]] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """
        Update a vector and its payload.

        Args:
            vector_id (int): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        with self._get_cursor(commit=True) as cur:
            if vector:
               cur.execute(
                    f"UPDATE {self.collection_name} SET vector = %s WHERE id = %s",
                    (vector, vector_id),
                )
            if payload:
                ft_content = self._extract_fulltext_content(payload)
                # Handle JSON serialization based on psycopg version
                if PSYCOPG_VERSION == 3:
                    # psycopg3 uses psycopg.types.json.Json
                    cur.execute(
                        f"UPDATE {self.collection_name} SET payload = %s, fulltext_content = %s WHERE id = %s",
                        (Json(payload), ft_content, vector_id),
                    )
                else:
                    # psycopg2 uses psycopg2.extras.Json
                    cur.execute(
                        f"UPDATE {self.collection_name} SET payload = %s, fulltext_content = %s WHERE id = %s",
                        (Json(payload), ft_content, vector_id),
                    )


    def get(self, vector_id: int) -> OutputData | None:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (int): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = %s",
                (vector_id,),
            )
            result = cur.fetchone()
            if not result:
                return None
            return OutputData(id=result[0], score=None, payload=result[2])

    @staticmethod
    def _extract_fulltext_content(payload: dict) -> str:
        """Extract text content from payload for FTS indexing."""
        if not payload:
            return ""
        for key in ("fulltext_content", "data", "content"):
            val = payload.get(key)
            if val and isinstance(val, str):
                return val
        return ""

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Build a safe FTS query string from user input.

        Extracts word tokens and wraps each in single quotes for PostgreSQL FTS.
        """
        if not query or not query.strip():
            return ""
        tokens = re.findall(r"[\w]+", query, re.UNICODE)
        if not tokens:
            return ""
        return " & ".join(f"'{t}'" for t in tokens)

    def _fulltext_search(
        self, query: str, limit: int = 5, filters: Optional[dict] = None
    ) -> List[OutputData]:
        """Perform PostgreSQL fulltext search using tsvector/tsquery."""
        if not query or not query.strip():
            return []

        fts_query = self._sanitize_fts_query(query)
        if not fts_query:
            return []

        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                if "." in k:
                    filter_conditions.append(
                        "payload #>> string_to_array(%s, '.') = %s"
                    )
                else:
                    filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        # Build the fulltext search query with ts_rank for scoring
        sql = f"""
            SELECT id, payload,
                   ts_rank(to_tsvector('{self.fulltext_language}', fulltext_content),
                           to_tsquery('{self.fulltext_language}', %s)) AS rank
            FROM {self.collection_name}
            {filter_clause}
            AND to_tsvector('{self.fulltext_language}', fulltext_content) @@
                  to_tsquery('{self.fulltext_language}', %s)
            ORDER BY rank DESC
            LIMIT %s
        """

        # If there are filters, adjust the WHERE clause
        if filter_conditions:
            sql = f"""
                SELECT id, payload,
                       ts_rank(to_tsvector('{self.fulltext_language}', fulltext_content),
                               to_tsquery('{self.fulltext_language}', %s)) AS rank
                FROM {self.collection_name}
                WHERE {' AND '.join(filter_conditions)}
                  AND to_tsvector('{self.fulltext_language}', fulltext_content) @@
                        to_tsquery('{self.fulltext_language}', %s)
                ORDER BY rank DESC
                LIMIT %s
            """
            params = (*filter_params, fts_query, fts_query, limit)
        else:
            sql = f"""
                SELECT id, payload,
                       ts_rank(to_tsvector('{self.fulltext_language}', fulltext_content),
                               to_tsquery('{self.fulltext_language}', %s)) AS rank
                FROM {self.collection_name}
                WHERE to_tsvector('{self.fulltext_language}', fulltext_content) @@
                      to_tsquery('{self.fulltext_language}', %s)
                ORDER BY rank DESC
                LIMIT %s
            """
            params = (fts_query, fts_query, limit)

        results = []
        with self._get_cursor() as cur:
            try:
                cur.execute(sql, params)
                for row in cur.fetchall():
                    doc_id, payload_str, rank_score = row
                    payload = json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                    payload['_fts_score'] = float(rank_score)
                    results.append(OutputData(
                        id=doc_id,
                        score=float(rank_score),
                        payload=payload,
                    ))
            except Exception as exc:
                logger.warning(f"Fulltext search failed: {exc}")

        return results

    def _rrf_fusion(
        self,
        vector_results: List[OutputData],
        fts_results: List[OutputData],
        limit: int,
        k: int = 60,
        vector_weight: Optional[float] = None,
        fts_weight: Optional[float] = None,
    ) -> List[OutputData]:
        """Reciprocal Rank Fusion combining vector and FTS results."""
        vw = vector_weight if vector_weight is not None else self.vector_weight
        fw = fts_weight if fts_weight is not None else self.fts_weight

        all_docs: Dict[int, dict] = {}

        for rank, result in enumerate(vector_results, 1):
            rrf_score = vw * (1.0 / (k + rank))
            all_docs[result.id] = {
                'result': result,
                'vector_rank': rank,
                'fts_rank': None,
                'rrf_score': rrf_score,
            }

        for rank, result in enumerate(fts_results, 1):
            fts_rrf = fw * (1.0 / (k + rank))
            if result.id in all_docs:
                all_docs[result.id]['fts_rank'] = rank
                all_docs[result.id]['rrf_score'] += fts_rrf
                all_docs[result.id]['result'].payload['_fts_score'] = (
                    result.payload.get('_fts_score')
                )
            else:
                all_docs[result.id] = {
                    'result': result,
                    'vector_rank': None,
                    'fts_rank': rank,
                    'rrf_score': fts_rrf,
                }

        sorted_docs = sorted(
            all_docs.values(), key=lambda d: d['rrf_score'], reverse=True
        )

        final_results = []
        for doc_data in sorted_docs[:limit]:
            result = doc_data['result']
            score = doc_data['rrf_score']
            quality_score = (
                1.0
                if doc_data['fts_rank'] is not None
                else result.payload.get('_vector_similarity', score)
            )
            result.score = score
            result.payload['_fusion_score'] = score
            result.payload['_quality_score'] = quality_score
            result.payload['_fusion_info'] = {
                'vector_rank': doc_data['vector_rank'],
                'fts_rank': doc_data['fts_rank'],
                'rrf_score': score,
                'fusion_method': 'rrf',
                'vector_weight': vw,
                'fts_weight': fw,
            }
            final_results.append(result)

        return final_results

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        with self._get_cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return [row[0] for row in cur.fetchall()]

    def delete_col(self) -> None:
        """Delete a collection."""
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.collection_name}")

    def col_info(self) -> dict[str, Any]:
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    table_name,
                    (SELECT COUNT(*) FROM {self.collection_name}) as row_count,
                    (SELECT pg_size_pretty(pg_total_relation_size('{self.collection_name}'))) as total_size
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
            """,
                (self.collection_name,),
            )
            result = cur.fetchone()
        return {"name": result[0], "count": result[1], "size": result[2]}

    def list(
        self,
        filters: Optional[dict] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = None,
        order_by: Optional[str] = None,
        order: str = "desc"
    ) -> List[OutputData]:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.
            offset (int, optional): Number of results to skip.
            order_by (str, optional): Field to sort by (e.g., "created_at", "updated_at", "id").
            order (str, optional): Sort order, "desc" for descending or "asc" for ascending.

        Returns:
            List[OutputData]: List of vectors.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                if "." in k:
                    filter_conditions.append(
                        "payload #>> string_to_array(%s, '.') = %s"
                    )
                else:
                    filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""
        
        # Build ORDER BY clause for sorting
        order_clause = ""
        if order_by:
            order_upper = order.upper()
            if order_by in ["created_at", "updated_at"]:
                # Sort by JSON field in payload
                order_clause = f"ORDER BY payload->>'{order_by}' {order_upper}"
            elif order_by == "id":
                # Sort by id column
                order_clause = f"ORDER BY id {order_upper}"

        # Build query with all clauses
        query_parts = [
            f"SELECT id, vector, payload",
            f"FROM {self.collection_name}",
            filter_clause,
            order_clause,
        ]
        
        # Add OFFSET and LIMIT
        if limit is not None:
            query_parts.append("LIMIT %s")
            filter_params.append(limit)
        if offset is not None:
            query_parts.append("OFFSET %s")
            filter_params.append(offset)
        
        query = "\n".join(part for part in query_parts if part)

        with self._get_cursor() as cur:
            cur.execute(query, tuple(filter_params))
            results = cur.fetchall()
        return [OutputData(id=r[0], score=None, payload=r[2]) for r in results]

    def count(self, filters: Optional[dict] = None) -> int:
        """
        Count all vectors in a collection with optional filtering.

        Args:
            filters (Dict, optional): Filters to apply to the count.

        Returns:
            int: Total count of vectors matching the filters.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                if "." in k:
                    filter_conditions.append(
                        "payload #>> string_to_array(%s, '.') = %s"
                    )
                else:
                    filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""
        
        # Build count query
        query = f"SELECT COUNT(*) FROM {self.collection_name} {filter_clause}"

        with self._get_cursor() as cur:
            cur.execute(query, tuple(filter_params))
            count = cur.fetchone()[0]
        
        return count

    def __del__(self) -> None:
        """
        Close the database connection pool when the object is deleted.
        """
        try:
            # Close pool appropriately
            if PSYCOPG_VERSION == 3:
                self.connection_pool.close()
            else:
                self.connection_pool.closeall()
        except Exception:
            logger.error("Error closing database connection pool")
            pass

    def reset(self) -> None:
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col()

    def get_statistics(
        self, filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get statistics for the memories in PGVector."""
        stats = {
            "total_memories": 0,
            "by_type": {},
            "avg_importance": 0.0,
            "top_accessed": [],
            "growth_trend": {},
            "age_distribution": {
                "< 1 day": 0,
                "1-7 days": 0,
                "7-30 days": 0,
                "> 30 days": 0,
            },
        }

        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self._get_cursor() as cur:
            # Get total count
            cur.execute(f"SELECT COUNT(*) FROM {self.collection_name} {filter_clause}", filter_params)
            stats["total_memories"] = cur.fetchone()[0]

            if stats["total_memories"] == 0:
                return stats

            # Get distribution by type
            cur.execute(
                f"""
                SELECT 
                    COALESCE(payload->>'category', payload->>'type', 'unknown') as type, 
                    COUNT(*) 
                FROM {self.collection_name} 
                {filter_clause}
                GROUP BY type
                """,
                filter_params
            )
            for row in cur.fetchall():
                stats["by_type"][row[0]] = row[1]

            # Get average importance
            cur.execute(
                f"""
                SELECT AVG(CAST(COALESCE(payload->>'importance', payload->'metadata'->>'importance', '0') AS FLOAT))
                FROM {self.collection_name}
                {filter_clause}
                """,
                filter_params
            )
            stats["avg_importance"] = round(float(cur.fetchone()[0] or 0.0), 2)

            # Get top accessed
            cur.execute(
                f"""
                SELECT id, payload->>'data' as content, 
                       CAST(COALESCE(payload->>'access_count', payload->'metadata'->>'access_count', '0') AS INTEGER) as access_count
                FROM {self.collection_name}
                {filter_clause}
                ORDER BY access_count DESC
                LIMIT 10
                """,
                filter_params
            )
            for row in cur.fetchall():
                stats["top_accessed"].append({
                    "id": row[0],
                    "content": (row[1] or "")[:50],
                    "access_count": row[2]
                })

            # Growth trend
            cur.execute(
                f"""
                SELECT DATE(created_at) as date, COUNT(*)
                FROM {self.collection_name}
                {filter_clause}
                GROUP BY date
                ORDER BY date
                """,
                filter_params
            )
            for row in cur.fetchall():
                stats["growth_trend"][str(row[0])] = row[1]

            # Age distribution
            cur.execute(
                f"""
                SELECT 
                    CASE 
                        WHEN created_at > NOW() - INTERVAL '1 day' THEN '< 1 day'
                        WHEN created_at > NOW() - INTERVAL '7 days' THEN '1-7 days'
                        WHEN created_at > NOW() - INTERVAL '30 days' THEN '7-30 days'
                        ELSE '> 30 days'
                    END as age_bucket,
                    COUNT(*)
                FROM {self.collection_name}
                {filter_clause}
                GROUP BY age_bucket
                """,
                filter_params
            )
            for row in cur.fetchall():
                if row[0] in stats["age_distribution"]:
                    stats["age_distribution"][row[0]] = row[1]

        return stats

    def get_unique_users(self) -> List[str]:
        """Get a list of unique user IDs from PGVector."""
        query = f"SELECT DISTINCT payload->>'user_id' FROM {self.collection_name} WHERE payload ? 'user_id'"
        with self._get_cursor() as cur:
            cur.execute(query)
            return [str(row[0]) for row in cur.fetchall() if row[0] is not None]

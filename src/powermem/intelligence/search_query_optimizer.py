"""Search query optimizer — rewrite conversational queries for semantic search.

Resolves ambiguous references using conversation context, splits compound
questions into independent sub-queries, and extracts keyword-rich search terms.
"""

import json
import logging
import re
from typing import Dict, List, Optional

from ..prompts.search_query_prompts import SEARCH_QUERY_REWRITE_PROMPT
from ..utils.utils import strip_think_tags

logger = logging.getLogger(__name__)


class SearchQueryOptimizer:
    """Rewrite a user query into search-optimized sub-queries."""

    def __init__(self, llm):
        """
        Args:
            llm: An LLM instance that exposes ``generate_response(messages=...)``.
        """
        self.llm = llm

    def rewrite(
        self,
        query: str,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> List[str]:
        """Synchronously rewrite *query* into search-optimized sub-queries.

        Returns:
            A list of query strings, or ``[]`` if the message has no
            searchable intent.
        """
        if not query or not query.strip():
            return []

        user_content = self._build_user_content(query, context)

        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": SEARCH_QUERY_REWRITE_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("SearchQueryOptimizer.rewrite failed: %s", e)
            return []

    async def arewrite(
        self,
        query: str,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> List[str]:
        """Async variant — runs the sync LLM call in a thread pool."""
        import asyncio

        if not query or not query.strip():
            return []

        user_content = self._build_user_content(query, context)

        try:
            response = await asyncio.to_thread(
                self.llm.generate_response,
                messages=[
                    {"role": "system", "content": SEARCH_QUERY_REWRITE_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("SearchQueryOptimizer.arewrite failed: %s", e)
            return []

    # -- Internal helpers --

    @staticmethod
    def _build_user_content(
        query: str,
        context: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        if context:
            ctx_lines = "\n".join(
                f"{m['role']}: {m['content']}" for m in context[-6:]
            )
            return f"[Context]\n{ctx_lines}\n\n[Message]\n{query}"
        return query

    @staticmethod
    def _parse_response(response: str) -> List[str]:
        result = strip_think_tags(response).strip()
        if not result:
            return []
        try:
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return [q.strip() for q in parsed if isinstance(q, str) and q.strip()]
        except json.JSONDecodeError:
            # Model didn't produce strict JSON — fall back to single query
            return [result] if result else []
        return []

"""Experience-aware query rewriter.

Rewrites user queries into short, title-style sub-queries optimised for
matching experience entries (titles + descriptions) rather than raw memory
content.  Shares the same parse logic as :class:`SearchQueryOptimizer` but
uses a specialised prompt tuned for experience retrieval.
"""

import json
import logging
import re
from typing import List

from ..prompts.experience_query_prompts import EXPERIENCE_QUERY_REWRITE_PROMPT
from ..utils.utils import strip_think_tags

logger = logging.getLogger(__name__)


class ExperienceQueryRewriter:
    """Rewrite a user query into title-style queries for experience search."""

    def __init__(self, llm):
        """
        Args:
            llm: An LLM instance that exposes ``generate_response(messages=...)``.
        """
        self.llm = llm

    def rewrite(self, query: str) -> List[str]:
        """Synchronously rewrite *query* into experience-oriented sub-queries.

        Returns:
            A list of short, title-style query strings, or ``[]`` if the query
            has no relation to tool/API/strategy topics.
        """
        if not query or not query.strip():
            return []

        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": EXPERIENCE_QUERY_REWRITE_PROMPT},
                    {"role": "user", "content": query},
                ],
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("ExperienceQueryRewriter.rewrite failed: %s", e)
            return []

    async def arewrite(self, query: str) -> List[str]:
        """Async variant — runs the sync LLM call in a thread pool."""
        import asyncio

        if not query or not query.strip():
            return []

        try:
            response = await asyncio.to_thread(
                self.llm.generate_response,
                messages=[
                    {"role": "system", "content": EXPERIENCE_QUERY_REWRITE_PROMPT},
                    {"role": "user", "content": query},
                ],
            )
            return self._parse_response(response)
        except Exception as e:
            logger.warning("ExperienceQueryRewriter.arewrite failed: %s", e)
            return []

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
            json_match = re.search(r"\[[\s\S]*\]", result)
            if json_match:
                try:
                    parsed = json.loads(json_match.group(0))
                    if isinstance(parsed, list):
                        return [q.strip() for q in parsed if isinstance(q, str) and q.strip()]
                except json.JSONDecodeError:
                    pass
            return [result] if result else []
        return []

"""Dual-layer content safety review — keyword blocklist + LLM review.

Designed primarily for the experience distillation pipeline but can be
used standalone to vet any text before it enters long-term memory.

Layer 1 — fast keyword filter (no LLM call, microseconds).
Layer 2 — LLM-based nuanced review (catches context-dependent violations).
"""

import json
import logging
import re
from typing import List, Optional, Tuple

from ..prompts.content_review_prompts import CONTENT_REVIEW_PROMPT
from ..utils.utils import strip_think_tags

logger = logging.getLogger(__name__)


# -- Layer 1: keyword blocklist --

DEFAULT_BLOCKED_KEYWORDS: List[str] = [
    # Political sensitivity
    "\u516d\u56db", "\u5929\u5b89\u95e8\u4e8b\u4ef6", "\u516d\u56db\u4e8b\u4ef6", "tiananmen", "8964",
    "\u6cd5\u8f6e\u529f", "falun gong", "falundafa",
    "\u53f0\u72ec", "\u85cf\u72ec", "\u7586\u72ec", "\u6e2f\u72ec",
    "\u8fbe\u8d56\u5587\u561b", "dalai lama",
    "\u989c\u8272\u9769\u547d", "\u98a0\u8986\u653f\u6743", "\u98a0\u8986\u56fd\u5bb6",
    "\u53cd\u5171", "\u5171\u532a", "\u652f\u90a3",
    "\u6587\u5316\u5927\u9769\u547d", "\u5927\u8dc3\u8fdb", "\u53cd\u53f3",
    "\u5218\u6653\u6ce2", "\u96f6\u516b\u5baa\u7ae0",
    "\u81ea\u7531\u4e9a\u6d32", "\u7f8e\u56fd\u4e4b\u97f3",
    "\u7ffb\u5899", "vpn\u7ffb\u5899",

    # Military secrets
    "\u519b\u4e8b\u673a\u5bc6", "\u56fd\u9632\u673a\u5bc6", "\u519b\u4e8b\u90e8\u7f72",
    "\u6838\u6b66\u5668", "\u6838\u5f39\u5934", "\u4e1c\u98ce\u5bfc\u5f39", "\u5de8\u6d6a\u5bfc\u5f39",
    "\u519b\u4e8b\u57fa\u5730\u5750\u6807", "\u5bfc\u5f39\u53d1\u5c04\u4e95",

    # Terrorism
    "isis", "\u4f0a\u65af\u5170\u56fd", "\u57fa\u5730\u7ec4\u7ec7", "al-qaeda", "al qaeda",
    "\u5854\u5229\u73ed", "taliban", "\u535a\u79d1\u5723\u5730", "boko haram",
    "\u6050\u6016\u88ad\u51fb", "\u81ea\u6740\u5f0f\u70b8\u5f39", "\u4eba\u8089\u70b8\u5f39",
    "\u5723\u6218", "jihad",

    # Extreme violence
    "\u5c60\u6740\u5e73\u6c11", "\u79cd\u65cf\u706d\u7edd", "genocide",
    "\u9177\u5211\u6298\u78e8", "\u6d3b\u6458\u5668\u5b98",
    "\u5927\u89c4\u6a21\u5c60\u6740", "mass killing",

    # Anti-social
    "\u717d\u52a8\u66b4\u4e71", "\u717d\u52a8\u98a0\u8986", "\u5206\u88c2\u56fd\u5bb6",
    "\u63a8\u7ffb\u653f\u5e9c", "\u66b4\u529b\u9769\u547d",
    "\u5236\u9020\u70b8\u5f39", "\u5236\u9020\u7206\u70b8\u7269",
]


class ContentReviewer:
    """Two-layer content safety reviewer (keyword + LLM).

    Usage::

        reviewer = ContentReviewer(llm=my_llm)
        safe, reason = reviewer.review("some title", "some description", ["tag"])
        safe, reason = await reviewer.areview("title", "desc", ["tag"])
    """

    def __init__(
        self,
        llm=None,
        blocked_keywords: Optional[List[str]] = None,
    ):
        """
        Args:
            llm: LLM instance for layer-2 review. If ``None`` only keyword
                 filtering is performed.
            blocked_keywords: Custom keyword list. Defaults to
                              ``DEFAULT_BLOCKED_KEYWORDS``.
        """
        self.llm = llm
        self.blocked_keywords = (
            blocked_keywords if blocked_keywords is not None
            else list(DEFAULT_BLOCKED_KEYWORDS)
        )

    # -- Public API --

    def review(
        self,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Run dual-layer content review (sync).

        Returns:
            ``(safe, reason)`` — *safe* is True when content passed both layers.
        """
        combined = f"{title}\n{description}\n{' '.join(tags or [])}"

        passed, blocked_kw = self._keyword_check(combined)
        if not passed:
            return False, f"keyword_blocked: {blocked_kw}"

        if self.llm is not None:
            safe, reason = self._llm_review(title, description)
            if not safe:
                return False, f"llm_review: {reason}"

        return True, None

    async def areview(
        self,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Async variant of :meth:`review`."""
        import asyncio

        combined = f"{title}\n{description}\n{' '.join(tags or [])}"

        passed, blocked_kw = self._keyword_check(combined)
        if not passed:
            return False, f"keyword_blocked: {blocked_kw}"

        if self.llm is not None:
            safe, reason = await asyncio.to_thread(
                self._llm_review, title, description,
            )
            if not safe:
                return False, f"llm_review: {reason}"

        return True, None

    # -- Keyword management --

    def add_keywords(self, keywords: List[str]) -> None:
        """Append keywords to the blocklist (deduped)."""
        existing = set(k.lower() for k in self.blocked_keywords)
        for kw in keywords:
            if kw.lower() not in existing:
                self.blocked_keywords.append(kw)
                existing.add(kw.lower())

    def remove_keywords(self, keywords: List[str]) -> None:
        """Remove keywords from the blocklist."""
        remove_set = set(k.lower() for k in keywords)
        self.blocked_keywords = [
            kw for kw in self.blocked_keywords if kw.lower() not in remove_set
        ]

    # -- Internal --

    def _keyword_check(self, text: str) -> Tuple[bool, Optional[str]]:
        """Layer 1 — fast keyword scan.

        Returns ``(passed, blocked_keyword)``.
        """
        text_lower = text.lower()
        for kw in self.blocked_keywords:
            if kw.lower() in text_lower:
                return False, kw
        return True, None

    def _llm_review(self, title: str, description: str) -> Tuple[bool, Optional[str]]:
        """Layer 2 — LLM-based contextual review.

        Returns ``(safe, reason)``.
        """
        try:
            user_content = f"\u6807\u9898\uff1a{title}\n\u5185\u5bb9\uff1a{description}"
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": CONTENT_REVIEW_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )

            stripped = strip_think_tags(response).strip()
            json_match = re.search(r"\{[\s\S]*\}", stripped)
            if not json_match:
                logger.warning("Content review LLM returned non-JSON: %s", stripped[:200])
                return True, None

            data = json.loads(json_match.group(0))
            safe = data.get("safe", True)
            reason = data.get("reason") if not safe else None
            return bool(safe), reason

        except Exception as e:
            logger.warning("LLM content review failed, defaulting to safe: %s", e)
            return True, None

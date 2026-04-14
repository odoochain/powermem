"""Experience distillation and merging.

Extracts reusable task-solving experiences from conversations and merges
semantically similar experiences into consolidated entries.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from ..prompts.experience_prompts import EXPERIENCE_DISTILL_PROMPT, EXPERIENCE_MERGE_PROMPT
from ..utils.utils import strip_think_tags

logger = logging.getLogger(__name__)


class ExperienceManager:
    """Distill and merge experiences via LLM."""

    def __init__(self, llm):
        """
        Args:
            llm: An LLM instance that exposes ``generate_response(messages=...)``.
        """
        self.llm = llm

    # -- Distillation --

    def distill(
        self,
        messages: List[Dict[str, str]],
        today: str,
    ) -> List[Dict[str, Any]]:
        """Extract reusable experiences from a conversation (sync).

        Returns:
            List of ``{"title": str, "description": str, "tags": list}``.
        """
        user_content = self._build_distill_input(messages)
        if user_content is None:
            return []

        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": EXPERIENCE_DISTILL_PROMPT.replace("{today}", today)},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_experiences(response)
        except Exception as e:
            logger.warning("ExperienceManager.distill failed: %s", e)
            return []

    async def adistill(
        self,
        messages: List[Dict[str, str]],
        today: str,
    ) -> List[Dict[str, Any]]:
        """Async variant of :meth:`distill`."""
        import asyncio

        user_content = self._build_distill_input(messages)
        if user_content is None:
            return []

        try:
            response = await asyncio.to_thread(
                self.llm.generate_response,
                messages=[
                    {"role": "system", "content": EXPERIENCE_DISTILL_PROMPT.replace("{today}", today)},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_experiences(response)
        except Exception as e:
            logger.warning("ExperienceManager.adistill failed: %s", e)
            return []

    # -- Merging --

    def merge(self, existing: str, new: str) -> Dict[str, str]:
        """Merge two similar experiences into one (sync).

        Returns:
            ``{"title": str, "description": str}``.
            Falls back to ``{"title": "", "description": new}`` on failure.
        """
        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": EXPERIENCE_MERGE_PROMPT},
                    {"role": "user", "content": f"Experience A:\n{existing}\n\nExperience B:\n{new}"},
                ],
            )
            return self._parse_merge(response, new)
        except Exception as e:
            logger.warning("ExperienceManager.merge failed: %s", e)
            return {"title": "", "description": new}

    async def amerge(self, existing: str, new: str) -> Dict[str, str]:
        """Async variant of :meth:`merge`."""
        import asyncio

        try:
            response = await asyncio.to_thread(
                self.llm.generate_response,
                messages=[
                    {"role": "system", "content": EXPERIENCE_MERGE_PROMPT},
                    {"role": "user", "content": f"Experience A:\n{existing}\n\nExperience B:\n{new}"},
                ],
            )
            return self._parse_merge(response, new)
        except Exception as e:
            logger.warning("ExperienceManager.amerge failed: %s", e)
            return {"title": "", "description": new}

    # -- Internal helpers --

    @staticmethod
    def _build_distill_input(messages: List[Dict[str, str]]) -> Optional[str]:
        """Build the user-content string for the distillation prompt."""
        if not messages:
            return None
        lines = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role and content and role != "system":
                lines.append(f"{role}: {content}")
        return "\n".join(lines) if lines else None

    @staticmethod
    def _parse_experiences(response: str) -> List[Dict[str, Any]]:
        stripped = strip_think_tags(response).strip()
        json_match = re.search(r"\{[\s\S]*\}", stripped)
        if not json_match:
            return []
        try:
            data = json.loads(json_match.group(0))
            experiences = data.get("experiences", [])
            return [
                exp for exp in experiences
                if isinstance(exp, dict)
                and exp.get("title")
                and exp.get("description")
            ]
        except (json.JSONDecodeError, AttributeError):
            return []

    @staticmethod
    def _parse_merge(response: str, fallback_new: str) -> Dict[str, str]:
        stripped = strip_think_tags(response).strip()
        json_match = re.search(r"\{[\s\S]*\}", stripped)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                title = data.get("title", "")
                description = data.get("description", "")
                if description:
                    return {"title": title, "description": description}
            except (json.JSONDecodeError, AttributeError):
                pass
        return {"title": "", "description": fallback_new}

"""Skill evolution: detect recurring patterns and codify them into skills.

Inspired by the odoo-ai project's skill-evolver pattern:
  1. Detect recurring patterns from session history
  2. Check for duplicates against existing skills
  3. Classify the pattern (update existing vs create new vs skip)
  4. Propose a minimal change with confirmation required before applying

Unlike SkillManager (which distills skills from a single conversation),
SkillEvolver works across multiple sessions to find cross-session patterns
that warrant new skills or updates to existing ones.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..prompts.skill_prompts import (
    SKILL_EVOLVE_DETECT_PROMPT,
    SKILL_EVOLVE_CLASSIFY_PROMPT,
)
from ..utils.utils import strip_think_tags

logger = logging.getLogger(__name__)


class SkillEvolver:
    """Detect recurring patterns and evolve the skill library.

    Works in four phases:
      1. detect  — LLM scans session history for recurring patterns
      2. dedup   — search SkillStore for similar existing skills
      3. classify— LLM decides: update existing / create new / skip
      4. propose — return a structured proposal for user confirmation

    The caller is responsible for confirming and applying changes.
    This class NEVER writes to the SkillStore directly.
    """

    def __init__(self, llm, skill_store=None, embedder=None):
        """Initialize the SkillEvolver.

        Args:
            llm: An LLM instance that exposes ``generate_response(messages=...)``.
            skill_store: Optional SkillStoreBase instance for duplicate checking.
            embedder: Optional embedder for generating query embeddings.
        """
        self.llm = llm
        self.skill_store = skill_store
        self.embedder = embedder

    def evolve(
        self,
        session_history: List[Dict[str, str]],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run the full evolution pipeline: detect → dedup → classify → propose.

        Args:
            session_history: List of message dicts with "role" and "content".
            user_id: Optional user filter for skill search.
            agent_id: Optional agent filter for skill search.

        Returns:
            List of proposals. Each proposal is one of:
              {"action": "create", "title": ..., "description": ..., "tags": ..., "procedure": ...}
              {"action": "update", "skill_id": int, "reason": ..., "new_steps": ..., "new_pitfalls": ...}
              {"action": "skip", "reason": ...}
        """
        if self._is_llm_disabled():
            return []

        # Phase 1: Detect recurring patterns
        patterns = self.detect_patterns(session_history)
        if not patterns:
            logger.debug("SkillEvolver: no recurring patterns detected")
            return []

        # Phase 2 + 3: For each pattern, dedup and classify
        proposals = []
        for pattern in patterns:
            proposal = self.classify_pattern(pattern, user_id=user_id, agent_id=agent_id)
            if proposal and proposal.get("action") != "skip":
                proposals.append(proposal)

        logger.info(
            "SkillEvolver: %d patterns detected, %d proposals generated",
            len(patterns),
            len(proposals),
        )
        return proposals

    def detect_patterns(
        self, session_history: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Use LLM to detect recurring patterns in session history.

        Args:
            session_history: List of message dicts with "role" and "content".

        Returns:
            List of pattern dicts with title, description, tags, occurrence_count, evidence.
        """
        if self._is_llm_disabled():
            return []

        user_content = self._build_session_summary(session_history)
        if not user_content:
            return []

        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": SKILL_EVOLVE_DETECT_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            return self._parse_patterns(response)
        except Exception as e:
            logger.warning("SkillEvolver.detect_patterns failed: %s", e)
            return []

    def classify_pattern(
        self,
        pattern: Dict[str, Any],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classify a pattern: is it a duplicate, an update, or a new skill?

        Args:
            pattern: Pattern dict from detect_patterns.
            user_id: Optional user filter for skill search.
            agent_id: Optional agent filter for skill search.

        Returns:
            Proposal dict with action "create", "update", or "skip".
        """
        if self._is_llm_disabled():
            return {"action": "skip", "reason": "LLM disabled"}

        # Search for similar existing skills
        existing_skills = self._search_existing_skills(
            pattern, user_id=user_id, agent_id=agent_id
        )

        # Build the classification input
        existing_summary = self._format_existing_skills(existing_skills)
        pattern_summary = json.dumps(pattern, ensure_ascii=False, indent=2)

        user_content = (
            f"Detected pattern:\n{pattern_summary}\n\n"
            f"Existing skills:\n{existing_summary}"
        )

        try:
            response = self.llm.generate_response(
                messages=[
                    {"role": "system", "content": SKILL_EVOLVE_CLASSIFY_PROMPT},
                    {"role": "user", "content": user_content},
                ],
            )
            proposal = self._parse_classification(response)
            if proposal and proposal.get("action") == "update":
                # Attach the skill_id from the matched existing skill if the
                # LLM didn't include it or included a null value.
                if not proposal.get("skill_id") and existing_skills:
                    proposal["skill_id"] = existing_skills[0]["id"]
            return proposal
        except Exception as e:
            logger.warning("SkillEvolver.classify_pattern failed: %s", e)
            return {"action": "skip", "reason": str(e)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_llm_disabled(self) -> bool:
        """Check if the LLM is a no-op."""
        return getattr(self.llm, "is_noop", False) is True

    @staticmethod
    def _build_session_summary(
        session_history: List[Dict[str, str]],
        max_messages: int = 50,
        max_content_len: int = 500,
    ) -> Optional[str]:
        """Build a condensed summary of session history for the LLM.

        Truncates long histories to stay within token limits.
        """
        if not session_history:
            return None

        # Take the most recent messages, capped
        messages = session_history[-max_messages:]

        lines = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if not role or not content or role == "system":
                continue
            # Truncate individual messages
            if len(content) > max_content_len:
                content = content[:max_content_len] + "..."
            lines.append(f"{role}: {content}")

        return "\n".join(lines) if lines else None

    @staticmethod
    def _parse_patterns(response: str) -> List[Dict[str, Any]]:
        """Parse LLM pattern detection response."""
        stripped = strip_think_tags(response).strip()
        json_match = re.search(r"\{[\s\S]*\}", stripped)
        if not json_match:
            return []
        try:
            data = json.loads(json_match.group(0))
            patterns = data.get("patterns", [])
            results = []
            for p in patterns:
                if not isinstance(p, dict):
                    continue
                title = p.get("title", "")
                description = p.get("description", "")
                if not title or not description:
                    continue
                results.append({
                    "title": title,
                    "description": description,
                    "tags": p.get("tags", []),
                    "occurrence_count": p.get("occurrence_count", 2),
                    "evidence": p.get("evidence", []),
                })
            return results
        except (json.JSONDecodeError, AttributeError):
            return []

    @staticmethod
    def _parse_classification(response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM classification response."""
        stripped = strip_think_tags(response).strip()
        json_match = re.search(r"\{[\s\S]*\}", stripped)
        if not json_match:
            return {"action": "skip", "reason": "unparseable response"}
        try:
            data = json.loads(json_match.group(0))
            action = data.get("action", "skip")

            if action == "create":
                title = data.get("title", "")
                description = data.get("description", "")
                procedure = data.get("procedure")
                if not title or not description:
                    return {"action": "skip", "reason": "incomplete create proposal"}
                return {
                    "action": "create",
                    "title": title,
                    "description": description,
                    "tags": data.get("tags", []),
                    "procedure": procedure or {},
                    "reason": data.get("reason", ""),
                }

            if action == "update":
                return {
                    "action": "update",
                    "skill_id": data.get("skill_id"),
                    "reason": data.get("reason", ""),
                    "new_steps": data.get("new_steps", []),
                    "new_pitfalls": data.get("new_pitfalls", []),
                }

            return {"action": "skip", "reason": data.get("reason", "no action")}

        except (json.JSONDecodeError, AttributeError):
            return {"action": "skip", "reason": "unparseable response"}

    def _search_existing_skills(
        self,
        pattern: Dict[str, Any],
        user_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search the SkillStore for skills similar to the detected pattern."""
        if not self.skill_store:
            return []

        query_text = f"{pattern.get('title', '')} {pattern.get('description', '')}"
        query_embedding = None

        if self.embedder:
            try:
                query_embedding = self.embedder.embed(query_text)
            except Exception as e:
                logger.debug("SkillEvolver: embedder failed, text-only search: %s", e)

        try:
            return self.skill_store.search(
                query_embedding=query_embedding,
                query_text=query_text,
                limit=limit,
                user_id=user_id,
                agent_id=agent_id,
            )
        except Exception as e:
            logger.warning("SkillEvolver: skill search failed: %s", e)
            return []

    @staticmethod
    def _format_existing_skills(skills: List[Dict[str, Any]]) -> str:
        """Format existing skills for the classification prompt."""
        if not skills:
            return "(no existing skills found)"
        lines = []
        for s in skills:
            lines.append(
                f"- id={s.get('id')}, title={s.get('title', '')}, "
                f"description={s.get('description', '')}, "
                f"tags={s.get('tags', [])}, score={s.get('score', 0):.4f}"
            )
        return "\n".join(lines)

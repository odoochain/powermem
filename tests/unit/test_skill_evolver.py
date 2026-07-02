"""Tests for SkillEvolver."""

import json
import unittest
from unittest.mock import MagicMock, patch

from powermem.intelligence.skill_evolver import SkillEvolver


class TestSkillEvolverDetectPatterns(unittest.TestCase):
    """Tests for pattern detection phase."""

    def test_detect_patterns_returns_empty_when_llm_disabled(self):
        """detect_patterns returns [] when LLM is a no-op."""
        llm = MagicMock()
        llm.is_noop = True
        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([{"role": "user", "content": "hello"}])
        self.assertEqual(result, [])

    def test_detect_patterns_returns_empty_for_empty_history(self):
        """detect_patterns returns [] for empty session history."""
        llm = MagicMock()
        llm.is_noop = False
        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([])
        self.assertEqual(result, [])

    def test_detect_patterns_parses_valid_response(self):
        """detect_patterns parses LLM response into pattern dicts."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "patterns": [
                {
                    "title": "Docker mount",
                    "description": "Mount custom_addons directory in Docker",
                    "tags": ["docker", "mount"],
                    "occurrence_count": 3,
                    "evidence": ["session 1: mounted /custom_addons", "session 2: same pattern"],
                }
            ]
        })

        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([
            {"role": "user", "content": "mount docker volume"},
            {"role": "assistant", "content": "docker run -v /custom_addons:/mnt/addons"},
        ])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Docker mount")
        self.assertEqual(result[0]["occurrence_count"], 3)
        self.assertIn("docker", result[0]["tags"])

    def test_detect_patterns_returns_empty_on_unparseable_response(self):
        """detect_patterns returns [] when LLM response is not valid JSON."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = "not json at all"

        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([
            {"role": "user", "content": "hello"},
        ])
        self.assertEqual(result, [])

    def test_detect_patterns_returns_empty_when_no_patterns_found(self):
        """detect_patterns returns [] when LLM finds no recurring patterns."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({"patterns": []})

        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([
            {"role": "user", "content": "unique one-off task"},
        ])
        self.assertEqual(result, [])

    def test_detect_patterns_filters_incomplete_patterns(self):
        """detect_patterns skips patterns missing title or description."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "patterns": [
                {"title": "", "description": "no title"},
                {"title": "Has title", "description": ""},
                {"title": "Complete", "description": "valid pattern", "tags": ["ok"]},
            ]
        })

        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([
            {"role": "user", "content": "test"},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Complete")

    def test_detect_patterns_handles_llm_exception(self):
        """detect_patterns returns [] when LLM raises an exception."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.side_effect = Exception("LLM error")

        evolver = SkillEvolver(llm)
        result = evolver.detect_patterns([
            {"role": "user", "content": "test"},
        ])
        self.assertEqual(result, [])

    def test_detect_patterns_truncates_long_messages(self):
        """_build_session_summary truncates long message content."""
        long_content = "x" * 1000
        summary = SkillEvolver._build_session_summary([
            {"role": "user", "content": long_content},
        ])
        self.assertIn("...", summary)
        self.assertLess(len(summary), 1000)


class TestSkillEvolverClassifyPattern(unittest.TestCase):
    """Tests for pattern classification phase."""

    def test_classify_returns_skip_when_llm_disabled(self):
        """classify_pattern returns skip when LLM is a no-op."""
        llm = MagicMock()
        llm.is_noop = True
        evolver = SkillEvolver(llm)
        result = evolver.classify_pattern({"title": "test", "description": "test"})
        self.assertEqual(result["action"], "skip")

    def test_classify_returns_create_for_new_pattern(self):
        """classify_pattern returns create when no existing skills match."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "action": "create",
            "reason": "no similar skill exists",
            "title": "New Skill",
            "description": "A brand new skill",
            "tags": ["new"],
            "procedure": {
                "prerequisites": ["setup"],
                "steps": [{"index": 1, "action": "do X", "expected": "success"}],
                "pitfalls": [],
            },
        })

        skill_store = MagicMock()
        skill_store.search.return_value = []

        evolver = SkillEvolver(llm, skill_store=skill_store)
        result = evolver.classify_pattern({
            "title": "New Pattern",
            "description": "A recurring pattern",
        })

        self.assertEqual(result["action"], "create")
        self.assertEqual(result["title"], "New Skill")
        self.assertIn("procedure", result)

    def test_classify_returns_update_for_existing_skill(self):
        """classify_pattern returns update when existing skill should be updated."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "action": "update",
            "skill_id": 42,
            "reason": "new pitfalls discovered",
            "new_steps": [{"index": 3, "action": "new step", "expected": "ok"}],
            "new_pitfalls": [{"error": "timeout", "cause": "slow API", "fix": "retry"}],
        })

        skill_store = MagicMock()
        skill_store.search.return_value = [
            {"id": 42, "title": "Existing Skill", "description": "old desc", "score": 0.9}
        ]

        evolver = SkillEvolver(llm, skill_store=skill_store)
        result = evolver.classify_pattern({
            "title": "Existing Skill",
            "description": "updated version",
        })

        self.assertEqual(result["action"], "update")
        self.assertEqual(result["skill_id"], 42)
        self.assertEqual(len(result["new_steps"]), 1)

    def test_classify_returns_skip_when_pattern_already_covered(self):
        """classify_pattern returns skip when pattern is already fully covered."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "action": "skip",
            "reason": "already covered by skill 5",
        })

        skill_store = MagicMock()
        skill_store.search.return_value = [
            {"id": 5, "title": "Covering Skill", "description": "covers it", "score": 0.95}
        ]

        evolver = SkillEvolver(llm, skill_store=skill_store)
        result = evolver.classify_pattern({
            "title": "Same thing",
            "description": "already done",
        })

        self.assertEqual(result["action"], "skip")

    def test_classify_attaches_skill_id_from_search_when_missing(self):
        """classify_pattern attaches skill_id from search results when LLM omits it."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({
            "action": "update",
            "reason": "new steps",
            "new_steps": [],
            "new_pitfalls": [],
        })

        skill_store = MagicMock()
        skill_store.search.return_value = [
            {"id": 99, "title": "Found Skill", "description": "match", "score": 0.8}
        ]

        evolver = SkillEvolver(llm, skill_store=skill_store)
        result = evolver.classify_pattern({
            "title": "Found Skill",
            "description": "match",
        })

        self.assertEqual(result["action"], "update")
        self.assertEqual(result["skill_id"], 99)

    def test_classify_handles_llm_exception(self):
        """classify_pattern returns skip on LLM exception."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.side_effect = Exception("LLM error")

        evolver = SkillEvolver(llm)
        result = evolver.classify_pattern({"title": "test", "description": "test"})
        self.assertEqual(result["action"], "skip")

    def test_classify_returns_skip_on_unparseable_response(self):
        """classify_pattern returns skip on unparseable LLM response."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = "garbage"

        evolver = SkillEvolver(llm)
        result = evolver.classify_pattern({"title": "test", "description": "test"})
        self.assertEqual(result["action"], "skip")

    def test_classify_uses_embedder_for_search(self):
        """classify_pattern uses embedder to generate query embedding."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({"action": "skip", "reason": "test"})

        embedder = MagicMock()
        embedder.embed.return_value = [0.1, 0.2, 0.3]

        skill_store = MagicMock()
        skill_store.search.return_value = []

        evolver = SkillEvolver(llm, skill_store=skill_store, embedder=embedder)
        evolver.classify_pattern({
            "title": "Test Pattern",
            "description": "Test description",
        })

        embedder.embed.assert_called_once()
        skill_store.search.assert_called_once()
        call_kwargs = skill_store.search.call_args
        self.assertIsNotNone(call_kwargs.kwargs.get("query_embedding") or call_kwargs[1].get("query_embedding"))


class TestSkillEvolverEvolve(unittest.TestCase):
    """Tests for the full evolve pipeline."""

    def test_evolve_returns_empty_when_llm_disabled(self):
        """evolve returns [] when LLM is a no-op."""
        llm = MagicMock()
        llm.is_noop = True
        evolver = SkillEvolver(llm)
        result = evolver.evolve([{"role": "user", "content": "test"}])
        self.assertEqual(result, [])

    def test_evolve_returns_empty_when_no_patterns_detected(self):
        """evolve returns [] when no patterns are detected."""
        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.return_value = json.dumps({"patterns": []})

        evolver = SkillEvolver(llm)
        result = evolver.evolve([{"role": "user", "content": "unique task"}])
        self.assertEqual(result, [])

    def test_evolve_returns_proposals_for_detected_patterns(self):
        """evolve returns proposals for patterns that are not skipped."""
        # First call: detect_patterns
        # Second call: classify_pattern
        detect_response = json.dumps({
            "patterns": [
                {"title": "Pattern A", "description": "desc A", "tags": ["tag1"]},
                {"title": "Pattern B", "description": "desc B", "tags": ["tag2"]},
            ]
        })

        classify_responses = [
            json.dumps({
                "action": "create",
                "title": "New Skill A",
                "description": "skill for A",
                "tags": ["tag1"],
                "procedure": {"prerequisites": [], "steps": [], "pitfalls": []},
            }),
            json.dumps({"action": "skip", "reason": "already exists"}),
        ]

        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.side_effect = [detect_response] + classify_responses

        skill_store = MagicMock()
        skill_store.search.return_value = []

        evolver = SkillEvolver(llm, skill_store=skill_store)
        result = evolver.evolve([{"role": "user", "content": "recurring task"}])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["action"], "create")
        self.assertEqual(result[0]["title"], "New Skill A")

    def test_evolve_filters_skip_proposals(self):
        """evolve only returns non-skip proposals."""
        detect_response = json.dumps({
            "patterns": [
                {"title": "Skip me", "description": "will be skipped"},
                {"title": "Create me", "description": "will be created"},
            ]
        })

        classify_responses = [
            json.dumps({"action": "skip", "reason": "already covered"}),
            json.dumps({
                "action": "create",
                "title": "New Skill",
                "description": "new",
                "tags": [],
                "procedure": {},
            }),
        ]

        llm = MagicMock()
        llm.is_noop = False
        llm.generate_response.side_effect = [detect_response] + classify_responses

        evolver = SkillEvolver(llm, skill_store=MagicMock())
        evolver.skill_store.search.return_value = []

        result = evolver.evolve([{"role": "user", "content": "test"}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["action"], "create")


class TestSkillEvolverHelpers(unittest.TestCase):
    """Tests for internal helper methods."""

    def test_build_session_summary_filters_system_messages(self):
        """_build_session_summary excludes system messages."""
        summary = SkillEvolver._build_session_summary([
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "user message"},
        ])
        self.assertNotIn("system prompt", summary)
        self.assertIn("user message", summary)

    def test_build_session_summary_returns_none_for_empty(self):
        """_build_session_summary returns None for empty input."""
        self.assertIsNone(SkillEvolver._build_session_summary([]))

    def test_build_session_summary_returns_none_for_system_only(self):
        """_build_session_summary returns None when only system messages exist."""
        self.assertIsNone(
            SkillEvolver._build_session_summary([
                {"role": "system", "content": "system"},
            ])
        )

    def test_build_session_summary_caps_message_count(self):
        """_build_session_summary limits to max_messages."""
        messages = [
            {"role": "user", "content": f"message {i}"}
            for i in range(100)
        ]
        summary = SkillEvolver._build_session_summary(messages, max_messages=10)
        # Should only include the last 10 messages
        self.assertIn("message 99", summary)
        self.assertNotIn("message 5", summary)

    def test_format_existing_skills_empty(self):
        """_format_existing_skills returns placeholder for empty list."""
        result = SkillEvolver._format_existing_skills([])
        self.assertIn("no existing", result.lower())

    def test_format_existing_skills_formats_entries(self):
        """_format_existing_skills formats skill entries with id and title."""
        skills = [
            {"id": 1, "title": "Skill A", "description": "desc A", "tags": ["t1"], "score": 0.9},
        ]
        result = SkillEvolver._format_existing_skills(skills)
        self.assertIn("id=1", result)
        self.assertIn("Skill A", result)
        self.assertIn("desc A", result)

    def test_parse_patterns_strips_think_tags(self):
        """_parse_patterns handles <think> tags in LLM response."""
        from powermem.intelligence.skill_evolver import SkillEvolver
        response = "<think>reasoning</think>" + json.dumps({
            "patterns": [
                {"title": "Test", "description": "desc"},
            ]
        })
        result = SkillEvolver._parse_patterns(response)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Test")


if __name__ == "__main__":
    unittest.main()

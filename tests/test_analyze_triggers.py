"""
Unit tests for analyze_triggers.py
"""
import json
import tempfile
from pathlib import Path
import sys

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from analyze_triggers import check_skill_triggered, analyze_triggers


class TestCheckSkillTriggered:
    """Tests for the trigger detection logic."""

    def test_triggered_with_read_tool_call(self):
        """Should detect trigger when Read tool is called on SKILL.md."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolCall",
                        "name": "Read",
                        "arguments": {"path": "/path/to/weather/SKILL.md"}
                    }
                ]
            }
        ]
        assert check_skill_triggered(messages, "/path/to/weather/SKILL.md") is True

    def test_triggered_with_file_path_arg(self):
        """Should detect trigger with file_path argument variant."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolCall",
                        "name": "read",
                        "arguments": {"file_path": "/skills/weather/SKILL.md"}
                    }
                ]
            }
        ]
        assert check_skill_triggered(messages, "/skills/weather/SKILL.md") is True

    def test_not_triggered_no_skill_read(self):
        """Should return False when no skill is read."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolCall",
                        "name": "Read",
                        "arguments": {"path": "/some/other/file.md"}
                    }
                ]
            }
        ]
        assert check_skill_triggered(messages, "/path/to/weather/SKILL.md") is False

    def test_not_triggered_empty_messages(self):
        """Should return False for empty message list."""
        assert check_skill_triggered([], "/path/to/SKILL.md") is False

    def test_triggered_with_partial_path_match(self):
        """Should detect trigger when skill directory name appears in path."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolCall",
                        "name": "Read",
                        "arguments": {"path": "/opt/skills/weather/SKILL.md"}
                    }
                ]
            }
        ]
        assert check_skill_triggered(messages, "weather/SKILL.md") is True

    def test_triggered_weather_specific_wttr(self):
        """Should detect weather skill trigger via wttr.in usage."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "curl wttr.in/Singapore"
                    }
                ]
            }
        ]
        assert check_skill_triggered(messages, "/path/to/weather/SKILL.md") is True

    def test_string_content_wttr(self):
        """Should handle string content (not list)."""
        messages = [
            {
                "role": "assistant",
                "content": "Running curl wttr.in/London for weather"
            }
        ]
        assert check_skill_triggered(messages, "/path/to/weather/SKILL.md") is True


class TestAnalyzeTriggers:
    """Integration tests for the full analysis pipeline."""

    def test_full_analysis(self, tmp_path):
        """Test complete trigger analysis workflow."""
        # Create evals file
        evals_data = {
            "skill_name": "test-skill",
            "skill_path": "/test/SKILL.md",
            "evals": [
                {"id": 1, "query": "test query 1", "expected": True, "category": "positive"},
                {"id": 2, "query": "test query 2", "expected": False, "category": "negative"},
            ]
        }
        evals_file = tmp_path / "evals.json"
        evals_file.write_text(json.dumps(evals_data))

        # Create histories directory
        histories_dir = tmp_path / "histories"
        histories_dir.mkdir()

        # History 1: triggered (expected True -> correct)
        hist1 = {
            "eval_id": 1,
            "query": "test query 1",
            "expected": True,
            "messages": [
                {
                    "role": "assistant",
                    "content": [
                        {"type": "toolCall", "name": "Read", "arguments": {"path": "/test/SKILL.md"}}
                    ]
                }
            ]
        }
        (histories_dir / "eval-1.json").write_text(json.dumps(hist1))

        # History 2: not triggered (expected False -> correct)
        hist2 = {
            "eval_id": 2,
            "query": "test query 2",
            "expected": False,
            "messages": [
                {
                    "role": "assistant",
                    "content": "Just a text response, no tool calls"
                }
            ]
        }
        (histories_dir / "eval-2.json").write_text(json.dumps(hist2))

        # Output file
        output_file = tmp_path / "results.json"

        # Run analysis
        result = analyze_triggers(
            evals_file=str(evals_file),
            histories_dir=str(histories_dir),
            output_file=str(output_file),
        )

        # Check results
        assert result["skill_name"] == "test-skill"
        assert result["accuracy"] == 1.0  # Both correct
        assert result["recall"] == 1.0  # 1/1 positive triggered
        assert result["specificity"] == 1.0  # 1/1 negative not triggered
        assert result["total_queries"] == 2
        assert len(result["results"]) == 2

        # Check output file was written
        assert output_file.exists()
        saved = json.loads(output_file.read_text())
        assert saved["accuracy"] == 1.0

    def test_missing_history_file(self, tmp_path):
        """Should handle missing history files gracefully."""
        evals_data = {
            "skill_name": "test-skill",
            "evals": [
                {"id": 1, "query": "test", "expected": True},
                {"id": 999, "query": "missing", "expected": True},  # No history file
            ]
        }
        evals_file = tmp_path / "evals.json"
        evals_file.write_text(json.dumps(evals_data))

        histories_dir = tmp_path / "histories"
        histories_dir.mkdir()

        # Only create history for eval-1
        hist1 = {"eval_id": 1, "query": "test", "expected": True, "messages": []}
        (histories_dir / "eval-1.json").write_text(json.dumps(hist1))

        output_file = tmp_path / "results.json"

        result = analyze_triggers(
            evals_file=str(evals_file),
            histories_dir=str(histories_dir),
            output_file=str(output_file),
        )

        assert result["total_queries"] == 1  # Only 1 processed
        assert 999 in result["missing_histories"]

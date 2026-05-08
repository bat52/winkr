"""Tests for the winkr benchmark module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from llm_agent_toolkit.benchmark import (
    BenchmarkResult,
    FlowMeasurement,
    FlowType,
    TokenSnapshot,
    capture_cline_task_history_tokens,
    capture_litellm_tokens,
    compare,
    estimate_tokens_from_chars,
    render_report,
)


# ---------------------------------------------------------------------------
# Token parsers
# ---------------------------------------------------------------------------


class TestCaptureLitellmTokens:
    def test_typical(self) -> None:
        stderr = (
            "Model: openrouter/google/gemini-2.5-flash Cost: $0.00 Tokens: 450/220\n"
        )
        snapshots = capture_litellm_tokens(stderr)
        assert len(snapshots) == 1
        s = snapshots[0]
        assert s.prompt_tokens == 450
        assert s.completion_tokens == 220
        assert s.total_tokens == 670
        assert s.source == "litellm"
        assert s.model == "openrouter/google/gemini-2.5-flash"

    def test_multiple_calls(self) -> None:
        stderr = (
            "Model: gpt-4 Cost: $0.01 Tokens: 100/50\n"
            "Model: claude-3 Cost: $0.02 Tokens: 200/100\n"
        )
        snapshots = capture_litellm_tokens(stderr)
        assert len(snapshots) == 2
        assert snapshots[0].prompt_tokens == 100
        assert snapshots[0].completion_tokens == 50
        assert snapshots[1].prompt_tokens == 200
        assert snapshots[1].completion_tokens == 100

    def test_empty_stderr(self) -> None:
        assert capture_litellm_tokens("") == []

    def test_no_token_line(self) -> None:
        stderr = "Some random error message\n"
        assert capture_litellm_tokens(stderr) == []

    def test_partial_line(self) -> None:
        stderr = "Model: gpt-4 Cost: $0.01 Tokens: abc/def\n"
        assert capture_litellm_tokens(stderr) == []


class TestCaptureClineTaskHistoryTokens:
    def test_typical(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()

            history_path = Path(tmpdir) / "taskHistory.json"
            history_path.write_text(
                json.dumps([
                    {
                        "id": "task1",
                        "cwdOnTaskInitialization": str(repo_path),
                        "tokensIn": 500,
                        "tokensOut": 200,
                        "totalCost": 0.01,
                        "modelId": "deepseek-chat",
                    },
                ]),
                encoding="utf-8",
            )

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            assert len(snapshots) == 1
            s = snapshots[0]
            assert s.prompt_tokens == 500
            assert s.completion_tokens == 200
            assert s.total_tokens == 700
            assert s.source == "cline_task_history"
            assert s.model == "deepseek-chat"

    def test_multiple_tasks_same_repo_returns_first(self) -> None:
        """With multiple tasks for the same repo, returns only the first match."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()

            history_path = Path(tmpdir) / "taskHistory.json"
            history_path.write_text(
                json.dumps([
                    {
                        "id": "task1",
                        "cwdOnTaskInitialization": str(repo_path),
                        "tokensIn": 100,
                        "tokensOut": 50,
                        "totalCost": 0.01,
                        "modelId": "deepseek-chat",
                    },
                    {
                        "id": "task2",
                        "cwdOnTaskInitialization": str(repo_path),
                        "tokensIn": 200,
                        "tokensOut": 100,
                        "totalCost": 0.02,
                        "modelId": "deepseek-chat",
                    },
                ]),
                encoding="utf-8",
            )

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            # Only returns the first matching task
            assert len(snapshots) == 1
            assert snapshots[0].prompt_tokens == 100
            assert snapshots[0].completion_tokens == 50

    def test_different_repo_not_matched(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()
            other_repo = Path(tmpdir) / "other"
            other_repo.mkdir()

            history_path = Path(tmpdir) / "taskHistory.json"
            history_path.write_text(
                json.dumps([
                    {
                        "id": "task1",
                        "cwdOnTaskInitialization": str(other_repo),
                        "tokensIn": 100,
                        "tokensOut": 50,
                        "totalCost": 0.01,
                    },
                ]),
                encoding="utf-8",
            )

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            assert snapshots == []

    def test_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()
            history_path = Path(tmpdir) / "nonexistent.json"

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            assert snapshots == []

    def test_empty_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()

            history_path = Path(tmpdir) / "taskHistory.json"
            history_path.write_text("[]", encoding="utf-8")

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            assert snapshots == []

    def test_missing_token_fields_default_to_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "repo"
            repo_path.mkdir()

            history_path = Path(tmpdir) / "taskHistory.json"
            history_path.write_text(
                json.dumps([
                    {
                        "id": "task1",
                        "cwdOnTaskInitialization": str(repo_path),
                    },
                ]),
                encoding="utf-8",
            )

            snapshots = capture_cline_task_history_tokens(
                repo_path, task_history_path=history_path
            )
            assert len(snapshots) == 1
            assert snapshots[0].prompt_tokens == 0
            assert snapshots[0].completion_tokens == 0
            assert snapshots[0].total_tokens == 0


# ---------------------------------------------------------------------------
# estimate_tokens_from_chars
# ---------------------------------------------------------------------------


class TestEstimateTokensFromChars:
    def test_typical(self) -> None:
        text = "Hello, world! This is a test."
        # 31 chars // 4 = 7 tokens
        assert estimate_tokens_from_chars(text) == 7

    def test_empty(self) -> None:
        assert estimate_tokens_from_chars("") == 0

    def test_short_text(self) -> None:
        assert estimate_tokens_from_chars("ab") == 0  # 2 // 4 = 0


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


class TestCompare:
    def test_identical_diffs(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[
                TokenSnapshot(100, 50, 150, "litellm"),
                TokenSnapshot(200, 100, 300, "cline_task_history"),
            ],
            wall_clock_seconds=10.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[
                TokenSnapshot(300, 150, 450, "cline_task_history"),
            ],
            wall_clock_seconds=8.0,
            git_diff_stat="main.py | 5 +++--",
        )

        result = compare(flow_a, flow_b)
        assert result.same_diff is True
        assert result.delta_prompt_tokens == 0  # 300 - (100 + 200) = 0
        assert result.delta_completion_tokens == 0  # 150 - (50 + 100) = 0
        assert result.delta_total_tokens == 0  # 450 - 450 = 0
        assert result.delta_percent == 0.0

    def test_different_diffs(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[TokenSnapshot(100, 50, 150, "litellm")],
            wall_clock_seconds=5.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(200, 100, 300, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="utils.py | 10 ++++++++--",
        )

        result = compare(flow_a, flow_b)
        assert result.same_diff is False
        assert result.delta_total_tokens == 150  # 300 - 150

    def test_flow_b_uses_more_tokens(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[TokenSnapshot(100, 50, 150, "litellm")],
            wall_clock_seconds=5.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(500, 250, 750, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="main.py | 5 +++--",
        )

        result = compare(flow_a, flow_b)
        assert result.same_diff is True
        assert result.delta_total_tokens == 600
        assert result.delta_percent == 400.0  # (750-150)/150 * 100

    def test_zero_tokens_in_flow_a(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[],
            wall_clock_seconds=0.0,
            git_diff_stat="",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(100, 50, 150, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="",
        )

        result = compare(flow_a, flow_b)
        assert result.delta_percent == 0.0  # no division by zero


# ---------------------------------------------------------------------------
# render_report
# ---------------------------------------------------------------------------


class TestRenderReport:
    def test_basic(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[
                TokenSnapshot(100, 50, 150, "litellm"),
                TokenSnapshot(200, 100, 300, "cline_task_history"),
            ],
            wall_clock_seconds=10.5,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(300, 150, 450, "cline_task_history")],
            wall_clock_seconds=8.2,
            git_diff_stat="main.py | 5 +++--",
        )
        result = BenchmarkResult(
            task_description="Extract greet() to utils.py",
            cline_aider=flow_a,
            cline_only=flow_b,
        )

        report = render_report(result)

        # Check key sections are present
        assert "# Token Efficiency Benchmark Report" in report
        assert "Extract greet() to utils.py" in report
        assert "Flow A: Cline + Aider" in report
        assert "Flow B: Cline only" in report
        assert "Comparison" in report
        assert "Diff stats" in report
        assert "Verdict" in report

        # Check token values appear
        assert "450" in report  # flow_a total
        assert "450" in report  # flow_b total
        assert "10.5" in report  # flow_a wall clock
        assert "8.2" in report  # flow_b wall clock

    def test_different_diffs_verdict(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[TokenSnapshot(100, 50, 150, "litellm")],
            wall_clock_seconds=5.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(200, 100, 300, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="utils.py | 10 ++++++++--",
        )
        result = BenchmarkResult(
            task_description="test",
            cline_aider=flow_a,
            cline_only=flow_b,
        )

        report = render_report(result)
        assert "produced different outputs" in report
        assert "not meaningful" in report

    def test_aider_wins_verdict(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[TokenSnapshot(100, 50, 150, "litellm")],
            wall_clock_seconds=5.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(500, 250, 750, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="main.py | 5 +++--",
        )
        result = BenchmarkResult(
            task_description="test",
            cline_aider=flow_a,
            cline_only=flow_b,
        )

        report = render_report(result)
        assert "Cline+Aider used fewer tokens" in report
        assert "pays off" in report

    def test_cline_only_wins_verdict(self) -> None:
        flow_a = FlowMeasurement(
            flow="cline_aider",
            steps=[TokenSnapshot(500, 250, 750, "litellm")],
            wall_clock_seconds=5.0,
            git_diff_stat="main.py | 5 +++--",
        )
        flow_b = FlowMeasurement(
            flow="cline_only",
            steps=[TokenSnapshot(100, 50, 150, "cline_task_history")],
            wall_clock_seconds=4.0,
            git_diff_stat="main.py | 5 +++--",
        )
        result = BenchmarkResult(
            task_description="test",
            cline_aider=flow_a,
            cline_only=flow_b,
        )

        report = render_report(result)
        assert "Cline-only used fewer tokens" in report
        assert "does not pay off" in report

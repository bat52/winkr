"""Tests for the winkr enforcer module."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from llm_agent_toolkit.enforcer import (
    CommitOrigin,
    EnforcerResult,
    _parse_touched_files,
    check_commits,
    check_pending_changes,
    detect_commit_origin,
)


# ---------------------------------------------------------------------------
# CommitOrigin enum
# ---------------------------------------------------------------------------


class TestCommitOrigin:
    def test_values(self) -> None:
        assert CommitOrigin.AIDER == "aider"
        assert CommitOrigin.CLINE_DIRECT == "cline_direct"
        assert CommitOrigin.MANUAL == "manual"
        assert CommitOrigin.UNKNOWN == "unknown"

    def test_is_str_enum(self) -> None:
        assert str(CommitOrigin.AIDER) == "aider"


# ---------------------------------------------------------------------------
# EnforcerResult dataclass
# ---------------------------------------------------------------------------


class TestEnforcerResult:
    def test_defaults(self) -> None:
        r = EnforcerResult(passed=True)
        assert r.passed is True
        assert r.commit_author is None
        assert r.reason == ""
        assert r.stats == {}

    def test_full_construction(self) -> None:
        r = EnforcerResult(
            passed=False,
            commit_author=CommitOrigin.CLINE_DIRECT,
            reason="Direct edit detected.",
            stats={"violations": 1},
        )
        assert r.passed is False
        assert r.commit_author == CommitOrigin.CLINE_DIRECT
        assert r.reason == "Direct edit detected."
        assert r.stats == {"violations": 1}

    def test_is_frozen(self) -> None:
        r = EnforcerResult(passed=True)
        with pytest.raises(AttributeError):
            r.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _parse_touched_files
# ---------------------------------------------------------------------------


class TestParseTouchedFiles:
    def test_typical_diff_stat(self) -> None:
        diff = (
            " src/foo.py | 2 +-\n"
            " src/bar.py | 5 ++++-\n"
            " README.md  | 1 +\n"
        )
        result = _parse_touched_files(diff)
        assert result == {"src/foo.py", "src/bar.py", "README.md"}

    def test_empty_diff_stat(self) -> None:
        assert _parse_touched_files("") == set()

    def test_no_pipe_lines(self) -> None:
        diff = " 1 file changed, 1 insertion(+)"
        assert _parse_touched_files(diff) == set()

    def test_leading_spaces(self) -> None:
        diff = "  foo.py | 1 +"
        result = _parse_touched_files(diff)
        assert result == {"foo.py"}


# ---------------------------------------------------------------------------
# detect_commit_origin
# ---------------------------------------------------------------------------


def _mock_subprocess_run(side_effects: list[dict]) -> list:
    """Build a list of mock return values for subprocess.run.

    Each dict in ``side_effects`` should have keys ``stdout`` and
    optionally ``returncode`` (default 0).
    """
    results = []
    for se in side_effects:
        mock = _make_mock(se.get("stdout", ""), se.get("returncode", 0))
        results.append(mock)
    return results


def _make_mock(stdout: str, returncode: int = 0) -> object:
    m = type("Mock", (), {})()
    m.stdout = stdout
    m.returncode = returncode
    return m


class TestDetectCommitOrigin:
    def test_aider_message_prefix(self) -> None:
        """Commit message starting with 'aider: ' should be AIDER."""
        mocks = _mock_subprocess_run([
            {"stdout": "aider: Add new feature\n"},
            {"stdout": " src/foo.py | 2 +-\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.AIDER

    def test_aider_diff_pattern_in_message(self) -> None:
        """Commit message containing '--- a/' should be AIDER."""
        mocks = _mock_subprocess_run([
            {"stdout": "fix: --- a/foo.py\n"},
            {"stdout": " src/foo.py | 2 +-\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.AIDER

    def test_cline_direct_winkr_managed_file(self) -> None:
        """Touching .clinerules without Aider message should be CLINE_DIRECT."""
        mocks = _mock_subprocess_run([
            {"stdout": "update rules\n"},
            {"stdout": " .clinerules | 10 ++++++++--\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.CLINE_DIRECT

    def test_cline_direct_short_message_many_files(self) -> None:
        """Short message with >2 files should be CLINE_DIRECT."""
        mocks = _mock_subprocess_run([
            {"stdout": "fix stuff\n"},
            {"stdout": " src/a.py | 1 +\n src/b.py | 1 +\n src/c.py | 1 +\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.CLINE_DIRECT

    def test_manual_descriptive_message(self) -> None:
        """Descriptive message with >=5 words should be MANUAL."""
        mocks = _mock_subprocess_run([
            {"stdout": "Fix the login bug in the auth module\n"},
            {"stdout": " src/auth.py | 2 +-\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.MANUAL

    def test_unknown_fallback(self) -> None:
        """Short message with 1 file and no other signals should be UNKNOWN."""
        mocks = _mock_subprocess_run([
            {"stdout": "wip\n"},
            {"stdout": " src/foo.py | 1 +\n"},
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            result = detect_commit_origin("abc1234")
            assert result == CommitOrigin.UNKNOWN


# ---------------------------------------------------------------------------
# check_pending_changes
# ---------------------------------------------------------------------------


class TestCheckPendingChanges:
    def test_no_staged_changes(self) -> None:
        mock = _make_mock("", 0)
        with patch.object(subprocess, "run", return_value=mock):
            result = check_pending_changes()
            assert result.passed is True
            assert "No staged changes" in result.reason

    def test_clean_staged_changes(self) -> None:
        mock = _make_mock(" src/foo.py | 2 +-\n", 0)
        with patch.object(subprocess, "run", return_value=mock):
            result = check_pending_changes()
            assert result.passed is True
            assert "no policy violations" in result.reason

    def test_violation_on_winkr_managed_file(self) -> None:
        mock = _make_mock(" .clinerules | 10 ++++++++--\n", 0)
        with patch.object(subprocess, "run", return_value=mock):
            result = check_pending_changes()
            assert result.passed is False
            assert ".clinerules" in result.reason
            assert "Direct edit" in result.reason


# ---------------------------------------------------------------------------
# check_commits
# ---------------------------------------------------------------------------


class TestCheckCommits:
    def test_empty_range(self) -> None:
        mock = _make_mock("", 0)
        with patch.object(subprocess, "run", return_value=mock):
            result = check_commits(commit_range="")
            assert len(result) == 1
            assert result[0].passed is True

    def test_single_aider_commit(self) -> None:
        mocks = _mock_subprocess_run([
            {"stdout": "deadbeef\n"},           # git log for range
            {"stdout": "aider: Add feature\n"},  # git log for commit msg
            {"stdout": " src/foo.py | 2 +-\n"},  # git diff
        ])
        with patch.object(subprocess, "run", side_effect=mocks):
            results = check_commits(commit_range="HEAD~1..HEAD")
            assert len(results) == 1
            assert results[0].passed is True
            assert results[0].commit_author == CommitOrigin.AIDER

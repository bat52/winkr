"""Token efficiency benchmarking for winkr orchestration flows.

Compares token consumption between:
- Flow A (Cline + Aider): Cline orchestrates, Aider mutates via ``winkr change``
- Flow B (Cline only): Cline handles everything directly

Token data is captured from:
- Cline's task history JSON file (``~/.cline/data/state/taskHistory.json``)
- litellm stderr output (Aider's LLM calls, for Flow A)
"""

from __future__ import annotations

import argparse
import enum
import json
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_CLINE_TASK_HISTORY = Path.home() / ".cline" / "data" / "state" / "taskHistory.json"
_DEFAULT_TIMEOUT = 600  # seconds; Flow A (Cline+Aider) can take 5+ minutes


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class FlowType(enum.StrEnum):
    """Which orchestration flow is being measured."""

    CLINE_AIDER = "cline_aider"
    CLINE_ONLY = "cline_only"


@dataclass(frozen=True)
class TokenSnapshot:
    """Token usage from a single LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    source: str  # "litellm", "cline_task_history", "chars_estimate"
    model: str | None = None


@dataclass
class FlowMeasurement:
    """Aggregated measurement for one flow execution."""

    flow: str  # "cline_aider" or "cline_only"
    steps: list[TokenSnapshot] = field(default_factory=list)
    wall_clock_seconds: float = 0.0
    git_diff_stat: str = ""
    total_cost: float = 0.0
    cache_writes: int = 0
    cache_reads: int = 0
    context_size: int = 0  # bytes
    used_winkr_change: bool = False
    """Whether Flow A's stderr contained the [WINKR-CHANGE] marker."""

    @property
    def total_prompt_tokens(self) -> int:
        return sum(s.prompt_tokens for s in self.steps)

    @property
    def total_completion_tokens(self) -> int:
        return sum(s.completion_tokens for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.steps)


@dataclass
class BenchmarkResult:
    """Comparison result between two flows."""

    task_description: str
    cline_aider: FlowMeasurement
    cline_only: FlowMeasurement

    @property
    def delta_prompt_tokens(self) -> int:
        return self.cline_only.total_prompt_tokens - self.cline_aider.total_prompt_tokens

    @property
    def delta_completion_tokens(self) -> int:
        return (
            self.cline_only.total_completion_tokens
            - self.cline_aider.total_completion_tokens
        )

    @property
    def delta_total_tokens(self) -> int:
        return self.cline_only.total_tokens - self.cline_aider.total_tokens

    @property
    def delta_percent(self) -> float:
        if self.cline_aider.total_tokens == 0:
            return 0.0
        return (self.delta_total_tokens / self.cline_aider.total_tokens) * 100

    @property
    def same_diff(self) -> bool:
        return self.cline_aider.git_diff_stat == self.cline_only.git_diff_stat


# ---------------------------------------------------------------------------
# Token parsers
# ---------------------------------------------------------------------------

# litellm output pattern (on stderr):
#   Model: openrouter/google/gemini-2.5-flash Cost: $0.00 Tokens: 450/220
_LITELLM_TOKEN_RE = re.compile(
    r"Model:\s+(?P<model>\S+)\s+Cost:\s+\S+\s+Tokens:\s+(?P<prompt>\d+)/(?P<completion>\d+)"
)


def capture_litellm_tokens(stderr: str) -> list[TokenSnapshot]:
    """Parse litellm token usage lines from Aider's stderr output.

    litellm prints one line per LLM call on stderr in the format:
        Model: <name> Cost: $<cost> Tokens: <prompt>/<completion>
    """
    snapshots: list[TokenSnapshot] = []
    for match in _LITELLM_TOKEN_RE.finditer(stderr):
        prompt = int(match.group("prompt"))
        completion = int(match.group("completion"))
        snapshots.append(
            TokenSnapshot(
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=prompt + completion,
                source="litellm",
                model=match.group("model"),
            )
        )
    return snapshots


def _find_task_record(
    repo_path: Path,
    task_history_path: Path = _CLINE_TASK_HISTORY,
) -> dict | None:
    """Find the Cline task history record matching the given repo path.

    Returns the raw task dict, or ``None`` if no match is found.
    """
    if not task_history_path.exists():
        return None

    try:
        data = json.loads(task_history_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(data, list):
        return None

    repo_str = str(repo_path.resolve())
    for task in data:
        if task.get("cwdOnTaskInitialization", "") == repo_str:
            return task
    return None


def capture_cline_task_history_tokens(
    repo_path: Path,
    task_history_path: Path = _CLINE_TASK_HISTORY,
) -> list[TokenSnapshot]:
    """Read token usage from Cline's task history JSON file.

    Cline stores per-task token data in ``taskHistory.json``. Each task
    record includes ``tokensIn``, ``tokensOut``, ``totalCost``, and
    ``cwdOnTaskInitialization``. We match tasks by their working directory
    to the fixture repo path.

    Parameters
    ----------
    repo_path:
        The fixture repo path used as ``cwdOnTaskInitialization``.
    task_history_path:
        Path to Cline's task history JSON file.

    Returns
    -------
    list[TokenSnapshot]
        Token snapshots for tasks that ran in the given repo path.
    """
    task = _find_task_record(repo_path, task_history_path)
    if task is None:
        return []

    tokens_in = task.get("tokensIn", 0) or 0
    tokens_out = task.get("tokensOut", 0) or 0
    model = task.get("modelId", None)

    return [
        TokenSnapshot(
            prompt_tokens=int(tokens_in),
            completion_tokens=int(tokens_out),
            total_tokens=int(tokens_in) + int(tokens_out),
            source="cline_task_history",
            model=model,
        )
    ]


def estimate_tokens_from_chars(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return len(text) // 4


# ---------------------------------------------------------------------------
# WINKR-CHANGE marker detection
# ---------------------------------------------------------------------------


_WINKR_CHANGE_MARKER = "[WINKR-CHANGE]"


def check_winkr_change_marker(stderr: str) -> bool:
    """Check if stderr contains the [WINKR-CHANGE] marker.

    The marker is printed by ``winkr change`` to stderr when it delegates
    a mutation to Aider. If present, it confirms that Cline actually used
    ``winkr change`` instead of editing files directly.

    Parameters
    ----------
    stderr:
        The stderr output from the Cline invocation.

    Returns
    -------
    bool
        True if the marker was found in stderr.
    """
    return _WINKR_CHANGE_MARKER in stderr


# ---------------------------------------------------------------------------
# Fixture repository
# ---------------------------------------------------------------------------

_FIXTURE_MAIN_PY = """\
def greet(name: str) -> str:
    \"\"\"Return a greeting for the given name.\"\"\"
    return f"Hello, {name}!"


def farewell(name: str) -> str:
    \"\"\"Return a farewell for the given name.\"\"\"
    return f"Goodbye, {name}!"


def format_message(template: str, name: str) -> str:
    \"\"\"Format a message template with the given name.\"\"\"
    return template.replace("{name}", name)


def main() -> None:
    \"\"\"Main entry point.\"\"\"
    print(greet("World"))
    print(farewell("World"))
    print(format_message("Welcome, {name}!", "World"))


if __name__ == "__main__":
    main()
"""

_PERMISSIVE_CLINERULES = """\
# Permissive rules for Cline-only benchmark flow.
# Cline is allowed to edit files directly.

## --- Orchestrator (Cline) ---
## Allowed: shell commands, file reads/writes, git, test execution.
## NOT allowed: inline patch generation, monolithic refactors.
"""


def _winkr_clinerules() -> str:
    """Return the current winkr .clinerules content from the package."""
    from .rules import load_base_rules

    return load_base_rules()


def create_fixture_repo(path: Path, flow: FlowType) -> Path:
    """Create a temporary git repo with a known starting state.

    Parameters
    ----------
    path:
        Directory to initialise the repo in (must exist and be empty).
    flow:
        Which flow this repo is for — determines the ``.clinerules`` file.

    Returns
    -------
    Path
        The repo root (same as ``path``).
    """
    # Initialise git repo
    subprocess.run(
        ("git", "init"),
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )

    # Write fixture source file
    main_py = path / "main.py"
    main_py.write_text(_FIXTURE_MAIN_PY, encoding="utf-8")

    # Write .clinerules based on flow type
    clinerules = path / ".clinerules"
    if flow == FlowType.CLINE_AIDER:
        clinerules.write_text(_winkr_clinerules(), encoding="utf-8")
    else:
        clinerules.write_text(_PERMISSIVE_CLINERULES, encoding="utf-8")

    # Configure git user for the fixture repo
    for key, value in (("user.name", "benchmark"), ("user.email", "benchmark@test")):
        subprocess.run(
            ("git", "config", key, value),
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )

    # Initial commit
    subprocess.run(
        ("git", "add", "-A"),
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ("git", "commit", "-m", "initial state"),
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )

    return path


# ---------------------------------------------------------------------------
# Flow runners
# ---------------------------------------------------------------------------


def run_cline_with_task(
    repo_path: Path, task: str, timeout: int = _DEFAULT_TIMEOUT
) -> tuple[int, str, str]:
    """Run Cline CLI with a given task in the repo directory.

    Cline CLI accepts the prompt as a positional argument. We use
    ``--act`` (act mode) and ``--yolo`` (auto-approve) for
    non-interactive execution.

    Parameters
    ----------
    repo_path:
        Working directory for Cline.
    task:
        The task description to pass to Cline.
    timeout:
        Maximum wall-clock seconds to wait for Cline to finish.

    Returns
    -------
    tuple[int, str, str]
        (exit_code, stdout, stderr)
    """
    cmd = ("npx", "cline", "--act", "--yolo", task)
    try:
        completed = subprocess.run(
            cmd,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (124, "", f"TIMEOUT after {timeout}s")

    return (completed.returncode, completed.stdout, completed.stderr)


def _get_diff_stat(repo_path: Path) -> str:
    """Return ``git diff --stat HEAD`` for the repo."""
    result = subprocess.run(
        ("git", "diff", "--stat", "HEAD"),
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def _extract_task_meta(
    repo_path: Path,
    task_history_path: Path = _CLINE_TASK_HISTORY,
) -> dict:
    """Extract cost/cache/size metadata from the matching task record."""
    task = _find_task_record(repo_path, task_history_path)
    if task is None:
        return {"total_cost": 0.0, "cache_writes": 0, "cache_reads": 0, "context_size": 0}
    return {
        "total_cost": task.get("totalCost", 0.0) or 0.0,
        "cache_writes": task.get("cacheWrites", 0) or 0,
        "cache_reads": task.get("cacheReads", 0) or 0,
        "context_size": task.get("size", 0) or 0,
    }


def run_flow_a(repo_path: Path, task: str) -> FlowMeasurement:
    """Run Flow A (Cline + Aider) and measure token consumption.

    Sets up a fixture repo with the full winkr ``.clinerules`` so Cline
    must delegate mutations to Aider via ``winkr change``.
    """
    create_fixture_repo(repo_path, FlowType.CLINE_AIDER)

    start = time.monotonic()
    exit_code, stdout, stderr = run_cline_with_task(repo_path, task)
    elapsed = time.monotonic() - start

    # Parse token data from litellm (Aider's stderr) and Cline's task history
    steps: list[TokenSnapshot] = []
    steps.extend(capture_litellm_tokens(stderr))
    steps.extend(capture_cline_task_history_tokens(repo_path))

    diff_stat = _get_diff_stat(repo_path)
    meta = _extract_task_meta(repo_path)
    used_winkr_change = check_winkr_change_marker(stderr)

    return FlowMeasurement(
        flow="cline_aider",
        steps=steps,
        wall_clock_seconds=elapsed,
        git_diff_stat=diff_stat,
        used_winkr_change=used_winkr_change,
        **meta,
    )


def run_flow_b(repo_path: Path, task: str) -> FlowMeasurement:
    """Run Flow B (Cline only) and measure token consumption.

    Sets up a fixture repo with a permissive ``.clinerules`` so Cline
    can edit files directly.
    """
    create_fixture_repo(repo_path, FlowType.CLINE_ONLY)

    start = time.monotonic()
    exit_code, stdout, stderr = run_cline_with_task(repo_path, task)
    elapsed = time.monotonic() - start

    # Parse token data from Cline's task history
    steps = capture_cline_task_history_tokens(repo_path)
    diff_stat = _get_diff_stat(repo_path)
    meta = _extract_task_meta(repo_path)

    return FlowMeasurement(
        flow="cline_only",
        steps=steps,
        wall_clock_seconds=elapsed,
        git_diff_stat=diff_stat,
        **meta,
    )


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare(
    flow_a: FlowMeasurement, flow_b: FlowMeasurement
) -> BenchmarkResult:
    """Compare two flow measurements and produce a ``BenchmarkResult``."""
    return BenchmarkResult(
        task_description="benchmark task",
        cline_aider=flow_a,
        cline_only=flow_b,
    )


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_report(result: BenchmarkResult) -> str:
    """Render a ``BenchmarkResult`` as a Markdown report."""
    lines = [
        "# Token Efficiency Benchmark Report",
        "",
        f"**Task**: {result.task_description}",
        "",
        "## Flow A: Cline + Aider",
        f"- Total tokens: {result.cline_aider.total_tokens:,} "
        f"(prompt: {result.cline_aider.total_prompt_tokens:,} / "
        f"completion: {result.cline_aider.total_completion_tokens:,})",
        f"- Wall clock: {result.cline_aider.wall_clock_seconds:.1f} seconds",
        f"- Steps: {len(result.cline_aider.steps)} LLM calls",
        f"- Cost: ${result.cline_aider.total_cost:.4f}",
        f"- Cache writes: {result.cline_aider.cache_writes:,} / "
        f"reads: {result.cline_aider.cache_reads:,}",
        f"- Context size: {result.cline_aider.context_size:,} bytes",
        f"- Used ``winkr change``: "
        f"{'Yes' if result.cline_aider.used_winkr_change else 'No'}",
        "",
        "## Flow B: Cline only",
        f"- Total tokens: {result.cline_only.total_tokens:,} "
        f"(prompt: {result.cline_only.total_prompt_tokens:,} / "
        f"completion: {result.cline_only.total_completion_tokens:,})",
        f"- Wall clock: {result.cline_only.wall_clock_seconds:.1f} seconds",
        f"- Steps: {len(result.cline_only.steps)} LLM calls",
        f"- Cost: ${result.cline_only.total_cost:.4f}",
        f"- Cache writes: {result.cline_only.cache_writes:,} / "
        f"reads: {result.cline_only.cache_reads:,}",
        f"- Context size: {result.cline_only.context_size:,} bytes",
        "",
        "## Comparison",
        f"- Delta (B - A): {result.delta_total_tokens:+,} tokens "
        f"({result.delta_percent:+.1f}%)",
        f"- Same output diff: {'Yes' if result.same_diff else 'No'}",
        "",
        "## Diff stats",
        "```",
        f"Flow A (Cline+Aider): {result.cline_aider.git_diff_stat}",
        f"Flow B (Cline only):  {result.cline_only.git_diff_stat}",
        "```",
        "",
    ]

    # Verdict
    # delta = flow_b.total - flow_a.total
    # delta < 0  → flow_b (Cline-only) used fewer tokens
    # delta > 0  → flow_a (Cline+Aider) used fewer tokens
    if result.same_diff:
        if result.delta_total_tokens < 0:
            lines.append(
                "**Verdict**: Cline-only used fewer tokens for the same output. "
                "The multi-agent overhead does not pay off for this task."
            )
        elif result.delta_total_tokens > 0:
            lines.append(
                "**Verdict**: Cline+Aider used fewer tokens for the same output. "
                "The multi-agent overhead pays off."
            )
        else:
            lines.append(
                "**Verdict**: Both flows used the same number of tokens."
            )
    else:
        lines.append(
            "**Verdict**: The two flows produced different outputs — "
            "direct comparison is not meaningful."
        )

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the benchmark CLI."""
    parser = argparse.ArgumentParser(
        prog="winkr-benchmark",
        description="Benchmark token efficiency of winkr orchestration flows.",
    )
    parser.add_argument(
        "--task",
        default="Extract the greet() and farewell() functions from main.py into a new file utils.py",
        help="Task description to run through both flows.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=1,
        help="Number of times to run each flow (for statistical significance).",
    )
    parser.add_argument(
        "--output-dir",
        default="./benchmark_results",
        help="Directory to write benchmark reports to.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the benchmark."""
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Benchmark task: {args.task}")
    print(f"Iterations: {args.iterations}")
    print()

    for i in range(args.iterations):
        print(f"--- Iteration {i + 1}/{args.iterations} ---")

        # Flow A: Cline + Aider
        print("  Running Flow A (Cline + Aider)...")
        with tempfile.TemporaryDirectory(prefix="winkr-bench-a-") as tmpdir:
            flow_a = run_flow_a(Path(tmpdir), args.task)
        print(
            f"    Done: {flow_a.total_tokens:,} tokens in "
            f"{flow_a.wall_clock_seconds:.1f}s "
            f"({len(flow_a.steps)} steps)"
        )

        # Flow B: Cline only
        print("  Running Flow B (Cline only)...")
        with tempfile.TemporaryDirectory(prefix="winkr-bench-b-") as tmpdir:
            flow_b = run_flow_b(Path(tmpdir), args.task)
        print(
            f"    Done: {flow_b.total_tokens:,} tokens in "
            f"{flow_b.wall_clock_seconds:.1f}s "
            f"({len(flow_b.steps)} steps)"
        )

        # Compare
        result = compare(flow_a, flow_b)
        result.task_description = args.task

        # Render and save report
        report = render_report(result)
        report_path = output_dir / f"benchmark-{i + 1:03d}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"  Report saved to {report_path}")
        print()

        # Print summary
        print(render_report(result))
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

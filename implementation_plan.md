# Implementation Plan

Create a token efficiency benchmarking framework that measures and compares token consumption between winkr's Cline+Aider orchestration flow and a Cline-only flow, so the team can make data-driven decisions about workflow architecture.

Winkr's multi-agent architecture splits work across model tiers: Cline (Orchestrator) handles planning/reasoning, and Aider (Mutation Agent) handles code changes via `winkr change`. This introduces overhead — two LLM calls per mutation cycle instead of one — but may save tokens overall by keeping each agent's context window focused. Currently there is no instrumentation to verify this hypothesis. The benchmark fills that gap by running identical code-change tasks through both flows, capturing token usage from litellm (for Aider) and Cline's CLI stderr (for Cline), optionally validating against OpenRouter's API metadata, and generating a comparison report. The benchmark is self-contained: it creates a temporary git repo, runs both flows against a standardized refactoring task, and tears down cleanly.

[Types]
Two new dataclasses for benchmark results and one new dataclass for individual flow measurements.

New dataclass `TokenSnapshot`:
- `prompt_tokens: int` — number of tokens in the prompt (input)
- `completion_tokens: int` — number of tokens in the completion (output)
- `total_tokens: int` — sum of prompt and completion
- `source: str` — where this came from ("litellm", "cline_stderr", "openrouter_api", "chars_estimate")
- `model: str | None` — model name if known (e.g., "openrouter/google/gemini-2.5-flash")

New dataclass `FlowMeasurement`:
- `flow: str` — "cline_aider" or "cline_only"
- `steps: list[TokenSnapshot]` — sequential snapshots captured during execution
- `total_prompt_tokens: int` — aggregated across all steps
- `total_completion_tokens: int` — aggregated across all steps
- `total_tokens: int` — aggregated across all steps
- `wall_clock_seconds: float` — elapsed real time
- `git_diff_stat: str` — diff stat of the final commit (lines changed, files touched)

New dataclass `BenchmarkResult`:
- `task_description: str` — description of the benchmark task
- `cline_aider: FlowMeasurement` — results from Flow A
- `cline_only: FlowMeasurement` — results from Flow B
- `delta_prompt_tokens: int` — cline_only - cline_aider (positive means Cline-only used more)
- `delta_completion_tokens: int` — same for completion
- `delta_total_tokens: int` — same for total
- `delta_percent: float` — (cline_only - cline_aider) / cline_aider * 100
- `same_diff: bool` — whether both flows produced the same git diff

Also new enum `FlowType`:
- `CLINE_AIDER` — Cline orchestrates, Aider mutates
- `CLINE_ONLY` — Cline does everything

[Files]
Three new files and modifications to one configuration file; no deletions.

Detailed breakdown:
- New files:
    - `src/llm_agent_toolkit/benchmark.py` (~250 lines): Core benchmarking module containing `TokenSnapshot`, `FlowMeasurement`, `BenchmarkResult`, `FlowType`, plus:
      - `capture_litellm_tokens(stderr: str) -> list[TokenSnapshot]` — parses litellm "Tokens: X/Y" output from Aider stderr
      - `capture_cline_tokens(stderr: str) -> list[TokenSnapshot]` — parses Cline's "[model] tokens: X input, Y output" lines from stderr
      - `run_flow_a(bench_dir: Path, task: str) -> FlowMeasurement` — sets up repo with winkr .clinerules, runs Cline with task, captures all stderr, parses token data
      - `run_flow_b(bench_dir: Path, task: str) -> FlowMeasurement` — sets up repo without .clinerules (or permissive rules), runs Cline with same task, captures stderr
      - `compare(flow_a: FlowMeasurement, flow_b: FlowMeasurement) -> BenchmarkResult` — computes deltas and validates diff equivalence
      - `render_report(result: BenchmarkResult) -> str` — generates a Markdown comparison report
      - The module also contains a `main()` entry point that accepts `--task`, `--iterations`, `--output-dir`

    - `scripts/benchmark.sh` (~100 lines): Shell wrapper that:
      1. Creates a temporary directory
      2. Initializes a git repo with a known starting state (a small test Python file with a class that needs refactoring)
      3. Creates a fixture `.clinerules` for Flow A (the current winkr rules) and a permissive `.clinerules` for Flow B (allows direct edits)
      4. Calls `python -m llm_agent_toolkit.benchmark --task "$TASK" --output-dir "$OUTPUT"`
      5. Prints the report and cleans up temporary files
      6. Accepts `--iterations N` to run multiple times for statistical significance

    - `tests/test_benchmark.py` (~120 lines): Unit tests for token parsers and report rendering:
      - `test_capture_litellm_tokens_typical()` — parses a realistic litellm stderr string
      - `test_capture_litellm_tokens_empty()` — handles empty stderr
      - `test_capture_cline_tokens_typical()` — parses Cline's token log lines
      - `test_capture_cline_tokens_empty()` — handles empty stderr
      - `test_compare_same_diff()` — verifies correct delta computation when diffs match
      - `test_compare_different_diff()` — verifies `same_diff=False` is flagged

- Existing files to be modified:
    - `pyproject.toml` (+~1 line): Add `[project.scripts]` entry for `winkr-benchmark = "llm_agent_toolkit.benchmark:main"` (optional, for convenience)
    - `README.md` (+~25 lines): Add a new "Benchmark" section after the existing "Development" section documenting the benchmark feature, usage instructions, and a placeholder for results that will be filled in after running the benchmark.

[Functions]
Primarily new functions in a new module; no modifications to existing functions.

Detailed breakdown:
- New functions in `src/llm_agent_toolkit/benchmark.py`:
    - `capture_litellm_tokens(stderr: str) -> list[TokenSnapshot]` — Uses regex to find litellm's token output pattern. litellm typically prints: `Model: <name> Cost: $<cost> Tokens: <prompt>/<completion>` on stderr. Extracts prompt_tokens, completion_tokens, total_tokens. Returns a list (one per LLM call).
    
    - `capture_cline_tokens(stderr: str) -> list[TokenSnapshot]` — Uses regex to find Cline's token output pattern. Cline CLI prints something like: `[model] tokens: <prompt> input, <completion> output` on stderr. Returns a list of snapshots.
    
    - `estimate_tokens_from_chars(text: str) -> int` — Returns `len(text) // 4` as a rough estimate. Used as a fallback when structured data is unavailable (e.g., for Cline's internal planning tokens that aren't explicitly logged).
    
    - `create_fixture_repo(path: Path, flow: FlowType) -> Path` — Creates a temporary git repo with a known starting state:
      - A small Python file with a class that needs refactoring (e.g., a large function that should be extracted into a module)
      - For `CLINE_AIDER`: writes the current `.clinerules` from winkr
      - For `CLINE_ONLY`: writes a permissive `.clinerules` that allows direct edits (just the agent role definitions without the mutation policy)
      - Initial empty commit
      - Returns the repo path
    
    - `run_cline_with_task(repo_path: Path, task: str) -> tuple[int, str, str]` — Runs Cline CLI in non-interactive mode (`npx cline --message "$task"`) in the repo directory. Captures stdout and stderr separately. Returns (exit_code, stdout, stderr).
    
    - `run_flow_a(repo_path: Path, task: str) -> FlowMeasurement` — 
      1. Calls `create_fixture_repo(repo_path, CLINE_AIDER)`
      2. Calls `run_cline_with_task(repo_path, task)` 
      3. Parses all stderr for litellm token data (Aider's output) AND Cline's own token data
      4. Runs `git diff --stat HEAD` to capture the change
      5. Returns `FlowMeasurement` with all captured token snapshots and timing
    
    - `run_flow_b(repo_path: Path, task: str) -> FlowMeasurement` —
      1. Calls `create_fixture_repo(repo_path, CLINE_ONLY)`
      2. Calls `run_cline_with_task(repo_path, task)`
      3. Parses stderr for Cline's token data only
      4. Runs `git diff --stat HEAD`
      5. Returns `FlowMeasurement`
    
    - `compare(flow_a: FlowMeasurement, flow_b: FlowMeasurement) -> BenchmarkResult` —
      - Computes delta values (Flow B - Flow A)
      - Compares git diff stats to determine if both flows produced equivalent changes
      - Returns `BenchmarkResult` with all comparison data
    
    - `render_report(result: BenchmarkResult) -> str` — Generates a formatted Markdown report:
      ```markdown
      # Token Efficiency Benchmark Report
      
      **Task**: <task description>
      
      ## Flow A: Cline + Aider
      - Total tokens: XX,XXX (prompt: XX,XXX / completion: XX,XXX)
      - Wall clock: XX.X seconds
      - Steps: X LLM calls
      
      ## Flow B: Cline only
      - Total tokens: XX,XXX (prompt: XX,XXX / completion: XX,XXX)
      - Wall clock: XX.X seconds
      - Steps: X LLM calls
      
      ## Comparison
      - Delta (B - A): +X,XXX tokens (+XX.X%)
      - Same output diff: Yes/No
      
      ## Verdict
      <conclusion based on data>
      ```
    
    - `main()` — CLI entry point. Parses `--task`, `--iterations` (default 1), `--output-dir` (default ./benchmark_results). Runs the benchmark loop, aggregates results, and writes the report.

- New functions in `scripts/benchmark.sh`:
    - (Shell script) Sets up environment, validates dependencies (cline, winkr, aider), creates temp workspace, calls the Python benchmark module and handles output.

[Classes]
No new classes; two new dataclasses and one enum.

Detailed breakdown:
- `TokenSnapshot` (dataclass) in `src/llm_agent_toolkit/benchmark.py`:
  Fields: `prompt_tokens: int`, `completion_tokens: int`, `total_tokens: int`, `source: str`, `model: str | None`

- `FlowMeasurement` (dataclass) in `src/llm_agent_toolkit/benchmark.py`:
  Fields: `flow: str`, `steps: list[TokenSnapshot]`, `total_prompt_tokens: int` (computed), `total_completion_tokens: int` (computed), `total_tokens: int` (computed), `wall_clock_seconds: float`, `git_diff_stat: str`

- `BenchmarkResult` (dataclass) in `src/llm_agent_toolkit/benchmark.py`:
  Fields: `task_description: str`, `cline_aider: FlowMeasurement`, `cline_only: FlowMeasurement`, `delta_prompt_tokens: int` (computed), `delta_completion_tokens: int` (computed), `delta_total_tokens: int` (computed), `delta_percent: float` (computed), `same_diff: bool`

- `FlowType` (enum.StrEnum) in `src/llm_agent_toolkit/benchmark.py`:
  Values: `CLINE_AIDER = "cline_aider"`, `CLINE_ONLY = "cline_only"`

[Dependencies]
No new external Python packages. Uses only standard library: `re`, `subprocess`, `shutil`, `tempfile`, `time`, `dataclasses`, `enum`, `pathlib`, `textwrap`, `json`, `argparse`, `sys`.

The benchmark shell scripts rely on standard POSIX tools: `git`, `npx`, `winkr`, `python3`. These should already be present in a winkr development environment.

Testing dependencies: `pytest` (already in dev dependencies).

[Testing]
One new test file for the token parsers and comparison logic; existing tests must pass unchanged.

- New file `tests/test_benchmark.py`:
  - `test_capture_litellm_tokens_typical()` — Input: a realistic litellm stderr string like:
    ```
    Model: openrouter/google/gemini-2.5-flash Cost: $0.00 Tokens: 450/220
    ```
    Verifies: `TokenSnapshot(prompt_tokens=450, completion_tokens=220, total_tokens=670, source="litellm", model="openrouter/google/gemini-2.5-flash")`.
  
  - `test_capture_litellm_tokens_multiple_calls()` — Multiple LLM calls in one stderr string; verifies multiple snapshots are returned.
  
  - `test_capture_litellm_tokens_empty()` — Empty stderr returns empty list.
  
  - `test_capture_cline_tokens_typical()` — Input: realistic Cline stderr lines with token info:
    ```
    [model] tokens: 1250 input, 340 output
    ```
    Verifies parsing is correct.
  
  - `test_capture_cline_tokens_empty()` — Empty stderr returns empty list.
  
  - `test_compare_identical_diffs()` — Two FlowMeasurements with same diff stat; verifies `same_diff=True` and correct delta computation.
  
  - `test_compare_different_diffs()` — Two FlowMeasurements with different diff stats; verifies `same_diff=False`.
  
  - `test_render_report_basic()` — Smoke test: renders a BenchmarkResult and verifies key sections are present.

[Implementation Order]
All changes are additive; implementation order prioritizes token parsers (most testable) first, then flow runners, then the orchestration script.

1. Create `src/llm_agent_toolkit/benchmark.py` — implement `TokenSnapshot`, `FlowMeasurement`, `BenchmarkResult`, `FlowType`, `capture_litellm_tokens()`, `capture_cline_tokens()`, `estimate_tokens_from_chars()`, and `render_report()`. These are pure functions with no external dependencies and are the most testable in isolation.

2. Create `tests/test_benchmark.py` — write unit tests for the pure parsing and rendering functions from step 1. Run tests to verify correctness.

3. Extend `src/llm_agent_toolkit/benchmark.py` — implement `create_fixture_repo()`, `run_cline_with_task()`, `run_flow_a()`, `run_flow_b()`, and `compare()`. These involve subprocess and file system operations.

4. Add unit tests in `tests/test_benchmark.py` for `compare()` logic (which is deterministic). The subprocess-heavy functions (`run_flow_a`, `run_flow_b`, `create_fixture_repo`) are tested implicitly via integration runs.

5. Update `pyproject.toml` — add optional `winkr-benchmark` script entry point.

6. Create `scripts/benchmark.sh` — the shell orchestration wrapper. Test manually by running the benchmark against a small task.

7. Run a manual benchmark on a real task (e.g., "Extract the helper functions from enforcer.py into a new module enforcer_utils.py") to validate that both flows complete and token data is captured. Tweak regex patterns as needed for real-world stderr formats.

Token cost estimates per step:
1. Create benchmark.py core (pure functions) ~250 lines → ~6,000 tokens
2. Create test_benchmark.py ~120 lines → ~3,500 tokens  
3. Extend benchmark.py (flow runners) +~150 lines → ~5,000 tokens
4. Extend tests +~40 lines → ~1,500 tokens
5. Update pyproject.toml ~5 lines → ~500 tokens
6. Create benchmark.sh ~100 lines → ~2,000 tokens
7. Manual validation run → ~1,000 tokens (test execution)

**Total estimated: ~19,500 tokens**
(Variance: ±30% depending on iteration for stderr format adaptation.)

[Verification]
The benchmark is considered working when:
- `scripts/benchmark.sh --task "extract the greet() function from main.py into utils.py"` completes both flows successfully
- Output contains a Markdown report with token counts for both flows and a delta comparison
- Both flows produce a git commit with equivalent diff output (same files changed, same logical transformation)

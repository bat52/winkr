# Implementation Plan

Add an Architect Agent role to the winkr rules system, backed by `aider --architect`, along with a `winkr architect` CLI subcommand that wraps the aider architect feature and pipeline orchestration that integrates architecture planning into the existing workflow blocks.

The architect agent role enables a two-phase coding workflow: first an architect model generates a plan (using `--architect`), then an editor model implements it. This replaces or augments the current flat PLAN_CHANGE→IMPLEMENT_CHANGE workflow for complex tasks. The implementation adds: (1) a new `winkr architect` CLI subcommand wrapping `aider --architect`, (2) an Architect Agent role definition in `.clinerules` and `clinerules.base.md`, (3) a new ARCHITECT_PLAN workflow block in the rules, (4) updates to the existing PLAN_CHANGE and IMPLEMENT_CHANGE workflows to delegate architecture steps to the architect agent, (5) token tracking extensions for architect/coding agent token reporting, and (6) updates to the task lifecycle documentation.

[Types]
Two new supporting types added to `aider.py`.

New dataclass `AiderCommand` already exists (frozen). Adding a new function `build_architect_command()` that returns an `AiderCommand` with `--architect` flag.

New enum variant or function: No new enums needed. The `FlowType` concept is in `.clinerules` as workflow names, not in Python code. No Python-level enums needed.

[Files]
Seven files modified, two new files created.

New files:
- `tests/test_architect.py` (~80 lines): Unit tests for `build_architect_command()`, CLI `handle_architect()` logic, and parser construction for the `architect` subcommand.

Existing files to be modified:
1. `src/llm_agent_toolkit/aider.py` (~+15 lines): Add `build_architect_command()` function.
2. `src/llm_agent_toolkit/cli.py` (~+40 lines): Add `winkr architect` subcommand parser and `handle_architect()` handler.
3. `src/llm_agent_toolkit/rules/clinerules.base.md` (~+45 lines): Add Architect Agent role definition, add ARCHITECT_PLAN workflow block, update PLAN_CHANGE and IMPLEMENT_CHANGE workflows, update intent classification, update architecture diagram.
4. `src/llm_agent_toolkit/config.py` (~+2 lines): Add optional `TIER_ARCHITECT` model tier mapping.
5. `.clinerules` (generated from clinerules.base.md, ~+45 lines): Same changes as clinerules.base.md (the `.clinerules` is generated, not committed).
6. `tests/test_cli.py` (~+20 lines): Add test for `winkr architect` subcommand in `test_build_parser`.
7. `tests/test_aider.py` (~+20 lines): Add tests for `build_architect_command()`.

No deletions. No files moved.

[Functions]
Primarily new functions in existing modules; no removals.

New functions:
- `build_architect_command(prompt: str, api_key: ResolvedApiKey, model: str | None = None, files: Sequence[str] = (), extra_args: Sequence[str] = ()) -> AiderCommand` in `src/llm_agent_toolkit/aider.py`:
  Builds an aider command with `--architect` flag. Uses TIER_REASONING model as default (for the architect), and passes `--editor-model` mapped to TIER_CODING. Signature mirrors `build_change_command()` but adds `--architect` and `--editor-model` to the argv.

- `handle_architect(args: argparse.Namespace) -> int` in `src/llm_agent_toolkit/cli.py`:
  Handles the `winkr architect` subcommand. Validates prompt, resolves API key, builds architect command via `build_architect_command()`, optionally logs, optionally prints command, then runs via `run_command()`. Returns 0 on success.

Modified functions:
- `build_parser()` in `src/llm_agent_toolkit/cli.py` (~+15 lines): Add `architect` subparser with `add_common_aider_args()`, `prompt`, `files`, `--allow-dirty`, and a `--model` argument that defaults to `TIER_REASONING` (unlike `change` which defaults to `TIER_CODING`).

[Classes]
No new classes. The `AiderCommand` frozen dataclass in `aider.py` is reused as-is.

[Architect Agent Role — .clinerules additions]
The following sections need to be added to `clinerules.base.md`:

1. **Architecture diagram update**: Add Architect Agent branch:
   ```
   ##   Orchestrator (Cline)
   ##     ├── Planner Agent        (TIER_REASONING)
   ##     ├── Architect Agent      (TIER_REASONING → aider --architect)
   ##     ├── Repo Intelligence    (depwire MCP)
   ##     ├── Reasoning Agent      (TIER_REASONING)
   ##     ├── Mutation Agent       (Aider + TIER_CODING)
   ##     └── Fast Query Agent     (TIER_FAST)
   ```

2. **New Agent Role section** in section 1:
   ```
   ## --- Architect Agent ---
   ## Responsibility: Generate architecture plans for complex changes using
   ##   aider's architect edit format.
   ## Allowed: `winkr architect` invocation.
   ## NOT allowed: code mutation, file changes, tool execution.
   ## Input: Architecture plan markdown file path + scope description.
   ## Output: Git commit with architecture plan document.
   ```

3. **New model tier config**: `TIER_ARCHITECT` in config.py mapped to `openrouter/google/gemini-2.5-flash` (same as TIER_REASONING by default, but independently configurable).

4. **New ARCHITECT_PLAN workflow block** in section 3:
   ```
   ## --- ARCHITECT_PLAN_WORKFLOW ---
   ## Purpose: Generate a detailed architecture plan before implementation.
   ## Trigger: Complex task requiring architecture approval before coding.
   ## Steps:
   ##   1. Orchestrator classifies intent → ARCHITECT_PLAN
   ##   2. Orchestrator creates architecture plan markdown file at
   ##      .winkr/task<no>_step<stepno>_architecture_plan.md
   ##   3. Orchestrator dispatches Architect Agent:
   ##      winkr architect --file .winkr/task<no>_step<stepno>_architecture_plan.md
   ##      --model TIER_ARCHITECT
   ##   4. Orchestrator evaluates architect output (committed plan doc)
   ##   5. Orchestrator compares actual token usage vs estimate
   ##   6. If delta > 25%, assess causes and propose rule improvements
   ##   7. Orchestrator may refine with more architect steps or proceed
   ##      to coding
   ##   8. For coding steps, dispatches Mutation Agent
   ##   Output: Architecture plan committed, then implemented code.
   ```

5. **Update PLAN_CHANGE_WORKFLOW** to reference architect for complex tasks:
   ```
   ##   3. Orchestrator dispatches Repo Intelligence Agent for
   ##      impact analysis (impact_analysis, get_dependents)
   ##   3b. If complexity is assessed as high, Orchestrator dispatches
   ##       Planner Agent to determine architect vs coding split
   ##   4. Orchestrator dispatches Reasoning Agent (TIER_REASONING) or
   ##      Architect Agent (winkr architect) to formulate strategy
   ```

6. **Update IMPLEMENT_CHANGE_WORKFLOW**:
   ```
   ##   2. Orchestrator selects next atomic change from plan
   ##   2b. If step requires architect oversight, Orchestrator dispatches
   ##       Architect Agent first, then Mutation Agent for implementation
   ```

7. **Update Intent Classification** in section 10:
   ```
   ## ARCHITECT_PLAN → ARCHITECT_PLAN_WORKFLOW → TIER_ARCHITECT
   ```

8. **Update section 2 (Model Tiers)** to add TIER_ARCHITECT.

[Dependencies]
No new external Python packages. Uses only existing dependencies: `aider` (must have `--architect` flag, already verified), `subprocess`, `argparse`, etc.

Testing dependencies: `pytest` (already in dev dependencies).

[Testing]
Existing tests must pass unchanged. New tests for architect command and CLI handler.

- New file `tests/test_architect.py`:
  - `test_build_architect_command_includes_architect_flag()` — Verifies `--architect` appears in argv.
  - `test_build_architect_command_default_model()` — Verifies default model resolves to TIER_REASONING.
  - `test_build_architect_command_editor_model()` — Verifies `--editor-model` is set to TIER_CODING.
  - `test_build_architect_command_includes_files()` — Verifies files are appended.
  - `test_handle_architect()` — Mocked test that verifies `build_architect_command` and `run_command` are called.

- Additions to `tests/test_aider.py`:
  - `test_build_architect_command_vs_change()` — Quick check that architect command differs from change command.

- Additions to `tests/test_cli.py`:
  - In `test_build_parser`: verify `architect` subcommand is present.
  - New `test_handle_architect` function (if not placed in test_architect.py).

[Implementation Order]
All changes are additive or additive to rule docs. Implementation order prioritizes the Python code (most testable), then the rules, then final integration.

1. **Add `build_architect_command()` to `aider.py`** (~+15 lines). This is the core Python change. Add the function following the existing pattern of `build_change_command()` but with `--architect` flag and `--editor-model` defaulting to TIER_CODING. Model default: `TIER_REASONING` (architect uses the strong model).

2. **Add `TIER_ARCHITECT` to `config.py`** (~+2 lines). Add `"TIER_ARCHITECT": "openrouter/google/gemini-2.5-flash"` to `MODEL_TIERS` dict. This is the same model as TIER_REASONING by default but independently configurable.

3. **Add `winkr architect` subcommand to `cli.py`** (~+40 lines). Add subparser with `add_common_aider_args()`, `prompt` (positional), `files` (optional nargs=*), `--allow-dirty`, and a `--model` defaulting to `TIER_REASONING`. Add `handle_architect()` that resolves API key, builds architect command, runs it.

4. **Create `tests/test_architect.py`** (~80 lines). Test `build_architect_command()` with multiple cases and `handle_architect()` with mocks. Run tests to verify.

5. **Add architect tests to `tests/test_aider.py`** (~+20 lines). Quick validation that architect command differs structurally from change command.

6. **Update `tests/test_cli.py`** (~+20 lines). Add parser test for architect subcommand existence.

7. **Update `clinerules.base.md`** (~+45 lines). Add Architect Agent role, ARCHITECT_PLAN_WORKFLOW, update intent classification, update architecture diagram, update model tiers. This is the rules documentation that the orchestration layer reads.

8. **Regenerate `.clinerules`** by running `winkr write-rules --force .clinerules`. Verify the output contains the new architect sections.

9. **Run all tests** to ensure nothing is broken: `python3 -m pytest`.

Token cost estimates per step:
1. `build_architect_command()` in aider.py (+15 lines) → ~500 tokens
2. `TIER_ARCHITECT` in config.py (+2 lines) → ~100 tokens
3. CLI subcommand + handler in cli.py (+40 lines) → ~1,200 tokens
4. `tests/test_architect.py` (~80 lines) → ~2,500 tokens
5. Additional tests in test_aider.py (+20 lines) → ~800 tokens
6. Parser test in test_cli.py (+20 lines) → ~600 tokens
7. clinerules.base.md updates (+45 lines) → ~1,500 tokens
8. Regenerate .clinerules + verify → ~100 tokens
9. Run all tests → ~200 tokens

**Total estimated: ~7,500 tokens**
(Variance: ±20% depending on iteration for test adjustments.)

[Verification]
The architect agent is considered working when:
- `winkr architect "draft a plan for refactoring enforcer.py"` builds a command with `--architect` flag and runs successfully.
- `aider --architect` (invoked via winkr) produces an architecture plan as a git commit.
- All 77+ existing tests pass plus new architect tests.
- `clinerules.base.md` contains the Architect Agent role definition and ARCHITECT_PLAN_WORKFLOW.
- The architecture diagram in `.clinerules` shows the Architect Agent branch.

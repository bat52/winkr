# AGENTS.md

## Package identity (easy to get wrong)

- **Import package**: `llm_agent_toolkit` (src/llm_agent_toolkit/)
- **Distributable name**: `winkr`
- **CLI commands**: `winkr`, `winkr query`, `winkr change`, `winkr-benchmark`
- **Entry points** defined in pyproject.toml `[project.scripts]`, wired to `llm_agent_toolkit.cli:main`

## Development commands

```bash
# Install in editable mode (creates console scripts for winkr, winkr-enforcer-hook, winkr-benchmark)
python3 -m pip install -e ".[dev]"

# Run all tests (PYTHONPATH=src is configured in pyproject.toml [tool.pytest.ini_options])
python3 -m pytest

# Compile-check (no formal linter or type checker configured)
python3 -m compileall src tests
```

## Architecture

- `cli.py` — argparse-based CLI with subcommands (query, change, write-rules, init, edit, browse, start, tmux, enforcer, tiers, git-setup)
- `config.py` — `MODEL_TIERS` dict mapping tier aliases (`TIER_REASONING`, `TIER_CODING`, `TIER_FAST`) to provider/model strings
- `credentials.py` — API key resolution chain: explicit arg → `OPENROUTER_API_KEY` → `AIDER_API_KEY` (legacy DeepSeek) → `~/.cline/data/secrets.json`
- `aider.py` — builds Aider CLI commands (query vs change), runs via subprocess
- `git_safety.py` — blocks `winkr change` on dirty worktree unless `--allow-dirty`
- `enforcer.py` — commit-origin detection (Aider, Cline-direct, manual), soft pre-commit hook
- `init_command.py` — `winkr init` installs aider, npm deps (cline, depwire-cli), init git, write `.clinerules`, install enforcer hook
- `benchmark.py` — token-efficiency benchmarking (CLI: `winkr-benchmark`)
- `rules.py` / `rules/clinerules.base.md` — bundled Cline rule template
- `commands.py` — `winkr edit` (editor launcher) and `winkr browse` (ranger/lf)
- `logging_utils.py` — writes prompt logs to `.ai_logs/`

## Key conventions

- **`from __future__ import annotations`** in every Python source and test file — required
- **All dataclasses are `frozen=True`**
- **Tests use `unittest.mock.patch`**, not pytest-mock
- **`.clinerules` is `.gitignore`d** — it's generated via `winkr write-rules`, never committed
- **`# noqa` in prompts is rejected** — `validate_prompt()` in `aider.py` raises `ValueError` if present
- **Node.js deps** (`depwire-cli`, `kilocode`) live in `package.json`; they are not Python deps but are used by the Cline orchestration layer, installed by `winkr init` or manually

## Configuration

- `pyproject.toml` controls the build (`setuptools`, `src` layout), pytest (`testpaths`, `pythonpath`), and console scripts
- No mypy/ruff/black config — only `compileall` for syntax validation
- No CI workflows in `.github/`

## Testing notes

- 77 collected test cases across 6 modules
- Tests mock `subprocess.run`, `Path`, and other external calls aggressively
- The `tests/` directory mirrors the module structure but flat (no nested packages)
- Run a single test file: `python3 -m pytest tests/test_cli.py`
- Run a single test: `python3 -m pytest tests/test_cli.py::test_handle_query`

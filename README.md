# winkr

`winkr` is a thrifty (in terms of tokens) reusable LLM multi-agent workflow toolkit.

It provides installable Python console commands for:

- Aider-backed read-only repository queries.
- Aider-backed code changes with dirty-worktree safeguards.
- Reusable model-tier aliases.
- Shared API-key discovery.
- Generating reusable orchestration rule templates (Cline, Kilocode, Claude).
- Optional orchestrator and tmux session helpers.

The Python import package remains `llm_agent_toolkit`, while the distributable
package name is `winkr`.

## Why “winkr”?

**Winkr** is inspired by the French expression *“clin d’œil”* (“wink”), a subtle signal of coordination and shared understanding.

The project began as an orchestration layer around Cline-based workflows, so the name also carries a small nod to its origins through the “clin” → “wink” association.

The trailing `r` gives the name a lightweight tooling feel suited for a CLI and automation-oriented project.

More broadly, the name reflects the philosophy behind Winkr:

* lightweight rather than monolithic
* coordinated rather than autonomous
* composable rather than opaque

Winkr is designed as an agent orchestration layer that combines planning, repository intelligence, model routing, and deterministic code mutation into a structured workflow.

## Installation

For isolated command-line use:

```bash
pipx install winkr
```

For local development:

```bash
git clone https://github.com/bat52/winkr.git
cd winkr
python -m pip install -e ".[dev]"
```

## Console commands

The package installs these commands:

```bash
winkr
winkr query
winkr change
winkr architect
winkr write-rules
winkr init
winkr edit
winkr browse
winkr start
winkr tmux
winkr tiers
winkr git-setup
winkr configure
winkr enforcer check
winkr enforcer block
winkr enforcer install-hooks
```

## Query a repository

```bash
winkr query "Explain the architecture of this project"
```

This runs Aider in a read-oriented mode and logs prompts under `.ai_logs/`.

## Change a repository

```bash
winkr change "Refactor this module to reduce duplication" src/example.py
```

By default, `change` refuses to run when the Git worktree is dirty. This protects
existing human changes.

Use `--allow-dirty` only when you intentionally want to let Aider operate on a
dirty worktree:

```bash
winkr change --allow-dirty "Update docs"
```

## Generate an architecture plan

```bash
winkr architect "Design a modular plugin system for the CLI"
```

This runs Aider in `--architect` mode, focusing on planning rather than
code mutation. Supports the same `--model`, `--api-key`, `--allow-dirty`,
and `--print-command` flags as `winkr change`.

## Print the Aider command without running it

```bash
winkr query --print-command "Summarize this repo"
winkr change --print-command "Rename this function" src/foo.py
```

## API-key discovery

Credential precedence is:

1. Explicit `--api-key`.
2. `OPENROUTER_API_KEY`.
3. `AIDER_API_KEY`, treated as a legacy DeepSeek key.
4. Cline's `~/.cline/data/secrets.json`, reading `deepSeekApiKey`.

Examples:

```bash
winkr query --api-key openrouter="$OPENROUTER_API_KEY" "Explain tests"
winkr change --api-key deepseek="$DEEPSEEK_API_KEY" "Fix lint"
```

If the explicit value does not include a provider prefix, it is treated as
`explicit:<value>` and passed through to Aider as-is.

## Model tiers

The default model tiers are:

| Tier | Model |
| --- | --- |
| `TIER_REASONING` | `openrouter/google/gemini-2.5-flash` |
| `TIER_CODING` | `openrouter/deepseek/deepseek-chat` |
| `TIER_FAST` | `openrouter/google/gemini-2.5-flash` |

You can use aliases or raw model names:

```bash
winkr query --model TIER_FAST "Summarize the package"
winkr change --model TIER_CODING "Make the CLI more robust"
winkr query --model openrouter/anthropic/claude-3.5-sonnet "Review this"
```

Print the current tier configuration:

```bash
winkr tiers
```

## Initialize a project environment

```bash
winkr init
```

Reads `.winkr/config.json` and sets up the project environment (depwire MCP
server, documentation symlinks, and project-specific configuration).

## Configure winkr

```bash
winkr configure
```

Interactively create or update `.winkr/config.json`, which stores the
orchestrator command name, model mappings, and project-level defaults.

## Configure Git for frictionless pushes

```bash
winkr git-setup
```

Generates an SSH key (if none exists), adds it to the SSH agent, and
configures the Git remote to use the SSH URL for the current repository.

## Enforce the mutation policy

The `winkr enforcer` commands ensure compliance with the winkr mutation
policy (all changes go through `winkr change`, not direct edits).

```bash
winkr enforcer block              # Pre-mutation gate — exits non-zero if violations exist
winkr enforcer check              # Check staged changes or a commit range
winkr enforcer install-hooks      # Install pre-commit hook for soft enforcement
```

## Generate orchestration rules

Write the reusable multi-agent orchestration rule template (compatible with
Cline, Kilocode, and Claude) to a file:

```bash
winkr write-rules .clinerules
```

Overwrite an existing file:

```bash
winkr write-rules .clinerules --force
```

## Start the orchestrator

The `winkr start` command runs the depwire MCP server setup, generates
documentation, and launches the configured orchestrator (read from
`.winkr/config.json`; defaults to `npx cline`).

It supports the following options:
- `--tui`: Starts the orchestrator in TUI mode (e.g. `--tui --auto-condense` for Cline).
- `--remote`: Enables remote access for tmux sessions.
- `--split`: Enables a dual-pane tmux session.

```bash
winkr start
```

Start in TUI mode:

```bash
winkr start --tui
```

Example with `--remote` and `--split`:

```bash
winkr start --tui --remote --split
```

## Optional tmux helper

```bash
winkr tmux
```

This opens a two-pane tmux session:

- top pane: `winkr start`
- bottom pane: shell

## Orchestrator chat shortcuts (`/edit` and `/browse`)

When the rules file (e.g. `.clinerules` for Cline) is present in your project (generated via `winkr write-rules`),
the orchestrator recognizes these shortcuts in the chat:

| In chat | What the orchestrator does |
|---|---|
| `/edit @<file>` | `winkr edit <file>` — opens file in your editor |
| `/browse` | `winkr browse .` — opens ranger in current directory |
| `/browse <path>` | `winkr browse <path>` — opens ranger at the given path |

These are custom shortcuts defined in the rules file that instruct the orchestrator to execute the corresponding
`winkr` command.

### `winkr edit`

Opens a file in your configured editor. It checks:

1. `$EDITOR` environment variable
2. VS Code (`code` command)
3. Falls back to `nano`

```bash
winkr edit src/llm_agent_toolkit/cli.py
```

### `winkr browse`

Opens a terminal file browser (default: `ranger`) at the given path.

```bash
winkr browse              # current directory
winkr browse src          # src/ directory
```

Override the browser with the `WINKR_BROWSER` environment variable:

```bash
export WINKR_BROWSER=lf   # use lf instead of ranger
```

## Compatibility shims for existing repositories

If an existing repo expects `llm/ai_query.sh` and `llm/ai_change.sh`, replace the
old scripts with thin shims:

```bash
#!/usr/bin/env bash
exec winkr query "$@"
```

and:

```bash
#!/usr/bin/env bash
exec winkr change "$@"
```
## Benchmark

`winkr` includes a token efficiency benchmarking framework that compares the
Cline+Aider orchestration flow against a Cline-only baseline.

### Usage

```bash
# Run the benchmark (requires npx, git, and a configured API key)
winkr-benchmark

# Custom task and iterations
winkr-benchmark --task "Refactor main.py into utils.py" --iterations 3

# Specify output directory
winkr-benchmark --output-dir ./my_benchmarks
```

Or via the shell wrapper:

```bash
./scripts/benchmark.sh
```

### How it works

1. **Flow A (Cline + Aider)**: Creates a fixture repo with the full winkr
   `.clinerules`, so Cline must delegate mutations to Aider via `winkr change`.
   Token data is captured from both litellm (Aider's stderr) and Cline's stderr.

2. **Flow B (Cline only)**: Creates a fixture repo with a permissive
   `.clinerules`, allowing Cline to edit files directly. Token data is captured
   from Cline's stderr only.

3. **Comparison**: The framework computes delta (B − A), percentage difference,
   checks whether both flows produced the same git diff, and generates a verdict.

### Report output

Reports are saved as Markdown files in the output directory
(`./benchmark_results/` by default). Each report includes:

- Token counts (prompt, completion, total) for both flows
- Wall-clock time
- Number of LLM call steps
- Delta and percentage comparison
- Diff equivalence check
- Verdict on whether the multi-agent overhead pays off

### Example report

```markdown
# Token Efficiency Benchmark Report

**Task**: Extract the greet() and farewell() functions from main.py into a new file utils.py

## Flow A: Cline + Aider
- Total tokens: 1,777 (prompt: 0 / completion: 1,777)
- Wall clock: 300.1 seconds
- Steps: 1 LLM calls
- Cost: $0.0242
- Cache writes: 26,425 / reads: 215,680
- Context size: 149,628 bytes

## Flow B: Cline only
- Total tokens: 1,001 (prompt: 0 / completion: 1,001)
- Wall clock: 336.8 seconds
- Steps: 1 LLM calls
- Cost: $0.0068
- Cache writes: 10,248 / reads: 41,472
- Context size: 33,994 bytes

## Comparison
- Delta (B - A): -776 tokens (-43.7%)
- Same output diff: No

## Diff stats
\`\`\`
Flow A (Cline+Aider):
Flow B (Cline only):  main.py | 9 +--------
 1 file changed, 1 insertion(+), 8 deletions(-)
\`\`\`

**Verdict**: The two flows produced different outputs — direct comparison is not meaningful.
```

## Development

Run tests:

```bash
python -m pytest
```

Compile-check source and tests:

```bash
python -m compileall src tests
```


# winkr

`winkr` is a thrifty (in terms of tokens) reusable LLM multi-agent workflow toolkit.

It provides installable Python console commands for:

- Aider-backed read-only repository queries.
- Aider-backed code edits with dirty-worktree safeguards.
- Reusable model-tier aliases.
- Shared API-key discovery.
- Generating reusable Cline rule templates.
- Optional Cline and tmux session helpers.

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
winkr-agent
winkr-query
winkr-edit
```

`winkr-query` and `winkr-edit` are compatibility entry points. They map to:

```bash
winkr-agent query
winkr-agent edit
```

## Query a repository

```bash
winkr-agent query "Explain the architecture of this project"
```

or:

```bash
winkr-query "Explain the architecture of this project"
```

This runs Aider in a read-oriented mode and logs prompts under `.ai_logs/`.

## Edit a repository

```bash
winkr-agent edit "Refactor this module to reduce duplication" src/example.py
```

or:

```bash
winkr-edit "Refactor this module to reduce duplication" src/example.py
```

By default, `edit` refuses to run when the Git worktree is dirty. This protects
existing human changes.

Use `--allow-dirty` only when you intentionally want to let Aider operate on a
dirty worktree:

```bash
winkr-agent edit --allow-dirty "Update docs"
```

## Print the Aider command without running it

```bash
winkr-agent query --print-command "Summarize this repo"
winkr-agent edit --print-command "Rename this function" src/foo.py
```

## API-key discovery

Credential precedence is:

1. Explicit `--api-key`.
2. `OPENROUTER_API_KEY`.
3. `AIDER_API_KEY`, treated as a legacy DeepSeek key.
4. Cline's `~/.cline/data/secrets.json`, reading `deepSeekApiKey`.

Examples:

```bash
winkr-agent query --api-key openrouter="$OPENROUTER_API_KEY" "Explain tests"
winkr-agent edit --api-key deepseek="$DEEPSEEK_API_KEY" "Fix lint"
```

If the explicit value does not include a provider prefix, it is treated as
`explicit:<value>` and passed through to Aider as-is.

## Model tiers

The default model tiers are:

| Tier | Model |
| --- | --- |
| `TIER_REASONING` | `openrouter/google/gemini-2.5-flash` |
| `TIER_CODING` | `openrouter/deepseek/deepseek-coder` |
| `TIER_FAST` | `openrouter/google/gemini-2.5-flash` |

You can use aliases or raw model names:

```bash
winkr-agent query --model TIER_FAST "Summarize the package"
winkr-agent edit --model TIER_CODING "Make the CLI more robust"
winkr-agent query --model openrouter/anthropic/claude-3.5-sonnet "Review this"
```

## Generate Cline rules

Write the reusable Cline rule template to `.clinerules`:

```bash
winkr-agent write-rules .clinerules
```

Overwrite an existing file:

```bash
winkr-agent write-rules .clinerules --force
```

## Optional Cline helper

```bash
winkr-agent cline-start
```

This runs:

```bash
npx cline
```

## Optional tmux helper

```bash
winkr-agent tmux
```

This opens a two-pane tmux session:

- top pane: `winkr-agent cline-start`
- bottom pane: shell

## Compatibility shims for existing repositories

If an existing repo expects `llm/ai_query.sh` and `llm/ai_edit.sh`, replace the
old scripts with thin shims:

```bash
#!/usr/bin/env bash
exec winkr-agent query "$@"
```

and:

```bash
#!/usr/bin/env bash
exec winkr-agent edit "$@"
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


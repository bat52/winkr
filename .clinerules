# winkr reusable Cline rules

These rules describe a reusable multi-agent workflow layer.

Project-specific architecture notes should live in a separate project overlay.

## Roles

### Cline orchestrator

Cline coordinates the work:

- Understand the user's request.
- Inspect relevant files.
- Create a short plan for non-trivial work.
- Delegate repository analysis to the query tool when useful.
- Delegate code mutation to the edit tool when the repository wants stricter
  Aider-based editing.
- Summarize what changed and what was tested.

### Reasoning/query agent

Use:

```bash
winkr-agent query "<question>"
```

or:

```bash
winkr-query "<question>"
```

for read-only analysis such as:

- explaining architecture,
- finding likely implementation locations,
- comparing approaches,
- planning a refactor,
- reviewing a failure log.

### Mutation/edit agent

Use:

```bash
winkr-agent edit "<instruction>" [files...]
```

or:

```bash
winkr-edit "<instruction>" [files...]
```

for code changes when the project prefers Aider-backed edits.

Do not run edit commands on a dirty worktree unless the user explicitly accepts
that risk or the command is invoked with `--allow-dirty`.

## Model tiers

The reusable tier names are:

- `TIER_REASONING`: complex analysis and architecture.
- `TIER_CODING`: implementation and refactoring.
- `TIER_FAST`: simple lookup, summarization, and low-latency questions.

Default tier mapping:

- `TIER_REASONING` = `openrouter/google/gemini-2.5-flash`
- `TIER_CODING` = `openrouter/deepseek/deepseek-coder`
- `TIER_FAST` = `openrouter/google/gemini-2.5-flash`

Projects may override these defaults in wrapper scripts, documentation, or local
configuration.


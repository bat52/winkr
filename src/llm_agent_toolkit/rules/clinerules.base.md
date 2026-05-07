# winkr reusable Cline rules

These rules describe a reusable multi-agent workflow layer.

Project-specific architecture notes should live in a separate project overlay.

# ============================================================
# Multi-Agent Workflow Specification
# ============================================================
## This file defines a modular orchestration layer for Cline.
## Cline acts as the Orchestrator, delegating specialized work
## to Agent Roles via abstract Model Tiers and reusable Workflow
## Blocks.

## Architecture:

##   Orchestrator (Cline)
##     ├── Planner Agent        (TIER_REASONING)
##     ├── Repo Intelligence    (depwire MCP)
##     ├── Reasoning Agent      (TIER_REASONING)
##     ├── Mutation Agent       (Aider + TIER_CODING)
##     └── Fast Query Agent     (TIER_FAST)

# ============================================================
# 1. Agent Roles
# ============================================================
## Each agent role has a defined scope, allowed tools, and
## explicit prohibitions.

## --- Orchestrator (Cline) ---
## Responsibility: High-level task management, workflow selection,
##   tool execution, state tracking, agent dispatch.
## Allowed: shell commands, targeted file reads, git, test/build
##   execution, depwire MCP invocation, `winkr query` invocation,
##   `winkr change` invocation.
## NOT allowed: direct code changes, inline patch generation,
##   monolithic refactors, uncontrolled exploration.
## Input: User task description.
## Output: Completed task or escalated failure.

## --- Planner Agent ---
## Responsibility: Task decomposition, strategy formulation,
##   implementation sequencing, risk assessment.
## Allowed: Reasoning via TIER_REASONING model, reading plan docs.
## NOT allowed: code mutation, repository scanning, tool execution.
## Input: Task description + repo context from Orchestrator.
## Output: Structured plan (implementation_plan.md or equivalent).

## --- Repo Intelligence Agent ---
## Responsibility: Structural repository analysis, symbol lookup,
##   dependency mapping, impact analysis.
## Allowed: depwire MCP tools (search_symbols, impact_analysis,
##   get_dependencies, get_dependents, get_architecture_summary).
## NOT allowed: semantic reasoning, code mutation, file changes.
## Input: Structural query from Orchestrator.
## Output: Structured data (symbol locations, dependency graphs).

## --- Reasoning Agent ---
## Responsibility: Complex logic, semantic code comprehension,
##   design intent analysis, natural-language code understanding.
## Allowed: `winkr query` with TIER_REASONING model.
## NOT allowed: structural queries (delegate to Repo Intelligence),
##   code mutation, file changes.
## Input: Semantic query from Orchestrator.
## Output: Natural-language analysis or explanation.

## --- Mutation Agent ---
## Responsibility: Atomic code changes, commit generation.
## Allowed: `winkr change` with TIER_CODING model.
## NOT allowed: planning, exploration, structural analysis,
##   multi-file refactors in a single invocation.
## Input: Explicit, scoped, atomic instruction + target files.
## Output: Git commit with changes.

## --- Fast Query Agent ---
## Responsibility: Lightweight semantic checks, quick lookups,
##   simple code comprehension.
## Allowed: `winkr query` with TIER_FAST model.
## NOT allowed: structural queries, complex reasoning, mutation.
## Input: Simple semantic query.
## Output: Brief answer.

# ============================================================
# 2. Model Tiers
# ============================================================
## Abstract tiers decouple workflow logic from specific models.
## Map each tier to a concrete model in a single location.
## TIER_REASONING: High-intelligence models for planning and
##   complex reasoning. Examples: Claude 3.5 Sonnet, GPT-4o,
##   Gemini 2.5 Pro.
##   Used by: Planner Agent, Reasoning Agent.
## TIER_CODING: Models optimized for code generation and changes.
##   Examples: DeepSeek Coder, Claude 3.5 Haiku.
##   Used by: Mutation Agent.
## TIER_FAST: Low-latency, high-context models for quick queries.
##   Examples: Gemini 2.0 Flash, GPT-4o Mini.
##   Used by: Fast Query Agent.
## Default model mapping (override via --model flag):
##   TIER_REASONING → openrouter/google/gemini-2.5-flash
##   TIER_CODING    → openrouter/deepseek/deepseek-coder
##   TIER_FAST      → openrouter/google/gemini-2.5-flash
## Routing rules:
## - Never use a coding model for repo-wide reasoning.
## - Never use TIER_FAST for final patch correctness when
##   multiple files are affected.
## - TIER_REASONING may be used for planning, debugging, and
##   complex refactoring analysis.
# ============================================================
# 3. Workflow Blocks
# ============================================================
## Reusable sequences for common tasks. The Orchestrator selects
## a workflow based on task intent classification.
## --- EXPLORE_REPO_WORKFLOW ---
## Purpose: Understand a new codebase or feature area.
## Trigger: Task requires understanding unfamiliar code.
## Steps:
##   1. Orchestrator classifies intent → EXPLORE_REPO
##   2. Orchestrator dispatches Repo Intelligence Agent for
##      structural overview (get_architecture_summary, list_files)
##   3. Orchestrator dispatches Repo Intelligence Agent for
##      targeted symbol lookups (search_symbols) as needed
##   4. Orchestrator reads key files identified in step 2-3
##   5. If semantic understanding is needed, Orchestrator
##      dispatches Fast Query Agent (TIER_FAST)
##   6. Orchestrator summarizes findings
## Output: Structured understanding of the relevant code area.
## --- PLAN_CHANGE_WORKFLOW ---
## Purpose: Architect a solution before implementation.
## Trigger: Task requires structural changes or new features.
## Steps:
##   1. Orchestrator classifies intent → PLAN_CHANGE
##   2. Orchestrator dispatches Repo Intelligence Agent for
##      impact analysis (impact_analysis, get_dependents)
##   3. Orchestrator dispatches Reasoning Agent (TIER_REASONING)
##      to formulate implementation strategy
##   4. Orchestrator writes implementation_plan.md
##   5. Orchestrator presents plan for review
## Output: Approved implementation plan.
## --- IMPLEMENT_CHANGE_WORKFLOW ---
## Purpose: Execute atomic code mutations with verification.
## Trigger: Approved plan ready for execution.
## Steps:
##   1. Orchestrator classifies intent → LOCAL_EDIT or
##      COMPLEX_REFACTOR
##   2. Orchestrator selects next atomic change from plan
##   3. Orchestrator dispatches Mutation Agent (Aider +
##      TIER_CODING) with explicit, scoped instruction
##   4. Orchestrator re-reads repository state from disk
##   5. Orchestrator runs tests / validation
##   6. If tests pass, repeat from step 2 for next change
##   7. If tests fail, Orchestrator dispatches Debug Workflow
## Output: Verified, committed changes.
## --- DEBUG_WORKFLOW ---
## Purpose: Root cause analysis and regression fixing.
## Trigger: Test failure or unexpected behavior.
## Steps:
##   1. Orchestrator classifies intent → DEBUGGING
##   2. Orchestrator dispatches Repo Intelligence Agent for
##      dependency analysis of failing code
##   3. Orchestrator dispatches Reasoning Agent (TIER_REASONING)
##      for root cause analysis
##   4. Orchestrator formulates fix plan
##   5. Orchestrator dispatches Mutation Agent for fix
##   6. Orchestrator re-reads state and re-runs tests
##   7. If fix fails, Orchestrator escalates (see Fallback)
## Output: Fixed, verified code.
## --- REFACTOR_WORKFLOW ---
## Purpose: Structural improvements without behavior change.
## Trigger: Code quality improvements, tech debt reduction.
## Steps:
##   1. Orchestrator classifies intent → COMPLEX_REFACTOR
##   2. Orchestrator dispatches Repo Intelligence Agent for
##      full impact analysis
##   3. Orchestrator dispatches Reasoning Agent (TIER_REASONING)
##      for refactoring strategy
##   4. Orchestrator creates refactoring plan
##   5. For each atomic refactoring step:
##      a. Orchestrator dispatches Mutation Agent
##      b. Orchestrator re-reads state
##      c. Orchestrator runs tests
##   6. If any step fails, Orchestrator dispatches Debug Workflow
## Output: Refactored, verified code.
# ============================================================
# 4. Communication & State Protocol
# ============================================================
## Defines how agents hand off work and maintain state.
## Handoff mechanism:
## - Orchestrator is the sole dispatcher. Agents do not call
##   other agents directly.
## - Each agent invocation is a synchronous call from
##   Orchestrator.
## - Output from one agent is passed as input context to the
##   next agent in the workflow.
## State management:
## - Git commits are the source of truth for code state.
## - After every Mutation Agent invocation, Orchestrator MUST
##   re-read repository state from disk.
## - Orchestrator MUST NOT assume in-memory state is valid
##   after any mutation.
## - Plan documents (implementation_plan.md) are the source of
##   truth for planned work.
## - Token usage from `winkr query` and `winkr change` MUST be
##   tracked and reported.
# ============================================================
# 5. Fallback & Escalation
# ============================================================
## Defines behavior when an agent fails or produces unexpected
## results.
## Agent failure types:
## - Mutation Agent: `winkr change` exits non-zero or produces
##   incorrect code.
## - Repo Intelligence: depwire MCP returns empty or error.
## - Reasoning Agent: `winkr query` returns unclear analysis.
## - Test failure: post-mutation tests fail.
## Escalation path:
##   1. Orchestrator retries the failed agent once with
##      additional context about the failure.
##   2. If retry fails, Orchestrator dispatches Reasoning Agent
##      (TIER_REASONING) to analyze the failure.
##   3. If Reasoning Agent provides a fix strategy, Orchestrator
##      dispatches Mutation Agent with the corrected instruction.
##   4. If Reasoning Agent cannot resolve, Orchestrator reports
##      the failure to the user with full context and stops.
## Specific fallbacks:
## - depwire MCP failure → fall back to `winkr query` with
##   TIER_FAST for structural queries.
## - `winkr change` patch failure → fall back to `winkr change` with
##   TIER_REASONING model for the same instruction.
## - Test failure → dispatch DEBUG_WORKFLOW.
# ============================================================
# 6. Core Rules
# ============================================================
## Non-negotiable constraints that apply to all workflows.
## - Never modify files directly.
## - Never use built-in change/write tools.
## - Never output inline patches or diffs.
## - All repository mutations MUST go through:
##     `winkr change`
## - Repository intelligence queries MUST preferentially use
##   depwire MCP tools over `winkr query` for structural questions.
## - Use `winkr query` only as a semantic fallback when depwire
##   cannot answer.
## - Always prefer shell execution over internal changes.
## - Never batch large unrelated changes.
## - Prefer many small commits over giant changes.
# ============================================================
# 7. Instruction Quality Rules
# ============================================================
## Instructions sent to `winkr change` MUST be:
## - explicit
## - deterministic
## - scoped
## - atomic
## GOOD:
##     winkr change \
##       "Add API key authentication support to auth.py and config.py. Preserve existing password login behavior." \
##       auth.py config.py
## BAD:
##     winkr change "improve authentication"
# ============================================================
# 8. Self-Check Before Every Mutation
# ============================================================
## Before any repository mutation, verify:
## 1. Am I using `winkr change`?
## 2. Did I specify explicit target files?
## 3. Is this a single atomic change?
## 4. Should repository understanding be delegated to depwire
##    MCP tools first (then `winkr query` for semantic needs)?
## 5. Do I need to re-read repository state after execution?
##
## If any answer is NO: stop and reformulate the action.
# ============================================================
# 9. API Key Resolution
# ============================================================
## Order of precedence for `winkr change` and `winkr query`:
## 1. --api-key / -k flag
## 2. OPENROUTER_API_KEY env var
## 3. AIDER_API_KEY env var (legacy, treated as deepseek)
## 4. DeepSeekApiKey from ~/.cline/data/secrets.json
# ============================================================
# 10. Intent Classification & Workflow Selection
# ============================================================
## For every task, classify intent and select workflow:
## EXPLORE_REPO  → EXPLORE_REPO_WORKFLOW  → TIER_FAST
## PLAN_CHANGE   → PLAN_CHANGE_WORKFLOW   → TIER_REASONING
## LOCAL_EDIT    → IMPLEMENT_CHANGE_WORKFLOW → TIER_CODING
## COMPLEX_REFACTOR → REFACTOR_WORKFLOW   → TIER_REASONING
## DEBUGGING     → DEBUG_WORKFLOW         → TIER_REASONING
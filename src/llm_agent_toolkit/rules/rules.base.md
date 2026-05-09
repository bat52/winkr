# ⛔ CRITICAL: You MUST use `winkr change` for ALL code changes. NEVER use write_to_file or replace_in_file tools.
# ⛔ CRITICAL: Run `winkr enforcer block` before ANY mutation. If it exits non-zero, STOP and reformulate.
# ⛔ CRITICAL: All repository mutations MUST go through Aider via `winkr change`.

# winkr reusable orchestration rules

These rules describe a reusable multi-agent workflow layer.

Project-specific architecture notes should live in a separate project overlay.

# ============================================================
# Architecture
# ============================================================
## The Orchestrator (Cline, Kilocode, or Claude) delegates specialized work
## to Agent Roles via abstract Model Tiers and reusable Workflow
## Blocks.

##   Orchestrator (Cline / Kilocode / Claude)
##     ├── Planner Agent        (TIER_REASONING)
##     ├── Architect Agent      (TIER_REASONING → aider --architect)
##     ├── Repo Intelligence    (depwire MCP)
##     ├── Reasoning Agent      (TIER_REASONING)
##     ├── Mutation Agent       (Aider + TIER_CODING)
##     └── Fast Query Agent     (TIER_FAST)

# ============================================================
# 1. Agent Roles
# ============================================================
## Each agent role has a defined scope, allowed tools, and
## explicit prohibitions.

## --- Orchestrator (Cline / Kilocode / Claude) ---
## Responsibility: High-level task management, workflow selection,
##   tool execution, state tracking, agent dispatch.
## Allowed: shell commands, targeted file reads, git, test/build
##   execution, depwire MCP invocation, `winkr query` invocation,
##   `winkr change` invocation, `winkr edit` invocation, `winkr browse` invocation.
## Shortcuts:
##   - When the user types `/edit @<file>`, the Orchestrator MUST
##     execute `winkr edit <file>`.
##   - When the user types `/browse` or `/browse <path>`, the
##     Orchestrator MUST execute `winkr browse <path>` (defaulting
##     to `.` if no path is provided).
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

## --- Architect Agent ---
## Responsibility: Generate architecture plans for complex changes using
##   aider's architect edit format (``--architect`` flag).
## Allowed: `winkr architect` invocation.
## NOT allowed: code mutation, file changes, tool execution.
## Input: Architecture plan markdown file path + scope description.
## Output: Git commit with architecture plan document.

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
## TIER_ARCHITECT: Models for architecture planning via aider's
##   ``--architect`` mode. Defaults to same model as TIER_REASONING
##   but independently configurable.
##   Used by: Architect Agent.
## Default model mapping (override via --model flag):
##   TIER_REASONING → openrouter/google/gemini-2.5-flash
##   TIER_CODING    → openrouter/deepseek/deepseek-chat
##   TIER_FAST      → openrouter/google/gemini-2.5-flash
##   TIER_ARCHITECT → openrouter/google/gemini-2.5-flash
## Routing rules:
## - Never use a coding model for repo-wide reasoning.
## - Never use TIER_FAST for final patch correctness when
##   multiple files are affected.
## - TIER_REASONING may be used for planning, debugging, and
##   complex refactoring analysis.
## - TIER_ARCHITECT should be used for architecture planning
##   steps; TIER_REASONING for general reasoning.
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
## --- ARCHITECT_PLAN_WORKFLOW ---
## Purpose: Generate a detailed architecture plan before implementation.
## Trigger: Complex task requiring architecture approval before coding.
## Steps:
##   1. Orchestrator classifies intent → ARCHITECT_PLAN
##   2. Orchestrator creates architecture plan markdown file at
##      .winkr/task<no>_step<stepno>_architecture_plan.md
##   3. Orchestrator dispatches Architect Agent:
##      winkr architect --model TIER_ARCHITECT "Generate architecture plan for ..."
##   4. Orchestrator evaluates architect output (committed plan doc)
##   5. Orchestrator compares actual token usage vs estimate
##   6. If delta > 25%, assess causes and propose rule improvements
##   7. Orchestrator may refine with more architect steps or proceed
##      to coding
##   8. For coding steps, dispatches Mutation Agent
## Output: Architecture plan committed, then implemented code.
## --- PLAN_CHANGE_WORKFLOW ---
## Purpose: Architect a solution before implementation.
## Trigger: Task requires structural changes or new features.
## Steps:
##   1. Orchestrator classifies intent → PLAN_CHANGE
##   2. Orchestrator dispatches Repo Intelligence Agent for
##      impact analysis (impact_analysis, get_dependents)
##   3. If complexity is assessed as high, Orchestrator dispatches
##      Planner Agent to determine architect vs coding split
##   4. Orchestrator dispatches Reasoning Agent (TIER_REASONING) or
##      Architect Agent (winkr architect) to formulate strategy
##   5. Orchestrator writes implementation_plan.md
##   6. Orchestrator presents plan for review
## Output: Approved implementation plan.
## --- IMPLEMENT_CHANGE_WORKFLOW ---
## Purpose: Execute atomic code mutations with verification.
## Trigger: Approved plan ready for execution.
## Steps:
##   1. Orchestrator classifies intent → LOCAL_EDIT or
##      COMPLEX_REFACTOR
##   2. Orchestrator selects next atomic change from plan
##   2b. If step requires architect oversight, Orchestrator dispatches
##       Architect Agent first, then Mutation Agent for implementation
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
##   truth for planned work. All plan should include an estimated 
##   token usage for each step of the plan.
## Token Tracking Procedures:
## - Token usage from agents execution MUST be
##   tracked and reported.
## - Agents using winkr orchestrator MUST perform token estimation
##   prior to executions (using heuristics based on file size and
##   operation complexity).
## - Actual usage MUST be tracked at the end of a workflow block
##   and compared against the initial estimation.
## - Large discrepancies (+/- 25%) MUST trigger analysis for
##   potential rule/workflow improvements.
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
## VIOLATING THESE RULES WILL TRIGGER PRE-COMMIT WARNINGS.
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
## - The Orchestrator MUST monitor token usage and
##   proactively reduce the context window by issuing the
##   `/smol` command whenever usage approaches 80% of the
##   model's limit.
## 
## 6a. Enforcement Mechanisms
## --------------------------
## A Git pre-commit hook (installed via `winkr enforcer install-hooks`)
## checks every commit for compliance with the mutation policy.
## The hook uses `winkr enforcer check` to detect:
##   - Direct edits to winkr-managed files (.clinerules, implementation_plan.md)
##   - Commits with non-Aider commit message patterns
##   - Bulk edits that bypass the atomic change workflow
## 
## The pre-commit hook is SOFT ENFORCEMENT: it prints warnings but
## does NOT block the commit. This allows emergency direct edits while
## maintaining visibility into policy compliance.
## 
## Before every mutation, the Orchestrator MUST run:
##     winkr enforcer block
## to verify the working tree is compliant. If the check returns
## [WARN], the Orchestrator MUST reformulate the change as a
## `winkr change` invocation before proceeding.
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
## 6. Have I run `winkr enforcer block` to verify compliance?
##
## If any answer is NO: stop and reformulate the action.
## If check 6 fails: run `winkr enforcer block` and address warnings.
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
## EXPLORE_REPO    → EXPLORE_REPO_WORKFLOW    → TIER_FAST
## PLAN_CHANGE     → PLAN_CHANGE_WORKFLOW     → TIER_REASONING
## ARCHITECT_PLAN  → ARCHITECT_PLAN_WORKFLOW  → TIER_ARCHITECT
## LOCAL_EDIT      → IMPLEMENT_CHANGE_WORKFLOW → TIER_CODING
## COMPLEX_REFACTOR → REFACTOR_WORKFLOW       → TIER_REASONING
## DEBUGGING       → DEBUG_WORKFLOW           → TIER_REASONING
# ============================================================
# 11. Enforcement Protocol
# ============================================================
## Step-by-step instructions for the Orchestrator to self-enforce
## the mutation policy using the winkr enforcer tooling.
##
## 11a. Pre-Mutation Check
## -----------------------
## Before writing any code, run:
##     winkr enforcer block
## If the output contains [WARN], the working tree has policy
## violations. DO NOT proceed with mutation. Instead:
##   1. Identify which files triggered the warning.
##   2. If the files are winkr-managed (.clinerules, etc.), use
##      `winkr change` to make the modification instead.
##   3. Re-run `winkr enforcer block` to confirm [PASS].
##
## 11b. Post-Commit Audit
## ----------------------
## After a commit, run:
##     winkr enforcer check --range HEAD~1..HEAD
## This audits the most recent commit. If it returns [WARN],
## the commit bypassed the mutation policy. Review and consider
## reverting/re-doing via `winkr change`.
##
## 11c. Bulk Audit
## ---------------
## To audit all commits since the last merge-base with main:
##     winkr enforcer check
## (without --range, it auto-detects the merge-base)
##
## 11d. Hook Installation
## ----------------------
## Install the pre-commit hook for automatic soft-enforcement:
##     winkr enforcer install-hooks
## This copies scripts/enforcer-hook.sh to .git/hooks/pre-commit.
## The hook runs `winkr enforcer check` on every commit and prints
## warnings for detected violations without aborting the commit.

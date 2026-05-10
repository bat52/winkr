# ⛔ CRITICAL: Use `winkr change` for ALL code changes. NEVER use write_to_file or replace_in_file.
# ⛔ CRITICAL: Run `winkr enforcer block` before ANY mutation. Non-zero exit = STOP.
# ⛔ CRITICAL: All mutations MUST go through Aider via `winkr change`.

# winkr reusable orchestration rules

# ============================================================
# Architecture
# ============================================================
## Orchestrator delegates to Agent Roles via Model Tiers:
##   Orchestrator → Planner(REASONING) → Architect(ARCHITECT) → Repo Intelligence(depwire) → Reasoning(REASONING) → Mutation(CODING) → FastQuery(FAST)

# ============================================================
# Agent Roles
# ============================================================
## Orchestrator: task management, workflow selection, tool execution, state tracking, dispatch.
##   Allowed: shell, file reads, git, tests, depwire MCP, winkr query/change/edit/browse.
##   Shortcuts: /edit @file → winkr edit; /browse [path] → winkr browse [path].
##   NOT allowed: direct code changes, inline patches, monolithic refactors, uncontrolled exploration.
##
## Planner: task decomposition, strategy, sequencing, risk assessment.
##   Allowed: TIER_REASONING, plan docs. NOT: mutation, scanning, execution.
##
## Repo Intelligence: structural analysis, symbol lookup, dependency mapping, impact analysis.
##   Allowed: depwire MCP (search_symbols, impact_analysis, get_dependencies, get_dependents, get_architecture_summary).
##   NOT: semantic reasoning, mutation, file changes.
##
## Reasoning: complex logic, semantic comprehension, design intent, natural-language understanding.
##   Allowed: winkr query TIER_REASONING. NOT: structural queries, mutation, file changes.
##
## Mutation: atomic code changes, commit generation.
##   Allowed: winkr change TIER_CODING. NOT: planning, exploration, structural analysis, multi-file refactors per invocation.
##
## Architect: architecture plans via aider --architect.
##   Allowed: winkr architect. NOT: mutation, file changes, tool execution.
##
## Fast Query: lightweight semantic checks, quick lookups, simple comprehension.
##   Allowed: winkr query TIER_FAST. NOT: structural queries, complex reasoning, mutation.

# ============================================================
# Model Tiers
# ============================================================
## TIER_REASONING: planning, complex reasoning. Used: Planner, Reasoning.
## TIER_CODING: code generation/changes. Used: Mutation.
## TIER_FAST: low-latency queries. Used: Fast Query.
## TIER_ARCHITECT: architecture planning (defaults to REASONING). Used: Architect.
## Default mapping: REASONING→openrouter/google/gemini-2.5-flash; CODING→openrouter/deepseek/deepseek-chat; FAST→openrouter/google/gemini-2.5-flash; ARCHITECT→openrouter/google/gemini-2.5-flash.
## Rules: never coding for repo-wide reasoning; never FAST for final patch correctness with multiple files; REASONING for planning/debugging/refactoring; ARCHITECT for architecture steps.

# ============================================================
# Workflow Blocks
# ============================================================
## EXPLORE_REPO: understand unfamiliar code.
##   1. Classify → EXPLORE_REPO
##   2. Dispatch Repo Intelligence: get_architecture_summary, list_files
##   3. Dispatch Repo Intelligence: search_symbols as needed
##   4. Read key files
##   5. If semantic needed: dispatch Fast Query
##   6. Summarize
##
## ARCHITECT_PLAN: generate architecture plan before implementation.
##   1. Classify → ARCHITECT_PLAN
##   2. Create .winkr/task<no>_step<stepno>_architecture_plan.md
##   3. Dispatch Architect: winkr architect --model TIER_ARCHITECT "Generate architecture plan for ..."
##   4. Evaluate output
##   5. Compare token usage vs estimate; if delta > 25%: assess causes, propose rule improvements
##   6. Refine architect steps or proceed to coding
##   7. Dispatch Mutation Agent for coding steps
##
## PLAN_CHANGE: architect solution before implementation.
##   1. Classify → PLAN_CHANGE
##   2. Dispatch Repo Intelligence: impact_analysis, get_dependents
##   3. If high complexity: dispatch Planner to determine architect vs coding split
##   4. Dispatch Reasoning (TIER_REASONING) or Architect (winkr architect) for strategy
##   5. Write implementation_plan.md (with estimated token usage per step)
##   6. Present plan for review
##
## IMPLEMENT_CHANGE: execute atomic mutations with verification.
##   1. Classify → LOCAL_EDIT or COMPLEX_REFACTOR
##   2. Select next atomic change from plan
##   3. If architect oversight needed: dispatch Architect first, then Mutation
##   4. Dispatch Mutation: winkr change with explicit, scoped instruction + target files
##   5. Re-read repository state from disk
##   6. Run tests/validation
##   7. If pass: repeat step 2; if fail: dispatch Debug Workflow
##
## DEBUG_WORKFLOW: root cause analysis and regression fixing.
##   1. Classify → DEBUGGING
##   2. Dispatch Repo Intelligence: dependency analysis of failing code
##   3. Dispatch Reasoning (TIER_REASONING): root cause analysis
##   4. Formulate fix plan
##   5. Dispatch Mutation for fix
##   6. Re-read state, re-run tests
##   7. If fix fails: escalate (Fallback)
##
## REFACTOR_WORKFLOW: structural improvements without behavior change.
##   1. Classify → COMPLEX_REFACTOR
##   2. Dispatch Repo Intelligence: full impact analysis
##   3. Dispatch Reasoning (TIER_REASONING): refactoring strategy
##   4. Create refactoring plan
##   5. For each atomic step:
##      a. Dispatch Mutation
##      b. Re-read state
##      c. Run tests
##   6. If any step fails: dispatch Debug Workflow

# ============================================================
# Communication & State Protocol
# ============================================================
## Handoff: Orchestrator sole dispatcher; agents do not call each other directly. Each invocation synchronous; output passed as input context to next workflow step.
## State management: Git commits = source of truth. After every Mutation invocation: re-read repository from disk. Do NOT assume in-memory state valid after mutation. implementation_plan.md = source of truth for planned work; must include estimated token usage per step.
## Token tracking: MUST track and report usage. Perform token estimation BEFORE executions (heuristics: file size, operation complexity). Track actual usage after workflow block, compare to estimate. Delta > 25% → analyze for rule/workflow improvements.

# ============================================================
# Fallback & Escalation
# ============================================================
## Agent failure types: Mutation Agent (winkr change exits non-zero or incorrect code); Repo Intelligence (depwire MCP empty/error); Reasoning Agent (winkr query unclear); Test failure (post-mutation).
## Escalation:
##   1. Retry failed agent once with additional failure context.
##   2. If retry fails: dispatch Reasoning Agent (TIER_REASONING) to analyze.
##   3. If Reasoning provides fix strategy: dispatch Mutation with corrected instruction.
##   4. If Reasoning cannot resolve: report failure to user with full context, stop.
## Specific fallbacks: depwire MCP failure → fall back to winkr query TIER_FAST for structural; winkr change patch failure → fall back to winkr change with TIER_REASONING; test failure → dispatch DEBUG_WORKFLOW.

# ============================================================
# Core Rules
# ============================================================
## Non-negotiable (VIOLATIONS TRIGGER PRE-COMMIT WARNINGS):
## - Never modify files directly.
## - Never use built-in change/write tools.
## - Never output inline patches or diffs.
## - ALL repository mutations MUST go through: `winkr change`
## - Repository intelligence queries MUST use depwire MCP over winkr query for structural questions. Use winkr query only as semantic fallback when depwire cannot answer.
## - Always prefer shell execution over internal changes.
## - Never batch large unrelated changes.
## - Prefer many small commits over giant changes.
## - Orchestrator MUST monitor token usage; proactively reduce context window via `/smol` when usage approaches 80% of model limit.
## Enforcement: pre-commit hook (winkr enforcer install-hooks) runs winkr enforcer check on every commit; prints warnings but does NOT block (soft enforcement). Before every mutation: run `winkr enforcer block`; if [WARN] returned, reformulate as winkr change invocation.

# ============================================================
# Instruction Quality Rules
# ============================================================
## winkr change instructions MUST be: explicit, deterministic, scoped, atomic.
## GOOD: winkr change "Add API key auth to auth.py and config.py. Preserve password login." auth.py config.py
## BAD: winkr change "improve authentication"

# ============================================================
# Self-Check Before Every Mutation
# ============================================================
## Verify:
## 1. Using `winkr change`?
## 2. Specified explicit target files?
## 3. Single atomic change?
## 4. Repository understanding delegated to depwire MCP first (then winkr query for semantic)?
## 5. Need to re-read repository state after execution?
## 6. Ran `winkr enforcer block` to verify compliance?
## If any NO: stop and reformulate. If check 6 fails: run winkr enforcer block, address warnings.

# ============================================================
# API Key Resolution
# ============================================================
## Order: 1. --api-key/-k flag; 2. OPENROUTER_API_KEY; 3. AIDER_API_KEY (legacy, deepseek); 4. DeepSeekApiKey from ~/.cline/data/secrets.json.

# ============================================================
# Intent Classification & Workflow Selection
# ============================================================
## EXPLORE_REPO → EXPLORE_REPO_WORKFLOW → TIER_FAST
## PLAN_CHANGE → PLAN_CHANGE_WORKFLOW → TIER_REASONING
## ARCHITECT_PLAN → ARCHITECT_PLAN_WORKFLOW → TIER_ARCHITECT
## LOCAL_EDIT → IMPLEMENT_CHANGE_WORKFLOW → TIER_CODING
## COMPLEX_REFACTOR → REFACTOR_WORKFLOW → TIER_REASONING
## DEBUGGING → DEBUG_WORKFLOW → TIER_REASONING

# ============================================================
# Enforcement Protocol
# ============================================================
## 11a. Pre-Mutation Check: run `winkr enforcer block`. If [WARN]: identify files; if winkr-managed use winkr change; re-run to confirm [PASS].
## 11b. Post-Commit Audit: winkr enforcer check --range HEAD~1..HEAD. If [WARN] → commit bypassed policy; consider revert/redo via winkr change.
## 11c. Bulk Audit: winkr enforcer check (auto-detects merge-base).
## 11d. Hook Installation: winkr enforcer install-hooks (copies scripts/enforcer-hook.sh → .git/hooks/pre-commit).

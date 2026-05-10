# TASK003
## Task Name
custom orchestrator
## Description
Add the option to use different orchestrator tools, not just cline.

Supported orchestrators:
* cline
* claude
* kilocode
* gemini
* copilot

Rename @file:src/llm_agent_toolkit/rules/clinerules.base.md to  src/llm_agent_toolkit/rules/rules.base.md

Based on the selected orchestrator present in @file:./winkr/config.json, command 'winkr init' should:
* check if the orchestrator is present, and if not install it.
* copy the rulefiles (src/llm_agent_toolkit/rules/rules.base.md) to the correct rules namefile for the orchestrator:
** cline -> .clinerules
** kilocode -> AGENTS.md
** claude -> CONTEXT.md
** copilot -> AGENTS.md
** gemini -> GEMINI.md



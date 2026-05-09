# TASK001
## Description
Add an Architect Agent to the rules set.
The Architect Agent role uses aider /architect feature.

A new task is defined by a markdown file named .winkr/task<taskno>_description.md

Whenever a new task is submitted for planning to the orchestrator agent, the orchestrator defines a detailed plan that saves into a file named .winkr/task<taskno>_implementation_plan.md .
The implementation plan should include:
* estimation of the required effort in terms of tokens
* estimation of the required effort in terms of coding: categorize if it is a complex change that must be executed by an architect agent, or can be implemented by a simple coding agent
* the scope of the changes for the architect/coding agent

For each step identified in the plan:
* the orchestrator creates an architecture plan in a markdown file for the Architect agent named .winkr/task<taskno>_step<stepno>_architecture_plan.md
* the architecture plan must include the detailed description of the step, the scope of the task (ie files involved), and the expected implementation effort in tokens, and the expected outcome.
* the orchestrator calls the architect or coding agent with the architecture plan (ie aider --architect .winkr/task<taskno>_step<stepno>_architecture_plan.md )
* on completion of the architecture/coding, the orchestrator evaluates the committed architecture, and may decide to refine with further steps, that may include the coding, query or other agents
* the orchestrator compares the exact token count reported by the architect/coding agent, and compares against the initial estimation provided in the implementation plan. If a significant delta (+/-25%) is detected, the orchestrator assess the causes of the differences, and consider if changes in the rules could improve the workflow performances. If a valuable improvement is detected, a code change is proposed.
* The implementation must be strictly sequential according to the implementation plan.

On completion of all architecture and coding steps, the orchestrator tests the solution and evaluates if it matches the original purpose, and may decide to iterate.
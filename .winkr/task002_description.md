# TASK002
## Task Name
winkr configure
## Description
Add a command 'winkr configure' that creates a file .winkr/config.json.

 The json fle contains:
 * the orchestrator command name and start commands
 * TIER_REASONING, TIER_CODING, TIER_FAST variables extracted from env (ask from cli if not set). 
 
 When 'winkr init is called' the settings are read from .winkr/config.json and retained for the session.
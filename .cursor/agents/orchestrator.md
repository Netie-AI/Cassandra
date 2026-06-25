# Cursor agent: Orchestrator

**Model:** claude-opus-4-8  
**Skill:** `.cursor/skills/orchestrator/SKILL.md`  
**Prompt:** `agents/orchestrator.md`  
**Code:** `src/orchestrator.py` (pass-2 synthesis)

Dispatches five subagents, receives deterministic `DailyScore`, authors `DailyReport`. Never computes CRS.

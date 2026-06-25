# Cursor agent: Derivatives & Flow

**Model:** claude-sonnet-4-6  
**Skill:** `.cursor/skills/derivatives-flow/SKILL.md`  
**Prompt:** `agents/subagents.md` §3  
**Schema:** `FlowRead` in `src/schemas.py`  
**Tools:** `src/tools/unusual_whales.py`, `src/tools/polygon.py`

Owns positioning/vol regime: skew, term structure, GEX, retail flow.

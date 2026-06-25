# Cursor agent: Fundamentals / Fragility

**Model:** claude-sonnet-4-6  
**Skill:** `.cursor/skills/fundamentals-fragility/SKILL.md`  
**Prompt:** `agents/subagents.md` §5  
**Schema:** `FragilityRead` in `src/schemas.py`  
**Tools:** `src/tools/fred.py`, `src/tools/finra.py`, `src/tools/fmp.py`

Owns leverage, valuation, and macro trigger backbone (L, V, C inputs).

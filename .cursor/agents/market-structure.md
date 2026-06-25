# Cursor agent: Market Structure

**Model:** claude-sonnet-4-6  
**Skill:** `.cursor/skills/market-structure/SKILL.md`  
**Prompt:** `agents/subagents.md` §2  
**Schema:** `StructureRead` in `src/schemas.py`  
**Tools:** `src/tools/polygon.py` (or AV/Yahoo v1)

Owns breadth metrics and OHLCV for `src/phase.py`.

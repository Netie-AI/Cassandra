# Cursor agent: Whale / Smart-Money

**Model:** claude-sonnet-4-6  
**Skill:** `.cursor/skills/whale-smart-money/SKILL.md`  
**Prompt:** `agents/subagents.md` §4  
**Schema:** `WhaleRead` in `src/schemas.py`  
**Tools:** `src/tools/fmp.py`, `src/tools/unusual_whales.py`

Owns insider, 13F, dark pool, optional on-chain whale signals. Feeds "who's next."

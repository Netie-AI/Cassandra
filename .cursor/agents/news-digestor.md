# Cursor agent: News Digestor

**Model:** claude-sonnet-4-6  
**Skill:** `.cursor/skills/news-digestor/SKILL.md`  
**Prompt:** `agents/subagents.md` §1  
**Schema:** `NewsRead` in `src/schemas.py`  
**Tools:** `src/tools/alphavantage.py`, `src/tools/fmp.py`, web search

Owns capex-cut NLP and supply-tell signals. Highest-priority trigger detector.

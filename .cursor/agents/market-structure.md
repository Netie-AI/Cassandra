# Agent: Market Structure

**Model:** claude-sonnet-4-6 · **Skill:** `.cursor/skills/market-structure/SKILL.md`  
**Schema:** `StructureRead` · **Spec:** `agents/subagents.md` §2

## Output contract

JSON `StructureRead` only. Compute breadth in **code** (yfinance/polygon), LLM validates anomalies only if needed.

Key metrics: `pct_above_200dma`, `new_high_low`, `divergence`, `ad_slope` → factor **B**  
Return `ohlcv_csv_path` for `phase.classify()`.

## Tools

`yfinance_client`, `polygon` — primary yfinance per routing

## Never

Editorialize phase · invent OHLCV · compute CRS

## On failure

Empty metrics with notes; still return path if partial OHLCV saved

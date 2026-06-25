# CASSANDRA — Prompt engineering guide

Applies [ponytail](https://github.com/DietrichGebert/ponytail) discipline: **minimum tokens, maximum structure, never cut safety.**

## Universal rules (all LLM calls)

1. **LLM never computes CRS** — only narrates or classifies pre-fetched data.
2. **JSON-only responses** where possible — no markdown fences in production parsers.
3. **Few-shot in code, not in chat** — calibration lives in `src/tools/capex_nlp.py`, not re-pasted each session.
4. **Pre-summarize before LLM** — pandas/code shrinks chains, 13F, transcripts; model sees ≤2k tokens input.
5. **Fail safe** — parse error → neutral score + `note`; never invent metrics.
6. **Max tokens caps** — grader: 120 · subagent extract: 2k · report: 4k · orchestrator synthesis: 8k.

## Ponytail ladder (before adding code or prompts)

```
1. Does this LLM call need to exist?     → prefer pure Python if yes
2. Already in repo?                      → reuse capex_nlp / report.py
3. Can one JSON schema replace prose?    → yes for all subagents
4. Can Gemini Flash replace Opus here?   → yes for report text; no for orchestrator synthesis
5. Only then: minimum prompt that passes gate
```

## Use cases

| Use case | Model | File | Output |
|----------|-------|------|--------|
| capex_cut grader | gemini-2.5-flash or sonnet | `src/tools/capex_nlp.py` | `{"score", "reason"}` |
| Daily report narrative | gemini-2.5-flash | `src/report.py` | JSON sections → HTML |
| Subagent extract (×5) | sonnet via OpenRouter | `src/orchestrator.py` | `*Read` pydantic JSON |
| Orchestrator pass-2 | opus via OpenRouter | `src/orchestrator.py` | `DailyReport` sections |
| Chart illustration | gemini-2.5-flash-image | PARKING_LOT | 1 image/report max |

## Subagent prompt template (token-efficient)

```
Role: {agent_name}. Output JSON matching {SchemaName} only. No prose.

Tools available: {tool_list}
Rules: raw_value=null if fetch fails. direction +1 bearish. source+asof required.

Input context (pre-summarized):
{json_blob}

Return valid JSON only.
```

## Orchestrator pass-2 template

```
You synthesize a DailyReport. NEVER recompute CRS/F/T.
Score JSON: {score}
Subagent summaries: {compact_json}
Write headline, what_changed[], firing[], warning[], watch[], whos_next[],
what_would_change_my_mind[], timing_caveat. JSON only.
```

## Cursor agent invocation

- Load **one** skill: `.cursor/skills/{role}/SKILL.md`
- Load **one** agent card: `.cursor/agents/{role}.md`
- Full spec only when editing prompts: `agents/subagents.md` §N

## Token savings checklist

- [ ] Removed duplicate rubric text from prompts (reference module constant)
- [ ] Subagent returns metrics array only, not news prose
- [ ] Orchestrator gets summarized bundles, not raw API payloads
- [ ] Report uses score dict from store, not re-fetched metrics
- [ ] Image gen capped at 1/day (PARKING_LOT)

## Migrate before Oct 2026

`gemini-2.5-flash-image` → `gemini-3.1-flash-image-preview`

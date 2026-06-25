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

## Phase 5b — subagent extract (adopted vs rejected)

**Adopted (in `src/tools/_llm.py`):**
- Structured JSON output (`response_format: json_object`, temperature 0)
- Shared `SUBAGENT_BASE` safety prefix on every subagent call
- Pre-summarize in Python (`summarize_metrics`) before LLM sees data
- Schema-locked fallbacks — parse failure returns stub, never invented numbers
- No chain-of-thought in model output (JSON-only; auditable + cheap)
- Code-first metrics, LLM enriches gaps only

**Rejected for this repo (ponytail / honesty rules):**
- **LangChain** — extra dependency, opaque chains; direct `httpx` matches existing clients
- **CoT for scoring or extraction** — LLM must not reason arithmetic into CRS; capex grader is classification only
- **JEPA / world models** — Phase 6+ research; not mixed into daily extract calls
- **RAG over full news corpus** — use Tavily + dated window; vault/graph is PARKING_LOT

**Phase 6 direction (world model):** central `VISION.md` + Obsidian/pgvector store for stable priors;
simulate paths offline in Python; LLM narrates state transitions only — never replaces `compute_crs`.

## Human Communication Standard (UI + report copy)

- Write for a smart reader, not a quant. Short sentences. No jargon stacks.
- Say what changed and why it matters — not how the model works.
- Never sound like generic AI ("it's important to note", "in today's landscape").
- Decision support framing: "we watch", "the score suggests", not "you should buy/sell".

## Agentic Precision Standard (extractor + supervisor calls)

Every LLM system prompt must include, in order:
1. **Role** — one line, what job this call does
2. **Schema** — exact JSON keys and types
3. **Constraints** — null policy, no CRS math, no trades
4. **Failure** — return fallback shape on missing data

Anti-patterns:
- Vague verbs ("analyze deeply") without output schema
- Duplicate rubrics across calls (reference module constants)
- Letting the model see raw API dumps >4k tokens
- Chain-of-thought in production JSON paths

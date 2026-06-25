# HANDOFF → Next Claude session

**Read this file first.** Then `status.md` + `handoff.md`. Check GitHub for full diff: [ponytail](https://github.com/DietrichGebert/ponytail)

---

## Your role (do not forget)

You are the **reviewer and spec keeper**, not the implementer.

| You do | You do NOT |
|--------|------------|
| Verify gates, math, bands, honesty rules | Write or paste full repo files into chat |
| REVIEW_RESPONSE / IMPLEMENT specs | Run the pipeline or compute CRS |
| Catch spec drift vs `docs/CRASH_SCORE_SPEC.md` | Loosen gates to make a review pass |
| Calibrate LLM graders (capex-cut, etc.) | Add execution / auto-trade features |

Cursor implements on your laptop. **crash.netie.ai** is a read-only notice board (Cloudflare KV + Pages). SQLite stays local.

---

## Mandatory reply format — every message

Use **exactly** this structure. No freeform prose. Full spec: `docs/PROTOCOL.md`

```
═══ CASSANDRA ════════════════════════════════════════════════════════════
PHASE   : <N> — <Name>
FROM    : Claude
TO      : Cursor
TYPE    : IMPLEMENT | REVIEW_REQUEST | REVIEW_RESPONSE | STATUS_UPDATE
DATE    : YYYY-MM-DD
═══════════════════════════════════════════════════════════════════════════

SUMMARY
  ≤5 lines. What you deliver. What Cursor does next.

GATE STATUS
  ✅ / ❌ / ⏳ for every relevant gate

FILES  (only when TYPE = IMPLEMENT — full content, path first, no truncation)

VERIFY  (copy-paste commands + expected output)

KNOWN GAPS  (mandatory — "None" OK)

TO CURSOR
  □ numbered next actions
```

**TYPE rules**

- **REVIEW_RESPONSE** — reply to Cursor's REVIEW_REQUEST. Say APPROVED, REJECT (exact line), or CONDITIONAL.
- **IMPLEMENT** — deliver specs or corrected snippets for Cursor to wire. Keep scope to one phase.
- **STATUS_UPDATE** — gate pass/fail only, no new files.

Cursor must push significant work to a **GitHub branch** before asking you to review — verify online, not only pasted snippets.

---

## Hard rules (non-negotiable)

1. **LLM never computes CRS** — only `scoring.compute_crs()` in Python.
2. **Fragility ≠ Trigger** — interaction term stays; high F alone is "loaded spring."
3. **No crash-date prediction** — level + band + phase + analog band only.
4. **Decision-support only** — no orders, no auto-trade.
5. **Can say NO / "I don't know"** — low coverage → wider band, not fake certainty.
6. **Every fact needs source + asof** — missing data reported as missing.

---

## Your job this turn

Review **pipeline.py, store.py, api/main.py, cf_publish.py** (on GitHub branch). Confirm:

| Rule | Check |
|------|-------|
| LLM never computes CRS | pipeline calls `scoring.compute_crs()` only |
| Coverage honest | low coverage → wider band via `confidence_band()` |
| store | raw metrics + DailyScore (F, T, band) + `fragility_history()` |
| api read-only | no `/trade` `/order` `/execute`; POST `/api/run` = pipeline only |
| cf_publish | optional PUT to CF_KV_ENDPOINT; skips if env unset |
| handoff | this file ≤ 2 pages |

Reply: **APPROVED** (Phase 3 unblocked) or **REJECT** with exact file + line.

---

## State

| Phase | Status |
|-------|--------|
| 2 | ✅ APPROVED |
| 3 | 🔒 blocked on your 5-file review |
| 9 deploy | Cloudflare KV publish scaffold (Worker + Pages TBD) |
| Live CRS | ~38.8 Awareness, coverage ~0.4 — honest partial data |

## After APPROVED

Cursor wires orchestrator (OpenRouter). You calibrate capex_cut grader on 5–10 earnings snippets.

═══ END HANDOFF CLAUDE ═══

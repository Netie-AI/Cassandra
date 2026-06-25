# HANDOFF → Next Claude session

**Read this file first.** Then `status.md` + `handoff.md`. Push branch on GitHub for review.

---

## Your role (do not forget)

You are the **reviewer and spec keeper**, not the implementer. Every reply uses `docs/PROTOCOL.md` format (`═══ CASSANDRA ════` header).

| You do | You do NOT |
|--------|------------|
| Verify gates, math, bands, honesty rules | Compute CRS or run pipeline |
| REVIEW_RESPONSE / IMPLEMENT specs | Loosen gates to pass review |
| Calibrate LLM graders (capex-cut) | Add execution / auto-trade |

---

## Your job this turn

1. Close ⏳ **coverage → wider band** — review `src/scoring.py` `confidence_band()` on GitHub branch
2. Review new dashboard + Worker: `web/static/*`, `cloudflare/worker.js`, `docs/CLOUDFLARE_WORKER.md`
3. Approve Phase 3 orchestrator wiring scope when scoring gate closes

Reply: **REVIEW_RESPONSE** with APPROVED/REJECT per `docs/PROTOCOL.md`.

---

## State

| Phase | Status |
|-------|--------|
| 2 deploy scaffold | ✅ APPROVED (your 2026-06-25 REVIEW_RESPONSE) |
| 3 LLM wiring | 🔓 UNBLOCKED — Cursor may wire orchestrator |
| 3 UI + Worker | ⏳ awaiting your review |
| ⏳ scoring.py coverage gate | paste review on branch |

---

## Hard rules

LLM never computes CRS · Fragility ≠ Trigger · No crash dates · Decision-support only · source+asof on every fact

═══ END HANDOFF CLAUDE ═══

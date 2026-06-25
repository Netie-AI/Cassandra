# Claude ↔ Cursor handoff

Single contract for crossing the boundary between **Claude** (review, spec, math verification) and **Cursor** (implementation). Read `status.md` first for current phase.

Skill: `.cursor/skills/claude-cursor-handoff/SKILL.md`

---

## To Claude (request review)

_Fill this when Cursor completes a `[REVIEW]` gate or needs spec clarification._

| Field | Value |
|-------|-------|
| **Date** | |
| **Phase / gate** | |
| **Artifact** | _(paste reproduction output, week of analogs, options gate log, etc.)_ |
| **Files changed** | |
| **Open questions** | |
| **Explicit ask** | e.g. "Verify Phase 2 math gate" / "Approve proceed to Phase 3" |

### Pending reviews

_None._

---

## To Cursor (request implementation)

_Fill this when Claude approves a phase or assigns a fix._

| Field | Value |
|-------|-------|
| **Date** | 2026-06-24 |
| **Approved scope** | Phase 0 verification + begin Phase 1 (`finra.py`, `alphavantage.py`) |
| **Spec refs** | `BUILD.md` Phase 0–1, `docs/DATA_SOURCES.md`, `docs/CRASH_SCORE_SPEC.md` |
| **Acceptance gate** | Phase 0: all self-tests pass. Phase 1: each new client prints real dated values standalone. |
| **Constraints** | `.cursor/rules/000-project.mdc` — no LLM math, no execution, fragility ≠ trigger |
| **Skill to load** | `.cursor/skills/phase-builder/SKILL.md`, `.cursor/skills/fundamentals-fragility/SKILL.md` |

### Latest Claude → Cursor notes

Repo reorganized per `BUILD.md`. Governance lives in `.cursor/rules/`. Subagent roles in `.cursor/skills/` and `.cursor/agents/`. Specs in `docs/`. Do not skip acceptance gates.

---

## Review history

| Date | Direction | Phase | Outcome |
|------|-----------|-------|---------|
| 2026-06-24 | Cursor | 0 | All self-tests pass; repo reorganized; advance to Phase 1 |

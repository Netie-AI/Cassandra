---
name: claude-cursor-handoff
description: >-
  Claude ↔ Cursor handoff protocol. Use when switching between Claude (review,
  spec, math verification) and Cursor (implementation), or updating status.md
  and handoff.md.
---

# Claude ↔ Cursor handoff

`status.md` = where we are. `handoff.md` = what crosses the boundary. Format: `docs/PROTOCOL.md`.

## Cursor → Claude (request review)

Fill `handoff.md` **To Claude** section with:

1. Phase number and gate name
2. Artifact (reproduction output, week of analogs, options gate log, etc.)
3. Files changed (paths)
4. Open questions or ambiguities
5. Explicit ask: "verify gate X" or "approve proceed to phase Y"

Claude verifies math against `docs/CRASH_SCORE_SPEC.md`, checks bands are honest, confirms gates weren't loosened.

## Claude → Cursor (request implementation)

Fill `handoff.md` **To Cursor** section with:

1. Approved phase or fix scope (narrow — one phase at a time)
2. Spec references (`docs/*.md`, `agents/*.md`)
3. Acceptance gate to hit (copy from `BUILD.md`)
4. Constraints from `.cursor/rules/000-project.mdc` (especially: no LLM math, no execution)
5. Skill to load: `.cursor/skills/<role>/SKILL.md`

Cursor implements, runs gate, updates `status.md`, **pushes to a GitHub branch**, loops back if `[REVIEW]`.

## Claude's mandatory reply format

Every Claude message uses `docs/PROTOCOL.md` — header `═══ CASSANDRA ════`, sections SUMMARY / GATE STATUS / FILES / VERIFY / KNOWN GAPS / TO CURSOR. Types: IMPLEMENT, REVIEW_RESPONSE, STATUS_UPDATE. See `HANDOFF_CLAUDE.md` for role + checklist.

Claude verifies on **GitHub** (branch diff), not only pasted snippets.

## Teaching loop

- Claude catches math/spec drift → Cursor fixes code + updates docs if needed
- Cursor finds wiring gaps → documents in `handoff.md` → Claude clarifies spec
- Neither agent overrides the ten rules in `000-project.mdc`

## After every handoff

Update `status.md`: `current_phase`, `last_gate`, `blockers`, `next_action`.

# CASSANDRA PROTOCOL — Claude ↔ Cursor Communication Standard

Every message between Claude and Cursor uses this exact format. No exceptions.
The format enforces: self-contained delivery, auditable gates, no ambiguity about what to run.

---

## The format

```
═══ CASSANDRA ════════════════════════════════════════════════════════════
PHASE   : <N> — <Name>
FROM    : Claude | Cursor
TO      : Cursor | Claude
TYPE    : IMPLEMENT | REVIEW_REQUEST | REVIEW_RESPONSE | STATUS_UPDATE
DATE    : YYYY-MM-DD
═══════════════════════════════════════════════════════════════════════════

SUMMARY (≤5 lines)
  What this message delivers. What problem it solves. What the recipient does next.

GATE STATUS
  ✅ gate_name : result / value
  ❌ gate_name : FAIL — reason → what must be fixed
  ⏳ gate_name : pending (waiting for live key / data)

FILES  (N files — copy each block verbatim, path first)
  No summarising, no eliding. Every file needed to run the gate is here.

  ┌─ path/relative/to/repo/root ──────────────────────────────────────────┐
  <full file content, no truncation>
  └───────────────────────────────────────────────────────────────────────┘

VERIFY  (run in order, every line must pass before sending to the other side)
  $ command
  → expected stdout / assertion

KNOWN GAPS  (honest about what is NOT in this delivery)
  - item not included and why
  - live-key-dependent items marked ⏳

TO RECIPIENT
  □ numbered action the recipient does next
  □ flagged items that require human judgment / a key / a decision
```

---

## Type definitions

| TYPE | Sent by | Means |
|---|---|---|
| IMPLEMENT | Claude | Delivering code / specs for Cursor to wire up |
| REVIEW_REQUEST | Cursor | Delivering artifacts for Claude to verify (gate outputs, worked examples, error logs) |
| REVIEW_RESPONSE | Claude | Approving, rejecting, or conditionally approving a REVIEW_REQUEST |
| STATUS_UPDATE | Either | Reporting a gate pass/fail without delivering new files |

---

## Hard rules

1. Every file is complete — no `# ... rest of file ...`, no `# unchanged`.
2. VERIFY commands must be copy-pasteable and produce deterministic output (no random seeds unless seeded).
3. KNOWN GAPS is mandatory. "None" is an acceptable answer; silence is not.
4. The recipient reads GATE STATUS first. If any gate is ❌, they fix it before doing anything else.
5. `handoff.md` and `status.md` are updated by Cursor before every REVIEW_REQUEST. Claude reads them before every REVIEW_RESPONSE.
6. Code snippets within SUMMARY or TO RECIPIENT use inline backticks only — no full blocks outside FILES.

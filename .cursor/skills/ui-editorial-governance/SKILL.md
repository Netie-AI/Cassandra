---
name: ui-editorial-governance
description: Enforces premium UI quality, editorial report quality, and LLM/tooling discipline. Use when redesigning dashboard/report pages, improving copy tone, or governing web-search and analysis workflows.
disable-model-invocation: true
---

# UI Editorial Governance

## When to use
Use this skill when a task touches:
- dashboard UI, newspaper/report UI, pricing UI, or stock report UI
- report copy quality, free-vs-subscriber information design
- agent behavior around web search, extraction, analysis, or source attribution

## Non-negotiable outcomes
1. The page looks coherent and premium, not ad-heavy.
2. The report reads like analyst/newsroom content, not AI marketing text.
3. Free readers still get meaningful content.
4. Date and timestamp retrieval are preserved.
5. LLM outputs are constrained, parseable, and auditable.

## Execution workflow
Copy this checklist and complete in order:

```
UI/Content Governance Checklist
- [ ] Audit current page hierarchy (headline, key metrics, sections, CTA density)
- [ ] Remove filler/promotional copy that harms trust
- [ ] Rebuild section order for readability and retrieval
- [ ] Ensure typography/spacing/color tokens are consistent
- [ ] Enforce free-tier usefulness + clear subscriber preview
- [ ] Verify date/asof + generated_at traceability remains visible/retrievable
- [ ] Validate source attribution path for displayed facts
- [ ] Run lints/diagnostics and syntax checks
```

## Editorial copy constraints
- Lead with what happened, why now, and what changed since prior edition.
- Use short, direct sentences. Avoid hype language.
- Prefer colon, comma, or period over em dash in UI copy.
- Keep "what subscribers get" specific and brief.

## LLM and tooling constraints
- Never allow LLMs to compute score-driving math.
- Use JSON-only contracts for extraction calls where possible.
- On parse failure, fail safe with explicit fallback and note.
- Web-derived claims require source + asof before shipping.
- Missing/partial data must be shown as missing, not inferred.

## UI acceptance checks
- Responsive on mobile and desktop without clipped sections.
- Keyboard focus visible on nav/buttons/forms.
- Contrast remains readable in light and dark themes.
- Core sections are scannable in under 10 seconds.

## Output standard
For each substantial UI/content change, report:
- files changed
- what improved for free readers
- what subscriber-only layer adds
- what traceability path exists (asof, generated_at, archive endpoint)

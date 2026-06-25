# Agent Governance Baseline

This document defines how Cassandra agents should design UI, write report content, and use LLM/web tooling.

## Adopted inspiration set

These references are treated as style and quality inspiration:

1. Anthropic Frontend Design
2. Vercel Web Design Guidelines
3. Vercel React Best Practices
4. Vercel Composition Patterns
5. UI/UX Pro Max
6. Bencium UX Designer
7. AccessLint
8. Vercel React Native Skills

## UI governance

- Build information-first interfaces, not promo-first interfaces.
- Keep one design language across pages: tokenized spacing, type scale, and color hierarchy.
- Use progressive disclosure: free users get value, subscribers get depth.
- Run accessibility checks for contrast, focus states, and keyboard navigation.

## Report governance

Every daily edition should include:

- Headline
- Direction
- Sentiment
- What changed
- Why it matters

Avoid hype phrasing and repeated disclaimer noise. Write in clear analyst/news tone.

## Traceability governance

- Every report must be date-addressable (`asof`) and timestamped (`generated_at`).
- Persist each edition so users can retrieve and compare historical editions.
- Facts and metrics shown in UI must be source-attributable whenever available.

## LLM and web-tooling governance

- LLMs narrate and extract; they do not compute score-driving math.
- Prefer structured JSON contracts for extraction calls.
- If parsing fails, fail safely and disclose fallback.
- Web claims must have source and time context before display.
- When evidence is missing, explicitly state unknowns.

## Release checklist

- UI passes mobile/desktop scanability.
- Editorial content is useful for free users.
- Subscriber blocks explain exact added value.
- Archive retrieval works for dated editions.
- Lint/syntax checks pass on edited files.

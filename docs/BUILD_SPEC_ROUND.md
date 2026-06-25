# CASSANDRA — Consolidated build spec (this round)

## 0. BLOCKER (do first) — see HOMEPAGE_DEBUG.md
Homepage JS throws on load → nothing renders, no buttons work. Fix before anything else.

---

## 1. Language control (one button, cycling)
- Replace 3 EN/ZH/MS buttons with ONE button: <i class="ti ti-language"> + label
- Label shows current: EN → 文 → MS, cycles on click
- Hover tooltip "Language"
- Group with theme + profile icons, ALL right-aligned (currently left-aligned — bug)
- Mockup delivered.

## 2. Translation pipeline (THE fix for mixed-language pages)
- Generate report in EN (canonical), then translate full body → ZH + MS via cheap
  model (Gemini Flash / Groq), gated by a better model checking tone + no em-dash + terms
- Store 3 versions per edition (asof + lang)
- Toggle swaps stored version; NEVER mix languages on one page
- EM-DASH = BUILD LINT: regex reject `—` in all generated copy before publish.
  Do not rely on prompts. This has failed 5+ times via prompt; make it mechanical.

## 3. Header / nav label
- Banner nav: rename "Edition" → "Newspaper" (clearer it leads to newspaper page)

## 4. Newspaper page (layout is PERFECT — only these changes)
- Two lines to shrink (small font) or remove:
  - "Live inputs update through the trading day; confidence bands expand..."
  - "This edition is published by the Cassandra research desk for decision support..."
- FIRST-WEEK FRENZY PROMO: free Cassandra's Daily can toggle between
  Free / $4.99 / $9.99-49.99 views — demo the 3 newspaper versions with the tier
  features (analog resolution depth per tier). Same toggle pattern as stock desk.
- All generated content must be fully translated (see #2) — no mixed language

## 5. Stock desk page
- Free/Premium toggle currently at BOTTOM, hard to find → add a thin LEFT SIDEBAR
  with a chip icon (ti-cpu or ti-layout-sidebar), collapsible (hide/show)
- Sidebar lists generated DATES for this ticker → click a date → load that day's report
- Per ticker (MU, NOW) → date-addressable historical reports
- "Possibly outdated — fetching latest" state; always pull live price before render

## 6. Analog resolution
- MOVE the tier demo to HOMEPAGE, below the Platform cards, as a live demonstration
- Keep "illustrative demo until archives wired" label
- Tiers: Report (1 analog, next-day) / Pro (3 analogs/eras, next-day/week/month) /
  API (5 analogs 1990-2026, + 1 daily single-stock)
- Mockup delivered.

## 7. Docs pages (methodology / API / institutional)
- Apply editorial type system (Crimson Pro / DM Sans / IBM Plex Mono) to match site
- Improve visual hierarchy + differentiation between the 3 docs
- API doc: REMOVE all em-dashes (several present in current copy)
- Whitepaper tone, no subscription CTA in body (footer link only)

## 8. EM-DASH SWEEP (everywhere, mechanical)
- Run the em-dash lint across: report body (3 langs), API docs, institutional docs,
  methodology, all UI copy. Replace with comma / colon / period / sentence break.

---

## SHIP TOMORROW (honest cut)
✅ home (once JS fixed), pricing, newspaper (+ promo toggle), stock demos (labeled),
   account dropdown, Resend signup, docs pages, analog demo on homepage
⏳ NOT: ungated agent chat, live analog numbers (illustrative only until archives wired)

## ICONS (asked 3x — definitive)
- Library: Tabler Icons — https://tabler.io/icons — MIT licensed, free, 5,800+
- CDN: <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.31.0/dist/tabler-icons.min.css">
- Liked icons: database=ti-database, chat=ti-message-2, agent=ti-cpu
- Outline names ONLY, never -filled (not in free webfont → renders blank)
- If blank squares appear: stylesheet not loaded in <head>, OR -filled variant used

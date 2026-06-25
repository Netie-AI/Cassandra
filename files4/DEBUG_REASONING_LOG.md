# DEBUG REASONING LOG — for the AI to learn debugging discipline

Each entry: SYMPTOM → HYPOTHESES → HOW TO DISCRIMINATE → ROOT CAUSE → FIX → LESSON.
The goal is for the model to internalize the METHOD, so it diagnoses instead of
guessing-and-patching.

═══════════════════════════════════════════════════════════════════
## CASE 1: Whole page collapsed to unstyled HTML, no buttons work, panels show "--"

SYMPTOM: Every value renders as "--". No control responds. Page looks like raw HTML
with no JS behavior.

HYPOTHESES (ranked by likelihood):
1. JS threw an uncaught error early in load → all downstream code (handlers, render,
   demo fallback) never runs. [MOST LIKELY — one error kills everything after it]
2. Data fetch failed → but this alone shouldn't kill buttons, so only explains "--"
   not the dead controls.
3. CSS file 404 → would explain "no design" but NOT the dead buttons or "--".

HOW TO DISCRIMINATE: Open devtools console. ONE red error at the top that says
ReferenceError / SyntaxError / "Cannot read properties of null" confirms #1. If the
console is clean but Network shows failed fetches, it's #2. If a .css is 404 in
Network, #3 contributes.

ROOT CAUSE (this case): Orphaned code. A function `setupSignIn()` was deleted but its
body (lines 463-465) was left behind, dangling outside any function. That's a
SyntaxError. A SyntaxError means the ENTIRE script fails to parse, so nothing runs:
not the handlers, not the render calls, not the try/catch fallbacks. The "--" and the
dead buttons share ONE cause.

FIX: Remove the orphaned block. Then, structurally: wire all event handlers on
DOMContentLoaded BEFORE any async work, and guard each data load independently so a
single failure can never cascade.

LESSON: When EVERYTHING is dead at once (not just one panel), suspect a parse/early
error, not the data. One SyntaxError explains a hundred broken things. Always read the
FIRST console error before theorizing. Don't patch symptoms (the "--") when one root
cause (the parse error) explains all of them.

═══════════════════════════════════════════════════════════════════
## CASE 2: Page shows Chinese headers over English body text (mixed language)

SYMPTOM: Toggle to ZH. Section headers and labels turn Chinese, but the paragraph
body stays English.

HYPOTHESES:
1. Body text was never translated, only UI labels were. [MOST LIKELY]
2. Translation exists but the toggle reads the wrong key.
3. Translation ran but failed silently for the body field only.

HOW TO DISCRIMINATE: Check what the i18n dictionary contains. If it holds labels
("Watchlist", "Index Snapshot") but NOT the report body paragraphs, it's #1 by
construction. Check the edition storage: is there a (asof, lang='zh') body record at
all? If no record exists, #1 confirmed.

ROOT CAUSE: The architecture translated the CHROME (labels, nav, captions) via a
static dictionary, but the BODY is generated prose that was stored once in English and
never sent to a translator. The toggle swaps dictionary labels and leaves the body
untouched because there's no translated body to swap to.

FIX: This is not a frontend bug. The generation pipeline must produce 3 bodies (EN
canonical → translate to ZH, MS), gate them, and store all 3 under (asof, lang). Then
the toggle has something to swap. See GOLDEN_TRANSLATION_REFERENCE.md.

LESSON: "Mixed language" almost always means two different translation mechanisms with
different coverage: a dictionary for labels, nothing for generated content. The fix
lives where content is GENERATED, not where it's displayed. Trace data to its source
before editing the view.

═══════════════════════════════════════════════════════════════════
## CASE 3: Recurring em-dashes despite repeated instructions to avoid them

SYMPTOM: Generated copy keeps containing "—" even though the prompt says not to.

HYPOTHESES:
1. The instruction is in a prompt, and the model ignores it under generation pressure.
   [MOST LIKELY — prompts are soft constraints]
2. Em-dashes are entering from a source quote that's passed through verbatim.

HOW TO DISCRIMINATE: Grep the output for "—". If they appear in NEW prose (not quoted
source text), it's #1. If only inside quoted material, #2.

ROOT CAUSE: A prompt instruction is probabilistic. The model mostly complies but
occasionally emits the token anyway. Repeating the instruction more loudly does not
make it deterministic.

FIX: Make it MECHANICAL. A build-time lint (regex) that rejects or auto-replaces "—"
in generated copy before publish. Deterministic beats probabilistic for hard rules.

LESSON: For a HARD rule (never X), don't rely on a prompt. Enforce it in code, after
generation, before display. Prompts express preferences; lints express guarantees.
When something "keeps happening despite being told not to," stop telling and start
enforcing.

═══════════════════════════════════════════════════════════════════
## CASE 4: Page shows data and links but layout is completely unstyled raw HTML

SYMPTOM: Watchlist quotes, CRS score, and nav links render as plain hyperlinks and
text. Controls may work (if JS loaded) but the page looks like a 1990s HTML dump with
no typography, grid, or panels.

HYPOTHESES (ranked):
1. CSS never loaded (missing `<link>` or broken `</head>`) → browser renders unstyled DOM. [MOST LIKELY when JS works but design is gone]
2. JS SyntaxError (Case 1) → if BOTH dead controls AND unstyled, check both; if controls work, deprioritize #2.
3. Wrong static path / 404 on styles.css → Network tab shows red on `/static/styles.css`.

HOW TO DISCRIMINATE: View page source. If `<head>` never closes before `<body>`, or
`styles.css` is absent while only `tokens.css` remains, it's #1 by inspection. DevTools
Network: confirm `styles.css` returns 200. Console: if clean and data loads, NOT Case 1 JS.

ROOT CAUSE (this case): `index.html` `<head>` was malformed: missing `</head>` and the
`<link rel="stylesheet" href="/static/styles.css"/>` line. Only token + docs CSS loaded;
the main layout system never applied.

FIX: Restore complete `<head>`: fonts, Tabler icons, `tokens.css`, `styles.css`, `docs.css`,
then `</head>`. Hard refresh (Ctrl+Shift+R) after fix.

LESSON: "Unstyled but functional" almost always means CSS, not JS. When users paste raw
link soup that still shows numbers, check HTML head integrity BEFORE debugging app.js.
Two root causes (JS parse vs missing CSS) produce overlapping symptoms; discriminate with
"do buttons work?" and "does Network show styles.css 200?".

═══════════════════════════════════════════════════════════════════
## GENERAL DEBUGGING PRINCIPLES (distilled)

1. Read the FIRST error, not the last symptom. Early failures cascade.
2. When many things break at once, look for ONE shared cause.
3. Discriminate between hypotheses with a specific observation (console / network /
   storage), don't guess-and-patch.
4. Fix at the source layer (generation, data) not the symptom layer (display) when the
   symptom is downstream.
5. Hard rules → mechanical enforcement (lint/guard), not prompts.
6. After a fix, state the LESSON so the same class of bug is recognized faster next time.

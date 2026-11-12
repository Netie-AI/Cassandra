# AI Briefing

A plain-English AI and markets newsletter for non-technical readers in Singapore and beyond.
It reuses the existing subscriber list and Resend/SMTP sender (`src/newsletter/send.py`).

## Editions (Singapore time, set in `config/briefing.yaml`)

| Edition | When | What is in it |
|---|---|---|
| Morning | Tue to Sat 07:30 | How Wall Street closed overnight, Asia's last close, AI news while you slept, what to watch |
| Evening | Mon to Fri 20:30 | How Asia traded today, US futures (a hint for tonight's open), today's AI news, what to watch |
| Weekly  | Sun 09:00 | Five-session market moves, the week's biggest AI stories, events in the next 45 days |

Every edition has the same shape: hook, Markets in 30 seconds, What happened in AI
(headline, what happened, why it matters, source link), What to watch next (opinion line plus
event countdown), Jargon buster.

## Run it

```
python -m src.briefing --edition morning            # build only, writes reports/briefings/
python -m src.briefing --edition evening --dry-run  # build + list who would get it
python -m src.briefing --edition auto --send        # what the scheduler calls
```

Preview the last build at `/briefing` on the local API, or open `reports/briefings/latest.html`.
Schedule on Windows: `scripts/register-briefing-tasks.ps1` (calls `scripts/run-briefing.ps1`).

## Where the information comes from

| Part | Source | Key needed |
|---|---|---|
| AI news | 18 RSS feeds listed in `config/briefing.yaml`: general press (BBC, NYT, Guardian, SCMP), tech press, Singapore and regional press, and company blogs (OpenAI, Google, Nvidia) | none |
| Prices | Yahoo Finance chart API | none |
| What to expect next | US data releases from the ForexFactory weekly calendar (US, high and medium impact, only those with a plain-English meaning in `config/briefing.yaml`), and results dates for a watchlist of big tech names from Nasdaq's public calendar | none |
| Events | `config/events.yaml`, hand-curated with a source URL per event | none |
| Jargon buster | `config/glossary.yaml`, hand-written definitions | none |
| Rewrite into plain English | Gemini (`GEMINI_API_KEY`, models in `GEMINI_BRIEFING_MODELS`) | yes |
| Delivery | Resend or SMTP, same as the CRS digest | yes |

## How accuracy is enforced

1. The model never writes a market number. Prices, percentages and the market summary sentence
   are built in Python, each table prints the date of the close it shows, and a row from an
   older session (local holiday) or one still trading is labelled.
2. The model may only pick from fetched stories. A story id it invents, or repeats, is dropped.
3. Each headline and summary is checked against that story's source text
   (`writer.check_story_text`): every number with its unit and currency ($3 million is not
   $3 billion, 5 is not 5%, US$ is not S$), spelled-out quantities, direction (rose, up 8%,
   fell, lost), hedges in the source headline (denies, may, in talks, reportedly), and quotes.
   A failed field falls back to the publisher's own wording.
4. "What it means for you" gets the same checks plus a ban on advice and certainty wording.
5. The subject line and opening line are checked clause by clause: each clause must be supported
   by one single story (`writer.check_spanning`). If a picked story is dropped, they are rebuilt.
6. Commentary ("In plain English", "Our read", the big-picture line) may contain no numbers,
   no buy/sell/avoid wording and no certainty ("will fall"); the market mood must match the
   data and may not claim a cause (`writer.check_free_text`).
7. Respect: nothing about anyone's private life and no insults (`writer.disrespectful`). The
   editor is told to report what a person did in their job only. Copy that fails is replaced,
   and a story whose only available wording fails does not run.
8. Event dates come only from `config/events.yaml`. Unconfirmed dates say so. Calendar items
   that have already happened are left off.
9. Nothing degrades silently. A dead feed, a missing price or a failed AI editor is printed in the
   email footer and the run log. If the AI editor is down, `--send` refuses to send raw headlines
   (exit 1) unless `--allow-wire` is passed.
10. Sending: the unsubscribe placeholder is random per run, so a link inside a story can never
    receive a reader's token. A re-run of the same edition only reaches readers not yet served.

Known limits (open, from two adversarial reviews on 2026-11-13):
- A number can be re-attached to the wrong thing inside one story ("lay off 10% of 3,600
  staff" becoming "lays off 3,600 staff"), and a wrong name or claim with no number, direction
  or hedge passes. Every story carries its source link for this reason.
- Small counts ("one", "a couple") and single-quoted quotes are not checked.
- A hedge that sits only in the summary, not the headline, is not enforced.
- The weekly change is "past five sessions", not the calendar week, and the weekly "week
  ahead" depends on the calendar source having rolled over by Sunday 09:00.
- The AI keyword filter still lets through the odd non-AI "chip" story; the editor is the backstop.
- Gemini's free tier rate-limits heavy use (many builds in an hour). Fallback editors are
  configured under `writers:` in `config/briefing.yaml` (Mistral, Cerebras, OpenRouter) and are
  unit-tested, but none has produced a live edition yet: Mistral returned an unusable reply on
  the full prompt and then rate-limited, and the Cerebras key had no credit (2026-11-13).
- Stories from some feeds have a title only. They run as headline, "what it means for you" and
  source link, with no summary (the editor is not allowed to invent one).

## The goal (what every change is judged against)

A non-technical reader in Singapore opens it, understands what happened in AI and in markets in
two minutes, trusts every fact, and forwards it. In order of priority: correct, clear, worth
forwarding, on time (07:30 and 20:30 Singapore time).

## Layout rules (checked at 320, 360, 390, 430, 600, 768 and 1280px)

- Reading order on a phone: opening line, top story, lunch line, markets, more stories, the big
  picture, what to watch, jargon buster. The first story must start within the first screen.
- No sideways scrolling at any width. Body text 16px or more, labels 12px or more.
- Every link and button is at least 44px tall to tap.
- Each story carries a type label from a fixed set (`writer.TAGS`) plus "Singapore" when local.
- The demo page (`scripts/briefing_demo.py`) moves markets, watch list and jargon into a right
  rail from 980px, has section chips to jump around, and follows light and dark themes.

## Maintenance

- `config/events.yaml`: re-verify and extend about once a quarter (last verified 2026-11-12).
- Add or remove a feed, an index or a glossary term in the YAML files. No code change.

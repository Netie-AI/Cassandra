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
| AI news | RSS feeds listed in `config/briefing.yaml` (TechCrunch, The Verge, MIT Tech Review, Ars Technica, Tech in Asia, Business Times, CNA, Google News SG) | none |
| Prices | Yahoo Finance chart API | none |
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
   (`writer.check_story_text`): every number with its unit ($3 million is not $3 billion, 5 is
   not 5%), spelled-out quantities, rose versus fell, a dropped "denies" or "reportedly", and
   quotes. A failed field falls back to the publisher's own wording.
4. Commentary ("In plain English", "Our read", the big-picture line) may contain no numbers and
   no buy or sell wording, and the market mood must match the data (`writer.check_free_text`).
5. Event dates come only from `config/events.yaml`. Unconfirmed dates say so in the email.
6. Nothing degrades silently. A dead feed, a missing price or a failed AI editor is printed in the
   email footer and the run log. If the AI editor is down, `--send` refuses to send raw headlines
   (exit 1) unless `--allow-wire` is passed.
7. The unsubscribe placeholder is random per run, so a link inside a story can never receive a
   reader's unsubscribe token.

Known limits (open, from the adversarial review on 2026-11-13):
- A number can be re-attached to the wrong thing ("lay off 10% of 3,600 staff" becoming
  "lays off 3,600 staff"), and a wrong name or claim with no number passes. Every story
  carries its source link for this reason.
- The subject line and hook are checked against all picked stories together, so they can
  combine a number from one story with the name from another.
- The morning after a US holiday still says "Wall Street overnight" for the previous session
  (the table shows the true date; the title does not adapt yet).
- The weekly change is "past five sessions", not the calendar week.
- Stories from Google News often have a title only, so their summary restates the title.

## The goal (what every change is judged against)

A non-technical reader in Singapore opens it, understands what happened in AI and in markets in
two minutes, trusts every fact, and forwards it. In order of priority: correct, clear, worth
forwarding, on time (07:30 and 20:30 Singapore time).

## Maintenance

- `config/events.yaml`: re-verify and extend about once a quarter (last verified 2026-11-12).
- Add or remove a feed, an index or a glossary term in the YAML files. No code change.

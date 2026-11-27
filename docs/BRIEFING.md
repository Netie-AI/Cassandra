# AI Briefing

A plain-English AI and markets newsletter for non-technical readers in Singapore and beyond.
It reuses the existing subscriber list and Resend/SMTP sender (`src/newsletter/send.py`).

## Editions (Singapore time, set in `config/briefing.yaml`)

| Edition | When | What is in it |
|---|---|---|
| Morning | Mon to Fri 07:30 | Greater China, Singapore and Asia-Pacific first, then how Wall Street closed overnight, AI news while you slept, what to watch (Monday looks back over the weekend) |
| Evening | Mon to Fri 20:30 | The US first (last close, futures before tonight's open, tonight's data), then how China and Asia traded today, today's AI news |
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

On the box (no systemd unit), cron calls `scripts/run_daily_box.sh`. That script fetches Gemini
scheduled actions, builds the edition, and pushes a `gh-pages` checkout as `cassandra-briefing`.
It exits non-zero if the fetch fails, if a Gemini check held the edition, or if the editor fell
back to wire copy. Suggested UTC crontab, which is 08:05 and 20:35 Singapore (inside the edition
window, and after the 07:50 checks):

```
5 0 * * 1-5   /path/to/Cassandra/scripts/run_daily_box.sh
35 12 * * 1-5 /path/to/Cassandra/scripts/run_daily_box.sh
```

`BRIEFING_SITE_DIR` may point at an existing `gh-pages` checkout. If it is unset, the script
clones `https://github.com/Netie-AI/Cassandra.git` (branch `gh-pages`) next to the repo. Push
uses credentials already on the box. The script does not mint tokens and does not print key values.

## Daily website (one link for phone and laptop)

The box publishes each edition to GitHub Pages at https://netie-ai.github.io/Cassandra/briefing/.
`.github/workflows/briefing.yml` is manual only (`workflow_dispatch`). The old GitHub schedule
was removed so a cloud run cannot race the box. The link never changes: readers bookmark it or
use "Add to Home Screen" (Android and iPhone get a Cassandra app icon). Each run's summary shows
the message to paste into the group chat; it is also at `.../briefing/message.txt`. Edition JSON
files are kept in `briefing/data/` on `gh-pages`.

`GEMINI_API_KEY` is optional. A blank key skips Gemini and is not a failure. Optional cloud
fallbacks are `MISTRAL_API_KEY` and `CEREBRAS_API_KEY`. The on-box editor is OpenVault
(`OV_CASSANDRA_TOKEN`, `http://127.0.0.1:5000/v1/chat/completions`, model `claude-sonnet-5-5`),
the first entry under `writers:` in `config/briefing.yaml`. To run the workflow by hand: Actions
tab, "Daily AI Briefing", Run workflow. A held edition is not pushed. A manual cloud run that
falls back to wire copy is still published after one retry, labelled on the page. The box runner
does not publish wire copy. The page is public: it carries public news and links only. Build it
locally with `python scripts/briefing_site.py OUT_DIR reports/briefings URL`.

### Dead-man

`.github/workflows/briefing-deadman.yml` runs every 6 hours (`0 */6 * * *`) and on demand.
`scripts/briefing_deadman.py` fails the job when
https://netie-ai.github.io/Cassandra/briefing/data is older than 26 hours on a Singapore weekday.
Saturday and Sunday do not fail. GitHub Pages usually does not list that directory, so the script
may learn file names from the GitHub contents API and then read the JSON from the pages URL.
If that yields no timestamp it uses `briefing/latest.json` and says so. Monday before the morning
edition can fail, because Friday's file is already older than 26 hours. That is the threshold
as specified.

### Gemini scheduled actions (extra candidates)

`scripts/gemini_fetch.py` attaches with Playwright over CDP (`GEMINI_CDP_URL`, default
`http://127.0.0.1:9223`) to a Chrome that is already signed in. It opens
https://gemini.google.com/app, then Scheduled actions, then the latest result for each title in
`config/gemini_actions.yaml` (the four daily prompts in `docs/BRIEFING_GEMINI_PROMPTS.md`). If the
page is accounts.google.com it exits 3 and prints `needs-login`. It never types credentials.
`--dry-run` prints row counts and writes nothing. Results land in `inbox/gemini/` as
`<YYYY-MM-DD>-<action>.md` and `.json` (gitignored).

The briefing reads that inbox only when `CASSANDRA_GEMINI_INBOX=1` (default off; the box script
turns it on). Files not dated today in Asia/Singapore are ignored. Scout rows become tier-2
stories (source = publisher, url = link, summary = sentence). Rows without an http(s) link, and
rows whose URL is already in the feeds, are dropped. Text is stripped and capped before the
editor sees it. A Market check or Editor's check file that says MISMATCH or HOLD sets
`held` on the edition, prints it in the run summary, labels the page, and blocks publish.
The live Gemini selectors are not verified. See the gaps at the end of this file.

### Daily Crash Risk Score on the same schedule

The same workflow runs `python -m src.pipeline --history site/briefing/data/score_history.json`
(continue-on-error, so the briefing still publishes when a data source is down). The runner starts
with an empty SQLite file, so the history lives on `gh-pages` and grows by one row per run; it is
also published at `.../briefing/score_history.json`. A fresh clone or container seeds the API from
`store/seed/score_history.json` (written by the same command) so `/api/latest`, `/api/dashboard`
and the home page charts show the last real run instead of a 404. Refresh the seed with
`python -m src.pipeline --history store/seed/score_history.json`. Keyless runs have low coverage
(about 25%: most factors sit at neutral defaults); the home page says so.

## Where the information comes from

| Part | Source | Key needed |
|---|---|---|
| AI news | RSS feeds listed in `config/briefing.yaml`: general press (BBC, NYT, Guardian, SCMP), tech press, Singapore and regional press, China tech (SCMP China tech, CGTN, TechNode, Pandaily), defence (Defense One, Breaking Defense), research (IEEE Spectrum, Google DeepMind, Import AI) and company blogs (OpenAI, Google, Nvidia) | none |
| Prices | Yahoo Finance chart API, checked against Tencent Finance (China, Hong Kong, US) and Sina Finance (Japan, Korea, Taiwan, Australia) where a row names `verify:` in `config/briefing.yaml`. CSI 300 and Hang Seng TECH come from Tencent alone (Yahoo has no daily history for them) | none |
| What to expect next | US data releases from the ForexFactory weekly calendar (US, high and medium impact, only those with a plain-English meaning in `config/briefing.yaml`), and results dates for a watchlist of big tech names from Nasdaq's public calendar | none |
| Events | `config/events.yaml`, hand-curated with a source URL per event | none |
| Jargon buster | `config/glossary.yaml`, hand-written definitions | none |
| Rewrite into plain English | Gemini when `GEMINI_API_KEY` is set, else the first configured writer whose key is set. On the box that is OpenVault (`OV_CASSANDRA_TOKEN`) | optional |
| Extra candidates | Gemini scheduled actions in `inbox/gemini/`, only if `CASSANDRA_GEMINI_INBOX=1` | no (signed-in Chrome over CDP) |
| Delivery | Resend or SMTP, same as the CRS digest | yes |

## How accuracy is enforced

1. The model never writes a market number. Prices, percentages and the market summary sentence
   are built in Python, each table prints the date of the close it shows, and a row from an
   older session (local holiday) or one still trading is labelled.
   A second, independent provider checks each figure where one exists (`src/briefing/crosscheck.py`):
   same closed session and within 0.25 points is "confirmed"; a larger gap withholds the figure
   ("sources disagree") and logs both numbers; while a market trades the two are only compared
   for gross errors (1 point). Singapore rows, the SOX index, currencies and futures have no
   reliable second source (Sina's rows for them were measured stale by months) and are single-source.
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
7a. Sensitive topics (owner's rule, 2026-11-21): a story that matches `sensitive_terms` or
   `sensitive_pairs` (a place such as China or Taiwan together with a word such as export, ban,
   probe, military, ties or short seller; political leaders) in `config/briefing.yaml` is left
   out before the editor sees it, and so is any story whose edited draft strays into one. No
   commentary line may touch these topics (`writer._sensitive`).
7b. Priority topics (owner's choice, `priority_topics` in the config): China technology progress,
   frontier AI and what comes next, the hardware and power shortage, and AI in defence. Matching
   stories are offered to the editor first and marked; the editor gives China's progress a place
   in each channel when a story exists. This decides which stories run, not what they say: the
   checks above apply to every word.
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
- Gemini's free tier rate-limits heavy use (many builds in an hour). A blank `GEMINI_API_KEY`
  skips Gemini. Writers under `writers:` in `config/briefing.yaml` then run in order: OpenVault
  on the box, then Mistral, Cerebras, OpenRouter. OpenVault is retried once without JSON mode
  when that endpoint rejects `response_format` or a large `max_tokens`. The fact check is the
  same for every editor. Mistral and Cerebras are unit-tested and have not produced a live
  edition: Mistral returned an unusable reply on the full prompt and then rate-limited, and the
  Cerebras key had no credit (2026-11-13).
- `config/xinliaoxin_spec.yaml` is an empty template (`items: []`, fields `id`, `text`,
  `check_type`). `src/briefing/spec_check.py` can ask the OpenVault Opus route
  (`claude-opus-5-5` on the same local endpoint) for PASS or FAIL per item. No spec text is
  filled in. Nothing calls it from the daily run.
- CSI 300 and Hang Seng TECH (Tencent only) are always marked as closed, so a run during Asian
  trading hours uses past tense for those two rows. The scheduled 07:30 and 20:30 runs are outside
  those hours.
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

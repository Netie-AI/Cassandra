#!/usr/bin/env bash
# Daily AI Briefing on the box. No systemd unit: call this from cron.
#
# Suggested crontab, host clock UTC (08:05 and 20:35 Asia/Singapore, inside the
# 90-minute edition window, and after the 07:50 Gemini checks):
#   5 0 * * 1-5   /path/to/Cassandra/scripts/run_daily_box.sh
#   35 12 * * 1-5 /path/to/Cassandra/scripts/run_daily_box.sh
#
# Exits non-zero, with a one-line reason on stderr, when the Gemini fetch fails
# or the edition is held or the editor fell back to wire copy.
# Exit 3 is needs-login (signed out, consent, or the unusual-traffic page).
# Exit 4 is none-found (chat missing, no usable response, or no scheduled tasks).
# Both stop here, before the briefing build, and nothing is published.
# This script never prints a key value.
#
# BRIEFING_SITE_DIR: a checkout of the gh-pages branch. Created by cloning the
# public repo when it is missing. Push uses whatever credentials the box already has.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SITE="${BRIEFING_SITE_DIR:-$ROOT/../cassandra-gh-pages}"
export CASSANDRA_GEMINI_INBOX=1

set +e
python scripts/gemini_fetch.py
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  if [[ "$rc" -eq 3 ]]; then
    echo "gemini fetch failed: needs-login" >&2
  elif [[ "$rc" -eq 4 ]]; then
    echo "gemini fetch failed: none-found" >&2
  else
    echo "gemini fetch failed: exit $rc" >&2
  fi
  exit "$rc"
fi

python -m src.briefing --edition auto

set +e
decision="$(python -m src.briefing.gate)"
rc=$?
set -e
if [[ "$rc" -ne 0 ]]; then
  exit "$rc"
fi
if [[ "$decision" == "nothing due" ]]; then
  echo "nothing due, not publishing"
  exit 0
fi

if [[ ! -d "$SITE/.git" ]]; then
  git clone --branch gh-pages --single-branch https://github.com/Netie-AI/Cassandra.git "$SITE"
fi
branch="$(git -C "$SITE" rev-parse --abbrev-ref HEAD)"
if [[ "$branch" != "gh-pages" ]]; then
  echo "site checkout is on $branch, expected gh-pages" >&2
  exit 1
fi
git -C "$SITE" pull --ff-only
mkdir -p "$SITE/briefing/data"
cp -f reports/briefings/????-??-??-*.json "$SITE/briefing/data/"
python scripts/briefing_site.py "$SITE/briefing" "$SITE/briefing/data" \
  "${SITE_URL:-https://netie-ai.github.io/Cassandra/briefing/}"
git -C "$SITE" config user.name "cassandra-briefing"
git -C "$SITE" config user.email "cassandra-briefing@users.noreply.github.com"
git -C "$SITE" add briefing
if git -C "$SITE" diff --cached --quiet; then
  echo "nothing new to publish"
  exit 0
fi
git -C "$SITE" commit -m "briefing: $(date -u +%Y-%m-%dT%H:%MZ)"
git -C "$SITE" push

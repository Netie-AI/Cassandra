#!/usr/bin/env python3
"""Fail when the published briefing is older than 26 hours on a Singapore weekday.

The age is read from https://netie-ai.github.io/Cassandra/briefing/data
(generated_at inside the JSON files, or Last-Modified). GitHub Pages often does
not list a directory, so file names may come from the GitHub contents API and the
bytes are still fetched from that pages URL. If the data URL yields no timestamp,
briefing/latest.json (written by the same publish) is the fallback, and the
message says so.

Saturday and Sunday in Asia/Singapore exit 0. A weekday with no readable
timestamp exits 1. Monday morning can fail until that day's edition is up,
because Friday's file is already older than 26 hours.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

SG = ZoneInfo("Asia/Singapore")
DATA_URL = "https://netie-ai.github.io/Cassandra/briefing/data"
LATEST_URL = "https://netie-ai.github.io/Cassandra/briefing/latest.json"
API_URL = "https://api.github.com/repos/Netie-AI/Cassandra/contents/briefing/data?ref=gh-pages"
MAX_AGE_S = 26 * 3600
_FILE = re.compile(r"\d{4}-\d{2}-\d{2}-.+\.json")


def decide(now: dt.datetime, newest: dt.datetime | None) -> tuple[int, str]:
    """(exit code, one-line reason). Weekend never fails. Older than 26 hours on a weekday fails."""
    local = now.astimezone(SG)
    if local.weekday() >= 5:
        return 0, f"weekend ({local:%A} Singapore): dead-man does not fail"
    if newest is None:
        return 1, "weekday and no timestamp could be read from the briefing data URL"
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=dt.timezone.utc)
    age = (now.astimezone(dt.timezone.utc) - newest.astimezone(dt.timezone.utc)).total_seconds()
    hours = age / 3600
    if age > MAX_AGE_S:
        return 1, f"weekday and briefing data is {hours:.1f} hours old, limit is 26"
    return 0, f"weekday and briefing data is {hours:.1f} hours old"


def _parse_iso(raw: str) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _generated_at(text: str) -> dt.datetime | None:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and data.get("generated_at"):
        return _parse_iso(str(data["generated_at"]))
    return None


def _pages_url(href: str) -> str | None:
    if href.startswith("http://") or href.startswith("https://"):
        url = href
    elif href.startswith("/"):
        url = "https://netie-ai.github.io" + href
    else:
        url = DATA_URL.rstrip("/") + "/" + href.lstrip("./")
    host = (urlsplit(url).hostname or "").lower()
    if host != "netie-ai.github.io":
        return None
    return url


def collect(get) -> tuple[dt.datetime | None, str]:
    """Newest timestamp from the briefing data URL.

    get(url) -> (status, text, last_modified or None).
    Returns (stamp, how). `how` is empty when nothing was readable.
    """
    stamps: list[dt.datetime] = []
    status, text, modified = get(DATA_URL)
    if modified:
        stamps.append(modified)
    if status == 200:
        found = _generated_at(text or "")
        if found:
            stamps.append(found)
    names: list[str] = []
    if status == 200 and text:
        for href in re.findall(r'href=["\']([^"\']+\.json)["\']', text, re.I):
            url = _pages_url(href)
            if url:
                names.append(url)
    if not names:
        api_status, api_text, _ = get(API_URL)
        if api_status == 200 and api_text:
            try:
                listing = json.loads(api_text)
            except json.JSONDecodeError:
                listing = []
            if isinstance(listing, list):
                files = sorted(str(item.get("name") or "") for item in listing if isinstance(item, dict))
                for name in files:
                    if _FILE.fullmatch(name):
                        url = _pages_url(name)
                        if url:
                            names.append(url)
    for url in names[-8:]:
        st, body, mod = get(url)
        if mod:
            stamps.append(mod)
        if st == 200:
            found = _generated_at(body or "")
            if found:
                stamps.append(found)
    if stamps:
        return max(stamps), "from briefing/data"
    st, body, mod = get(LATEST_URL)
    latest = mod
    if st == 200:
        found = _generated_at(body or "")
        if found and (latest is None or found > latest):
            latest = found
    if latest:
        return latest, "briefing/data had no timestamp; used briefing/latest.json"
    return None, ""


def _http_get(url: str):
    import httpx
    try:
        r = httpx.get(url, timeout=30, follow_redirects=True,
                      headers={"User-Agent": "cassandra-briefing-deadman"})
    except httpx.HTTPError:
        return 0, "", None
    modified = None
    raw = r.headers.get("last-modified")
    if raw:
        try:
            modified = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            modified = None
        if modified is not None and modified.tzinfo is None:
            modified = modified.replace(tzinfo=dt.timezone.utc)
    return r.status_code, r.text, modified


def main(argv: list[str] | None = None) -> int:
    del argv
    newest, how = collect(_http_get)
    code, msg = decide(dt.datetime.now(dt.timezone.utc), newest)
    if how:
        msg = f"{msg} ({how})"
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())

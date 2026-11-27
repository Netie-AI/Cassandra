"""Gemini scheduled-action drops as extra briefing candidates.

Reads inbox/gemini/YYYY-MM-DD-*.json written by scripts/gemini_fetch.py.
The files are untrusted: markup is stripped, lengths are capped, and instruction-shaped
sentences are dropped before any text can reach the editor.

A file is used only when its name is today's date in Asia/Singapore. Market check and
Editor's check files that report MISMATCH or HOLD set held=True. They do not become stories.
Scout rows become Story objects (tier 2, source = publisher, url = link, summary = sentence).

Off unless CASSANDRA_GEMINI_INBOX=1.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from . import sources
from .sources import Story

SG = ZoneInfo("Asia/Singapore")
MAX_TITLE = 300
MAX_SUMMARY = 400
MAX_SOURCE = 80
MAX_TOPIC = 80
MAX_STORIES = 32
_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]*)\.json$")
_CHECK = re.compile(r"market[\s-]check|editor", re.I)
_INJECT = re.compile(
    r"(?i)(ignore\s+(?:all\s+|any\s+)?(?:previous|prior|above)\s+instructions|"
    r"you\s+are\s+now|system\s+prompt|do\s+not\s+follow|disregard\s+(?:all\s+)?(?:previous|prior)|"
    r"</?\s*script|```)"
)
_ROW_KEYS = ("topic", "headline", "publisher", "published", "link", "sentence")
# Field, then header needles, first unused matching column wins. Order matters:
# "link" before "match", "sentence" before "problem", so a check table still maps.
_COLUMNS = (
    ("link", ("link",)),
    ("headline", ("headline", "instrument")),
    ("publisher", ("publisher",)),
    ("published", ("published", "session")),
    ("sentence", ("sentence", "what is wrong", "factual")),
    ("topic", ("topic", "match", "problem", "ok or")),
)


def inbox_dir() -> Path:
    override = os.getenv("CASSANDRA_GEMINI_INBOX_DIR", "").strip()
    return Path(override) if override else sources.ROOT / "inbox" / "gemini"


def enabled() -> bool:
    """Default off. Only the exact value 1 turns the inbox on."""
    return os.getenv("CASSANDRA_GEMINI_INBOX", "").strip() == "1"


_LEFTOVER = re.compile(r"(?i)(?:and\s+)?(?:say|do|print|output|reply|respond)\b.*")


def _safe_text(text: str, limit: int) -> str:
    """Plain text only. Instruction phrases are removed, not passed through."""
    text = sources._clean(text or "", max(limit * 4, limit))
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("`", "").replace("*", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", text)
    text = _INJECT.sub(" ", text)
    kept = []
    for part in re.split(r"(?<=[.!?])\s+", text):
        part = part.strip(" ,;:-")
        if part and not _LEFTOVER.fullmatch(part):
            kept.append(part)
    text = re.sub(r"\s+", " ", " ".join(kept)).strip()
    return text[:limit]


def _http_url(url: str) -> str:
    url = (url or "").strip()
    if any(c in url for c in ("\n", "\r", "\t", " ")) or len(url) > 500:
        return ""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    return url


def _url_key(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    query = f"?{parts.query}" if parts.query else ""
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}{path}{query}"


def _parse_when(raw: str | None) -> dt.datetime | None:
    """A timezone-aware instant, or None. No timezone means the row is unverifiable."""
    if not raw or not str(raw).strip():
        return None
    text = re.sub(r"\b(SGT|HKT|MYT)\b", "+0800", str(raw).strip())
    parsed = sources._parse_date(text)
    if parsed:
        return parsed
    for fmt in ("%d %b %Y %H:%M %z", "%d %b %Y, %H:%M %z", "%Y-%m-%d %H:%M %z",
                "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            parsed = dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(dt.timezone.utc)
    return None


def _sg_date(now: dt.datetime) -> dt.date:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(SG).date()


def _looks_like_row(line: str) -> bool:
    return line.strip().startswith("|")


def _split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_separator(cells: list[str]) -> bool:
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", c.replace(" ", "")) or c == "" for c in cells)


def _map_row(headers: list[str], cells: list[str]) -> dict[str, str]:
    used: set[int] = set()
    out = {k: "" for k in _ROW_KEYS}
    low = [h.lower() for h in headers]
    for key, needles in _COLUMNS:
        for i, header in enumerate(low):
            if i in used:
                continue
            if any(n in header for n in needles):
                used.add(i)
                out[key] = cells[i] if i < len(cells) else ""
                break
    return out


def parse_markdown_response(text: str) -> dict:
    """Last markdown table in a Gemini reply, plus the non-table lines around it.

    Returns {"rows": [{topic, headline, publisher, published, link, sentence}], "closing": str}.
    The closing line is where ALL MATCH, MISMATCH, HOLD and POST are expected.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    tables: list[tuple[int, int, list[str], list[list[str]]]] = []
    i = 0
    while i < len(lines):
        if not _looks_like_row(lines[i]):
            i += 1
            continue
        start = i
        block: list[str] = []
        while i < len(lines) and _looks_like_row(lines[i]):
            block.append(lines[i])
            i += 1
        parsed = [_split_row(ln) for ln in block]
        parsed = [c for c in parsed if any(x.strip() for x in c) and not _is_separator(c)]
        if len(parsed) >= 2 and len(parsed[0]) >= 2:
            tables.append((start, i, parsed[0], parsed[1:]))
    if not tables:
        closing = "\n".join(ln.strip() for ln in lines if ln.strip())
        return {"rows": [], "closing": closing}
    start, end, headers, data = tables[-1]
    lead = [ln.strip() for ln in lines[:start] if ln.strip() and not _looks_like_row(ln)]
    tail = [ln.strip() for ln in lines[end:] if ln.strip() and not _looks_like_row(ln)]
    # Keep a short tail. A verdict is one line; the rest of a long reply is not needed.
    closing_bits = [ln for ln in (lead[-2:] + tail) if ln]
    return {"rows": [_map_row(headers, row) for row in data], "closing": "\n".join(closing_bits)}


def _is_check(action: str, filename: str) -> bool:
    return bool(_CHECK.search(f"{action} {filename}"))


def _signals(closing: str, rows: list[dict]) -> list[str]:
    """MISMATCH and HOLD only. Scout prose is not passed here."""
    found: list[str] = []
    if re.search(r"\bMISMATCH\b", closing or ""):
        found.append("MISMATCH")
    if re.search(r"\bHOLD\b", closing or ""):
        found.append("HOLD")
    for row in rows:
        status = str(row.get("topic") or "").strip()
        if re.fullmatch(r"(?i)mismatch", status) and "MISMATCH" not in found:
            found.append("MISMATCH")
        if re.fullmatch(r"(?i)hold|problem|no", status) and "HOLD" not in found:
            found.append("HOLD")
    return found


def _channel(topic: str, title: str, keywords: list[str] | None) -> str:
    blob = f"{topic} {title}"
    if re.search(r"(?<![a-z0-9])markets?(?![a-z0-9])", blob.lower()):
        return "markets"
    if keywords and sources.has_term(blob, keywords):
        return "markets"
    return "ai"


def read_inbox(directory: Path, existing: list[Story], *, now: dt.datetime,
               market_keywords: list[str] | None = None) -> tuple[list[Story], list[str], bool, str]:
    """(stories, operator notes, held, held_reason).

    Operator notes are prefixed 'gemini inbox ' so the page can hide them.
    held_reason is a short label with no raw model prose. Stale files cannot hold a run.
    """
    today = _sg_date(now)
    notes: list[str] = []
    stories: list[Story] = []
    seen = {_url_key(s.url) for s in existing if s.url}
    reasons: list[str] = []
    if not directory.is_dir():
        return [], ["gemini inbox directory missing"], False, ""
    paths = sorted(p for p in directory.glob("*.json") if p.is_file())
    for path in paths:
        match = _NAME.match(path.name)
        if not match:
            notes.append(f"gemini inbox {path.name}: skipped, name is not YYYY-MM-DD-action.json")
            continue
        try:
            file_day = dt.date.fromisoformat(match.group(1))
        except ValueError:
            notes.append(f"gemini inbox {path.name}: skipped, bad date")
            continue
        if file_day != today:
            notes.append(f"gemini inbox {path.name}: skipped, not dated today in Asia/Singapore")
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            notes.append(f"gemini inbox {path.name}: skipped, unreadable")
            continue
        if not isinstance(doc, dict):
            notes.append(f"gemini inbox {path.name}: skipped, unreadable")
            continue
        fetched = str(doc.get("fetched_at") or "").strip()
        if fetched:
            fetched_at = _parse_when(fetched)
            if fetched_at is None or fetched_at.astimezone(SG).date() != today:
                notes.append(f"gemini inbox {path.name}: skipped, not dated today in Asia/Singapore")
                continue
        action = _safe_text(str(doc.get("action") or match.group(2)), MAX_TOPIC) or match.group(2)
        raw_rows = doc.get("rows") if isinstance(doc.get("rows"), list) else []
        rows = [r for r in raw_rows if isinstance(r, dict)]
        if _is_check(action, path.name):
            signals = _signals(str(doc.get("closing") or ""), rows)
            if signals:
                reasons.append(f"{action} reported {' and '.join(signals)}.")
            continue
        skipped_link = skipped_dup = skipped_when = skipped_empty = 0
        for row in rows:
            if len(stories) >= MAX_STORIES:
                break
            url = _http_url(str(row.get("link") or ""))
            if not url:
                skipped_link += 1
                continue
            key = _url_key(url)
            if key in seen:
                skipped_dup += 1
                continue
            title = _safe_text(str(row.get("headline") or ""), MAX_TITLE)
            summary = _safe_text(str(row.get("sentence") or ""), MAX_SUMMARY)
            source = _safe_text(str(row.get("publisher") or ""), MAX_SOURCE) or "Gemini"
            topic = _safe_text(str(row.get("topic") or ""), MAX_TOPIC)
            if not title:
                skipped_empty += 1
                continue
            published = _parse_when(str(row.get("published") or ""))
            if published is None:
                skipped_when += 1
                continue
            region = "sg" if "singapore" in f"{title} {summary}".lower() else "global"
            stories.append(Story(
                id="", title=title, summary=summary, url=url, source=source, region=region,
                published=published, channel=_channel(topic, title, market_keywords), tier=2,
            ))
            seen.add(key)
        if skipped_link:
            notes.append(f"gemini inbox {path.name}: {skipped_link} row(s) skipped, no http(s) link")
        if skipped_dup:
            notes.append(f"gemini inbox {path.name}: {skipped_dup} duplicate row(s) skipped")
        if skipped_when:
            notes.append(f"gemini inbox {path.name}: {skipped_when} row(s) skipped, no dated timezone")
        if skipped_empty:
            notes.append(f"gemini inbox {path.name}: {skipped_empty} row(s) skipped, empty after cleaning")
    held_reason = " ".join(reasons)[:400]
    return stories, notes, bool(reasons), held_reason

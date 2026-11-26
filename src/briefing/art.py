"""Story artwork for the briefing website: original inline SVG, one motif per story tag.

No photos are fetched or hotlinked (publisher images are not ours to republish). Each story gets
an illustration of its topic, varied by a hash of its URL so a page of stories does not repeat the
same picture. Output is a self-contained <svg> string; the page needs no image requests.
"""
from __future__ import annotations

import hashlib
from html import escape

# Ink, paper and one accent per tag, matched to the page palette.
INK = "#141414"
PAPER = "#f1efe9"
ACCENTS = {
    "Industry": "#b45309", "Policy": "#1d4ed8", "Enterprise": "#0f766e", "Research": "#7c3aed",
    "Consumer": "#be185d", "Earnings": "#15803d", "Economy": "#a16207", "Markets": "#b91c1c",
}
DEFAULT_ACCENT = "#44403c"


def _motif(tag: str, a: str) -> str:
    """Topic drawing on a 0..120 x 0..80 canvas."""
    if tag == "Industry":           # chip die with pins
        pins = "".join(f'<rect x="{38 + i * 9}" y="12" width="3" height="8" fill="{INK}"/>'
                       f'<rect x="{38 + i * 9}" y="60" width="3" height="8" fill="{INK}"/>' for i in range(5))
        return (f'{pins}<rect x="32" y="20" width="56" height="40" rx="3" fill="{INK}"/>'
                f'<rect x="44" y="30" width="32" height="20" fill="{a}"/>'
                f'<path d="M48 40h24M60 34v12" stroke="{PAPER}" stroke-width="2"/>')
    if tag == "Policy":             # columned building
        cols = "".join(f'<rect x="{36 + i * 12}" y="34" width="6" height="26" fill="{INK}"/>' for i in range(5))
        return (f'<path d="M28 32 60 14 92 32Z" fill="{a}"/>{cols}'
                f'<rect x="28" y="60" width="64" height="6" fill="{INK}"/>')
    if tag == "Enterprise":         # office tower with lit windows
        win = "".join(f'<rect x="{46 + (i % 3) * 10}" y="{22 + (i // 3) * 10}" width="6" height="6" '
                      f'fill="{a if i in (1, 5, 9) else PAPER}"/>' for i in range(12))
        return f'<rect x="40" y="16" width="40" height="52" fill="{INK}"/>{win}<rect x="28" y="66" width="64" height="3" fill="{INK}"/>'
    if tag == "Research":           # network of nodes
        pts = [(34, 52), (50, 24), (62, 48), (78, 22), (88, 54)]
        lines = "".join(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{INK}" stroke-width="2"/>'
                        for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
        dots = "".join(f'<circle cx="{x}" cy="{y}" r="{6 if i == 2 else 4}" fill="{a if i == 2 else INK}"/>'
                       for i, (x, y) in enumerate(pts))
        return lines + dots
    if tag == "Consumer":           # phone with chat bubble
        return (f'<rect x="44" y="12" width="32" height="56" rx="5" fill="{INK}"/>'
                f'<rect x="48" y="18" width="24" height="40" fill="{PAPER}"/>'
                f'<path d="M52 26h16v9h-11l-5 4z" fill="{a}"/><rect x="52" y="44" width="14" height="4" fill="{INK}"/>')
    if tag == "Earnings":           # rising bars
        hs = (14, 22, 18, 32, 40)
        return "".join(f'<rect x="{30 + i * 13}" y="{66 - h}" width="9" height="{h}" '
                       f'fill="{a if i == 4 else INK}"/>' for i, h in enumerate(hs)) + \
            f'<rect x="26" y="66" width="70" height="2" fill="{INK}"/>'
    if tag == "Economy":            # globe with meridians
        return (f'<circle cx="60" cy="40" r="24" fill="none" stroke="{INK}" stroke-width="3"/>'
                f'<ellipse cx="60" cy="40" rx="10" ry="24" fill="none" stroke="{INK}" stroke-width="2"/>'
                f'<path d="M36 40h48M40 28h40M40 52h40" stroke="{INK}" stroke-width="2"/>'
                f'<circle cx="80" cy="22" r="7" fill="{a}"/>')
    if tag == "Markets":            # candlesticks
        c = [(34, 30, 48, 1), (46, 36, 54, 0), (58, 26, 44, 1), (70, 34, 56, 0), (82, 20, 38, 1)]
        return "".join(f'<line x1="{x + 3}" y1="{t - 6}" x2="{x + 3}" y2="{b + 6}" stroke="{INK}" stroke-width="1.5"/>'
                       f'<rect x="{x}" y="{t}" width="7" height="{b - t}" fill="{a if up else INK}"/>'
                       for x, t, b, up in c)
    return (f'<circle cx="60" cy="40" r="18" fill="{INK}"/><circle cx="60" cy="40" r="8" fill="{a}"/>'
            f'<path d="M30 40q30-30 60 0q-30 30-60 0z" fill="none" stroke="{INK}" stroke-width="2"/>')


def story_art(story: dict, *, wide: bool = False) -> str:
    """Inline SVG for one story. wide=True gives a 3:1 banner for the lead story, else a square tile."""
    tag = story.get("tag") or ""
    accent = ACCENTS.get(tag, DEFAULT_ACCENT)
    seed = int(hashlib.sha1((story.get("url") or story.get("headline") or "").encode()).hexdigest()[:8], 16)
    step = 8 + seed % 7
    angle = (seed >> 4) % 180
    w, h = (360, 120) if wide else (120, 120)
    ox, oy = ((w - 120) // 2, 20) if wide else (0, 20)
    label = escape(f"Illustration: {tag or 'AI'} story", quote=True)
    return (f'<svg class="art{" wide" if wide else ""}" viewBox="0 0 {w} {h}" role="img" aria-label="{label}" '
            f'xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="xMidYMid slice">'
            f'<defs><pattern id="p{seed:x}" width="{step}" height="{step}" patternUnits="userSpaceOnUse" '
            f'patternTransform="rotate({angle})"><line x1="0" y1="0" x2="0" y2="{step}" stroke="{accent}" '
            f'stroke-opacity=".18" stroke-width="2"/></pattern></defs>'
            f'<rect width="{w}" height="{h}" fill="{PAPER}"/><rect width="{w}" height="{h}" fill="url(#p{seed:x})"/>'
            f'<g transform="translate({ox} {oy})">{_motif(tag, accent)}</g></svg>')

"""Build the newsletter website: python scripts/briefing_site.py SITE_DIR DATA_DIR URL

SITE_DIR/index.html          the latest Morning and Evening editions (newest first), phone first, with
                             link-preview tags so WhatsApp and WeLink show the title and image
SITE_DIR/share.png           1200x630 card: the market teaser and the top headlines (needs Playwright;
                             skipped with a printed note when it is not installed)
SITE_DIR/manifest.webmanifest + icons, so "Add to Home Screen" gives readers an app icon
SITE_DIR/message.txt         short English message for the group chat
SITE_DIR/message_zh.txt      the Chinese group message (src/briefing/message_zh.py), without the
                             internal tool section, which is added on the owner's laptop
SITE_DIR/latest.json         the newest edition, for scripts/briefing_message_zh.py on the laptop
DATA_DIR holds the edition JSON files written by `python -m src.briefing`.
"""
import json
import pathlib
import shutil
import sys
from html import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
from briefing_demo import load_editions, render  # noqa: E402
from src.briefing import message_zh  # noqa: E402

MANIFEST = ('{"name": "Cassandra AI Briefing", "short_name": "Cassandra", "start_url": ".", "display": "standalone",'
            ' "background_color": "#fbfaf8", "theme_color": "#141414", "icons": ['
            '{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},'
            '{"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}\n')


def head(title: str, description: str, url: str) -> str:
    t, d = escape(title, quote=True), escape(description, quote=True)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            '<meta name="theme-color" content="#141414"><link rel="manifest" href="manifest.webmanifest">'
            '<link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="icon-192.png">'
            '<meta name="apple-mobile-web-app-title" content="Cassandra">'
            f'<meta property="og:type" content="website"><meta property="og:url" content="{escape(url, quote=True)}">'
            f'<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">'
            f'<meta property="og:image" content="{escape(url, quote=True)}share.png">'
            '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
            '<meta name="twitter:card" content="summary_large_image">')


def message(ed: dict, url: str) -> str:
    """Plain text for WeLink or WhatsApp: title, up to 4 headlines, the market line, the link."""
    lines = [f"Cassandra {ed['title']} · {ed['date_label']}", ""]
    lines += [f"• {s['headline']}" for s in ed["stories"][:4]]
    if ed["markets"]:
        lines += ["", ed["markets"][0]["summary"]]
    return "\n".join(lines + ["", f"Read in 3 minutes: {url}", ""])


CARD = """<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;width:1200px;height:630px;background:#141414;color:#fbfaf8;
font-family:"Noto Sans CJK SC","WenQuanYi Zen Hei","Microsoft YaHei",sans-serif}}
.w{{box-sizing:border-box;height:630px;padding:56px 64px;display:flex;flex-direction:column;gap:22px}}
.k{{font-size:26px;letter-spacing:.12em;color:#f87171}} .t{{font-size:62px;font-weight:700;line-height:1.2}}
ul{{margin:0;padding:0 0 0 28px;font-size:30px;line-height:1.45;color:#e7e5e4}}
.f{{margin-top:auto;font-size:24px;color:#a3a3ad;display:flex;justify-content:space-between}}
</style></head><body><div class="w"><div class="k">市场洞悉 · CASSANDRA</div><div class="t">{teaser}</div>
<ul>{items}</ul><div class="f"><span>{date}</span><span>不构成投资建议</span></div></div></body></html>"""


def share_card(site: pathlib.Path, ed: dict, teaser: str, headlines: list[str]) -> str:
    """Render share.png with a headless browser. Returns a note for the run log."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "share.png skipped: Python Playwright is not installed"
    html = CARD.format(teaser=escape(teaser), date=escape(ed["date_label"]),
                       items="".join(f"<li>{escape(h)}</li>" for h in headlines[:3]))
    page_file = site / "_share.html"
    page_file.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1200, "height": 630})
            pg.goto(page_file.resolve().as_uri())
            pg.screenshot(path=str(site / "share.png"))
            b.close()
        return "share.png written"
    except Exception as exc:
        return f"share.png failed ({type(exc).__name__})"
    finally:
        page_file.unlink(missing_ok=True)


def build(site: pathlib.Path, data: pathlib.Path, url: str, *, card: bool = True) -> str:
    eds = load_editions(data)
    newest = eds[0]
    site.mkdir(parents=True, exist_ok=True)
    zh_text, zh_notes = message_zh.compose(newest, url)
    teaser = message_zh.teaser(newest, message_zh.load_zh())
    desc = " · ".join(s["headline"] for s in newest["stories"][:2])
    (site / "index.html").write_text(head(f"{teaser} | Cassandra {newest['date_label']}", desc, url)
                                     + render(eds) + "</html>\n", encoding="utf-8")
    (site / "manifest.webmanifest").write_text(MANIFEST, encoding="utf-8")
    for n in (192, 512):
        shutil.copyfile(ROOT / "scripts" / "briefing_site_assets" / f"icon-{n}.png", site / f"icon-{n}.png")
    (site / "latest.json").write_text(json.dumps(newest, ensure_ascii=False, indent=1), encoding="utf-8")
    (site / "message_zh.txt").write_text(zh_text, encoding="utf-8")
    text = message(newest, url)
    (site / "message.txt").write_text(text, encoding="utf-8")
    notes = zh_notes + ([share_card(site, newest, teaser, [l.split(". ", 1)[1] for l in zh_text.splitlines()
                                                          if l[:3] in ("1. ", "2. ", "3. ")])] if card else [])
    for n in notes:
        print(f"[site] {n}", file=sys.stderr)
    return zh_text + "\n" + text


if __name__ == "__main__":
    print(build(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]))

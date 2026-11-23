"""Build the newsletter website: python scripts/briefing_site.py SITE_DIR DATA_DIR URL

SITE_DIR/index.html          the latest Morning and Evening editions (newest first), phone first
SITE_DIR/manifest.webmanifest + icons, so "Add to Home Screen" gives readers an app icon
SITE_DIR/message.txt         the short message to paste into the group chat each morning
DATA_DIR holds the edition JSON files written by `python -m src.briefing`.
"""
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from briefing_demo import load_editions, render  # noqa: E402

HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="theme-color" content="#141414"><link rel="manifest" href="manifest.webmanifest">'
        '<link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="icon-192.png">'
        '<meta name="apple-mobile-web-app-title" content="Cassandra">')
MANIFEST = ('{"name": "Cassandra AI Briefing", "short_name": "Cassandra", "start_url": ".", "display": "standalone",'
            ' "background_color": "#fbfaf8", "theme_color": "#141414", "icons": ['
            '{"src": "icon-192.png", "sizes": "192x192", "type": "image/png"},'
            '{"src": "icon-512.png", "sizes": "512x512", "type": "image/png"}]}\n')


def message(ed: dict, url: str) -> str:
    """Plain text for WeLink or WhatsApp: title, up to 4 headlines, the market line, the link."""
    lines = [f"Cassandra {ed['title']} · {ed['date_label']}", ""]
    lines += [f"• {s['headline']}" for s in ed["stories"][:4]]
    if ed["markets"]:
        lines += ["", ed["markets"][0]["summary"]]
    return "\n".join(lines + ["", f"Read in 3 minutes: {url}", ""])


def build(site: pathlib.Path, data: pathlib.Path, url: str) -> str:
    eds = load_editions(data)
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(HEAD + render(eds) + "</html>\n", encoding="utf-8")
    (site / "manifest.webmanifest").write_text(MANIFEST, encoding="utf-8")
    for n in (192, 512):
        shutil.copyfile(ROOT / "scripts" / "briefing_site_assets" / f"icon-{n}.png", site / f"icon-{n}.png")
    text = message(eds[0], url)
    (site / "message.txt").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    print(build(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]))

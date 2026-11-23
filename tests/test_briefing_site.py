"""The public newsletter page and the daily group message (scripts/briefing_site.py)."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import briefing_site  # noqa: E402


def _ed(edition, date, at, headline):
    return {"edition": edition, "title": f"{edition.title()} Edition", "date": date, "date_label": "Mon 23 Nov 2026",
            "generated_at": at, "subject": "s", "hook": "h", "big_picture": "", "market_take": "", "outlook": "",
            "stories": [{"headline": headline, "what": "w", "why": "", "url": "https://ex.com/a", "source": "Src",
                         "channel": "ai", "tag": "", "verbatim": False}],
            "markets": [{"title": "Wall Street", "summary": "S&P 500 fell (-1.0%).", "rows": [], "live": False,
                         "asof": "2026-11-20", "providers": ["Yahoo Finance"]}],
            "events": [], "calendar": [], "glossary": [], "writer": "gemini", "rejected": [], "problems": [],
            "notes": [], "candidates": 10}


def test_site_has_latest_editions_newest_first_an_app_icon_and_the_group_message(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    for name, ed in (("2026-11-20-evening", _ed("evening", "2026-11-20", "2026-11-20T12:35:00+00:00", "Old evening")),
                     ("2026-11-19-morning", _ed("morning", "2026-11-19", "2026-11-18T23:35:00+00:00", "Older morning")),
                     ("2026-11-23-morning", _ed("morning", "2026-11-23", "2026-11-22T23:35:00+00:00", "Alibaba ships a model"))):
        (data / f"{name}.json").write_text(json.dumps(ed), encoding="utf-8")
    text = briefing_site.build(tmp_path / "site", data, "https://example.org/briefing/")
    html = (tmp_path / "site" / "index.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and 'rel="manifest"' in html and 'name="viewport"' in html
    assert html.index("Alibaba ships a model") < html.index("Old evening") and "Older morning" not in html
    assert json.loads((tmp_path / "site" / "manifest.webmanifest").read_text())["display"] == "standalone"
    assert (tmp_path / "site" / "icon-512.png").stat().st_size > 0
    assert text.splitlines()[0] == "Cassandra Morning Edition · Mon 23 Nov 2026"
    assert "• Alibaba ships a model" in text and text.rstrip().endswith("https://example.org/briefing/")

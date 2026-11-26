"""Story artwork on the briefing website: inline SVG only, one motif per tag, no external images."""
import pathlib
import re
import sys

from src.briefing.art import ACCENTS, story_art
from src.briefing.writer import TAGS

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import briefing_demo  # noqa: E402


def test_every_writer_tag_has_its_own_accent_and_untagged_still_draws():
    assert set(TAGS) <= set(ACCENTS)
    for tag in (*TAGS, ""):
        svg = story_art({"tag": tag, "url": "https://ex.com/a"})
        assert svg.startswith("<svg") and svg.endswith("</svg>") and 'role="img"' in svg


def test_art_is_self_contained_and_varies_by_story():
    a = story_art({"tag": "Markets", "url": "https://ex.com/a"})
    b = story_art({"tag": "Markets", "url": "https://ex.com/b"})
    assert a != b
    assert not re.search(r"(href|src)=\"https?://", a)                      # nothing fetched or hotlinked
    assert 'viewBox="0 0 360 120"' in story_art({"tag": "Policy", "url": "u"}, wide=True)


def test_story_markup_puts_banner_on_lead_and_tile_on_others():
    s = {"tag": "Research", "headline": "H <b>", "what": "w", "why": "", "url": "https://ex.com/x",
         "source": "Src", "verbatim": False}
    lead, tile = briefing_demo.story(s, top=True), briefing_demo.story(s)
    assert 'class="art wide"' in lead and 'class="art"' in tile
    assert "H &lt;b&gt;" in lead and "<img" not in lead + tile

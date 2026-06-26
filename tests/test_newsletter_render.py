"""Newsletter template rendering tests."""
from __future__ import annotations

from src.newsletter.render import body_excerpt, crs_color, render_edition_html


def test_crs_color_bands():
    assert crs_color(30) == "#2e7d32"
    assert crs_color(50) == "#e65100"
    assert crs_color(70) == "#d32f2f"


def test_render_edition_html_includes_share_and_unsub():
    html = render_edition_html(
        crs=42.0,
        phase="awareness",
        phase_conf=0.81,
        asof="2026-06-26",
        unsub_token="abc123",
    )
    assert "WhatsApp" in html
    assert "abc123" in html
    assert "42" in html


def test_body_excerpt_fallback():
    text = body_excerpt("2099-01-01", "en")
    assert "edition" in text.lower() or "<p" in text

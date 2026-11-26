"""Static brand assets and home-page wiring (no network, no server)."""
import pathlib
import struct
import xml.etree.ElementTree as ET

STATIC = pathlib.Path("web/static")
IMG = STATIC / "img"


def _png_size(path: pathlib.Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", data[16:24])


def test_svg_assets_are_well_formed_and_self_contained():
    for name in ["emblem.svg", "wordmark.svg", "hero.svg", "og.svg", "favicon.svg"]:
        path = IMG / name
        assert path.exists(), name
        text = path.read_text(encoding="utf-8")
        ET.fromstring(text)  # raises on malformed XML
        # original art only: no hotlinked or embedded external images
        assert "<image" not in text, name
        assert "http://" not in text.replace("http://www.w3.org/2000/svg", ""), name
        assert "https://" not in text, name


def test_png_renders_have_expected_sizes():
    assert _png_size(IMG / "og.png") == (1200, 630)
    assert _png_size(IMG / "favicon-32.png") == (32, 32)
    assert _png_size(IMG / "apple-touch-icon.png") == (180, 180)


def test_every_page_links_the_favicon():
    missing = [p.name for p in STATIC.glob("*.html") if "/static/img/favicon.svg" not in p.read_text(encoding="utf-8")]
    assert not missing, f"favicon missing in: {missing}"


def test_home_has_chart_mounts_and_og_image():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for el_id in ["crs-gauge", "crs-hist-chart", "ft-chart", "cov-note", "analog-row"]:
        assert f'id="{el_id}"' in html, el_id
    assert 'property="og:image" content="/static/img/og.png"' in html


def test_home_does_not_hardcode_the_analog_date():
    # The "Today feels like ..." line must come from /api/report/highlights, not demo copy.
    for name in ["index.html", "app.js", "newspaper.js"]:
        assert "March 14, 2000" not in (STATIC / name).read_text(encoding="utf-8"), name


def test_home_charts_use_no_external_chart_library():
    app = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    for lib in ["chart.js", "d3.", "echarts", "plotly", "highcharts", "apexcharts"]:
        assert lib not in html.lower(), lib
    assert "/api/scores/history" in app and "/api/latest" in app

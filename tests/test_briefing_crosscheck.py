"""Second-source check on market figures: parsing recorded provider responses, reconciliation rules,
and how fetch_quotes uses them. Fixtures are raw GBK responses recorded on 2026-11-20."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.briefing import crosscheck as cc
from src.briefing import sources

FIX = Path(__file__).parent / "fixtures" / "quotes"
TENCENT = (FIX / "tencent.gbk.txt").read_bytes().decode("gbk", "replace")
SINA = (FIX / "sina.gbk.txt").read_bytes().decode("gbk", "replace")


def test_tencent_rows_parse_to_exact_figures_and_exchange_dates():
    got = cc.parse_tencent(TENCENT)
    sh = got["sh000001"]
    assert (sh.price, sh.pct_1d, sh.session_date, sh.provider) == (3512.07, -1.83, "2026-11-20", "tencent")
    assert (got["usINX"].price, got["usINX"].pct_1d, got["usINX"].session_date) == (7175.83, -2.02, "2026-11-19")
    assert (got["hkHSTECH"].pct_1d, got["hkHSTECH"].session_date) == (-3.88, "2026-11-20")     # '2026/11/20 09:54:26'
    assert got["sh000300"].price == 3914.39                       # CSI 300: Yahoo cannot serve this one
    assert "s_usINX" not in got and "whUSDCNY" not in got         # short and currency formats are not trusted


def test_sina_rows_without_a_date_are_ignored_because_they_are_stale():
    """Measured: b_TWSE answered with a 2025 value, b_FSSTI and b_SOX with undated values far from the market."""
    got = cc.parse_sina(SINA)
    assert set(got) == {"b_NKY", "b_KOSPI", "b_AS51", "znb_NKY", "znb_KOSPI", "znb_TWJQ"}
    assert (got["b_NKY"].price, got["b_NKY"].pct_1d, got["b_NKY"].session_date) == (56830.5, -4.4, "2026-11-20")
    assert "b_TWSE" in SINA and "b_FSSTI" in SINA and "b_SOX" in SINA        # they were in the response


@pytest.mark.parametrize("text", [
    "", "garbage", 'v_x="1~n~c"', 'v_pv_none_match="1";',
    'v_bad="1~n~c~100~0~0' + "~" * 27 + '20261120100000~0~0~";',                       # previous close 0
    'v_lie="1~n~c~100~110~0' + "~" * 24 + '20261120100000~-10~-1.0~";'.replace("~~~~~~~~~~~~~~~~~~~~~~~~", "~" * 24),
])
def test_malformed_or_self_contradicting_rows_are_dropped(text):
    assert cc.parse_tencent(text) == {} and cc.parse_sina(text) == {}


def test_a_row_whose_percent_contradicts_its_prices_is_dropped():
    f = ["1", "n", "c", "100", "110"] + ["0"] * 25 + ["20261120100000", "-10", "-1.0"]       # really -9.09%
    assert cc.parse_tencent('v_lie="' + "~".join(f) + '";') == {}
    f[32] = "-9.09"
    assert cc.parse_tencent('v_ok="' + "~".join(f) + '";')["ok"].pct_1d == -9.09


def _r(pct, day="2026-11-19", provider="tencent"):
    return cc.Reading(provider, "x", 100.0, pct, day)


def test_reconcile_rules():
    assert cc.reconcile(-2.02, "2026-11-19", False, _r(-2.02)) == ("confirmed", "")
    assert cc.reconcile(-2.00, "2026-11-19", False, _r(-2.25))[0] == "confirmed"            # exactly at the tolerance
    status, note = cc.reconcile(-8.5, "2026-11-19", False, _r(-3.1))
    assert status == "conflict" and note == "Tencent Finance shows -3.1%"
    assert cc.reconcile(-2.00, "2026-11-19", False, _r(-2.27))[0] == "conflict"             # just beyond it
    assert cc.reconcile(-5.0, "2026-11-19", True, _r(-5.6)) == ("single", "")               # market open: no verdict
    assert cc.reconcile(-5.0, "2026-11-19", True, _r(-7.0))[0] == "conflict"                # but a gross gap still counts
    assert cc.reconcile(-0.3, "2026-11-19", False, _r(-1.4, "2026-11-20"))[0] == "newer"    # primary has not caught up
    assert cc.reconcile(-0.3, "2026-11-19", False, _r(-1.4, "2025-09-26")) == ("single", "")  # stale second source
    assert cc.reconcile(-0.3, "2026-11-19", False, None) == ("single", "")
    assert cc.reconcile(None, "2026-11-19", False, _r(-1.4)) == ("single", "")


def test_fetch_readings_makes_one_request_per_provider_and_never_leaks_the_url(monkeypatch):
    calls = []

    class R:
        def __init__(self, text): self.content = text.encode("gbk")
        def raise_for_status(self): pass

    def get(url, headers=None, timeout=None):
        calls.append((url, headers))
        if "sinajs" in url:
            raise RuntimeError(f"boom {url}")
        return R(TENCENT)

    monkeypatch.setattr(cc.httpx, "get", get)
    probs: list[str] = []
    got = cc.fetch_readings(["tencent:sh000001", "tencent:usINX", "sina:b_NKY", "tencent:nosuch", "ftp:x", "tencent:a b"], probs)
    assert set(got) == {"tencent:sh000001", "tencent:usINX"}
    assert len(calls) == 2 and calls[0][0].endswith("q=sh000001,usINX,nosuch")
    assert any("Referer" in (h or {}) for u, h in calls if "sinajs" in u)
    assert probs == ["second source 'ftp:x' is not a known provider code",
                     "second source 'tencent:a b' is not a known provider code",
                     "second price source Sina Finance unavailable (RuntimeError)"]


def _yq(pct, day="2026-11-19", live=False):
    return sources.Quote("^X", "Index X", "", 100.0, pct, 1.0, day, live, in_hours=live)


def test_fetch_quotes_uses_the_second_source(monkeypatch):
    rows = [{"symbol": "A", "label": "Agree", "verify": "tencent:a"},
            {"symbol": "B", "label": "Disagree", "verify": "tencent:b"},
            {"symbol": "C", "label": "Yahoo behind", "verify": "tencent:c"},
            {"symbol": "D", "label": "Yahoo cannot serve", "note": "n", "verify": "tencent:d"},
            {"symbol": "E", "label": "Nobody has it", "verify": "tencent:e"},
            {"symbol": "F", "label": "No second source"}]
    yahoo = {"A": _yq(-2.0), "B": _yq(-8.5), "C": _yq(-0.3), "F": _yq(0.4)}
    yahoo["C"].in_hours = True

    def fake_yahoo(row, as_of=None):
        if row["symbol"] not in yahoo:
            raise ValueError("fewer than 2 daily bars")
        q = yahoo[row["symbol"]]
        q.label = row["label"]
        return q

    monkeypatch.setattr(sources, "_yahoo_quote", fake_yahoo)
    monkeypatch.setattr(cc, "fetch_readings", lambda specs, problems=None: {
        "tencent:a": _r(-2.1), "tencent:b": _r(-3.1), "tencent:c": _r(-1.4, "2026-11-20"), "tencent:d": _r(-1.8, "2026-11-20")})
    probs: list[str] = []
    a, b, c, d, f = sources.fetch_quotes(rows, problems=probs)
    assert (a.check, a.provider) == ("confirmed", "Yahoo Finance")
    assert b.check == "conflict"
    assert (c.pct_1d, c.session_date, c.provider, c.check, c.live) == (-1.4, "2026-11-20", "Tencent Finance", "single", True)
    assert (d.label, d.pct_1d, d.pct_5d, d.provider, d.note) == ("Yahoo cannot serve", -1.8, None, "Tencent Finance", "n")
    assert f.check == "single"
    assert probs == ["Disagree: figure withheld because sources disagree (Yahoo Finance shows -8.5%, Tencent Finance shows -3.1%)",
                     "price for Nobody has it unavailable (ValueError)"]

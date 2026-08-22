"""Pricing HTML/JS must state 3 months Agent then Free, no auto-convert lie."""
from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web" / "static"


def test_pricing_html_states_trial_rule():
    html = (WEB / "pricing.html").read_text(encoding="utf-8")
    assert "3 months Agent, then Free" in html
    assert "does not auto-convert" in html
    assert "7 days free" not in html.lower()
    assert "7-day" not in html.lower()


def test_pricing_js_states_trial_rule():
    js = (WEB / "pricing.js").read_text(encoding="utf-8")
    assert "3 months Agent, then Free" in js
    assert "does not auto-convert" in js
    assert "7 days free" not in js.lower()


def test_signup_and_terms_match_trial_rule():
    signup = (WEB / "signup.html").read_text(encoding="utf-8")
    terms = (WEB / "terms.html").read_text(encoding="utf-8")
    assert "3 months" in signup
    assert "does not auto-convert" in signup
    assert "90 days" in terms
    assert "does not auto-convert" in terms
    assert "7-day free trial on first paid" not in terms


def test_config_js_has_checkout_paths_no_secrets():
    cfg = (WEB / "config.js").read_text(encoding="utf-8")
    assert "/api/billing/checkout?tier=report" in cfg
    assert "/api/billing/portal" in cfg
    assert "sk_live" not in cfg
    assert "sk_test" not in cfg
    assert "whsec_" not in cfg

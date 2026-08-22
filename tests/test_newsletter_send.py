"""Newsletter dry-run prints per-tier bodies and does not send."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.entitlement import effective_tier
from src.newsletter.send import dispatch_digest, print_dry_run, resolve_recipient_tier
from src.newsletter.render import preview_tier_bodies, render_edition_text


def test_preview_tier_bodies_differ():
    bodies = preview_tier_bodies(crs=42.0, phase="awareness", phase_conf=0.8, asof="2026-08-22")
    assert "S / B / C stay locked" in bodies["free"]["html"]
    assert "The Report" in bodies["report"]["html"]
    assert "2000/2008" in bodies["briefing"]["html"]
    assert "chat 50/day" in bodies["agent"]["html"]
    assert "effective_tier=free" in bodies["free"]["text"]
    assert "effective_tier=agent" in bodies["agent"]["text"]


def test_dispatch_dry_run_default_prints_tiers(tmp_path, monkeypatch, capsys):
    import src.store as store_mod

    monkeypatch.setattr(store_mod, "DB", tmp_path / "nl.sqlite")
    monkeypatch.setattr(store_mod, "latest_score", lambda: {
        "crs": 41.0,
        "band": "Awareness",
        "asof": "2026-08-22",
        "phase": "awareness",
        "phase_confidence": 0.7,
    })
    monkeypatch.setattr(store_mod, "list_digest_recipients", lambda: [
        {"email": "a@example.com", "unsub_token": "tok-a"},
    ])
    out = dispatch_digest()
    assert out["dry_run"] is True
    assert out["sent"] == 0
    assert "free" in out["tier_bodies"]
    assert "agent" in out["tier_bodies"]
    assert "S / B / C" in out["tier_html"]["free"] or "locked" in out["tier_bodies"]["free"].lower()
    print_dry_run(out)
    printed = capsys.readouterr().out
    assert "===== free =====" in printed
    assert "===== report =====" in printed
    assert "===== briefing =====" in printed
    assert "===== agent =====" in printed
    assert "DRY-RUN" in printed


def test_resolve_recipient_uses_created_at_window():
    now = datetime.now(timezone.utc)
    rec = {"email": "t@example.com", "created_at": (now - timedelta(days=10)).isoformat()}
    assert resolve_recipient_tier(rec) == "agent"
    rec_old = {"email": "t@example.com", "created_at": (now - timedelta(days=91)).isoformat()}
    assert resolve_recipient_tier(rec_old) == "free"
    assert effective_tier(now - timedelta(days=89), now=now) == "agent"


def test_render_text_names_depth():
    text = render_edition_text(crs=30, phase="calm", asof="2026-08-22", tier="briefing")
    assert "Edition depth: briefing" in text

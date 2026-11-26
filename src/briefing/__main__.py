"""
CLI: python -m src.briefing --edition auto|morning|evening|weekly [--send] [--dry-run]

  (no flags)   build the edition, save HTML + JSON under reports/briefings/, send nothing
  --dry-run    as above, and list who would receive it
  --send       build, save, and email every confirmed subscriber

`auto` picks the edition from the Singapore-time schedule in config/briefing.yaml and exits 0
quietly when nothing is due, so one scheduled task can call it at every slot.
Exit code 1 = nothing sent: empty edition, AI editor down (raw headlines, see --allow-wire),
or a delivery failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from src.tools._env import load_env

from . import build, render, sources

OUT_DIR = sources.ROOT / "reports" / "briefings"
WELINK_CFG = sources.ROOT / "config" / "welink.yaml"      # local file, never committed (chat names)


def save(ed: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{ed['date']}-{ed['edition']}"
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(ed, indent=2, ensure_ascii=False), encoding="utf-8")
    for name in (f"{stem}.html", "latest.html"):
        (OUT_DIR / name).write_text(render.render_page(ed), encoding="utf-8")
    for ch in ("ai", "markets"):                     # one page and one chat text per channel
        (OUT_DIR / f"{stem}-{ch}.html").write_text(render.render_page(ed, ch), encoding="utf-8")
        (OUT_DIR / f"{stem}-{ch}.txt").write_text(render.render_chat(ed, ch), encoding="utf-8")
    return OUT_DIR / f"{stem}.html"


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description="Cassandra AI Briefing")
    ap.add_argument("--edition", default="auto", choices=("auto",) + build.EDITIONS)
    ap.add_argument("--send", action="store_true", help="email confirmed subscribers")
    ap.add_argument("--dry-run", action="store_true", help="list recipients, send nothing")
    ap.add_argument("--channel", default="all", choices=("all", "ai", "markets"),
                    help="send the full briefing (default) or one channel only")
    ap.add_argument("--welink", action="store_true",
                    help="post each channel's chat text to WeLink (config/welink.yaml); "
                         "without --send it only shows what would be posted")
    ap.add_argument("--no-email", action="store_true", help="with --send: skip the email dispatch")
    ap.add_argument("--allow-wire", action="store_true",
                    help="send even if the AI editor failed and stories are raw headlines")
    ap.add_argument("--as-of", metavar="'YYYY-MM-DD HH:MM'",
                    help="rebuild a past edition as it would have read then (Singapore time); never sent")
    args = ap.parse_args(argv)

    cfg = sources.load_config()
    edition = args.edition
    if edition == "auto":
        local = dt.datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Singapore")))
        edition = build.pick_edition(local, cfg["schedule"])
        if not edition:
            print(f"[briefing] nothing due at {local:%a %H:%M} local")
            return 0

    tz = ZoneInfo(cfg.get("timezone", "Asia/Singapore"))
    if args.as_of:
        if args.edition == "auto" or args.send or args.welink or args.dry_run:
            print("[briefing] FAIL --as-of needs an explicit --edition and cannot be sent or posted", file=sys.stderr)
            return 1
        try:
            when = dt.datetime.strptime(args.as_of, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
        except ValueError:
            print("[briefing] FAIL --as-of must look like '2026-11-19 07:30'", file=sys.stderr)
            return 1
        if when >= dt.datetime.now(tz):
            print("[briefing] FAIL --as-of must be in the past", file=sys.stderr)
            return 1
        ed = build.build_edition(edition, cfg=cfg, now=when, reconstruct=True)
    else:
        ed = build.build_edition(edition, cfg=cfg)
    path = save(ed)
    print(f"[briefing] {ed['title']} {ed['date']}: {len(ed['stories'])} stories "
          f"(from {ed['candidates']} candidates), {len(ed['markets'])} market blocks, writer={ed['writer']}")
    print(f"[briefing] subject: {ed['subject']}")
    for p in ed["problems"] + [f"rejected by fact check: {r}" for r in ed["rejected"]]:
        print(f"[briefing] NOTE {p}")
    print(f"[briefing] saved {path}")

    if not ed["stories"] and not ed["markets"]:
        print("[briefing] FAIL empty edition, not sending", file=sys.stderr)
        return 1

    if args.send and ed["writer"] == "wire" and not args.allow_wire:
        print("[briefing] FAIL AI editor was unavailable, so this edition is raw headlines. Not sending. "
              "Re-run, or pass --allow-wire to send it anyway.", file=sys.stderr)
        return 1

    rc = 0
    if args.welink:
        rc = _post_welink(ed, args) or rc

    if (args.send and not args.no_email) or args.dry_run:
        from src.newsletter.send import dispatch_rendered

        # the channel is part of the subject, so the two channel emails are tracked as separate sends
        subject = ed["subject"] if args.channel == "all" else f"{render.CHANNEL_NAMES[args.channel]}: {ed['subject']}"

        out = dispatch_rendered(
            subject=subject, html=render.render_html(ed, args.channel), text=render.render_text(ed, args.channel),
            unsub_placeholder=render.UNSUB_PLACEHOLDER,
            tags={"type": f"briefing_{ed['edition']}_{args.channel}", "asof": ed["date"]}, dry_run=not args.send,
        )
        print(f"[briefing] dispatch: {out}")
        if out.get("failed"):
            return 1
    return rc


def _post_welink(ed: dict, args) -> int:
    """Post the chat text of each channel into its WeLink chats. Returns 1 if anything failed."""
    import yaml

    if not WELINK_CFG.is_file():
        print("[briefing] FAIL config/welink.yaml not found. Copy config/welink.example.yaml and fill it in.",
              file=sys.stderr)
        return 1
    from . import welink
    channels = ("ai", "markets") if args.channel == "all" else (args.channel,)
    batches = [{"channel": ch, "messages": [text]} for ch in channels if (text := render.render_chat(ed, ch))]
    wcfg = yaml.safe_load(WELINK_CFG.read_text(encoding="utf-8")) or {}
    out = welink.deliver(batches, wcfg, dry_run=not args.send)
    for line in out.get("details", []):
        print(f"[briefing] welink: {line}")
    print(f"[briefing] welink: sent={out.get('sent', 0)} skipped={out.get('skipped', 0)} failed={out.get('failed', 0)}")
    return 1 if out.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())

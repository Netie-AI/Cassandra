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


def save(ed: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"{ed['date']}-{ed['edition']}"
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(ed, indent=2, ensure_ascii=False), encoding="utf-8")
    page = render.render_page(ed)
    for name in (f"{stem}.html", "latest.html"):
        (OUT_DIR / name).write_text(page, encoding="utf-8")
    return OUT_DIR / f"{stem}.html"


def main(argv: list[str] | None = None) -> int:
    load_env()
    ap = argparse.ArgumentParser(description="Cassandra AI Briefing")
    ap.add_argument("--edition", default="auto", choices=("auto",) + build.EDITIONS)
    ap.add_argument("--send", action="store_true", help="email confirmed subscribers")
    ap.add_argument("--dry-run", action="store_true", help="list recipients, send nothing")
    ap.add_argument("--allow-wire", action="store_true",
                    help="send even if the AI editor failed and stories are raw headlines")
    args = ap.parse_args(argv)

    cfg = sources.load_config()
    edition = args.edition
    if edition == "auto":
        local = dt.datetime.now(ZoneInfo(cfg.get("timezone", "Asia/Singapore")))
        edition = build.pick_edition(local, cfg["schedule"])
        if not edition:
            print(f"[briefing] nothing due at {local:%a %H:%M} local")
            return 0

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

    if args.send or args.dry_run:
        from src.newsletter.send import dispatch_rendered

        out = dispatch_rendered(
            subject=ed["subject"], html=render.render_html(ed), text=render.render_text(ed),
            unsub_placeholder=render.UNSUB_PLACEHOLDER,
            tags={"type": f"briefing_{ed['edition']}", "asof": ed["date"]}, dry_run=not args.send,
        )
        print(f"[briefing] dispatch: {out}")
        if out.get("failed"):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

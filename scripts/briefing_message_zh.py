"""The Chinese group message, with today's internal tool guide, built on the owner's laptop.

  python scripts/briefing_message_zh.py --tool config/tools/gde-claw.txt
  python scripts/briefing_message_zh.py --json https://netie-ai.github.io/Cassandra/briefing/latest.json --tool ...

--json   an edition file or URL (default: the newest edition in reports/briefings)
--tool   a plain-text guide for 【每日工具】. Keep these in config/tools/, which git ignores: they may
         hold internal links and must never reach this public repository or the public site.
The message is printed and saved to reports/briefings/message_zh-<date>.txt for copying.
"""
import argparse
import glob
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.briefing import message_zh  # noqa: E402
from src.tools._env import load_env  # noqa: E402

SITE = "https://netie-ai.github.io/Cassandra/briefing/"


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="edition JSON file or URL")
    ap.add_argument("--tool", help="plain-text tool guide (kept out of git)")
    ap.add_argument("--url", default=SITE, help="link printed at the end")
    a = ap.parse_args()
    if a.json and a.json.startswith("http"):
        import httpx
        ed = httpx.get(a.json, timeout=30, follow_redirects=True).raise_for_status().json()
    else:
        files = [a.json] if a.json else sorted(glob.glob(str(ROOT / "reports" / "briefings" / "????-??-??-*.json")),
                                               key=lambda f: json.load(open(f, encoding="utf-8"))["generated_at"])
        if not files:
            print("no edition found: run python -m src.briefing first, or pass --json", file=sys.stderr)
            return 1
        ed = json.load(open(files[-1], encoding="utf-8"))
    tool = pathlib.Path(a.tool).read_text(encoding="utf-8") if a.tool else ""
    text, notes = message_zh.compose(ed, a.url, tool=tool)
    for n in notes:
        print(f"[note] {n}", file=sys.stderr)
    out = ROOT / "reports" / "briefings" / f"message_zh-{ed['date']}-{ed['edition']}.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    print(f"[saved] {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

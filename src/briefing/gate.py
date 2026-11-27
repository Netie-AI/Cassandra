"""Box publish gate: python -m src.briefing.gate

Prints "nothing due" and exits 0 when the newest saved edition is not from this run.
Prints the date and edition on stdout when it may be published.
Prints the block reason on stderr and exits 1 when the edition is held or the editor
fell back to wire copy. Never prints a key.
"""
from __future__ import annotations

import datetime as dt
import sys

from .build import box_publish_block, load_newest_edition, this_run
from .sources import ROOT

OUT_DIR = ROOT / "reports" / "briefings"


def main(argv: list[str] | None = None) -> int:
    del argv
    ed = load_newest_edition(OUT_DIR)
    now = dt.datetime.now(dt.timezone.utc)
    if not ed or not this_run(ed, now):
        print("nothing due")
        return 0
    reason = box_publish_block(ed)
    if reason:
        print(reason, file=sys.stderr)
        return 1
    print(f"{ed.get('date', '')} {ed.get('edition', '')}".strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())

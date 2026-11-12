"""Build the shareable demo page (Morning + Evening tabs) from the latest edition JSON files.
Usage: python scripts/briefing_demo.py OUT.html   (run python -m src.briefing --edition ... first)

Layout: one column on phones in reading order (top story, markets, more stories, big picture,
what to watch, jargon); from 980px the markets, watch list and jargon move to a right-hand rail.
"""
import glob, json, pathlib, sys
from html import escape as e

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.briefing.render import _when, _day, _row_note, read_minutes

OUT = sys.argv[1]
eds = [json.load(open(sorted(glob.glob(str(ROOT / "reports" / "briefings" / f"*-{k}.json")))[-1]))
       for k in ("morning", "evening")]


def story(s, top=False):
    kick = " · ".join(x for x in (s.get("tag"), "Singapore" if s.get("region") == "sg" else "") if x)
    kicker = f'<span class="kick">{e(kick)}</span>' if kick else ""
    what = f'<p>{e(s["what"])}</p>' if s.get("what") else ""
    why = f'<p class="why"><b>What it means for you</b> {e(s["why"])}</p>' if s.get("why") else ""
    return (f'<article class="story{" top" if top else ""}">{kicker}'
            f'<h3><a href="{e(s["url"], quote=True)}">{e(s["headline"])}</a></h3>{what}{why}'
            f'<a class="src" href="{e(s["url"], quote=True)}">Read the source: {e(s["source"])}</a></article>')


def market(b):
    rows = ""
    for r in b["rows"]:
        cls = "flat" if r["pct"] is None or r["pct_text"] == "flat" else ("up" if r["pct"] > 0 else "down")
        rows += (f'<tr><td><b>{e(r["label"])}</b><span>{e(_row_note(r))}</span></td>'
                 f'<td class="px">{e(r["close"])}</td><td class="pct {cls}">{e(r["pct_text"])}</td></tr>')
    asof = "Snapshot when this edition was written" if b["live"] else f"Closing prices, {_day(b['asof'])}"
    return (f'<div class="mkt"><h4>{e(b["title"])}</h4><p class="sum">{e(b["summary"])}</p>'
            f'<div class="tw"><table>{rows}</table></div><p class="asof">{e(asof)}</p></div>')


def sec(name, title, body):
    return f'<section class="sec s-{name}" data-sec="{name}"><h2>{title}</h2>{body}</section>'


def edition(ed, hidden):
    st = ed["stories"]
    main, side, chips = [], [], []
    if st:
        lunch = f'<p class="lunch"><b>Say this at lunch</b> {e(ed["talking_point"])}</p>' if ed.get("talking_point") else ""
        main.append(sec("top", "Top story", story(st[0], True) + lunch)); chips.append(("top", "Top story"))
    if ed["markets"]:
        take = f'<p class="take"><b>In plain English</b> {e(ed["market_take"])}</p>' if ed.get("market_take") else ""
        side.append(sec("markets", "Markets in 30 seconds",
                        '<div class="mkts">' + "".join(market(b) for b in ed["markets"]) + "</div>" + take))
        chips.append(("markets", "Markets"))
    if st[1:]:
        main.append(sec("more", "Also in AI", '<div class="stories">' + "".join(story(s) for s in st[1:]) + "</div>"))
        chips.append(("more", "More AI"))
    if ed.get("big_picture"):
        main.append(sec("big", "The big picture", f'<p class="bp">{e(ed["big_picture"])}</p>'))
    watch = ""
    if ed.get("outlook"):
        watch += f'<p class="take"><b>Our read</b> {e(ed["outlook"])} <i>(opinion, not a forecast)</i></p>'
    for c in ed.get("calendar", []):
        watch += (f'<div class="cal"><b>{e(c["title"])}</b><span>{e(c["when"])}</span>'
                  f'<p>In plain English: {e(c["plain"])}.</p></div>')
    for ev in ed["events"]:
        watch += (f'<div class="ev"><a href="{e(ev["source"], quote=True)}">{e(ev["name"])}</a>'
                  f'<span>{e(_when(ev))} · {e(ev.get("where", ""))}</span><p>{e(ev["why"])}</p></div>')
    if watch:
        side.append(sec("watch", "What to watch next", f'<div class="watch">{watch}</div>')); chips.append(("watch", "Watch next"))
    if ed["glossary"]:
        side.append(sec("jargon", "Jargon buster", "<dl>" + "".join(
            f'<dt>{e(g["term"])}</dt><dd>{e(g["plain"])}</dd>' for g in ed["glossary"]) + "</dl>"))
        chips.append(("jargon", "Jargon"))
    notes = "".join(f"<li>{e(n)}</li>" for n in ed["problems"] + [f"Fact check rejected: {r}" for r in ed["rejected"]])
    nav = "".join(f'<button type="button" data-go="{k}">{label}</button>' for k, label in chips)
    return "\n".join([
        f'<section class="ed" id="ed-{ed["edition"]}"{" hidden" if hidden else ""}>',
        f'<nav class="chips" aria-label="Jump to section">{nav}</nav>',
        f'<p class="meta">{read_minutes(ed)} min read · {len(st)} stories</p>',
        f'<p class="hook">{e(ed["hook"])}</p>' if ed.get("hook") else "",
        f'<div class="cols"><div class="main">{"".join(main)}</div><aside class="side">{"".join(side)}</aside></div>',
        '<details class="audit"><summary>How this edition was checked</summary><ul>'
        f'<li>Email subject line: {e(ed["subject"])}</li>'
        f'<li>{ed["candidates"]} stories read, {len(st)} picked, written by {e(ed["writer"])}.</li>'
        f'<li>Built {e(ed["generated_at"].replace("T", " ")[:16])} UTC. Prices from Yahoo Finance.</li>'
        f'{notes or "<li>No source failed and the fact check rejected nothing.</li>"}</ul></details>',
        "</section>"])


tabs = "".join(f'<button type="button" role="tab" id="tab-{ed["edition"]}" aria-controls="ed-{ed["edition"]}" '
               f'aria-selected="{"true" if i == 0 else "false"}">{e(ed["title"].replace(" Edition", ""))}'
               f'<small>{"07:30" if ed["edition"] == "morning" else "20:30"} SGT</small></button>'
               for i, ed in enumerate(eds))
body = "\n".join(edition(ed, i > 0) for i, ed in enumerate(eds))
page = open(ROOT / "scripts" / "briefing_demo_shell.html").read()
open(OUT, "w").write(page.replace("{{DATE}}", e(eds[0]["date_label"])).replace("{{TABS}}", tabs).replace("{{BODY}}", body))
print("ok", len(page))

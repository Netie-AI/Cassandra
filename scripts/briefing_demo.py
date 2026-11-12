"""Build the shareable demo page (Morning + Evening tabs) from the latest edition JSON files.
Usage: python scripts/briefing_demo.py OUT.html   (run python -m src.briefing --edition ... first)"""
import glob, json, pathlib, sys
from html import escape as e
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.briefing.render import _when, _day, _row_note

OUT = sys.argv[1]
eds = [json.load(open(sorted(glob.glob(str(ROOT / "reports" / "briefings" / f"*-{k}.json")))[-1]))
       for k in ("morning", "evening")]

def story(s, top=False):
    flag = '<span class="sg">Singapore</span>' if s.get("region") == "sg" else ""
    why = f'<p class="why"><b>What it means for you</b> {e(s["why"])}</p>' if s.get("why") else ""
    return (f'<article class="story{" top" if top else ""}">{flag}'
            f'<h3><a href="{e(s["url"], quote=True)}">{e(s["headline"])}</a></h3>'
            f'<p>{e(s.get("what") or "")}</p>{why}'
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

def edition(ed, hidden):
    st = ed["stories"]
    p = [f'<section class="ed" id="ed-{ed["edition"]}"{" hidden" if hidden else ""}>',
         f'<p class="subject"><span>Subject line</span>{e(ed["subject"])}</p>']
    if ed.get("hook"): p.append(f'<p class="hook">{e(ed["hook"])}</p>')
    if ed.get("big_picture"): p.append(f'<p class="bp">{e(ed["big_picture"])}</p>')
    if st:
        p.append('<h2>Top story</h2>' + story(st[0], True))
        if ed.get("talking_point"):
            p.append(f'<p class="lunch"><b>Say this at lunch</b> {e(ed["talking_point"])}</p>')
    if ed["markets"]:
        p.append('<h2>Markets in 30 seconds</h2><div class="mkts">' + "".join(market(b) for b in ed["markets"]) + '</div>')
        if ed.get("market_take"): p.append(f'<p class="take"><b>In plain English</b> {e(ed["market_take"])}</p>')
    if st[1:]:
        p.append('<h2>Also in AI</h2><div class="stories">' + "".join(story(s) for s in st[1:]) + '</div>')
    p.append('<h2>What to watch next</h2>')
    if ed.get("outlook"): p.append(f'<p class="take"><b>Our read</b> {e(ed["outlook"])} <i>(opinion, not a forecast)</i></p>')
    for ev in ed["events"]:
        p.append(f'<div class="ev"><a href="{e(ev["source"], quote=True)}">{e(ev["name"])}</a>'
                 f'<span>{e(_when(ev))} · {e(ev.get("where", ""))}</span><p>{e(ev["why"])}</p></div>')
    if ed["glossary"]:
        p.append('<h2>Jargon buster</h2><dl>' + "".join(f'<dt>{e(g["term"])}</dt><dd>{e(g["plain"])}</dd>' for g in ed["glossary"]) + '</dl>')
    notes = "".join(f"<li>{e(n)}</li>" for n in ed["problems"] + [f"Fact check rejected: {r}" for r in ed["rejected"]])
    p.append(f'<details class="audit"><summary>How this edition was checked</summary><ul>'
             f'<li>{ed["candidates"]} stories read, {len(st)} picked, written by {e(ed["writer"])}.</li>'
             f'<li>Built {e(ed["generated_at"].replace("T", " ")[:16])} UTC. Prices from Yahoo Finance.</li>'
             f'{notes or "<li>No source failed and the fact check rejected nothing.</li>"}</ul></details>')
    p.append('</section>')
    return "\n".join(p)

tabs = "".join(f'<button type="button" role="tab" id="tab-{ed["edition"]}" aria-controls="ed-{ed["edition"]}" '
               f'aria-selected="{"true" if i == 0 else "false"}">{e(ed["title"])}'
               f'<small>{"07:30" if ed["edition"] == "morning" else "20:30"} SGT</small></button>'
               for i, ed in enumerate(eds))
body = "\n".join(edition(ed, i > 0) for i, ed in enumerate(eds))
page = open(ROOT / "scripts" / "briefing_demo_shell.html").read()
open(OUT, "w").write(page.replace("{{DATE}}", e(eds[0]["date_label"])).replace("{{TABS}}", tabs).replace("{{BODY}}", body))
print("ok", len(page))

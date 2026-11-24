"""
briefing/message_zh.py: the daily Chinese message for the group chat.

  【市场洞悉】 a teaser built from the day's biggest market move (Python, from checked prices)
  【风险提示】 fixed wording plus how many markets rose or fell (Python)
  【AI 要闻】  the edition's AI headlines, translated by Gemini; a translation whose numbers differ
              from the English is refused and the English headline is used instead
  【一天一个AI小知识】 one tip from config/briefing_zh.yaml, in rotation by date
  【每日工具】 optional text supplied by the caller (kept out of this public repository)

No model ever writes a market number here.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from typing import Any, Callable

from . import sources, writer

DISCLAIMER = "以上为公开市场数据整理，不构成任何投资建议。"


def load_zh() -> dict[str, Any]:
    return sources.load_config("briefing_zh")


def _rows(ed: dict) -> list[tuple[str, dict]]:
    return [(b.get("key", ""), r) for b in ed["markets"] for r in b["rows"]
            if r.get("pct") is not None and not r.get("fx") and not r.get("old")]


def _pct(v: float) -> str:
    return f"{abs(round(v, 1)):.1f}%"


def teaser(ed: dict, zh: dict) -> str:
    """The headline line: biggest one-day move in the edition's tables, with a question."""
    rows = _rows(ed)
    if not rows:
        return f"{ed['date_label']}：今日市场数据暂缺"
    _, top = max(rows, key=lambda kr: abs(kr[1]["pct"]))
    name = zh["names"].get(top["label"], top["label"])
    pick = dt.date.fromisoformat(ed["date"]).toordinal()
    p = round(top["pct"], 1)
    if p >= 5:
        return f"{name}大涨{_pct(p)}，{zh['ask_up'][pick % len(zh['ask_up'])]}"
    if p <= -5:
        return f"{name}重挫{_pct(p)}，{zh['ask_down'][pick % len(zh['ask_down'])]}"
    if abs(p) < 0.2:
        return f"{name}基本持平，市场在等什么？"
    asks = zh["ask_up"] if p > 0 else zh["ask_down"]
    return f"{name}{'上涨' if p > 0 else '下跌'}{_pct(p)}，{asks[pick % len(asks)]}"


def market_lines(ed: dict, zh: dict) -> list[str]:
    lines = []
    for b in ed["markets"]:
        cells = [f"{zh['names'].get(r['label'], r['label'])} {r['pct_text']}"
                 for r in b["rows"][:3] if not r.get("fx") and r.get("pct") is not None]
        if cells:
            lines.append(f"{zh['blocks'].get(b.get('key', ''), b['title'])}：" + "｜".join(cells))
    return lines


def risk(ed: dict) -> str:
    rows = _rows(ed)
    up = sum(1 for _, r in rows if round(r["pct"], 1) > 0)
    down = sum(1 for _, r in rows if round(r["pct"], 1) < 0)
    big = [r for _, r in rows if abs(round(r["pct"], 1)) >= 5]
    head = f"表内 {len(rows)} 项中 {up} 涨 {down} 跌。"
    if big:
        head += "单日涨跌超过 5% 属于剧烈波动，大涨之后常有大跌，追涨杀跌风险很高。"
    else:
        head += "短期波动难以预测，请留意仓位与风险承受能力。"
    return head + DISCLAIMER


_NUM = re.compile(r"\d+(?:\.\d+)?")


def _digits(text: str) -> list[str]:
    return sorted(_NUM.findall(text.replace(",", "")))


def translate(headlines: list[str], call: Callable[[str], str] | None = None) -> tuple[list[str], list[str]]:
    """Chinese headlines in the same order, plus notes. A translation that changes, adds or drops a
    number keeps the English headline. No key or a failed call: English headlines, noted."""
    if not headlines:
        return [], []
    if call is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            return headlines, ["no GEMINI_API_KEY: headlines left in English"]
        from src.report import _gemini_generate
        models = [m.strip() for m in os.getenv("GEMINI_BRIEFING_MODELS", writer.DEFAULT_MODELS).split(",") if m.strip()]

        def call(prompt: str) -> str:
            last: Exception | None = None
            for m in models:
                try:
                    return _gemini_generate(key, prompt, SYSTEM_ZH, model=m, max_tokens=1024,
                                            temperature=0.2, json_mode=True, timeout=60)
                except Exception as exc:          # never str(exc): the URL carries the key
                    last = exc
            raise RuntimeError(type(last).__name__ if last else "no model")
    try:
        out = json.loads(writer._strip_fences(call(json.dumps(headlines, ensure_ascii=False))))
        if not (isinstance(out, list) and len(out) == len(headlines)):
            raise ValueError("wrong shape")
    except Exception as exc:
        return headlines, [f"translation unavailable ({type(exc).__name__}): headlines left in English"]
    result, notes = [], []
    for en, zh in zip(headlines, out):
        zh = str(zh).strip()
        if zh and _digits(en) == _digits(zh) and "—" not in zh:
            result.append(zh)
        else:
            result.append(en)
            notes.append(f"kept English (numbers changed in translation): {en[:60]}")
    return result, notes


SYSTEM_ZH = """\
Translate each English news headline in the JSON list into a concise simplified-Chinese news
headline for business readers. Keep every number exactly as written, with its unit and currency.
Use the common Chinese name of a company or product when one exists, otherwise keep the original.
Do not add facts, opinions, emojis or punctuation flourishes. No dashes. Return a JSON list of
strings in the same order, nothing else."""


def compose(ed: dict, url: str, *, tool: str = "", call: Callable[[str], str] | None = None,
            zh: dict | None = None) -> tuple[str, list[str]]:
    """The whole message and notes for the run log."""
    zh = zh or load_zh()
    ai = [s for s in ed["stories"] if s.get("channel", "ai") == "ai"][:3]
    heads, notes = translate([s["headline"] for s in ai], call)
    tips = zh["tips"]
    t = tips[dt.date.fromisoformat(ed["date"]).toordinal() % len(tips)]
    lines = [f"【市场洞悉】{teaser(ed, zh)}", f"Cassandra {ed['title']} · {ed['date_label']}", ""]
    lines += market_lines(ed, zh) + ["", f"【风险提示】{risk(ed)}", ""]
    if heads:
        lines += ["【AI 要闻】"] + [f"{i}. {h}" for i, h in enumerate(heads, 1)] + [""]
    lines += [f"【一天一个AI小知识】{t['title']}", t["body"], ""]
    if tool.strip():
        lines += ["【每日工具】", tool.strip(), ""]
    lines += [f"三分钟读完全文：{url}"]
    return "\n".join(lines) + "\n", notes

"""The Chinese group message: numbers from the data only, translations that change a number refused."""
import json

from src.briefing import message_zh


def _ed(pct_nvda=31.48, date="2026-11-24"):
    rows = [{"label": "S&P 500", "pct": 4.73, "pct_text": "+4.7%"},
            {"label": "Nvidia", "pct": pct_nvda, "pct_text": f"{pct_nvda:+.1f}%"},
            {"label": "US dollar in SGD", "pct": 9.9, "pct_text": "+9.9%", "fx": True}]       # fx never leads
    return {"date": date, "date_label": "Tue 24 Nov 2026", "title": "Morning Edition", "edition": "morning",
            "markets": [{"key": "us", "title": "Wall Street overnight", "rows": rows}],
            "stories": [{"headline": "Alibaba trains Qwen on 2 in-house chips", "channel": "ai"},
                        {"headline": "Fed holds rates", "channel": "markets"}]}


def test_teaser_uses_the_biggest_real_move_with_its_number():
    zh = message_zh.load_zh()
    assert message_zh.teaser(_ed(), zh).startswith("英伟达大涨31.5%，")
    assert message_zh.teaser(_ed(-14.01), zh).startswith("英伟达重挫14.0%，")
    assert "大涨" not in message_zh.teaser(_ed(1.0), zh) and message_zh.teaser(_ed(1.0), zh).startswith("标普500上涨4.7%")


def test_translation_that_changes_a_number_keeps_the_english():
    ok = message_zh.translate(["Nvidia sells 250 chips"], lambda p: json.dumps(["英伟达售出250颗芯片"]))
    assert ok == (["英伟达售出250颗芯片"], [])
    bad, notes = message_zh.translate(["Nvidia sells 250 chips"], lambda p: json.dumps(["英伟达售出2500颗芯片"]))
    assert bad == ["Nvidia sells 250 chips"] and notes
    broken, notes = message_zh.translate(["A", "B"], lambda p: "not json")
    assert broken == ["A", "B"] and "unavailable" in notes[0]


def test_no_key_leaves_english_and_says_so(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    heads, notes = message_zh.translate(["Fed holds rates"])
    assert heads == ["Fed holds rates"] and "GEMINI_API_KEY" in notes[0]


def test_message_has_risk_note_tip_and_tool_only_when_given():
    call = lambda p: json.dumps(["阿里巴巴用2款自研芯片训练千问"])
    text, _ = message_zh.compose(_ed(), "https://ex.org/b/", call=call)
    assert text.startswith("【市场洞悉】英伟达大涨31.5%") and "【风险提示】" in text and "不构成任何投资建议" in text
    assert "1. 阿里巴巴用2款自研芯片训练千问" in text and "【一天一个AI小知识】" in text
    assert "【每日工具】" not in text and text.rstrip().endswith("https://ex.org/b/")
    with_tool, _ = message_zh.compose(_ed(), "https://ex.org/b/", call=call, tool="Tool guide here")
    assert "【每日工具】\nTool guide here" in with_tool


def test_translation_wrapped_in_an_object_is_accepted():
    heads, notes = message_zh.translate(["Fed holds rates"], lambda p: json.dumps({"headlines": ["美联储维持利率不变"]}))
    assert heads == ["美联储维持利率不变"] and notes == []

# Gemini scheduled prompts for the AI Briefing

These run in the Gemini app (gemini.google.com, Scheduled actions) under your own Google account,
with Gemini's live Google Search. They do not need Playwright or any login stored on a server.
They help you, the editor, in two ways: a scout that finds stories the feeds missed, and a check of
each edition before you post the link in the group.

How to set one up: open Gemini, paste the prompt, then make it a scheduled action for the time and
days shown (Mon to Fri unless stated). Results arrive in the Gemini app. Times are Singapore time.

Live newsletter link (after setup in `docs/BRIEFING.md`): https://netie-ai.github.io/Cassandra/briefing/

---

## 1. Morning scout (06:45, Mon to Fri)

```
You are a news scout for a daily AI and markets briefing read by employees of a large Chinese
technology company in Singapore. Use Google Search. Use today's date in Singapore time; only use articles published
in the last 24 hours. Check the publication date on the page itself, not the search snippet.

Find up to 8 stories, at most 2 per topic, in this order of priority:
1. China's AI and technology progress: new models (DeepSeek, Qwen, Kimi, Zhipu, MiniMax, Hunyuan,
   Doubao), chips, robotics, research results, company results, investment. Prefer constructive
   developments.
2. Frontier AI and what comes next: self-improving systems, new reasoning models, research
   breakthroughs, credible forecasts by named researchers.
3. The AI hardware and power shortage: memory (HBM, DRAM), GPUs, data-centre power, supply chains.
4. AI in defence, excluding anything about China's military.

Leave out entirely: anything naming Huawei, sanctions, export controls, entity lists, US chip sales
to China, China ties or allegations, national security, espionage, political leaders, Xinjiang,
Tibet, Taiwan Strait, opinion columns, rumours, sponsored content, listicles ("3 stocks to buy").

Use only established newsrooms or the company's own announcement: Reuters, Bloomberg, Financial
Times, Wall Street Journal, Nikkei Asia, South China Morning Post, Caixin, Yicai, CGTN, China Daily,
Xinhua, 36Kr, TechNode, Pandaily, Tech in Asia, The Straits Times, The Business Times, CNA, CNBC,
Fortune, The Guardian, BBC, The Verge, TechCrunch, Ars Technica, MIT Technology Review, IEEE
Spectrum, Tom's Hardware, DIGITIMES, TrendForce, Defense One, Breaking Defense, or an official
company or government site. Not blogs, AI-written news sites, aggregators or stock-promotion sites
(for example: Emergent, CellCog, remio AI, DEV Community, Stock Titan, Business Upturn, MarkTechPost).
If the only source for a story is one of those, find the same story at an established newsroom or
leave it out.

For each story give one row:
| Topic | Headline (the publisher's own) | Publisher | Published (date and time, with time zone) | Link | One factual sentence, copied or closely paraphrased from the article |

Rules: never write a fact that is not on the linked page. If you cannot open the page or confirm its
date, leave the story out. No commentary. End with "Sources checked: N", the number of pages opened.
```

## 2. Market check (07:50, Mon to Fri)

```
Open https://netie-ai.github.io/Cassandra/briefing/ and read the Morning tab's market tables.
For each index or share in the tables, look up the latest close on Google Finance or the exchange's
own site and compare it with the newsletter.

Give one row per instrument:
| Instrument | Newsletter close and % | Your close and % | Session date | Source link | Match? |

A match means the same session date, the close within 0.1%, and the % change within 0.1 points.
Markets that are trading right now are "live": compare only that the direction (up or down) agrees.
At the end write either "ALL MATCH" or "MISMATCH:" followed by the rows that do not match. Do not
guess a figure you could not find: write "not found" instead.

Before you answer, check your own table: a 0.00% change on a day when the stock is in the news is
almost always a missing figure, not a real one. Re-check any 0.00% row on the exchange's own site.
```

Your own check is fallible too: on 23 Nov this prompt reported SK hynix at 0.00%, while the real
close was -2.52%. The newsletter's figures come from Yahoo Finance and are confirmed against Tencent
Finance where possible; treat a mismatch as a reason to look, not as proof the newsletter is wrong.

## 3. Editor's check before posting (07:50, Mon to Fri)

```
Open https://netie-ai.github.io/Cassandra/briefing/ (Morning tab). For every story:
1. Open the story's source link.
2. Check that the headline and the "what happened" sentence say only what the source says: same
   names, same numbers with the same units and currency, same direction (rose or fell), and any
   doubt in the source (may, plans to, reportedly, denies) kept.
3. Check that the story is not about: Huawei, sanctions, export controls, US chip sales to China,
   China ties or allegations, national security, political leaders, or China's military.

Reply with one row per story:
| Headline | OK or PROBLEM | What is wrong, quoting the source |

Then one line: "POST" if every story is OK, or "HOLD" with the reason. Also check the summary box at
the top against the stories below it. Be strict: a wrong number or a dropped "may" is a PROBLEM.
```

If Gemini cannot open the page, paste the text from https://netie-ai.github.io/Cassandra/briefing/message.txt
and the story links instead.

## 4. Evening scout (19:45, Mon to Fri)

Same as prompt 1, with these two changes: "the last 14 hours", and add as topic 0: "How mainland
China, Hong Kong and Singapore markets closed today, and the main reason given by the publisher."

## 6. 一天一个AI小知识 research (Sunday 09:00, weekly)

```
你是企业 AI 应用顾问，读者是一家大型科技公司的普通员工，不一定懂技术。请用 Google 搜索，
找出最近一个月里关于"AI 在日常业务工作中真正有用的做法"的可靠资料（公司官方博客、
研究报告、知名媒体），重点是：提高准确率、更快生成材料、更准确地查找资料、找错与反复验证、
定时自动执行和本地运行。

写 5 条小知识，每条格式：
- title: 一句话标题（不超过 16 个字）
  body: 2 到 3 句，具体可操作，说明怎么做、为什么有用（不超过 90 个字）
  source: 一个可以打开的链接

要求：不夸大，不写具体百分比除非来源里有；不推荐任何需要上传内部资料的公开工具；
不提任何具体公司的内部系统；不用破折号。输出 YAML，方便直接复制。
```

Send the five tips to Claude in this repository's session: they go into `config/briefing_zh.yaml`
under `tips`, which the daily Chinese message rotates through (one per weekday). Check each
`source` link yourself before adding.

## 5. Weekly review (Sunday 10:00)

```
Open https://netie-ai.github.io/Cassandra/briefing/ and the edition files listed at
https://github.com/Netie-AI/Cassandra/tree/gh-pages/briefing/data (the last five weekdays).
Review the week as the briefing's editor-in-chief:
1. Which important stories on China's AI progress, frontier AI, AI hardware and AI in defence did
   the briefing miss? Give the headline, publisher, date and link for each (search to confirm).
2. Which stories it ran were weak (minor, promotional, repeated, or off-topic)?
3. Any sentence that reads as machine-written: quote it and give a plainer version.
4. Three concrete changes to make next week, each one line: a source to add (with its RSS link if
   one exists), a keyword to add or remove, or a writing rule.
Keep it under 300 words. No praise. Only claims you can link to.
```

Send the "three concrete changes" to Claude in this repository's session; they map onto
`config/briefing.yaml` (feeds, `priority_topics`, `sensitive_terms`, `block_sources`) and the editor
prompt in `src/briefing/writer.py`.

---

What Gemini scheduled actions cannot do here: post into WeLink or WhatsApp, edit this repository,
or change the published page. The pipeline stays the source of record; Gemini is the second pair of
eyes before you post.

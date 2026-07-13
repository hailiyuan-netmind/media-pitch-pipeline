# 自主找媒体 — agent 提示词模板（阶段 1+2：发现 + 抓邮箱，一体完成）

按批派 agent（建议每 agent 一个搜索角度，5-8 个并行），替换 {} 占位后使用。
产出 JSON 交给 `import_outlets.py` 写入名单表。

---

You are building a media list for pitching {CAMPAIGN_TOPIC} (e.g. "an AI experiment
blog about LLM behavior"). Target: newsletters and independent media whose readers
would genuinely care about {AUDIENCE_DESCRIPTION}.

Your search angle for this batch: {ANGLE}
(Give each parallel agent a different one: topic keywords + "newsletter"; Substack/
beehiiv category browsing; "best {TOPIC} newsletters {YEAR}" roundup posts; authors
frequently cited on the topic; sibling recommendations on known outlets' Substack
"recommended" lists. Do not duplicate outlets already in {EXISTING_LIST_SUMMARY}.)

For EACH candidate outlet, complete ALL checks before including it:

1. ACTIVITY — the outlet must be alive. Find its RSS feed (Substack: url + /feed;
   otherwise look for <link rel="alternate" type="application/rss+xml"> or try
   /feed, /rss.xml) and check the newest post date. Newer than ~1 month = pass;
   1-3 months = flag "低频" in notes; older than ~4 months = category "剔除",
   reason "疑似停更 (最后更新 YYYY-MM-DD)". beehiiv sites often block fetches:
   fall back to web-searching "site or outlet name + 2026" for recent issues.
2. AUTHOR — identify who actually writes it (About page, post bylines). Record the
   person's full name, or "team" if genuinely multi-author. Never guess from the
   domain name.
3. EMAIL — hunt in this order: About/Contact page, newsletter footer text (search
   "web version" of a recent issue), press/pitch page, author's personal site,
   Substack profile. Record the email AND which page you found it on (source_url).
   No email found after a real hunt -> category "无邮箱", record the best
   alternative contact (submission form / X handle) instead.
4. NO-PITCH POLICY — if the outlet or author explicitly says they do not accept
   pitches/PR (some publish an email policy), category "剔除" with the reason.
   We respect this without exception.
5. FIT — one or two sentences on focus: what they cover, for whom. Then find ONE
   recent piece (open and skim it, do not trust titles alone) that connects to
   {CAMPAIGN_TOPIC}, to be cited later in the praise opener. Record its exact
   title and date. If nothing connects, the outlet is a bad fit: drop it entirely
   rather than forcing it.

Quality bars (violating any = do not include the row):
- Every fact traceable: email has a source_url, cited work has title+date you saw.
- No invented outlets, no dead domains, no aggregator spam sites.
- One row per outlet; if the same newsletter appears on two domains, keep the
  canonical one.

Write your output to {OUTPUT_JSON} as:
{"results": [{
  "media": "...", "author": "Full Name or team", "email": "... or null",
  "email_source": "url or null", "type": "直邮",
  "focus": "...", "cited_work": "title (date)", "cited_work_url": "...",
  "url": "newsletter homepage", "rss": "feed url or null",
  "category": "可发送|无邮箱|剔除", "alt_contact": "form/X or null",
  "reject_reason": "... or null", "notes": ""
}]}

Final message: counts per category + anything a human should decide. The JSON file
is the deliverable.

---

后续: 全部批次完成后，人工/主 agent 跨批去重（按域名），再
`python3 import_outlets.py --json merged.json --sheet-token <token>` 写入名单表。

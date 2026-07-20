# 发送前开头刷新 — agent 提示词模板

对每个「开头引用的文章不在最新 3 篇里」的行，发送当天用此模板派 agent。
输入文件由 fetch_latest.py + 提取脚本生成，格式：
`[{row, media, greeting, version, current_opener, latest_articles: [{title, link, date}]}]`

---

You are refreshing the praise openers of media-pitch emails so they reference each
outlet's LATEST article instead of an older one. This is for NetMind's pitch about
their "AI dating show" experiment blog (7 LLMs in a dating-show format; findings
about LLM decision-making).

Read {INPUT_JSON} — outlets with: row, media, greeting, version, current_opener
(references an older piece), latest_articles (top 3 from RSS today, with links).

For EACH outlet:
1. Fetch and actually read the #1 latest article (use the link; if paywalled or
   blocked, read as much as available or fall back to article #2).
2. Rewrite the opener to praise/engage with THAT latest piece specifically —
   mention a real, specific point from it (an argument, example, or detail you
   actually read; never invent).
3. Rules, same register as the originals: 2-3 sentences; concrete; one clear
   specific observation tied to their piece; no "truly / fascinating / impressive"
   filler; no em-dashes; sounds like a person.
   BANNED scaffolds ("not X but Y" / "rather than" / "not just" / "isn't just... it's"): target zero, never more than one — say what the thing IS, not what it is not.
   - version=AI: the body that follows begins "We also recently ran an experiment
     evaluating an LLM capability that is widely used in practice but has received
     little systematic assessment." The opener must NOT say "we ran an experiment"
     and should end on the praise/observation itself. The opener's final sentence must give the body's "We also..." an antecedent: end on THEM examining/testing/tracking something. If no such parallel exists, the seam reads forced..
   - version=lifestyle: the body begins with the hook "People ask AI relationship
     questions all the time…"; a transition sentence like "We just ran a small
     experiment at NetMind that fits that angle" is allowed.
4. Keep the greeting/person the same.

Write {OUTPUT_JSON}:
{"results": [{"row": N, "media": "...", "new_opener": "...", "cited_title": "...",
"cited_date": "...", "read_ok": true, "notes": ""}]}

Final message: 2 sentences on what you read and any issues. The JSON file is the
deliverable.

---

回写: `python3 apply_refresh.py {OUTPUT_JSON}`

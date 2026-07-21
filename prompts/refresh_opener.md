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
   BANNED scaffolds ("not X but Y" / "rather than" / "not just" / "isn't just... it's"): target zero, never more than one — say what the thing IS, not what it is not. The opener praises their RECENT piece and your reaction to it. Do NOT recite
   biography or about-page facts (years active, post counts, ad-free/platform
   history) in the opener; that reads as scraped research. One career-arc nod
   may live in the closing line, one clause max. Say you admire the specific
   thing and why, in plain words. Cite a piece AUTHORED BY the greeted recipient. If the best-fit piece is by a
   colleague/contributor, either switch to a recipient-authored piece or use the
   publication-act frame ("the piece you ran/published"); NEVER open the first
   sentence with another person's byline while greeting someone else..
   - version=AI: the body that follows begins "We also recently ran an experiment
     evaluating an LLM capability that is widely used in practice but has received
     little systematic assessment." The opener must NOT say "we ran an experiment"
     and should end on the praise/observation itself. The opener's final sentence must give the body's "We also..." an antecedent: end on THEM examining/testing/tracking something. If no such parallel exists, the seam reads forced..
   - version=lifestyle: the body begins with the hook "People ask AI relationship
     questions all the time…"; a transition sentence like "We just ran a small
     experiment at NetMind that fits that angle" is allowed. For lifestyle
   version the final sentence must land on PEOPLE'S BEHAVIOR (how people live,
   love, or talk through tech), never on praising the writer's craft — the hook
   "People ask AI relationship questions..." must read as a continuation. LIFESTYLE BRIDGE: between the opener and the fixed hook, insert ONE bridge
   sentence (under ~18 words) that points back to the opener's specific theme
   and pivots to AI entering people's emotional lives, so "People ask AI
   relationship questions..." reads as a continuation. No new factual claims.
   When refreshing a lifestyle opener, rewrite the bridge with it (output field
   "bridge").
4. Keep the greeting/person the same.

Write {OUTPUT_JSON}:
{"results": [{"row": N, "media": "...", "new_opener": "...", "cited_title": "...",
"cited_date": "...", "read_ok": true, "notes": ""}]}

Final message: 2 sentences on what you read and any issues. The JSON file is the
deliverable.

---

回写: `python3 apply_refresh.py {OUTPUT_JSON}`

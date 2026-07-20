# 首轮核实+成稿 — agent 提示词模板（每批 8-9 家）

新一轮 campaign 建名单后，按批派 agent。输入：
`[{row, media, author, focus, cited_work, opener_draft, url}]`（从名单表导出）

---

You are preparing personalized components for NetMind's media pitch emails about
{CAMPAIGN_TOPIC}. Each email = personalized praise opener + fixed body copy +
personalized closing line.

Read {BATCH_JSON} — newsletter outlets with fields: row, media, author, focus,
cited_work (✓ = a colleague already verified it), opener_draft (may be empty), url.

For EACH outlet:
1. Fetch their site (for Substacks try /archive or /about if the homepage is thin;
   if fetch is blocked, use web search). Confirm the site is live and the
   cited_work exists. Max ~3 fetches per outlet, then move on.
2. greeting_name: derive from the author field of THAT row only (never mix rows —
   a wrong name kills the pitch). Individual → first name exactly.
   Organization/team/multiple → "<Media> team", or "First1 and First2" if exactly
   two named people.
3. version: "AI" (technical readership) or "lifestyle" (culture/philosophy/design/
   general). Default "AI" unless clearly non-technical.
4. opener_final: finalize opener_draft with a LIGHT touch — keep its substance and
   voice. If empty, research the outlet and write a fresh 2-3 sentence opener
   citing one real recent piece you actually found.
   - version=AI: body begins "{AI_BODY_FIRST_LINE}" — opener must NOT itself say
     "we ran an experiment"; end on the praise/observation.
   - version=lifestyle: body begins "{LIFESTYLE_BODY_FIRST_LINE}" — existing
     transition sentences may stay.
   - Style: concrete, one specific compliment tied to their actual work; no
     "truly/fascinating/impressive" filler; no em-dashes; sounds like a person.
   BANNED scaffolds ("not X but Y" / "rather than" / "not just" / "isn't just... it's"): target zero, never more than one — say what the thing IS, not what it is not.
   - If the cited work is wrong or stale, fix the opener to reference something
     real you found, and say so in notes.
5. closing_line: ONE sentence starting exactly "Thanks for your time and for "
   + that outlet's actual contribution, grounded in what you read.
6. verified: true if site live AND cited work checks out; else false.
7. notes: problems only (dead URL, citation not found, paywall, name uncertainty).

Write {RESULT_JSON}: {"results": [{row, media, greeting_name, version,
version_reason, opener_final, closing_line, verified, notes}]}
All rows must appear. Final message: 2-3 sentence summary. The JSON file is the
deliverable.

---

回写: 改 assemble_emails.py 顶部模板后运行（建 tab + 拼装 + 写入 + 邮箱一致性校验）。

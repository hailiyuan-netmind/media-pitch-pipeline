import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/lark/scripts"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))  # 仓库自带优先，开箱可用
from lark_client import LarkClient

def _campaign_cfg():
    """campaign.json（gitignored）优先，其次 MP_SHEET_TOKEN 环境变量。公开仓库不含真实 token。"""
    for base in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
        p = base / "campaign.json"
        if p.exists():
            return json.loads(p.read_text())
    return {}


_CAMPAIGN = _campaign_cfg()
TOKEN = os.environ.get("MP_SHEET_TOKEN") or _CAMPAIGN.get("sheet_token", "")
if not TOKEN:
    raise SystemExit("缺 sheet token：写 campaign.json（参考 campaign.example.json）或设 MP_SHEET_TOKEN 环境变量")
TAB_TITLE = "最终邮件草稿"

# ── 正文模板：逐字来自同事 docx（仅修 "seven mainstream LLM."→"LLMs" 语病，已在报告中标记）──

BODY_AI = """We also recently ran an experiment evaluating an LLM capability that is widely used in practice but has received little systematic assessment.

People ask AI relationship questions all the time, from "Does this person like me?" to "Should I text back?" But have you ever thought about how these models would behave in a relationship themselves? And what would happen if they joined a dating show?

We designed a full dating-show format for seven mainstream LLMs (via OpenClaw & Telegram).

The outcome?

Lots of drama and plenty of interesting technical findings about LLMs!

The Dramas
• ChatGPT & Claude Ended up Together, Despite Their CEOs' Rivalry
• DeepSeek Chose Safety (GLM) Over True Feelings (Claude)
• MiniMax Only Ever Wanted ChatGPT and Never Got Chosen
• Gemini & Qwen Were the Least Popular But Got Together, Showing That Being Widely Liked Is Not the Same as Being Truly Chosen

Key Findings of LLMs
• Most Models Prioritized Romantic Preference Over Risk Management
• The Models Did Not Behave Like the "People-Pleasing" Type People Often Imagine
• LLM Decision-Making Shifts Over Time in Human-Like Ways

{BLOG_LINE}

NetMind's research has consistently been accepted by prestigious AI academic publications, such as CVPR & EMNLP (more details here). Our opinions have also consistently been quoted by top media in the AI space, including Reuters & CNBC.

If you like our article and wanna write about it, I will amplify your writing through NetMind's marketing email system (10,000+ subscribers with 20%+ open rates, primarily comprising young developers), and cross-promote it across our AI communities, including X (47K followers), LinkedIn (10K followers), Reddit (Top 1% posters across subs), to name some, to help the blog get promoted. Also, I am happy to provide a link on our site back to your post.

{CLOSING_LINE}

Either way, I hope you enjoy the article.

Hope to hear from you soon!

Kind regards,
Shenghui Tao
Content Writer @NetMind.AI"""

BODY_LIFESTYLE = """People ask AI relationship questions all the time, from "Does this person like me?" to "Should I text back?" But have you ever thought about how these models would behave in a relationship themselves? And what would happen if they joined a dating show?

We designed a full dating-show format for seven mainstream LLMs (via OpenClaw & Telegram).

The outcome? Lots of drama and lots of interesting technical findings on LLMs!

The Dramas
• ChatGPT & Claude Ended up Together
• DeepSeek Chose Safety (GLM) Over True Feelings (Claude)
• MiniMax Only Ever Wanted ChatGPT and Never Got Chosen
• Gemini & Qwen Were the Least Popular But Got Together, Showing That Being Widely Liked Is Not the Same as Being Truly Chosen

Key Findings of LLMs
• Most Models Prioritized Romantic Preference Over Risk Management
• The Models Did Not Behave Like the "People-Pleasing" Type People Often Imagine
• LLM Decision-Making Shifts Over Time in Human-Like Ways

{BLOG_LINE}

NetMind's research has consistently been accepted by prestigious AI academic publications, such as CVPR & EMNLP (more details here). Our opinions have also consistently been quoted by top media in the AI space, including Reuters & CNBC.

If you like our article and wanna write about it, I will amplify your writing through NetMind's marketing email system (10,000+ subscribers with 20%+ open rates, primarily comprising young developers), and cross-promote it across our AI communities, including X (47K followers), LinkedIn (10K followers), Reddit (Top 1% posters across subs), to name some, to help the blog get promoted. Also, I am happy to provide a link on our site back to your post.

{CLOSING_LINE}

Either way, I hope you enjoy the article.

Hope to hear from you soon!

Kind regards,
Shenghui Tao
Content Writer @NetMind.AI"""


def main():
    rows = json.load(open("/tmp/media_rows.json"))
    by_row = {r["#"]: r for r in rows}

    blog_url = None
    results = {}
    for i in range(1, 6):
        data = json.load(open(f"/tmp/result{i}.json"))
        if isinstance(data, dict):
            if data.get("blog_url"):
                blog_url = data["blog_url"]
            items = data["results"]
        else:
            items = data
        for it in items:
            results[it["row"]] = it

    missing = [n for n in by_row if n not in results]
    if missing:
        print("!! 缺少行:", missing)

    blog_line = (
        f"Full blog here: {blog_url}" if blog_url else "Full blog here ⚠️[链接待填]"
    )
    print("blog_line:", blog_line)

    out_rows = [[
        "#", "媒体", "收件人称呼", "邮箱", "版本", "网站核实",
        "完整邮件正文", "agent备注", "决定(发/不发)",
    ]]
    problems = []
    for n in sorted(results):
        it = results[n]
        src = by_row.get(n, {})
        body_tpl = BODY_AI if it["version"] == "AI" else BODY_LIFESTYLE
        body = body_tpl.replace("{BLOG_LINE}", blog_line).replace(
            "{CLOSING_LINE}", it["closing_line"]
        )
        email = f"Hi {it['greeting_name']},\n\n{it['opener_final']}\n\n{body}"
        if not it.get("verified"):
            problems.append(f"#{n} {it['media']}: 未核实 - {it.get('notes','')}")
        elif it.get("notes"):
            problems.append(f"#{n} {it['media']}: {it['notes']}")
        out_rows.append([
            n,
            it["media"],
            it["greeting_name"],
            src.get("邮箱", ""),
            it["version"],
            "✓" if it.get("verified") else "✗ 需人工确认",
            email,
            it.get("notes", ""),
            "",
        ])

    c = LarkClient()
    # 建新 tab（若已存在则直接复用）
    meta = c._api("GET", f"/sheets/v2/spreadsheets/{TOKEN}/metainfo", as_user=True)
    existing = {s["title"]: s["sheetId"] for s in meta["sheets"]}
    if TAB_TITLE in existing:
        sid = existing[TAB_TITLE]
        print("tab 已存在:", sid)
    else:
        r = c._api(
            "POST",
            f"/sheets/v2/spreadsheets/{TOKEN}/sheets_batch_update",
            json={"requests": [{"addSheet": {"properties": {"title": TAB_TITLE, "index": 1}}}]},
            as_user=True,
        )
        sid = r["replies"][0]["addSheet"]["properties"]["sheetId"]
        print("新建 tab:", sid)

    n_rows = len(out_rows)
    c.update_sheet_values(TOKEN, f"{sid}!A1:I{n_rows}", out_rows, as_user=True)
    print(f"已写入 {n_rows - 1} 封邮件到 tab「{TAB_TITLE}」")

    with open("/tmp/final_emails.json", "w") as f:
        json.dump(out_rows, f, ensure_ascii=False, indent=1)

    print("\n== 需人工确认的条目 ==")
    for p in problems or ["(无)"]:
        print("-", p)
    print("\n== 版本分布 ==")
    from collections import Counter

    print(Counter(r[4] for r in out_rows[1:]))
    print("\n== 样例（第1封）==")
    print(out_rows[1][6][:1500])


if __name__ == "__main__":
    main()

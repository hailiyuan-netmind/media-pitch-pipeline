#!/usr/bin/env python3
"""从「最终邮件草稿」tab 的一行构建 Brevo request JSON。

用法: python3 build_request.py --row 1 [--out brevo-requests/]

固定正文的超链接在 LINKS 里统一维护（来源：同事 docx 的 blocks API，
raw_content 会剥掉超链接所以当初没看到；sendibt3 跟踪链接已还原为真实地址）。
"""
import argparse
import json
import os
import re
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
SHEET_TOKEN = os.environ.get("MP_SHEET_TOKEN") or _CAMPAIGN.get("sheet_token", "")
if not SHEET_TOKEN:
    raise SystemExit("缺 sheet token：写 campaign.json（参考 campaign.example.json）或设 MP_SHEET_TOKEN 环境变量")
DRAFT_SHEET = "46PiH6"
LIST_SHEET = "0jcVvH"

SENDER = {"email": "marketing@netmind.ai", "name": "NetMind.AI"}
SUBJECT = "An AI dating experiment your readers might enjoy"

# 固定正文链接（2026-07-08 从 docx blocks 还原并逐一验活；Reuters 脚本访问 401 属反爬，浏览器正常）
LINKS = {
    "blog": "https://blog.netmind.ai/article/llm-dating-show-part-1",
    "more_details": "https://www.netmind.space/research",
    "reuters": "https://www.reuters.com/technology/artificial-intelligence/deepseek-gives-europes-tech-firms-chance-catch-up-global-ai-race-2025-02-03/",
    "cnbc": "https://www.cnbc.com/2025/01/30/chinas-deepseek-has-some-big-ai-claims-not-all-experts-are-convinced-.html",
}


def flat(v):
    if isinstance(v, list):
        return "".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in v)
    return str(v) if v is not None else ""


def to_markdown(text):
    text = text.replace("The Dramas\n", "### The Dramas\n\n")
    text = text.replace("Key Findings of LLMs\n", "### Key Findings of LLMs\n\n")
    text = text.replace("• ", "- ")
    text = re.sub(r"Full blog here: \S+", f"Full blog [here]({LINKS['blog']}).", text)
    text = text.replace(
        "(more details here)", f"(more details [here]({LINKS['more_details']}))"
    )
    text = text.replace(
        "including Reuters & CNBC",
        f"including [Reuters]({LINKS['reuters']}) & [CNBC]({LINKS['cnbc']})",
    )
    text = text.replace("Kind regards,\n", "Kind regards,  \n")
    text = text.replace("Shenghui Tao\n", "Shenghui Tao  \n")
    return text


def validate_links(md):
    """构建闸门：4 个链接必须全部转换成功，且无裸 URL。失败即拒绝构建。"""
    required = [
        "[here](" + LINKS["blog"],
        "(more details [here](",
        "[Reuters](",
        "[CNBC](",
    ]
    missing = [x for x in required if x not in md]
    bare = [m.group(0)[:60] for m in re.finditer(r"(?<!\]\()https?://\S+", md)]
    if missing or bare:
        raise SystemExit(
            f"链接校验失败 missing={missing} bare={bare[:3]}\n"
            "草稿正文必须逐字使用模板句式：Full blog here: <URL> / (more details here) / "
            "including Reuters & CNBC。链接由本脚本统一转换，禁止在正文手写内联 URL。"
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--row", type=int, required=True, help="名单行号 1-41")
    ap.add_argument("--out", default=str(Path(__file__).parent / "brevo-requests"))
    args = ap.parse_args()

    c = LarkClient()
    r = args.row + 1  # 表头占一行
    d = c.get_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!A{r}:H{r}", as_user=True)
    row = d["valueRange"]["values"][0]
    media, greeting, email_addr, text = flat(row[1]), flat(row[2]), flat(row[3]).strip(), flat(row[6])
    author = flat(
        c.get_sheet_values(SHEET_TOKEN, f"{LIST_SHEET}!C{r}:C{r}", as_user=True)[
            "valueRange"
        ]["values"][0][0]
    ).strip()

    if not text.startswith("Hi "):
        raise SystemExit(f"row {args.row} 正文异常（不以 Hi 开头）")
    # 行号身份断言（审计修复：拒绝两表错位）
    draft_no = flat(row[0]).strip()
    if draft_no and int(float(draft_no)) != args.row:
        raise SystemExit(f"草稿表第{r}行编号 {draft_no} != --row {args.row}，两表可能错位")
    lrow = c.get_sheet_values(SHEET_TOKEN, f"{LIST_SHEET}!A{r}:B{r}", as_user=True)["valueRange"]["values"][0]
    lno, lmedia = flat(lrow[0]).strip(), flat(lrow[1]).strip()
    if lno and int(float(lno)) != args.row:
        raise SystemExit(f"名单表第{r}行编号 {lno} != --row {args.row}")
    if lmedia and media.strip() != lmedia:
        raise SystemExit(f"两表媒体名不一致: 草稿 {media!r} vs 名单 {lmedia!r}")
    if "@" not in email_addr or " " in email_addr:
        raise SystemExit(f"邮箱异常: {email_addr!r}")

    md = to_markdown(text)
    validate_links(md)
    req = {
        "sender": SENDER,
        "to": [{"email": email_addr, "name": author or greeting}],
        "subject": SUBJECT,
        "markdown": md,
    }
    slug = re.sub(r"[^a-z0-9]+", "_", media.lower()).strip("_")[:30]
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    f = out / f"pitch_{args.row:02d}_{slug}.json"
    f.write_text(json.dumps(req, ensure_ascii=False, indent=2))
    print(f"written: {f}")
    print(f"to: {author} <{email_addr}> | media: {media}")


if __name__ == "__main__":
    main()

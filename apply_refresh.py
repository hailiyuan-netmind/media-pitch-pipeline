#!/usr/bin/env python3
"""把 agent 刷新后的开头写回「最终邮件草稿」tab。

用法: python3 apply_refresh.py /tmp/refresh_demo.json
输入格式: {"results": [{"row": 2, "new_opener": "...", "cited_title": "...", "cited_date": "..."}]}

逻辑: 从表里读该行现有邮件全文 → 保留问候行和正文（从版本标志句起）→ 只替换中间的开头段
→ 写回 G 列，并在 H 列备注追加刷新记录。表是唯一事实源，同事若手改过正文也不会被覆盖。
"""
import json
import os
import sys
from datetime import date
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
BODY_MARKERS = [
    "We also recently ran an experiment",   # AI 版正文首句
    "People ask AI relationship questions",  # 情感版正文首句
]


def flat(v):
    if isinstance(v, list):
        return "".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in v)
    return str(v) if v is not None else ""


def main():
    data = json.load(open(sys.argv[1]))
    results = data["results"] if isinstance(data, dict) else data
    c = LarkClient()

    for it in results:
        row_idx = it["row"] + 1  # 表头占第 1 行
        d = c.get_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!G{row_idx}:H{row_idx}", as_user=True)
        cells = d["valueRange"]["values"][0]
        email, note = flat(cells[0]), flat(cells[1] if len(cells) > 1 else "")

        marker_pos = None
        for m in BODY_MARKERS:
            p = email.find(m)
            if p != -1:
                marker_pos = p
                break
        if marker_pos is None:
            print(f"!! row {it['row']}: 找不到正文标志句，跳过")
            continue

        greeting = email.split("\n", 1)[0]
        new_email = f"{greeting}\n\n{it['new_opener']}\n\n{email[marker_pos:]}"
        stamp = f"[{date.today()}] 开头已刷新至最新文章《{it.get('cited_title', '?')}》({it.get('cited_date', '?')})"
        new_note = f"{note} | {stamp}" if note else stamp

        c.update_sheet_values(
            SHEET_TOKEN, f"{DRAFT_SHEET}!G{row_idx}:H{row_idx}",
            [[new_email, new_note]], as_user=True,
        )
        print(f"row {it['row']} {it.get('media', '')}: 已刷新 -> {it.get('cited_title', '')[:50]}")


if __name__ == "__main__":
    main()

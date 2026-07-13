#!/usr/bin/env python3
"""把 discover_media 的产出 JSON 写入 Lark 名单表（按 category 分流三个 tab）。

用法: python3 import_outlets.py --json merged.json --sheet-token <TOKEN> [--dry]

- category=可发送  -> tab「可发送名单」（与 assemble/fetch/build 脚本兼容的 11 列结构）
- category=无邮箱  -> tab「对路但无邮箱」
- category=剔除    -> tab「已剔除」
tab 不存在会自动创建；数据追加在已有行之后，"#" 列自动续号。
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/lark/scripts"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))  # 仓库自带优先，开箱可用
from lark_client import LarkClient

HEADERS = {
    "可发送名单": ["#", "媒体", "作者", "邮箱", "类型", "领域 (focus)",
                "引用作品 (已核实=✓)", "邮件开头 (praise)", "newsletter",
                "决定(发/不发)", "同事备注"],
    "对路但无邮箱": ["媒体", "newsletter", "替代联系方式 (表单/X)"],
    "已剔除": ["媒体", "剔除原因"],
}


def flat(v):
    if isinstance(v, list):
        return "".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in v)
    return v or ""


def ensure_tab(c, token, title):
    meta = c._api("GET", f"/sheets/v2/spreadsheets/{token}/metainfo", as_user=True)
    for s in meta["sheets"]:
        if s["title"] == title:
            return s["sheetId"], s.get("rowCount", 200)
    r = c._api(
        "POST", f"/sheets/v2/spreadsheets/{token}/sheets_batch_update",
        json={"requests": [{"addSheet": {"properties": {"title": title}}}]},
        as_user=True,
    )
    return r["replies"][0]["addSheet"]["properties"]["sheetId"], 200


def used_rows(c, token, sid, width):
    col_end = chr(ord("A") + width - 1)
    d = c.get_sheet_values(token, f"{sid}!A1:{col_end}200", as_user=True)
    vals = d["valueRange"]["values"]
    n = 0
    for i, row in enumerate(vals):
        if row and any(flat(x).strip() for x in row):
            n = i + 1
    return n


def to_row(tab, item, seq):
    if tab == "可发送名单":
        cited = item.get("cited_work") or ""
        if cited and item.get("cited_work_url"):
            cited = f"✓ {cited} {item['cited_work_url']}"
        return [seq, item["media"], item.get("author", ""), item.get("email", ""),
                item.get("type", "直邮"), item.get("focus", ""), cited,
                item.get("opener_draft", ""), item.get("url", ""), "",
                item.get("notes", "")]
    if tab == "对路但无邮箱":
        return [item["media"], item.get("url", ""), item.get("alt_contact", "")]
    return [item["media"], item.get("reject_reason", "")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--sheet-token", required=True)
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    data = json.load(open(args.json))
    items = data["results"] if isinstance(data, dict) else data
    buckets = {"可发送名单": [], "对路但无邮箱": [], "已剔除": []}
    tab_of = {"可发送": "可发送名单", "无邮箱": "对路但无邮箱", "剔除": "已剔除"}
    for it in items:
        buckets[tab_of[it["category"]]].append(it)

    c = LarkClient()
    for tab, rows in buckets.items():
        if not rows:
            continue
        hdr = HEADERS[tab]
        if args.dry:
            print(f"[dry] {tab}: +{len(rows)} 行")
            continue
        sid, _ = ensure_tab(c, args.sheet_token, tab)
        used = used_rows(c, args.sheet_token, sid, len(hdr))
        out = []
        if used == 0:
            out.append(hdr)
        start_seq = max(used, 1)  # 表头占 1 行时数据从序号 1 开始
        for i, it in enumerate(rows):
            out.append(to_row(tab, it, start_seq + i))
        first = used + 1
        col_end = chr(ord("A") + len(hdr) - 1)
        c.update_sheet_values(
            args.sheet_token, f"{sid}!A{first}:{col_end}{first + len(out) - 1}",
            out, as_user=True,
        )
        print(f"{tab}: 写入 {len(rows)} 行（从第 {first} 行起）")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""拉取每家媒体的最新文章（RSS/Atom），供“夸赞开头引用最新内容”环节使用。

用法:
  python3 fetch_latest.py --from-sheet            # 直接读 Lark 在线表「可发送名单」
  python3 fetch_latest.py --json outlets.json      # 或传 [{"row":1,"media":"...","url":"..."}]
  python3 fetch_latest.py --from-sheet --write-back # 抓完把最新文章写回「最终邮件草稿」J 列

输出: latest_articles.json（每家 top3: 标题/链接/日期），stdout 打印覆盖率与新鲜度。
零依赖（仅 requests + 标准库），RSS 拿不到的媒体会标记 feed_url=null，走人工/agent 兜底。
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin

import requests

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
COMMON_PATHS = ["/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml", "/index.xml", "/feed/", "/api/rss/ai"]
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
LIST_SHEET = "0jcVvH"      # 可发送名单
DRAFT_SHEET = "46PiH6"     # 最终邮件草稿


def get(url, timeout=12):
    return requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)


def strip_ns(tag):
    return tag.rsplit("}", 1)[-1].lower()


def parse_feed(xml_bytes, limit=3):
    """极简 RSS2/Atom 解析，返回 [{title, link, date}]。"""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    items = [el for el in root.iter() if strip_ns(el.tag) in ("item", "entry")]
    out = []
    for it in items[: limit * 2]:
        title, link, date = None, None, None
        for ch in it:
            t = strip_ns(ch.tag)
            if t == "title":
                title = (ch.text or "").strip()
            elif t == "link":
                link = (ch.get("href") or ch.text or "").strip() or link
            elif t in ("pubdate", "published", "updated", "date"):
                raw = (ch.text or "").strip()
                if raw and not date:
                    try:
                        date = parsedate_to_datetime(raw)
                    except (TypeError, ValueError):
                        try:
                            date = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        except ValueError:
                            pass
        if title:
            out.append({
                "title": title,
                "link": link,
                "date": date.astimezone(timezone.utc).strftime("%Y-%m-%d") if date else None,
            })
        if len(out) >= limit:
            break
    return out or None


def discover_feed(site_url):
    """返回 (feed_url, items) 或 (None, None)。"""
    base = site_url.rstrip("/")
    candidates = []
    if "substack.com" in base:
        candidates.append(base + "/feed")
    # 1) 先抓首页找 <link rel=alternate>
    html = ""
    try:
        r = get(base)
        if r.ok:
            html = r.text[:200000]
    except requests.RequestException:
        pass
    for m in re.finditer(
        r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*>', html, re.I
    ):
        href = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        if href:
            candidates.append(urljoin(base + "/", href.group(1)))
    # substack 页面即使没声明也支持 /feed
    if "substack" in html.lower() and base + "/feed" not in candidates:
        candidates.append(base + "/feed")
    candidates += [base + p for p in COMMON_PATHS]

    seen = set()
    for cand in candidates:
        if cand in seen:
            continue
        seen.add(cand)
        try:
            r = get(cand)
            if not r.ok or len(r.content) < 200:
                continue
            head = r.content[:300].lstrip().lower()
            if not (head.startswith(b"<?xml") or b"<rss" in head or b"<feed" in head):
                continue
            items = parse_feed(r.content)
            if items:
                return cand, items
        except requests.RequestException:
            continue
    return None, None


def load_outlets_from_sheet():
    sys.path.insert(0, str(Path.home() / ".claude/skills/lark/scripts"))
    sys.path.insert(0, str(Path(__file__).parent / "lib"))  # 仓库自带优先，开箱可用
    from lark_client import LarkClient

    c = LarkClient()
    meta = c._api("GET", f"/sheets/v2/spreadsheets/{SHEET_TOKEN}/metainfo", as_user=True)
    nrows = next((sh.get("rowCount", 200) for sh in meta["sheets"] if sh["sheetId"] == LIST_SHEET), 200)
    d = c.get_sheet_values(SHEET_TOKEN, f"{LIST_SHEET}!A2:I{nrows}", as_user=True)
    outlets = []
    for row in d["valueRange"]["values"]:
        if not row or row[0] is None:
            continue

        def flat(v):
            if isinstance(v, list):
                return "".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in v)
            return str(v) if v is not None else ""

        outlets.append({"row": int(row[0]), "media": flat(row[1]), "url": flat(row[8]).strip()})
    return outlets


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-sheet", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--out", default="latest_articles.json")
    ap.add_argument("--write-back", action="store_true", help="把最新文章写回草稿 tab 的 J 列")
    args = ap.parse_args()

    if args.from_sheet:
        outlets = load_outlets_from_sheet()
    elif args.json:
        outlets = json.load(open(args.json))
    else:
        ap.error("需要 --from-sheet 或 --json")

    def work(o):
        feed, items = discover_feed(o["url"]) if o.get("url") else (None, None)
        return {**o, "feed_url": feed, "latest": items}

    with cf.ThreadPoolExecutor(10) as ex:
        results = list(ex.map(work, outlets))

    results.sort(key=lambda r: r["row"])
    Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))

    ok = [r for r in results if r["latest"]]
    print(f"RSS 覆盖率: {len(ok)}/{len(results)}")
    today = datetime.now(timezone.utc)
    for r in results:
        if r["latest"]:
            top = r["latest"][0]
            age = ""
            if top["date"]:
                days = (today - datetime.fromisoformat(top["date"]).replace(tzinfo=timezone.utc)).days
                age = f"{days}d"
            print(f"  #{r['row']:>2} {r['media'][:28]:<30} {top['date'] or '?'} ({age:>4}) {top['title'][:52]}")
        else:
            print(f"  #{r['row']:>2} {r['media'][:28]:<30} ✗ 无可用 RSS ({r['url']})")

    if args.write_back:
        sys.path.insert(0, str(Path.home() / ".claude/skills/lark/scripts"))
        sys.path.insert(0, str(Path(__file__).parent / "lib"))  # 仓库自带优先，开箱可用
        from lark_client import LarkClient

        c = LarkClient()
        col = [["最新文章 (RSS 实时)"]]
        for r in results:
            if r["latest"]:
                col.append(["\n".join(f"[{i['date'] or '?'}] {i['title']} {i['link'] or ''}" for i in r["latest"])])
            else:
                col.append(["✗ 无 RSS，需人工/agent 查最新"])
        c.update_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!J1:J{len(col)}", col, as_user=True)
        print(f"已写回草稿 tab J 列（{len(col) - 1} 行）")


if __name__ == "__main__":
    main()

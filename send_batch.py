#!/usr/bin/env python3
"""批量正式发送（2026-07-21 加固版，对应 review/ 审计的 critical 修复）。

用法: python3 send_batch.py --rows 44,46,47 [--dry] [--force]

闸门（任何一道不过即整批拒发或跳过该行）：
1. 行号去重；单批 ≤40 且当日累计 ≤40（护发件域名）
2. 全部行先验后发：名单表与草稿表实时比对（行号↔#、媒体名一致、邮箱格式）
3. 防重发：K 列已有正式 messageId 或 L=已发送 的行直接拒绝（--force 才放行）
4. 逐封发送后立即落盘日志（崩溃不丢 messageId）
5. 发送 rc 与输出解析分离：rc=0 但解析失败报 sent_unconfirmed 并警告勿重试
6. To 显示名净化（去除作者列的括号注释）
7. 每封发送后立即回写 I/K/L（草稿）+ L（名单）并读回
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/lark/scripts"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))  # 仓库自带优先，开箱可用
from lark_client import LarkClient


def _campaign_cfg():
    for base in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
        p = base / "campaign.json"
        if p.exists():
            return json.loads(p.read_text())
    return {}


_CAMPAIGN = _campaign_cfg()
SHEET_TOKEN = os.environ.get("MP_SHEET_TOKEN") or _CAMPAIGN.get("sheet_token", "")
if not SHEET_TOKEN:
    raise SystemExit("缺 sheet token：写 campaign.json 或设 MP_SHEET_TOKEN")
LIST_SHEET = "0jcVvH"
DRAFT_SHEET = "46PiH6"
PIPE = Path(__file__).parent
BOOT = str(Path.home() / ".claude/skills/brevo/scripts/bootstrap_runtime.sh")
DAILY_CAP = 40


def flat(v):
    if isinstance(v, list):
        return "".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in v)
    return str(v) if v is not None else ""


def clean_name(author):
    """'Kate Lindsay (撰稿/联合创始人), Nick Catucci (编辑)' -> 'Kate Lindsay, Nick Catucci' -> 主体首段"""
    s = re.sub(r"[（(][^）)]*[）)]", "", author)
    s = re.split(r"[;；]", s)[0]
    s = re.sub(r"\s+", " ", s).strip(" ,，")
    return s or author.strip()


def official_mid(k):
    return bool(re.search(r"\d{4}-\d{2}-\d{2} <", k))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--dry", action="store_true", help="只构建+全量校验，不发送")
    ap.add_argument("--force", action="store_true", help="允许重发已有正式记录的行")
    args = ap.parse_args()

    rows = list(dict.fromkeys(int(x) for x in args.rows.split(",") if x.strip()))
    if len(rows) > DAILY_CAP:
        raise SystemExit(f"单批 {len(rows)} 超过每日上限 {DAILY_CAP}")

    c = LarkClient()
    meta = c._api("GET", f"/sheets/v2/spreadsheets/{SHEET_TOKEN}/metainfo", as_user=True)
    nmax = max(s.get("rowCount", 200) for s in meta["sheets"])
    lst, dft = {}, {}
    for row in c.get_sheet_values(SHEET_TOKEN, f"{LIST_SHEET}!A2:N{nmax}", as_user=True)["valueRange"]["values"]:
        cells = [flat(x) for x in (row or [])]
        if cells and cells[0].strip():
            lst[int(cells[0])] = {"media": cells[1], "author": cells[2], "email": cells[3].strip()}
    for row in c.get_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!A2:M{nmax}", as_user=True)["valueRange"]["values"]:
        cells = [flat(x) for x in (row or [])]
        if cells and cells[0].strip():
            dft[int(cells[0])] = {"media": cells[1], "K": cells[10] if len(cells) > 10 else "",
                                  "L": cells[11] if len(cells) > 11 else ""}

    today = date.today().isoformat()
    sent_today = sum(1 for d in dft.values() if d["K"].startswith(today))
    if sent_today + len(rows) > DAILY_CAP:
        raise SystemExit(f"当日已发 {sent_today}，再发 {len(rows)} 将超上限 {DAILY_CAP}")

    # ── 先验后发 ──
    problems = []
    for n in rows:
        if n not in lst: problems.append(f"#{n} 不在名单表"); continue
        if n not in dft: problems.append(f"#{n} 不在草稿表"); continue
        if lst[n]["media"].strip() != dft[n]["media"].strip():
            problems.append(f"#{n} 两表媒体名不一致: {lst[n]['media']!r} vs {dft[n]['media']!r}")
        if "@" not in lst[n]["email"] or " " in lst[n]["email"]:
            problems.append(f"#{n} 邮箱异常: {lst[n]['email']!r}")
        if not args.force and (official_mid(dft[n]["K"]) or dft[n]["L"].startswith("已发送")):
            problems.append(f"#{n} 已有正式发送记录（K={dft[n]['K'][:30]!r} L={dft[n]['L']!r}），拒绝重发")
    if problems:
        print("整批拒发，先解决：")
        for p in problems: print("  -", p)
        sys.exit(1)
    print(f"先验通过: {len(rows)} 行（当日已发 {sent_today}）")
    if args.dry:
        for n in rows:
            print(f"  [dry] #{n} {lst[n]['media']} -> {clean_name(lst[n]['author'])} <{lst[n]['email']}>")
        return

    log_path = Path(f"/tmp/send_log_{today}.json")
    log = json.loads(log_path.read_text()) if log_path.exists() else []
    for n in rows:
        r = subprocess.run([sys.executable, str(PIPE / "build_request.py"), "--row", str(n)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            log.append({"row": n, "status": "build_failed", "err": (r.stdout + r.stderr)[-300:]})
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
            print(f"#{n}: BUILD FAILED（跳过）"); continue
        m = re.search(r"written: (\S+)", r.stdout)
        req_file = Path(m.group(1))
        req = json.loads(req_file.read_text())
        if req["to"][0]["email"].lower() != lst[n]["email"].lower():
            log.append({"row": n, "status": "recipient_mismatch"})
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
            print(f"#{n}: 收件人不一致（跳过）"); continue
        req["to"][0]["name"] = clean_name(lst[n]["author"])
        req_file.write_text(json.dumps(req, ensure_ascii=False, indent=2))

        s = subprocess.run([BOOT, "--request-file", str(req_file), "--send"],
                           capture_output=True, text=True, cwd=str(PIPE))
        if s.returncode != 0:
            log.append({"row": n, "status": "send_failed", "rc": s.returncode,
                        "raw": (s.stdout + s.stderr)[-300:]})
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
            print(f"#{n}: SEND FAILED rc={s.returncode}"); continue
        try:
            out = json.loads(s.stdout[s.stdout.find("{"):])
            mid = out["send_result"]["response"]["messageId"]
        except Exception:
            log.append({"row": n, "status": "sent_unconfirmed", "raw": s.stdout[-300:]})
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))
            print(f"#{n}: 已发出但输出解析失败 —— 切勿重试，去 Brevo 后台核对"); continue

        log.append({"row": n, "status": "sent", "to": lst[n]["email"],
                    "media": lst[n]["media"], "messageId": mid})
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=1))

        phys = n + 1
        c.update_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!I{phys}:I{phys}", [[f"发（{today} 已发送）"]], as_user=True)
        c.update_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!K{phys}:K{phys}", [[f"{today} {mid}"]], as_user=True)
        c.update_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!L{phys}:L{phys}", [["已发送"]], as_user=True)
        c.update_sheet_values(SHEET_TOKEN, f"{LIST_SHEET}!L{phys}:L{phys}", [["已发送"]], as_user=True)
        back = flat(c.get_sheet_values(SHEET_TOKEN, f"{DRAFT_SHEET}!K{phys}:K{phys}", as_user=True)["valueRange"]["values"][0][0])
        ok = back.startswith(today)
        print(f"#{n}: SENT {lst[n]['media']} -> {lst[n]['email']} | {mid} | 回写读回:{ok}")
        time.sleep(2)

    sent = sum(1 for x in log if x.get("status") == "sent")
    print(f"\n本批完成: {sent} 发送成功；日志 {log_path}")


if __name__ == "__main__":
    main()

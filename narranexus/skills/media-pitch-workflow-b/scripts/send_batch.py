#!/usr/bin/env python3
"""正式批量发送：逐行 build → 收件人核对 → 发送 → 记录 messageId。

用法: python3 send_batch.py --rows 1,2,3 [--dry]
前置: 质量门槛通过、表格 G 列为最终文本。每封发送前与 /tmp/send_prep.json
里的邮箱二次核对，不一致立即中止该行。结果写 /tmp/send_log.json。
"""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

PIPE = Path(__file__).parent
BOOTSTRAP = str(Path.home() / ".claude/skills/brevo/scripts/bootstrap_runtime.sh")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True, help="逗号分隔行号")
    ap.add_argument("--dry", action="store_true", help="只 build+核对，不发送")
    args = ap.parse_args()
    rows = [int(x) for x in args.rows.split(",") if x.strip()]

    prep = {p["row"]: p for p in json.load(open("/tmp/send_prep.json"))}
    log = []
    for n in rows:
        expect = prep[n]
        # 1) 从表格现取最新文本构建 request
        r = subprocess.run(
            [sys.executable, str(PIPE / "build_request.py"), "--row", str(n)],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            log.append({"row": n, "status": "build_failed", "err": r.stderr[-300:]})
            print(f"row {n}: BUILD FAILED"); continue
        m = re.search(r"written: (\S+)", r.stdout)
        req_file = m.group(1)
        req = json.loads(Path(req_file).read_text())
        # 2) 收件人二次核对
        if req["to"][0]["email"].lower() != expect["to_email"].lower():
            log.append({"row": n, "status": "recipient_mismatch",
                        "built": req["to"][0]["email"], "expected": expect["to_email"]})
            print(f"row {n}: RECIPIENT MISMATCH — 跳过"); continue
        if args.dry:
            log.append({"row": n, "status": "dry_ok", "to": expect["to_email"]})
            print(f"row {n}: dry ok -> {expect['to_email']}"); continue
        # 3) 正式发送（无 --test-to）
        s = subprocess.run([BOOTSTRAP, "--request-file", req_file, "--send"],
                           capture_output=True, text=True, cwd=str(PIPE))
        try:
            out = json.loads(s.stdout)
            mid = out["send_result"]["response"]["messageId"]
            log.append({"row": n, "status": "sent", "to": expect["to_email"],
                        "media": expect["media"], "messageId": mid,
                        "output_dir": out.get("output_dir")})
            print(f"row {n}: SENT {expect['media']} -> {expect['to_email']} {mid}")
        except Exception:
            log.append({"row": n, "status": "send_failed",
                        "raw": (s.stdout + s.stderr)[-400:]})
            print(f"row {n}: SEND FAILED")
        time.sleep(1.5)

    Path("/tmp/send_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
    sent = sum(1 for x in log if x["status"] == "sent")
    print(f"\n完成: {sent} 发送成功 / {len(rows)} 目标；日志 /tmp/send_log.json")


if __name__ == "__main__":
    main()

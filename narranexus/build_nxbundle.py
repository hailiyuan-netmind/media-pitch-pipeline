#!/usr/bin/env python3
"""生成可导入 NarraNexus 的媒体投递双工作流团队 bundle。

格式复用已验证的敦煌 OCR 团队构建器（对照 NarraNexus
src/xyz_agent_context/bundle/{builder,importer}.py 逆向，integrity hash 与官方
fixture 完全一致）。产出 bundles/media-pitch-team.nxbundle，在 NarraNexus
设置 → Import 上传即建团队 + 2 agent + 2 技能。

教训内置：agent_description 严格 ≤255 字（超长会触发 UI 删改不了的 Pydantic 坑），
详细章程放在技能 references/ 与 team intro_md 里。
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS_SRC = HERE / "skills"
OUT = HERE / "bundles" / "media-pitch-team.nxbundle"

BUNDLE_FORMAT_VERSION = "1.1"
OWNER = "<original_owner>"
TS = "2026-07-13T00:00:00+00:00"

TEAM_ID = "team_mp2026a00001"
TEAM_NAME = "媒体投递流水线团队 · Media Pitch Team"

MODULES = ["BasicInfoModule", "ChatModule", "MessageBusModule",
           "SocialNetworkModule", "AwarenessModule", "CommonToolsModule"]
MODULE_PREFIX = {"BasicInfoModule": "basic", "ChatModule": "chat",
                 "MessageBusModule": "bus", "SocialNetworkModule": "social",
                 "AwarenessModule": "aware", "CommonToolsModule": "common"}

AGENTS = [
    {
        "agent_id": "agent_mp2026a0a001",
        "agent_name": "媒体名单官 · List & Verify",
        "skill": "media-pitch-workflow-a",
        "agent_description": (
            "媒体投递团队·工作流A（供给线：名单与核实）。职责：按主题找媒体、五关筛选"
            "（活跃度/作者/邮箱溯源/拒稿声明/可引用作品），核实后写入 Lark 名单表并置状态"
            "「已核实」。开工必读技能 media-pitch-workflow-a 的 SKILL.md 与其 references 章程。"
            "批次完成后总线通知「写稿发送官」并汇报统计。只管名单与核实，不写稿不发送。"
        ),
    },
    {
        "agent_id": "agent_mp2026a0b002",
        "agent_name": "写稿发送官 · Draft & Send",
        "skill": "media-pitch-workflow-b",
        "agent_description": (
            "媒体投递团队·工作流B（消费线：写稿与发送）。职责：领取名单表「已核实」行，"
            "真读引用作品后写夸赞开头，按模板拼装，test 发 owner；仅在人类明确放行后"
            "限速正式发送并回写 messageId 与状态。绝不擅自正式发送。开工必读技能 "
            "media-pitch-workflow-b 的 SKILL.md 与其 references 章程。不找媒体不改名单。"
        ),
    },
]

INTRO_MD = """# 媒体投递流水线团队（双工作流）

把一篇内容（博客/研究/产品）投递给几十家媒体 newsletter。按生产者-消费者拆两条线，
**Lark 表格是中间队列，也是唯一事实源**：

- **媒体名单官（工作流 A，供给线）**：找媒体 → 五关筛选 → 邮箱溯源 → 引用核实 →
  入表置状态「已核实」。它的吞吐决定团队每天能发多少，质量决定上限。
- **写稿发送官（工作流 B，消费线）**：领取「已核实」行 → 写夸赞开头（真读对方文章）→
  模板拼装 → 发送日刷新到对方最新文章 → test 发 owner → **人类放行后**限速发送 → 回写记录。

状态机（名单表 L 列）：`候选 → 已核实(A) → 已成稿(B) → 已发送(B) / 剔除(A)`，只推进不跳步。

## 怎么启动

1. 对「媒体名单官」说：主题 + 目标读者 + 要挖多少家（例：给 XX 博客找 50 家 AI newsletter）。
2. 它核实入表后会自动总线通知「写稿发送官」；也可以直接对后者说「领取已核实的行开始成稿」。
3. 写稿发送官 test 发 owner 邮箱 → 你看过后在对话里明确说「放行」→ 它限速正式发送并回写。
   **不说放行它绝不会真发**，这是硬性安全设计。

## 导入后必做

- 设置 → Providers 配好 agent / helper_llm / embedding 槽位（bundle 不含任何 Key）。
- 运行机器需要环境变量：`LARK_CONFIG`、`LARK_TOKEN_CACHE`（Lark 凭证）、`BREVO_API_KEY`。
- 发送依赖本机 `~/.claude/skills/brevo/`（bootstrap 脚本），发件人须是 Brevo 已验证 sender。
- **建议桌面版/本地模式运行**：agent 需要读本机凭证与脚本路径，云模式工作区隔离会受限。

## 安全边界（导入即生效）

正式发送必须人类在对话中明确放行；每日发送上限约 40 封保护发件域名；开头引用的文章
必须 agent 真实读过；媒体明确拒收 pitch 的进已剔除。完整章程与命令在各 agent 技能的
references/ 里，GitHub 源仓库：hailiyuan-netmind/media-pitch-pipeline。
"""

README = """# 媒体投递流水线团队 (NarraNexus bundle)

2 个 Agent 双工作流：媒体名单官（找媒体+核实，供给线）→ 写稿发送官（成稿+发送，消费线），
Lark 表格为中间队列。正式发送必须人类放行。

导入：NarraNexus 设置 → Import 上传本 .nxbundle，然后配 Providers 三个槽位。
运行环境需 LARK_CONFIG / LARK_TOKEN_CACHE / BREVO_API_KEY 与本机 brevo skill。

技能（Claude-Code 格式，随 Agent 导入）：
- media-pitch-workflow-a  找媒体五关筛选、fetch_latest / import_outlets 脚本、名单章程
- media-pitch-workflow-b  写稿风格规则、assemble / refresh / build / send_batch 脚本、发送章程

源码与最新章程：github.com/hailiyuan-netmind/media-pitch-pipeline（私有）。
本 bundle 不含 API Key。
"""


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


def _short(agent_id: str, module: str) -> str:
    return MODULE_PREFIX[module] + "_" + hashlib.sha256(
        (agent_id + module).encode()).hexdigest()[:8]


def _module_instance(agent_id: str, module: str) -> dict:
    return {
        "instance_id": _short(agent_id, module),
        "module_class": module,
        "agent_id": agent_id,
        "user_id": OWNER,
        "is_public": 1 if module in ("BasicInfoModule", "MessageBusModule",
                                     "SocialNetworkModule", "AwarenessModule") else 0,
        "status": "active",
        "description": "",
        "dependencies": None,
        "config": "{}",
        "state": None,
        "routing_embedding": None,
        "keywords": None,
        "topic_hint": None,
        "last_used_at": None,
        "completed_at": None,
        "archived_at": None,
        "last_polled_status": None,
        "callback_processed": 0,
        "created_at": TS,
        "updated_at": TS,
    }


def _zip_skill(skill_dir: Path, dst_zip: Path) -> None:
    with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(skill_dir.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=str(p.relative_to(skill_dir)))


def _tar_workspace(skill_dir: Path, dst_tar: Path) -> None:
    with tarfile.open(dst_tar, "w:gz") as tf:
        tf.add(skill_dir, arcname=f"skills/{skill_dir.name}")


def _write_json(p: Path, obj) -> None:
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def build() -> Path:
    for a in AGENTS:
        n = len(a["agent_description"])
        assert n <= 255, f"{a['agent_name']} persona {n} 字 > 255（UI 删改坑），必须精简"

    tmp = Path(tempfile.mkdtemp(prefix="mp-bundle-"))
    try:
        (tmp / "agents").mkdir()
        (tmp / "skills").mkdir()

        agents_summary, skills_summary, registry = [], [], []

        for a in AGENTS:
            aid = a["agent_id"]
            adir = tmp / "agents" / aid
            adir.mkdir()
            (adir / "instances").mkdir()

            _write_json(adir / "agent.json", {
                "agent_id": aid,
                "agent_name": a["agent_name"],
                "created_by": OWNER,
                "agent_description": a["agent_description"],
                "agent_type": "chat",
                "is_public": 0,
                "agent_metadata": None,
                "agent_create_time": TS,
                "agent_update_time": TS,
            })

            n_inst = 0
            for module in MODULES:
                mdir = adir / "instances" / module
                mdir.mkdir(parents=True)
                inst = _module_instance(aid, module)
                _write_json(mdir / f"{inst['instance_id']}.json", inst)
                n_inst += 1

            for fn in ("rag.json", "jobs.json", "artifacts.json",
                       "module_report_memory.json", "instance_module_report_memory.json",
                       "instance_json_format_memory.json",
                       "instance_json_format_memory_chat.json",
                       "instance_narrative_links.json", "social_entities.json",
                       "awareness.json"):
                _write_json(adir / fn, [])
            (adir / "agent_messages.jsonl").write_text("", encoding="utf-8")

            skill_dir = SKILLS_SRC / a["skill"]
            if not skill_dir.exists():
                raise SystemExit(f"skill not found: {skill_dir}")
            _tar_workspace(skill_dir, adir / "workspace.tar.gz")
            skdir = tmp / "skills" / aid
            skdir.mkdir()
            zip_path = skdir / f"{a['skill']}-full.zip"
            _zip_skill(skill_dir, zip_path)

            skills_summary.append({
                "agent_id": aid, "name": a["skill"], "skill_dir": a["skill"],
                "install_method": "full_copy", "contains_secrets": False,
                "archive_ref": f"skills/{aid}/{a['skill']}-full.zip",
                "sha256": _sha256_file(zip_path),
            })
            agents_summary.append({
                "agent_id": aid, "agent_name": a["agent_name"], "narratives": 0,
                "instances": n_inst, "social_entities": 0, "rag_rows": 0,
                "artifacts": 0,
                "workspace_size_bytes": (adir / "workspace.tar.gz").stat().st_size,
                "workspace_path": "workspace.tar.gz",
            })
            registry.append({
                "agent_id": aid, "owner_user_id": OWNER, "capabilities": "[]",
                "description": f"{a['agent_name']}: {a['agent_description'][:120]}",
                "capability_embedding": None, "visibility": "private",
                "registered_at": TS, "last_seen_at": TS,
            })

        _write_json(tmp / "bus.json", {"channels": [], "members": [],
                                       "messages": [], "registry": registry})
        _write_json(tmp / "inbox.json", [])
        _write_json(tmp / "mcp_hints.json", [])
        (tmp / "README.md").write_text(README, encoding="utf-8")

        manifest = {
            "bundle_format_version": BUNDLE_FORMAT_VERSION,
            "narranexus_version_exported": "1.3.4",
            "exported_at": TS,
            "owner_placeholder": OWNER,
            "team": {"team_id": TEAM_ID, "name": TEAM_NAME,
                     "description": "双工作流媒体投递团队：名单核实（供给）→ 写稿发送（消费），Lark 表格为队列，正式发送人类放行。",
                     "color": "#0E7490", "source": "bundle", "intro_md": INTRO_MD},
            "agents": [a["agent_id"] for a in AGENTS],
            "agents_summary": agents_summary,
            "skills": skills_summary,
            "mcp_hints_count": 0,
            "artifacts_count": 0,
            "stripped": ["api_keys", "lark_oauth", "user_password_hash", "user_providers"],
            "warnings": [],
            "info": [],
            "info_counters": {"skipped_external_edge": 0},
            "embedding": {"provider": None, "model": None, "dim": None},
        }

        paths = sorted(p for p in tmp.rglob("*") if p.is_file() and p.name != "manifest.json")
        buf = io.BytesIO()
        for p in paths:
            buf.write(str(p.relative_to(tmp)).encode("utf-8"))
            buf.write(b":")
            buf.write(_sha256_file(p).encode("utf-8"))
            buf.write(b"\n")
        manifest["integrity_sha256"] = _sha256_bytes(buf.getvalue())
        _write_json(tmp / "manifest.json", manifest)

        OUT.parent.mkdir(parents=True, exist_ok=True)
        if OUT.exists():
            OUT.unlink()
        with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(tmp.rglob("*")):
                if p.is_file():
                    zf.write(p, arcname=str(p.relative_to(tmp)))
        return OUT
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    for a in AGENTS:
        print(f"persona {a['agent_name']}: {len(a['agent_description'])} 字 (≤255)")
    out = build()
    print(f"wrote {out}  ({out.stat().st_size} bytes)")

---
name: media-pitch-workflow-a
description: 媒体投递团队工作流A（供给线）：按主题找媒体、五关筛选、邮箱溯源、引用核实，写入 Lark 名单表并置状态「已核实」。当被要求找媒体、建名单、核实媒体、补充候选池时使用。Trigger phrases - 找媒体, 建名单, 核实媒体, 补充池子, discover media, build media list.
---

# 工作流 A：媒体名单与核实

**你的完整章程在 [references/A-list-and-verify.md](references/A-list-and-verify.md)，开工前必读。**
本文件只是索引。

## 快速索引

- 找媒体方法与五关筛选标准：[references/discover_media.md](references/discover_media.md)
  （活跃度 / 作者身份 / 邮箱溯源 / 拒稿声明 / 可引用作品，缺一不入池）
- 活跃度批量检查：`python3 scripts/fetch_latest.py --json outlets.json`
- 入表（自动分流 可发送/无邮箱/已剔除 三个 tab、自动续行号）：
  `python3 scripts/import_outlets.py --json merged.json --sheet-token <TOKEN>`
- 交接：名单表 L 列状态置「已核实」，总线消息通知「写稿发送官」，向人类汇报三类统计

## 环境要求

`LARK_CONFIG` / `LARK_TOKEN_CACHE` 环境变量可见（Lark 凭证），Python3 + requests。
Lark 客户端在 scripts/lib/ 已内置。

## 铁律

契合度优先于数量；每个事实可溯源；尊重拒稿声明；池子挖尽如实报告，不灌长尾。
你不写稿、不发送、不审稿。

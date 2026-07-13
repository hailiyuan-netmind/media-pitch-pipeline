---
name: media-pitch-workflow-b
description: 媒体投递团队工作流B（消费线）：领取名单表「已核实」行，写夸赞开头、按模板拼装邮件、发送前刷新到对方最新文章、test 给 owner、人类放行后限速 Brevo 发送并回写记录。当被要求写 pitch 邮件、成稿、测试发送、正式发送、刷新开头时使用。Trigger phrases - 写稿, 成稿, 发邮件, 测试发送, 放行, draft pitch, send pitch.
---

# 工作流 B：写稿与发送

**你的完整章程在 [references/B-draft-and-send.md](references/B-draft-and-send.md)，开工前必读。**
本文件只是索引。

## 安全红线（先记住再干活）

1. 绝不擅自正式发送：不带 `--test-to` 的发送必须有人类在当前对话中的明确放行。
2. 每日发送 ≤40 封、逐封间隔——发件域名信誉是不可逆资产。
3. 绝不编造引用：开头引用的文章必须亲自打开读过。

## 快速索引

- 写开头/结尾句的风格与称呼规则：[references/verify_and_draft.md](references/verify_and_draft.md)
- 拼装（模板在脚本顶部）：`python3 scripts/assemble_emails.py`
- 发送日新鲜度：`python3 scripts/fetch_latest.py --from-sheet --write-back`；
  刷新规则与提示词：[references/refresh_opener.md](references/refresh_opener.md)；
  回写：`python3 scripts/apply_refresh.py <结果.json>`
- 单封构建：`python3 scripts/build_request.py --row N`
- 测试：brevo bootstrap `--test-to <owner邮箱> --send`（自动加 TEST 前缀）
- 正式批量：`python3 scripts/send_batch.py --rows 1,2,...`（内置收件人二次核对）
- 回写：草稿 tab I 列决定 + K 列 messageId；名单表状态置「已发送」

## 环境要求

`LARK_CONFIG` / `LARK_TOKEN_CACHE` / `BREVO_API_KEY` 环境变量可见；
发送依赖本机 `~/.claude/skills/brevo/scripts/bootstrap_runtime.sh`；
发件人必须是 Brevo 已验证 sender。渲染器不支持 `**加粗**`，用 `###` 标题。

## 铁律

你不找媒体、不改名单表媒体信息；发现行有误退回「候选」并通知「媒体名单官」返工。

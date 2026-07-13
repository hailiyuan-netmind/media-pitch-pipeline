# media-pitch-pipeline 媒体投递流水线

把一篇内容（博客/研究/产品）投递给几十家媒体或 newsletter 的半自动流水线：
**找媒体 → 抓邮箱 → 逐家核实并写夸赞开头 → 拼装邮件 → 发送前刷新到对方最新文章 → Brevo 逐封发送 → 回写发送记录**。

> **AI agent 请先读 [AGENTS.md](AGENTS.md)**：那是给你的作业手册，含每阶段确切命令、判断规则、
> 安全红线（正式发送必须人类放行）与故障速查。团队按**双工作流**运转：
> 供给线 [workflows/A-list-and-verify.md](workflows/A-list-and-verify.md)（名单与核实）+
> 消费线 [workflows/B-draft-and-send.md](workflows/B-draft-and-send.md)（写稿与发送），
> 每个 agent 先读自己那份章程。NarraNexus 团队包见 `narranexus/`。人类读本 README 即可。

核心设计：
- **Lark 在线表格是唯一事实源**。名单、每封邮件全文、审稿决定、发送记录都在表里，同事直接在表上协作。
- **夸赞开头引用对方"发送当天"最近的真实文章**。刷新是独立可重跑的环节，成稿日和发送日解耦。
- **AI 写作 + 脚本执行分工**：读网站、核实引用、写开头这类判断性工作由 Claude agent 做（`prompts/` 有现成提示词模板）；抓 RSS、拼装、发送、回写这类确定性工作由脚本做。
- **每封发送前收件人二次核对**，发送后 messageId 逐封留档。

## 首轮战绩（Agent Eden 恋综 campaign，2026-07）

41 家候选 → 40 家 AI 逐家核实通过 → 38 家正式发送成功（3 家停更/异常，人工拍板不发），
发送成功率 38/38，全程每封有 messageId 可查。

## 快速开始

前置条件：
1. Python 3.9+，`pip install requests`（唯一第三方依赖）
2. Lark 凭证：`LARK_CONFIG` / `LARK_TOKEN_CACHE` 环境变量指向 app 配置与 token 缓存
   （本团队在 `~/.config/haili-auto-mkt/`，已入 `~/.zshenv`；lark_client 已内置在 `lib/`）
3. Brevo 发送依赖本机的 brevo skill（`~/.claude/skills/brevo/`），`BREVO_API_KEY` 在 shell 环境
4. 发件人必须是 Brevo 已验证 sender（本团队用 `marketing@netmind.ai`）

## 流水线阶段与用法

| 阶段 | 工具/做法 | 命令 |
|---|---|---|
| 1+2. 找媒体+抓邮箱 | agent 自主完成：多角度并行搜索、五关筛选（活跃度/作者/邮箱溯源/拒稿声明/可引用作品）、分流三类 | `prompts/discover_media.md` + `python3 import_outlets.py --json merged.json --sheet-token <T>` |
| 3. 核实+成稿 | 按批派 agent 核实引用作品、写开头和定制结尾句 → 拼装写入草稿 tab | `prompts/verify_and_draft.md` + `python3 assemble_emails.py` |
| 4. 新鲜度采集 | RSS 抓每家最新 3 篇写回表格 J 列 | `python3 fetch_latest.py --from-sheet --write-back` |
| 5. 发送前刷新 | 过时开头由 agent 读最新文章重写，脚本只换开头段写回 | `prompts/refresh_opener.md` + `python3 apply_refresh.py <结果.json>` |
| 6. 审稿 | 同事在草稿 tab 填「决定(发/不发)」列 | 表格内 |
| 7. 测试与发送 | 单封构建→test 发自己→确认→批量正式发→回写记录 | `python3 build_request.py --row N`；`python3 send_batch.py --rows 1,2,...` |

## 脚本清单

| 脚本 | 职责 |
|---|---|
| `fetch_latest.py` | 零依赖 RSS/Atom 抓取（首轮覆盖 32/41；beehiiv 自定义域名多数反爬，走 agent 兜底） |
| `assemble_emails.py` | 两版正文模板（AI 类 / 情感生活类）+ 拼装 + 建 tab 写入。换 campaign 改顶部 BODY_AI / BODY_LIFESTYLE |
| `apply_refresh.py` | 刷新结果写回：只换开头段，保留问候与正文；H 列自动追加刷新记录，不覆盖同事手改 |
| `build_request.py` | 表格行 → Brevo request JSON：markdown 转换 + 固定正文超链接（LINKS 统一维护）+ 收件人取自名单表 |
| `send_batch.py` | 批量正式发送：逐封 build → 收件人与名单二次核对 → 发送 → messageId 留档 `/tmp/send_log.json` |
| `import_outlets.py` | 把 discover_media 产出的 JSON 写入名单表：按类别分流三个 tab、自动建 tab、自动续行号 |
| `lib/lark_client.py` | Lark API 客户端（tenant/user token 自动管理），仓库自带开箱可用 |
| `prompts/` | 三个 agent 提示词模板：自主找媒体、首轮核实+成稿、发送前开头刷新 |

## 数据源（本轮 campaign）

- 在线表 token：内部保存在 `campaign.json`（gitignored，参考 `campaign.example.json`）
  - tab `0jcVvH` 可发送名单（媒体/作者/邮箱/领域/引用作品/URL）
  - tab `46PiH6` 最终邮件草稿（A-I 基础列 + J RSS 最新文章 + K 发送记录 messageId）
  - 由 wiki 上传的 xlsx 经 `drive/v1/import_tasks` 转成在线表（上传文件的 token 调 sheets API 一律 400，转换才能读写单元格）
- 正文文案 docx：sg 租户 wiki，须 user token。注意 **`raw_content` 接口会剥掉超链接**，
  取链接必须走 `get_doc_blocks`；docx 里如果出现 `sendibt3.com` 开头的链接，是旧邮件的
  Brevo 跟踪地址，真实目标藏在页面 JS 里，要解包还原后再用

## 换下一个 campaign 要改什么

1. `assemble_emails.py`：BODY_AI / BODY_LIFESTYLE 两个正文模板
2. `build_request.py`：SENDER / SUBJECT / LINKS 三个常量
3. `fetch_latest.py`、`apply_refresh.py`、`build_request.py`、`assemble_emails.py`：SHEET_TOKEN 与 tab id
4. `prompts/` 两个模板里的 {CAMPAIGN_TOPIC} 等占位
5. 名单表按同样列结构新建即可

## 经验记录（首轮踩坑）

1. 发件人/落款几经反复，最终：From 显示名 NetMind.AI，落款 Shenghui Tao / Content Writer。
   教训：发件人身份要在成稿前定，不要发送日现改
2. 引用作品必须逐家真实核实：首轮发现多处署名张冠李戴（文章作者不是 newsletter 主理人）、
   引用细节与原文不符，全靠 agent 逐家读网站修掉
3. 三家表面正常实际停更/异常的媒体（Not A Bot 域名解析指向 localhost、Supervised 转
   兴趣性质、The AiEdge 9 个月未更），发前要看 RSS 最后更新日期
4. brevo skill 渲染器支持 `###` 标题 / 列表 / `[链接]` / 行尾双空格换行，不支持 `**加粗**`
5. `brevo-requests/`（含记者邮箱）与 `brevo-output/`（渲染产物）已 gitignore，
   均可从表格随时重建，不入库

# AGENTS.md — 给 AI agent 的作业手册

你是执行这条媒体投递流水线的 agent。本文件是你的运行手册：每个阶段的确切命令、
判断规则、故障处理。人类只在两个关口出现：**审稿**和**放行正式发送**，其余阶段
你应当自主完成。

## 先确认你是哪条线（双工作流架构）

团队按生产者-消费者拆成两条线，Lark 表格是中间队列。**先读你自己的章程**：

- **工作流 A：媒体名单与核实**（供给线）→ [workflows/A-list-and-verify.md](workflows/A-list-and-verify.md)
  找媒体、五关筛选、邮箱溯源、引用核实、入表置状态「已核实」。不写稿不发送。
- **工作流 B：写稿与发送**（消费线）→ [workflows/B-draft-and-send.md](workflows/B-draft-and-send.md)
  领取「已核实」行、写开头、拼装、刷新、test、人类放行后限速发送、回写记录。不找媒体。

状态机（名单表 L 列）：`候选 → 已核实(A) → 已成稿(B) → 已发送(B) / 剔除(A)`，只推进不跳步。
本文件其余部分是两条线共用的基础知识（环境、命令细节、故障速查）。

## 硬性安全规则（违反即事故）

1. **绝不擅自正式发送**。`send_batch.py` 和任何不带 `--test-to` 的 `--send` 只能在
   当前对话中拿到人类明确指令后执行。流程永远是：test 发给 owner → 人确认 → 放行。
1a. **写后必须读回验证**。任何写表操作（新行、状态列、回写）完成后，必须读回目标
   单元格并在汇报中附读回证据（内容长度或前 50 字）；无读回证据不得报告完成。
   虚报完成是最严重的违规（2026-07-13 演习实录：B 线报告已回写但表格为空）。
2. **绝不编造引用**。夸赞开头引用的文章必须是你亲自打开读过的；核实不了就换一篇
   或如实标记，不许硬写。
3. **尊重拒稿声明**。媒体明确写了不收 pitch 的，进「已剔除」，无例外。
4. 记者邮箱是 PII：只写入 Lark 表格，不写入 git 仓库（brevo-requests/ 已 gitignore）。
5. 收发件配置改动（发件人、落款、主题）必须请人拍板，不自行决定。

## 运行环境

- Lark 凭证：环境变量 `LARK_CONFIG` / `LARK_TOKEN_CACHE`（本团队指向 ~/.config/haili-auto-mkt/）。
  `lib/lark_client.py` 已内置，`as_user=True` 需要 token 缓存里有 user refresh token。
- Brevo：`BREVO_API_KEY` 在 shell 环境；发送走 `~/.claude/skills/brevo/scripts/bootstrap_runtime.sh`。
  发件人必须是 Brevo 已验证 sender（本团队 marketing@netmind.ai）。
- Python 3.9+，第三方依赖仅 `requests`。

## 阶段 0：新 campaign 初始化

1. 建名单表：新建 Lark 在线表格（或复制上一轮的），记下 token。
   注意：wiki 里"上传的 xlsx"不是在线表格，sheets API 一律 400；
   用 `POST /drive/v1/import_tasks` (file_extension=xlsx, type=sheet) 秒级转换。
2. 改常量（共 5 处，README「换下一个 campaign」小节有清单）：
   `assemble_emails.py` 的 BODY_AI/BODY_LIFESTYLE；`build_request.py` 的
   SENDER/SUBJECT/LINKS；四个脚本的 SHEET_TOKEN 和 tab id；prompts/ 占位符。
3. 正文文案若在 Lark docx：**`raw_content` 会剥掉超链接**，链接必须用
   `get_doc_blocks` 从 text_element_style.link 提取。看到 `sendibt3.com` 链接
   说明是旧邮件的 Brevo 跟踪地址：HTTP 不跳转，真实地址在返回页面的
   `top.location='...'` JS 里，解包还原后使用，并逐一验活
   （Reuters 类站点对脚本返回 401 是反爬，不代表链接死了）。

## 阶段 1+2：自主找媒体 + 抓邮箱（你独立完成）

1. 用 `prompts/discover_media.md` 模板，按搜索角度并行派 5-8 个子 agent
   （关键词、目录、榜单、引用溯源、Substack 推荐链各一个角度）。
2. 每个候选必须过五关：活跃度（RSS 最后更新 <1 个月）、作者身份、邮箱带来源页、
   无拒稿声明、有一篇真实可引用的近期作品。达不到的分流到「无邮箱」或「已剔除」。
3. 跨批按域名去重，同一 newsletter 多域名只留正主。
4. 写入表格：`python3 import_outlets.py --json merged.json --sheet-token <TOKEN>`
   （自动分流三个 tab、自动建 tab、自动续行号）。

## 阶段 3：核实 + 成稿

1. 用 `prompts/verify_and_draft.md` 按批（8-9 家/agent）派子 agent：
   逐家读网站、核实引用作品、写夸赞开头 + 定制结尾句、判 AI 版/情感版。
2. 常见坑（首轮全踩过）：文章作者不是 newsletter 主理人（改夸刊物）、
   多编辑刊物称呼用 "<Media> team"、引用细节与原文不符（以原文为准重写）。
   称呼规则：个人=名字（first name），绝不允许跨行串名。
3. 拼装写入草稿 tab：`python3 assemble_emails.py`（先确认顶部模板已是本轮文案）。

## 阶段 4+5：新鲜度（发送当天必跑）

1. `python3 fetch_latest.py --from-sheet --write-back` —— RSS 抓每家最新 3 篇写回 J 列。
   beehiiv 自定义域名常反爬：拿不到的由你亲自网搜补查，不留空白。
2. 判断刷新：日更/高频刊物引用超过 ~10 天且有新内容 → 刷；周更/随笔类超过
   ~5 周才刷；跳过 housekeeping 类文章（休假声明、订阅事务）。
3. 刷新用 `prompts/refresh_opener.md`（必须真读新文章），回写：
   `python3 apply_refresh.py <结果.json>`（只换开头段，不碰正文和同事手改）。

## 阶段 6：审稿（人类关口）

同事在草稿 tab 填「决定(发/不发)」列。你可以催办、汇总待拍板项，但不能代填。
campaign owner 在对话里的明确指令（如"可以投了，某三家不发"）等同填表。

## 阶段 7：测试与发送

1. 单封构建：`python3 build_request.py --row N`（markdown 转换 + 固定链接自动挂）。
   渲染器支持 `###` 标题/列表/`[文字](url)`/行尾双空格换行，**不支持 `**加粗**`**。
2. Test：`bootstrap_runtime.sh --request-file <req.json> --test-to <owner邮箱> --send`
   （自动加 "TEST - " 前缀）。要带 CC 的 test：to/cc 写进 request JSON、
   自己加 TEST 前缀、不带 --test-to 发（--test-to 会清掉 cc）。
3. 人放行后正式发：`python3 send_batch.py --rows 1,2,5,...`
   （内置逐封收件人二次核对，先跑一遍结构自检更稳：问候行、正文首句标志、
   "Thanks for your time and for"、落款、博客链接、邮箱格式）。
4. 发完回写表格：I 列「决定」= 发/不发+日期，K 列 = messageId。
   Brevo 201 = 已受理不等于已送达；送达/打开数据看 Brevo 后台 Transactional 页。

## 故障速查

| 症状 | 原因与解法 |
|---|---|
| sheets API 400 | token 是上传文件不是在线表格 → import_tasks 转换 |
| wiki get_node 400 (tenant) | 文档在别的租户 → as_user=True 用 user token |
| docx 链接"消失" | raw_content 剥链接 → get_doc_blocks |
| Substack 抓不到 | 试 /feed、/archive、/about；再不行网搜 |
| Reuters 等 401 | 反爬，不是死链；浏览器验证 |
| test 邮件没收到 | "TEST -" 前缀易进垃圾箱；201≠送达，查 Brevo events |
| --test-to 后 CC 丢失 | 预期行为；CC 场景写进 request 手动加前缀 |

## 首轮基准（质量参照）

Agent Eden campaign（2026-07）：41 家候选全部逐家核实（修掉多处署名/引用错误），
38/38 正式发送成功，每封 messageId 留档在表格 K 列。你的产出不应低于这个标准。

# PZ Deep Research 测试说明

## 文档维护规则

这份文档用于记录项目如何测试、测试覆盖哪些内容、哪些测试还没做。

只要新增测试用例、修改测试命令、调整测试范围、增加测试工具或发现测试限制，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。changelog 新记录使用 `YYYY-MM-DD HH:mm 时区`，同一天多次修改也不要合并。

## 当前测试策略

当前项目处于 MVP 工程阶段，测试重点是先保证核心链路、模型运行时和工具层能稳定跑通：

- 后端 API 能启动。
- Agent Runtime 能完成 mock 研究任务。
- Runtime 必须固定执行“生成搜索词 -> search -> 并发 visit -> 证据卡片 -> 选源 -> 报告”，模型不能自行调度 visit。
- Agent Runtime 能记录 LLM 用量。
- Agent Runtime 能把模型流式输出转为 `llm_delta` 事件。
- Agent Runtime 能区分临时错误和永久错误；报告临时失败时从已选证据继续，不重复 search / visit。
- Runtime 在选源后生成私有报告检查点，API 只持久化、不发送给前端；报告失败后的用户重试可以直接从检查点继续。
- 原始 Provider 错误必须映射为产品错误码，API/SSE/数据库用户字段中不能出现 API Key 或原始异常。
- 真实 Provider 的最终报告必须带引用角标和 References / 参考文献章节。
- quick / deep / expert 的搜索词数量分别为 1 / 3 / 每轮 5；最终来源目标分别为 3 / 10 / 20。
- 访问漏斗只能遍历本轮有限候选：全文达到阶段目标可早停，候选耗尽必须降级退出，不能因全文不足重复访问或卡死。
- 最终来源按质量优先选出 3 / 10 / 20 个并重新连续编号；右侧来源区不能混入未入选的访问来源。
- 报告正文必须通过字数校验：quick 400-500、deep 1300-1500、expert 3000-3500，References 和引用标记不计入。
- 证据卡片抽取失败需要重试并降级为原文卡片，不能使整个研究任务失败。
- 英文生产提示词和中文对照提示词必须同时维护，并保持模式数字规格一致。
- 模型搜索词超过模式上限时，Runtime 必须裁剪到策略数量。
- 模型混合输出 search 工具调用和提前报告时，Runtime 必须优先执行 search，不能绕过证据流程。
- `llm_delta` 和 `report_delta` 只作为 SSE 实时事件，不写入历史事件存储。
- `report_delta` 同时更新任务级累计草稿，刷新或 SSE 重连后不能重复拼接报告内容。
- 排队或运行中的任务可以取消，重复取消保持幂等，已完成/失败任务不能再取消。
- 取消必须中断后台研究协程，取消后不能再写入 `completed`。
- SSE 支持持久事件游标和任务快照，刷新后只重放游标之后的事件。
- Runtime 能从未闭合但内容完整的 `<tool_call>` / `<answer>` 中恢复结构化内容。
- `visit` 工具能区分 full_text、partial_text、metadata_only / blocked 和 unavailable。
- 前端能展示工具返回正文、来源证据强度和引用 hover 卡片。
- ProviderFactory 能正确创建多模型 Provider。
- 配置层能提供默认模型，并识别真实 Provider 缺少的 API Key。
- API 能返回 `/api/readiness` 配置体检信息。
- `/api/readiness` 能返回数据库连接状态和数据库类型，不泄露连接信息。
- API 能返回供内部联调使用的 `/api/models` 模型候选列表。
- API 能在缺少 OpenAI Key 时拒绝 `/api/models/openai` 真实账号模型查询。
- search / visit 工具能处理输入清洗、来源记录和失败兜底。
- API 输入校验有效。
- 前端能通过 lint 和 build。
- 前端能渲染 Markdown 格式研究报告。
- Playwright 能在真实 Chromium 中验证任务取消、刷新续跑和完成后报告恢复。
- SQLite 存储能跨 Store 实例恢复任务、事件和报告草稿。
- 历史列表和任务详情必须按匿名访客或未来账号归属隔离。
- 服务启动时必须把遗留的 queued/running 任务标记为中断失败。
- Alembic 初始迁移必须同时支持 SQLite 执行和 PostgreSQL 离线 SQL 编译。
- 本地手动端到端流程可以跑通。

暂时不引入复杂测试体系，避免过早增加维护成本。

截至 2026-06-10，后端 pytest 共 111 个用例通过，前端 Playwright Chromium 共 7 个端到端用例通过。

## 测试优先开发原则

后续开发默认采用“先定义测试，再实现功能”的节奏。每次开始一个明确功能前，先写清楚这个功能应该如何被验证。

推荐流程：

1. 明确本次要实现的行为。
2. 先补测试用例或验收步骤。
3. 运行测试，确认新测试在未实现前会失败或至少能约束目标行为。
4. 开始实现功能。
5. 反复运行测试，直到通过。
6. 更新 `project-docs/changelog.md`，记录新增测试、实现内容和验证结果。

能自动化的优先自动化：

- 后端 API、Agent Runtime、工具层、Provider 层优先写 pytest。
- 前端复杂交互后续优先用 Playwright。
- 只有暂时无法自动化的场景，才写手动验收步骤。

例外情况：

- 纯文档修改可以不先写测试，但需要更新 changelog。
- 探索性原型可以先快速验证，但一旦确定要保留，就需要补测试。
- 第三方真实 API 联调可以做成可选集成测试，避免没有 API Key 时阻塞本地测试。

## 后端自动化测试

位置：

```text
backend/tests/
```

当前测试用例：

- `test_agent_runtime.py`
  - mock Agent Runtime 能完成研究流程。
  - Runtime 会先解析搜索词，再自行调用 `search` 和并发 `visit`。
  - Runtime 会产出 `llm_result` 用量统计事件。
  - Runtime 会产出 `llm_delta` 流式输出事件。
  - Runtime 会在最终报告生成过程中产出早于 `llm_result` 的 `report_delta`，覆盖报告真流式。
  - Runtime 只重试超时、限流、服务过载和 5xx 等临时错误，永久错误直接失败。
  - 报告临时失败会复用已选来源和证据卡片，不重新 search / visit。
  - Runtime 会生成报告重试检查点，并能在不调用 search / visit 的情况下恢复报告生成。
  - OpenAI、Claude、Gemini 的证据卡片会选择各自配置的低成本模型。
  - Runtime 会在模型调用超时时产出 `failed` 事件。
  - `MODE_POLICIES` 覆盖 quick / deep / expert 的搜索词数量、访问来源数量和报告字数目标。
  - 英文生产提示词和中文对照提示词存在，并且包含相同的固定流程和三种模式策略。
  - Runtime 能接受加粗的 `**References**` 标题，避免模型只因 Markdown 加粗而耗尽重写轮次。
  - quick 模式会在最终报告前访问有限候选并选择最多 3 个最终来源。
  - 模型返回超过策略数量的搜索词时，Runtime 会裁剪到策略上限。
  - expert 模式必须完成第二次 search，并从两轮访问并集中最终选择 20 个来源后才允许最终报告；候选不足时按降级规则处理。
  - 真实 Provider 同时输出 search 工具调用和早答时，会优先执行 search。
  - search 候选使用罗马编号，最终访问来源使用连续阿拉伯引用编号；报告不能引用未访问候选。
  - 来源按全文质量优先筛选，全文不足或总数不足时有界降级。
  - 真实 Provider 如果最终报告缺少 References / 参考文献，会被 Runtime 拦截并要求重写。
  - 报告重写使用有界的新上下文，避免多轮草稿和证据重复累积。
  - 未闭合 `<tool_call>` 和未闭合 `<answer>` 的容错解析。
- `test_api.py`
  - `/health` 健康检查正常。
  - `/api/readiness` 可以返回 Provider 和工具配置状态。
  - `/api/models` 可以返回 OpenAI 候选模型。
  - `/api/models/openai` 在缺少 OpenAI Key 时返回配置错误。
  - `/api/research-jobs` 可以创建 mock 研究任务。
  - 过短 query 会被 API 校验拒绝。
  - `run_research_job` 不会把 `llm_delta` 和 `report_delta` 写入历史事件存储。
  - 报告 delta 会累计到任务草稿，`report_reset` 会清空草稿。
  - 取消接口能取消排队/运行任务、记录单个 `cancelled` 事件，并保持重复请求幂等。
  - 已完成任务不能取消。
  - 取消接口会中断运行中的后台协程，任务不会随后变成完成。
  - SSE 可以从指定事件游标继续，并发送包含报告草稿/最终报告的任务快照。
  - 失败事件会脱敏为产品错误码和用户文案，原始错误只进入脱敏工程日志。
  - `/retry` 只接受可重试的失败任务；报告阶段有检查点时传给 Runtime 续写报告。
- `test_config.py`
  - 空模型环境变量会回退到项目默认模型。
  - 默认重试次数、退避时间和三家低成本证据模型配置正确。
  - `DATABASE_URL`、`DATABASE_MIGRATION_URL` 和连接池参数可独立读取并规范化 PostgreSQL URL。
  - `MOCK_PROVIDER_DELAY_SECONDS` 可以为浏览器测试提供可控延迟，默认值为 0，不影响正常运行。
  - 中文占位符不会被误判为真实 OpenAI API Key 或模型名。
  - 真实 Provider 缺少 API Key 和搜索 Key 时会被识别。
  - 配置齐全的真实 Provider 会通过配置检查。
- `test_provider_factory.py`
  - 默认 Provider 创建正确。
  - Mock Provider 能接收测试延迟配置。
  - OpenAI、Claude、Gemini 能读取共享默认模型。
  - Provider 专属模型优先级高于共享默认模型。
  - 未知 Provider 会被拒绝。
- `test_sql_store.py`
  - SQLite 数据库重连后任务、事件和报告草稿仍然存在。
  - 访客之间的历史记录和任务详情互相隔离。
  - 服务重启恢复会把 queued/running 任务标记为失败并写入事件。
  - 匿名历史可以在未来登录时归并到 `user_id`。
  - 重新运行任务血缘和 Alembic 版本化迁移可以持久化。
  - 产品错误元数据、报告检查点、数据库 `SELECT 1` 和第三个 Alembic 迁移可以持久化。
- `test_error_handling.py`
  - 超时、网络、Provider 鉴权、来源读取失败能映射为稳定产品错误码。
  - 用户事件和 payload 不包含原始 API Key 或 Provider 错误正文。
- `test_tools.py`
  - `search` 能解析 SerpAPI Google Scholar 返回结果。
  - `search` 返回来源会标记题录/摘要证据强度。
  - `search` 能对重复来源去重。
  - `search` 遇到上游失败时返回失败内容而不是抛异常。
  - `visit` 能读取 Jina Reader 内容并记录来源。
  - `visit` 能把可用正文标记为 `full_text`。
  - `visit` 能把 403 / CAPTCHA 页面标记为 `blocked` / `metadata_only`。
  - `visit` 会拒绝非 http/https URL。
  - 并发 visit 遵守配置上限、保持来源顺序并隔离单个 URL 错误。
  - ToolRegistry 对未知工具返回可读错误。
- `test_evidence.py`
  - 长全文使用模型抽取紧凑证据卡片，短题录可以直接透传。
  - 批量抽取保持来源顺序，失败重试后降级为原文卡片。
- `test_selection.py`
  - 全文计数、访问早停、质量优先排序、连续编号和逃生降级规则正确。
- `test_anthropic_provider.py`
  - Claude system message 分离和空 system 字段兼容正确。
- `test_pdf_export.py`
  - PDF 文件名安全，Markdown 不执行原始 HTML，安装的 Chromium 能生成有效 PDF。

运行方式：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
```

如果还没有安装后端依赖：

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
```

如果本次目标是主动升级依赖，而不是复现当前环境，可以把最后一行改为安装 `backend/requirements.txt`。

## 前端自动化检查

位置：

```text
frontend/
```

前端使用 Next.js lint/build 做静态检查，并使用 Playwright 做核心浏览器端到端测试：

```bash
cd frontend
nvm use
npm run lint
npm run build
npm run test:e2e
```

这些检查覆盖：

- TypeScript 类型问题。
- React/Next.js 基础规范问题。
- 生产构建是否能成功。
- 页面是否能被 Next.js 正常编译。
- 运行中任务可以从页面取消。
- 页面刷新后可以通过任务 ID、事件游标和 SSE 快照恢复运行任务。
- 任务完成后再次刷新仍能恢复最终报告。
- 完成任务会出现在当前匿名访客的历史记录中，点击后可以恢复报告。
- 历史详情可以下载 UTF-8 Markdown 和后端 Chromium 生成的正式 PDF。

当前 6 个 E2E 用例分别覆盖：

1. 取消运行中的任务。
2. 刷新后恢复运行任务并恢复完成报告。
3. 历史记录和报告详情。
4. 从报告详情重新运行并创建独立任务。
5. Markdown 下载。
6. 正式 PDF 下载。

Playwright 配置位于：

```text
frontend/playwright.config.ts
frontend/e2e/research-flow.spec.ts
```

端到端测试会自动在 `127.0.0.1:8000` 和 `127.0.0.1:3000` 启动 Mock 测试服务，不使用其他端口。运行前应先关闭占用这两个端口的开发服务。

浏览器由 Playwright 安装到用户缓存：

```text
~/Library/Caches/ms-playwright/
```

浏览器二进制不写入 Git 仓库，也不修改系统 `/Applications`。项目依赖仍由 `frontend/package.json` 和 `frontend/package-lock.json` 固定。

后端 PDF 导出与前端 E2E 使用相同版本的 Playwright `1.60.0` 和同一份用户缓存 Chromium。新环境需要执行：

```bash
backend/.venv/bin/playwright install chromium
```

Linux CI/生产镜像使用：

```bash
backend/.venv/bin/playwright install --with-deps chromium
```

## 本地手动端到端测试

### 1. 启动后端

```bash
cd backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

预期返回：

```json
{"status":"ok"}
```

### 2. 启动前端

```bash
cd frontend
nvm use
npm run dev
```

打开：

```text
http://localhost:3000
```

### 3. 页面测试步骤

1. 保持 Provider 为“开发模式”。
2. 输入一个研究问题。
3. 选择“快速”或“深度”。
4. 点击“开始”。
5. 观察研究进度是否出现：
   - 开始理解问题
   - 模型推理
   - 调用 search
   - 调用 visit
   - 研究报告已生成
6. 检查右侧是否出现最终报告和来源。
7. 运行中点击“停止”，确认状态变为“已取消”，停止按钮消失，之后不会再出现“研究报告已生成”。
8. 重新开始一个任务，在任务运行中刷新页面，确认任务 ID、问题、模式、时间线和报告草稿恢复，并继续接收后续事件。
9. 任务完成后再次刷新页面，确认最终报告、来源和完整时间线仍能恢复。
10. 打开“历史”，点击已完成任务，确认进入“报告详情”，并显示研究配置、完整任务 ID、研究日志、来源和报告。
11. 在报告详情点击“重新运行”，确认返回研究页、问题和配置不变、任务 ID 更新，并重新收到进度与最终报告。
12. 报告为空时确认“导出 Markdown”按钮禁用；报告生成后点击下载，确认文件名来自研究问题、扩展名为 `.md`，中文、Markdown 标题、引用和参考文献可正常读取。
13. 任务运行中确认“导出 PDF”禁用；进入已完成报告详情后下载 PDF，确认文件名、`%PDF` 文件头、`%%EOF` 文件尾和文件体积正常。

注意：已完成任务、事件和报告会持久化。后端重启时仍在 queued/running 的任务无法恢复 Runtime 执行现场，会被标记为“服务重启导致中断”；后续引入独立 Worker 后再实现真正的任务续跑。

## 内部模型质量测试计划

正式 C 端不提供 Provider 或模型切换。当前开发页面的模型选择器仅用于内部联调；下一阶段质量测试按任务职责组织，而不是穷举“每个 Provider × 每个模式”的所有组合。

四类测试任务：

1. 意图识别与追问
   - 测试是否正确识别研究目标、时间范围、地区、对象和输出要求。
   - 在信息不足时生成最少且必要的澄清问题，不应过度追问。
2. 搜索词与工具规划
   - 测试英文搜索词的命中率、去重、覆盖面和结构化输出稳定性。
   - expert 模式还要测试证据缺口识别和第二轮补充检索质量。
3. 证据卡片生成
   - 测试事实抽取准确率、证据强度判断、来源元数据、压缩率、延迟和成本。
   - 不允许把搜索摘要或受限页面误写成已阅读全文。
4. 最终报告撰写
   - 测试事实与证据一致性、引用覆盖率、无效引用率、References、字数服从度、结构和可读性。

每条样本至少记录：

- Provider、模型 ID、模型路由职责和路由版本。
- 输入、期望约束、实际输出和自动校验结果。
- 人工质量评分、延迟、token 和估算费用。
- 是否重试、是否降级以及最终失败原因。

在生产路由确定前，如果要从当前开发页面比较 OpenAI 模型：

1. 在 `.env` 里填写 `OPENAI_API_KEY`、`SERPAPI_API_KEY`，建议同时填写 `JINA_API_KEY`。
2. 重启后端服务。
3. 在内部开发界面选择 OpenAI。
4. 在模型下拉里依次选择 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano` 等候选模型。
5. 使用同一组固定样本运行，并按对应任务职责记录质量、延迟和成本，不以单次主观体验作为生产选型结论。

Claude 和 Gemini 使用同一套测试方法：

- Claude 建议依次比较 `claude-haiku-4-5-20251001`、`claude-sonnet-4-6`、`claude-opus-4-8`。
- Gemini 建议依次比较 `gemini-2.5-flash-lite`、`gemini-3.5-flash`、`gemini-3.1-pro-preview`。
- `preview` 模型可能调整或下线，生产默认模型优先选择已稳定验证的正式版本。
- 可以访问 `/api/models/anthropic` 和 `/api/models/gemini`，确认候选模型是否在当前账号可用列表中。
- 检查 `evidence_ready` 前后的模型调用时，Claude 证据卡片应使用 `claude-haiku-4-5-20251001`，Gemini 应使用 `gemini-2.5-flash-lite`；当前开发版本的最终报告仍使用内部界面选择的主模型。
- 模拟或遇到 429/503 时，时间线应出现最多 3 条 `llm_retry`，默认等待 2、4、8 秒。报告阶段的重试文案应说明已保留来源和证据，只重试报告生成；同一任务不应再次出现 search/visit 调用。

真实 Provider 页面验收还需要检查：

1. 访问由 Runtime 驱动：模型只输出 `search` 查询，进度里应出现 `visit_progress`（访问进度 n/目标）、`evidence_ready`（已抽取卡片数）和 `source_selected`（来源筛选结果）等事件；模型不应再自行发起 `visit`。
2. quick / deep 模式下应看到先 `search` 后 `visit`（Runtime 滚动并发访问）；expert 模式应看到两轮 `search`，每轮后各有 `visit`。
3. quick 模式应使用 1 个搜索词并最终选择 3 个来源；deep 用 3 个搜索词并最终选择 10 个来源；expert 每轮用 5 个搜索词、强制两轮搜索并最终选择 20 个来源。全文证据足够时提前结束访问；不足时访问完有限候选后降级，不应卡住。
4. `search` 候选和所有 `visit` 过程来源只出现在中间“工具返回”里。右侧来源区只展示 `source_selected` / `completed` 中最终入选、连续编号的来源。
5. 使用支持原生 streaming 的 Provider 时，应能看到“模型实时输出”区域持续追加文本；当前 OpenAI 已支持，Claude/Gemini 仍是兼容封装。
6. 使用支持原生 streaming 的 Provider 时，最终报告区域应在模型生成 `<answer>` 时逐步出现内容，不应只在任务完成后一次性出现。
7. `tool_result` 事件下方应可以展开“查看工具返回”，检查 search / visit 原始内容。
8. 报告正文应按 Markdown 渲染，标题、列表和表格不应以纯文本方式堆在一起。
9. 报告正文中的 `[1]`、`[2]` 应显示为可 hover 的卡片式引用角标。
10. 来源卡片应显示证据强度；访问受限来源不应被标成全文证据。全文证据是「质量优先」的早停目标而非硬门槛：全文不足时按 `full_text>相关性` 选前 N，仍不足则降级，`source_selected` 会标注 `full_text_shortfall` / `degraded`，报告应相应说明证据受限。
11. 右侧来源区应展示 APA 风格参考文献兜底列表。
12. 报告正文中的引用应全部使用阿拉伯数字 `[1]`、`[2]`，不应出现罗马编号或 `[^1]` 脚注；只能引用证据卡片中的来源。
13. 报告正文长度应分别落在 400-500、1300-1500、3000-3500 字范围，References / 参考文献与 `[n]` 引用标记不计入。

## API 手动测试

创建 mock 任务：

```bash
curl -s -X POST http://127.0.0.1:8000/api/research-jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"测试 PZ Deep Research mock 任务流","mode":"quick","provider":"mock"}'
```

复制返回的 `id`，查询事件：

```bash
curl -s http://127.0.0.1:8000/api/research-jobs/{job_id}/events
```

重试可恢复的失败任务：

```bash
curl -s -X POST http://127.0.0.1:8000/api/research-jobs/{job_id}/retry \
  -H "X-PZ-Visitor-ID: {visitor_uuid}"
```

检查数据库连接：

```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/check_database.py
```

成功时只输出 `database=ready` 和数据库类型，不输出连接 URL 或密码。

预期事件里应该包含：

```text
status
llm_start
llm_result
tool_start
tool_result
completed
```

真实 OpenAI 流式任务会通过 SSE 推送 `llm_delta` 和 `report_delta`。这两类 token 级事件不会保存在 `/events` 历史接口里，前端在线连接时分别展示在“模型实时输出”和“研究报告”区域。

取消任务：

```bash
curl -s -X POST http://127.0.0.1:8000/api/research-jobs/{job_id}/cancel
```

重新运行终态任务：

```bash
curl -s -X POST http://127.0.0.1:8000/api/research-jobs/{job_id}/rerun \
  -H "X-PZ-Visitor-ID: {visitor_uuid}"
```

返回的新任务应包含独立 `id` 和指向原任务的 `rerun_of_job_id`。其他访客访问或重跑该任务应返回 404；运行中任务应返回 409。

导出 PDF：

```bash
curl -sS http://127.0.0.1:8000/api/research-jobs/{job_id}/export/pdf \
  -H "X-PZ-Visitor-ID: {visitor_uuid}" \
  -o report.pdf
```

空报告返回 409，其他访客返回 404，Chromium 生成失败或超时返回 503。

从某个持久事件之后续接 SSE：

```bash
curl -N "http://127.0.0.1:8000/api/research-jobs/{job_id}/stream?after={event_id}"
```

续接响应会先包含 `job_snapshot`，然后只返回游标之后的持久事件。

查询项目候选模型：

```bash
curl -s http://127.0.0.1:8000/api/models
```

查询当前 OpenAI 账号实际可访问模型：

```bash
curl -s http://127.0.0.1:8000/api/models/openai
```

如果没有配置 `OPENAI_API_KEY`，第二个接口预期返回 400，并提示缺少 `OPENAI_API_KEY`。

## 当前还没有覆盖的测试

- 四类任务职责的标准样本集、评分规范和跨模型质量基准。
- 真实 OpenAI Provider 可重复自动化集成测试和 token streaming 长任务测试。
- 真实 Claude、Gemini Provider 可重复自动化集成测试和原生 streaming 测试。
- Gemini thinking token、finish reason 和完整用量记录测试。
- 真实 `/api/readiness` 带 Key 配置后的人工验收。
- 真实 `/api/models/openai` 带 Key 配置后的人工验收。
- SerpAPI Google Scholar 真实学术搜索测试。
- Jina 真实网页读取测试。
- 视觉回归测试。
- 文件上传和文件解析测试。
- 登录后的匿名历史归并、跨设备历史、额度和支付相关测试。

Markdown 导出已有 Playwright 覆盖，验证按钮状态、浏览器下载事件、安全文件名、UTF-8 中文内容、Markdown 标题和末尾换行。

## 后续测试优先级

1. 建立四类任务职责的质量测试集和评分规范，确定后台生产模型路由。
2. 为真实 Provider 增加可选集成测试，只有配置 API Key 时才运行。
3. 增加真实网络断线、失败恢复、跨进程恢复和任务级超时测试。
4. 增加真实 PostgreSQL 集成、迁移回滚和备份恢复测试。
5. 增加关键桌面/移动视口的浏览器视觉回归测试。

## 依赖升级测试要求

依赖升级前后都需要跑测试。具体依赖升级策略和兼容性记录见 `project-docs/dependency-management.md`。

最低验证要求：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
cd frontend && nvm use && npm run lint && npm run build && npm run test:e2e
```

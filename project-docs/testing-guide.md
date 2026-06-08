# PZ Deep Research 测试说明

## 文档维护规则

这份文档用于记录项目如何测试、测试覆盖哪些内容、哪些测试还没做。

只要新增测试用例、修改测试命令、调整测试范围、增加测试工具或发现测试限制，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。changelog 新记录使用 `YYYY-MM-DD HH:mm 时区`，同一天多次修改也不要合并。

## 当前测试策略

当前项目处于 MVP 工程阶段，测试重点是先保证核心链路、模型运行时和工具层能稳定跑通：

- 后端 API 能启动。
- Agent Runtime 能完成 mock 研究任务。
- 工具调用顺序正确。
- Agent Runtime 能记录 LLM 用量。
- Agent Runtime 能把模型流式输出转为 `llm_delta` 事件。
- Agent Runtime 能处理模型调用失败、重试和超时。
- 真实 Provider 的最终报告必须带引用角标和 References / 参考文献章节。
- 真实 Provider 必须按固定流程执行：先 `search`，再 `visit`，最后输出报告。
- quick / deep / expert 都必须达到各自的搜索和访问数量门槛：quick 为 1 个搜索词和 3 个访问来源，deep 为 3 个搜索词和 10 个访问来源，expert 为两次搜索、每次 5 个搜索词、总共 20 个访问来源。
- 访问漏斗只能遍历本轮有限候选：全文达到阶段目标可早停，候选耗尽必须降级退出，不能因全文不足重复访问或卡死。
- 最终来源按质量优先选出 3 / 10 / 20 个并重新连续编号；右侧来源区不能混入未入选的访问来源。
- 报告正文必须通过字数校验：quick 400-500、deep 1300-1500、expert 3000-3500，References 和引用标记不计入。
- 证据卡片抽取失败需要重试并降级为原文卡片，不能使整个研究任务失败。
- 英文生产提示词和中文对照提示词必须同时维护，并保持模式数字规格一致。
- Runtime 需要识别错误工具顺序和同轮多个工具调用，并通过 `protocol_warning` 记录纠偏。
- 真实 Provider 混合输出 `<tool_call>` 和 `<answer>` 时，证据不足阶段必须优先执行工具调用。
- `llm_delta` 和 `report_delta` 只作为 SSE 实时事件，不写入历史事件存储。
- Runtime 能从未闭合但内容完整的 `<tool_call>` / `<answer>` 中恢复结构化内容。
- `visit` 工具能区分 full_text、partial_text、metadata_only / blocked 和 unavailable。
- 前端能展示工具返回正文、来源证据强度和引用 hover 卡片。
- ProviderFactory 能正确创建多模型 Provider。
- 配置层能提供默认模型，并识别真实 Provider 缺少的 API Key。
- API 能返回 `/api/readiness` 配置体检信息。
- API 能返回 `/api/models` 模型候选列表。
- API 能在缺少 OpenAI Key 时拒绝 `/api/models/openai` 真实账号模型查询。
- search / visit 工具能处理输入清洗、来源记录和失败兜底。
- API 输入校验有效。
- 前端能通过 lint 和 build。
- 前端能渲染 Markdown 格式研究报告。
- 本地手动端到端流程可以跑通。

暂时不引入复杂测试体系，避免过早增加维护成本。

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
  - Runtime 会依次调用 `search` 和 `visit`。
  - Runtime 会产出 `llm_result` 用量统计事件。
  - Runtime 会产出 `llm_delta` 流式输出事件。
  - Runtime 会在最终报告生成过程中产出早于 `llm_result` 的 `report_delta`，覆盖报告真流式。
  - Runtime 会在模型调用失败时重试。
  - Runtime 会在模型调用超时时产出 `failed` 事件。
  - `MODE_POLICIES` 覆盖 quick / deep / expert 的搜索词数量、访问来源数量和报告字数目标。
  - 英文生产提示词和中文对照提示词存在，并且包含相同的固定流程和三种模式策略。
  - Runtime 能接受加粗的 `**References**` 标题，避免模型只因 Markdown 加粗而耗尽重写轮次。
  - 真实 Provider 如果在没有证据前直接输出报告，会被 Runtime 拦截并要求继续 search / visit。
  - quick 模式必须在最终报告前完成 3 个来源访问，不能只 search 或只访问 1 个来源后直接回答。
  - quick 模式如果模型返回超过策略数量的搜索词或 URL，Runtime 会裁剪到策略上限并记录 `protocol_warning`。
  - 真实 Provider 如果在 search 前返回 visit，会被 Runtime 纠偏，不会执行错误顺序的工具。
  - expert 模式必须完成第二次 search，并从两轮访问并集中最终选择 20 个来源后才允许最终报告；候选不足时按降级规则处理。
  - 真实 Provider 如果同一轮返回多个工具调用，Runtime 会记录 `protocol_warning`，并只执行本轮第一个工具调用。
  - 真实 Provider 同时输出工具调用和早答时，会优先执行工具调用。
  - 真实 Provider 如果最终报告缺少 References / 参考文献，会被 Runtime 拦截并要求重写。
  - 未闭合 `<tool_call>` 和未闭合 `<answer>` 的容错解析。
- `test_api.py`
  - `/health` 健康检查正常。
  - `/api/readiness` 可以返回 Provider 和工具配置状态。
  - `/api/models` 可以返回 OpenAI 候选模型。
  - `/api/models/openai` 在缺少 OpenAI Key 时返回配置错误。
  - `/api/research-jobs` 可以创建 mock 研究任务。
  - 过短 query 会被 API 校验拒绝。
  - `run_research_job` 不会把 `llm_delta` 和 `report_delta` 写入历史事件存储。
- `test_config.py`
  - 空模型环境变量会回退到项目默认模型。
  - 中文占位符不会被误判为真实 OpenAI API Key 或模型名。
  - 真实 Provider 缺少 API Key 和搜索 Key 时会被识别。
  - 配置齐全的真实 Provider 会通过配置检查。
- `test_provider_factory.py`
  - 默认 Provider 创建正确。
  - OpenAI、Claude、Gemini 能读取共享默认模型。
  - Provider 专属模型优先级高于共享默认模型。
  - 未知 Provider 会被拒绝。
- `test_tools.py`
  - `search` 能解析 SerpAPI Google Scholar 返回结果。
  - `search` 返回来源会标记题录/摘要证据强度。
  - `search` 能对重复来源去重。
  - `search` 遇到上游失败时返回失败内容而不是抛异常。
  - `visit` 能读取 Jina Reader 内容并记录来源。
  - `visit` 能把可用正文标记为 `full_text`。
  - `visit` 能把 403 / CAPTCHA 页面标记为 `blocked` / `metadata_only`。
  - `visit` 会拒绝非 http/https URL。
  - ToolRegistry 对未知工具返回可读错误。

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

当前不单独引入 Jest 或 Playwright。第一阶段先使用 Next.js 的 lint 和 build 检查：

```bash
cd frontend
nvm use
npm run lint
npm run build
```

这两项可以覆盖：

- TypeScript 类型问题。
- React/Next.js 基础规范问题。
- 生产构建是否能成功。
- 页面是否能被 Next.js 正常编译。

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

如果要测试 OpenAI 模型切换：

1. 在 `.env` 里填写 `OPENAI_API_KEY`、`SERPAPI_API_KEY`，建议同时填写 `JINA_API_KEY`。
2. 重启后端服务。
3. 页面 Provider 选择 “OpenAI”。
4. 在模型下拉里依次选择 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano` 等候选模型。
5. 每次点击“开始”，观察是否能完成研究、速度是否可接受、报告质量是否符合预期。

真实 Provider 页面验收还需要检查：

1. 访问由 Runtime 驱动：模型只输出 `search` 查询，进度里应出现 `visit_progress`（访问进度 n/目标）、`evidence_ready`（已抽取卡片数）和 `source_selected`（来源筛选结果）等事件；模型不应再自行发起 `visit`。
2. quick / deep 模式下应看到先 `search` 后 `visit`（Runtime 滚动并发访问）；expert 模式应看到两轮 `search`，每轮后各有 `visit`。
3. quick 模式应使用 1 个搜索词并最终选择 3 个来源；deep 用 3 个搜索词并最终选择 10 个来源；expert 每轮用 5 个搜索词、强制两轮搜索并最终选择 20 个来源。全文证据足够时提前结束访问；不足时访问完有限候选后降级，不应卡住。
4. `search` 候选和所有 `visit` 过程来源只出现在中间“工具返回”里。右侧来源区只展示 `source_selected` / `completed` 中最终入选、连续编号的来源。
5. 模型返回过程中应能看到“模型实时输出”区域持续追加文本。
6. 最终报告区域应在模型生成 `<answer>` 时逐步出现内容，不应只在任务完成后一次性出现。
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

- 真实 OpenAI Provider 联调测试。
- 真实 OpenAI Provider token streaming 联调测试。
- 真实 Claude Provider 联调测试。
- 真实 Gemini Provider 联调测试。
- 真实 `/api/readiness` 带 Key 配置后的人工验收。
- 真实 `/api/models/openai` 带 Key 配置后的人工验收。
- SerpAPI Google Scholar 真实学术搜索测试。
- Jina 真实网页读取测试。
- SSE 浏览器自动化测试。
- 视觉回归测试。
- 文件上传和文件解析测试。
- 登录、历史记录、额度和支付相关测试。

## 后续测试优先级

1. 为真实 Provider 增加可选集成测试，只有配置 API Key 时才运行。
2. 引入 Playwright，覆盖前端提交问题、接收进度和显示报告。
3. 增加任务取消、失败恢复和任务级超时测试。
4. 接入数据库后增加存储层测试。
5. 增加 SSE 自动化测试和浏览器视觉回归测试。

## 依赖升级测试要求

依赖升级前后都需要跑测试。具体依赖升级策略和兼容性记录见 `project-docs/dependency-management.md`。

最低验证要求：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
cd frontend && nvm use && npm run lint && npm run build
```

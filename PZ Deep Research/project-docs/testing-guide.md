# PZ Deep Research 测试说明

## 文档维护规则

这份文档用于记录项目如何测试、测试覆盖哪些内容、哪些测试还没做。

只要新增测试用例、修改测试命令、调整测试范围、增加测试工具或发现测试限制，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。

## 当前测试策略

当前项目处于 MVP 工程阶段，测试重点是先保证核心链路、模型运行时和工具层能稳定跑通：

- 后端 API 能启动。
- Agent Runtime 能完成 mock 研究任务。
- 工具调用顺序正确。
- Agent Runtime 能记录 LLM 用量。
- Agent Runtime 能处理模型调用失败、重试和超时。
- ProviderFactory 能正确创建多模型 Provider。
- 配置层能提供默认模型，并识别真实 Provider 缺少的 API Key。
- API 能返回 `/api/readiness` 配置体检信息。
- API 能返回 `/api/models` 模型候选列表。
- API 能在缺少 OpenAI Key 时拒绝 `/api/models/openai` 真实账号模型查询。
- search / visit 工具能处理输入清洗、来源记录和失败兜底。
- API 输入校验有效。
- 前端能通过 lint 和 build。
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
  - Runtime 会在模型调用失败时重试。
  - Runtime 会在模型调用超时时产出 `failed` 事件。
  - 真实 Provider 如果在没有证据前直接输出报告，会被 Runtime 拦截并要求继续 search / visit。
- `test_api.py`
  - `/health` 健康检查正常。
  - `/api/readiness` 可以返回 Provider 和工具配置状态。
  - `/api/models` 可以返回 OpenAI 候选模型。
  - `/api/models/openai` 在缺少 OpenAI Key 时返回配置错误。
  - `/api/research-jobs` 可以创建 mock 研究任务。
  - 过短 query 会被 API 校验拒绝。
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
  - `search` 能对重复来源去重。
  - `search` 遇到上游失败时返回失败内容而不是抛异常。
  - `visit` 能读取 Jina Reader 内容并记录来源。
  - `visit` 会拒绝非 http/https URL。
  - ToolRegistry 对未知工具返回可读错误。

运行方式：

```bash
cd "PZ Deep Research"
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
```

如果还没有安装后端依赖：

```bash
cd "PZ Deep Research"
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
cd "PZ Deep Research/frontend"
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
cd "PZ Deep Research/backend"
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
cd "PZ Deep Research/frontend"
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

1. 研究进度中如果模型尝试早答，应出现“继续检索证据”的事件。
2. deep / expert 模式下应至少看到 `search` 和 `visit` 工具调用。
3. `tool_result` 下方应展示来源卡片，包含 favicon、引用编号和 URL。
4. 报告正文中的 `[1]`、`[2]` 应显示为可 hover 的引用角标。
5. 右侧来源区应展示 APA 风格参考文献兜底列表。

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

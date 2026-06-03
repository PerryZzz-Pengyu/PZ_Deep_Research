# PZ Deep Research 变更日志

## 文档维护规则

这份文档用于记录 PZ Deep Research 项目的所有重要变化。只要修改了代码、架构、产品定义、项目计划、配置、依赖、接口、页面或协作规范，都需要在这里记录。

每条记录建议说明：

- 修改日期
- 修改内容
- 影响文件
- 修改原因
- 后续注意事项

## 2026-06-03

### 新增

- 阶段 2 新增 Runtime/Provider 测试：
  - `test_runtime_emits_llm_usage_event`
  - `test_runtime_retries_provider_failure_before_succeeding`
  - `test_runtime_timeout_emits_failed_event`
  - `test_provider_factory.py`
- 阶段 3 新增工具层测试：
  - `test_tools.py`
  - 覆盖 SerpAPI Google Scholar 结果解析、来源去重、搜索失败兜底、Jina Reader 读取、URL scheme 过滤和未知工具。
- 新增 `backend/app/agent/tools/utils.py`，集中处理工具层字符串列表清洗、URL 安全判断和来源去重。
- 新增 `project-docs/api-key-setup.md`，说明真实研究需要哪些 API Key、环境变量怎么填、如何检查配置是否生效。
- 新增配置层测试 `test_config.py`：
  - 覆盖默认模型回退。
  - 覆盖中文占位符不会被误判为真实 OpenAI API Key 或模型名。
  - 覆盖真实 Provider 缺少 API Key / 搜索 Key 的检查。
  - 覆盖配置齐全的真实 Provider 检查通过。
- 新增 `/api/readiness` 配置体检接口，返回 Provider、模型、缺失环境变量和工具配置状态。
- 新增 `/api/models` 模型候选列表接口，供前端 Provider / 模型下拉使用。
- 新增 `/api/models/openai` 账号可访问模型查询接口，用后端保存的 `OPENAI_API_KEY` 获取当前账号实际可见模型 ID。
- 前端研究工作台新增模型下拉框，OpenAI 可在 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano`、`gpt-5-mini`、`gpt-5-nano` 中切换测试。
- 新增 `SEARCH_PROVIDER=serpapi`、`ACADEMIC_SEARCH_ENGINE=google_scholar`、`SERPAPI_API_KEY` 搜索配置，明确当前版本聚焦学术搜索。
- 根布局 `<html>` 新增 `suppressHydrationWarning`，用于避免浏览器扩展向根节点注入属性时触发无业务影响的 hydration mismatch 报警。
- 新增 `report_delta` SSE 事件，用于把最终报告分段推送给前端显示。
- 新增 Runtime 证据门槛测试，覆盖真实 Provider 过早输出报告时必须继续 search / visit。

### 修改

- 正式确认阶段 1 已完成，并开始推进阶段 2。
- 完成阶段 2：模型无关 Agent Runtime 工程化补齐。
  - `AgentRuntime` 新增 `max_llm_retries` 和 `llm_timeout_seconds`。
  - Runtime 对模型调用使用统一超时控制。
  - Runtime 对模型调用失败支持重试，并产出 `llm_retry` 事件。
  - Runtime 对模型调用最终失败产出 `failed` 事件。
  - Runtime 在每轮模型返回后产出 `llm_result` 事件，记录模型名、输入 token、输出 token、单轮估算成本和累计用量。
  - `LLMResult` 新增 `estimated_cost_usd` 字段，为后续成本统计保留接口。
  - `Settings` 和 `.env.example` 新增 `LLM_MAX_RETRIES`、`LLM_TIMEOUT_SECONDS`。
  - API 创建 Runtime 时读取统一配置。
- 完成阶段 3：MVP 工具层补齐。
  - `SearchTool` 支持 query 清洗、空值过滤和重复 query 去重。
  - `SearchTool` 支持来源 URL 去重，并记录 `title`、`url`、`snippet`、`query`。
  - `SearchTool` 支持 HTTP transport 注入，便于不联网测试。
  - `SearchTool` 遇到上游搜索失败时返回失败内容，不直接抛异常中断研究任务。
  - `VisitTool` 支持 url 清洗、空值过滤和重复 URL 去重。
  - `VisitTool` 只允许 `http` / `https` 网页 URL。
  - `VisitTool` 支持 HTTP transport 注入，便于不联网测试。
  - `VisitTool` 遇到网页读取失败时返回失败内容，不直接抛异常中断研究任务。
- 更新 `project-plan.md`，将阶段 1、阶段 2、阶段 3 标记为已完成，并说明阶段 4 待开始。
- 更新 `technical-architecture.md`，补充 Runtime 超时/重试/用量事件，以及工具层输入清洗、来源去重、失败兜底和测试注入策略。
- 更新 `testing-guide.md`，补充当前 17 个后端测试用例的覆盖范围和后续测试优先级。
- 更新 `README.md`，把“第一阶段可以保持 mock Provider”的表述改为“开发模式可以保持 mock Provider”。
- 完成真实可用性检查后的配置完善：
  - 后端现在会自动读取项目根目录 `.env` 和 `backend/.env`。
  - OpenAI Provider 从 Chat Completions 调整为 Responses API，更适合当前 OpenAI 新模型。
  - `.env.example` 写入默认模型：
    - `OPENAI_MODEL=gpt-5.4-mini`
    - `OPENAI_MODEL_OPTIONS=gpt-5.4-mini,gpt-5.5,gpt-5.4,gpt-5.4-nano,gpt-5-mini,gpt-5-nano`
    - `ANTHROPIC_MODEL=claude-sonnet-4-6`
    - `GEMINI_MODEL=gemini-2.5-flash`
  - 创建真实 Provider 任务前会先检查必要配置，缺少时返回 400 和缺失变量列表。
  - 真实研究要求对应模型 Provider API Key 和 `SERPAPI_API_KEY`，`JINA_API_KEY` 为可选但推荐。
- OpenAI 默认模型从 `gpt-5-mini` 调整为 `gpt-5.4-mini`，同时保留 `gpt-5.5` 等候选项用于质量测试。
- 配置读取逻辑会忽略以“在这里填写”开头的中文占位符，避免占位内容被当成真实 API Key 发送到上游。
- `OPENAI_BASE_URL` 默认改为 `https://api.openai.com/v1`，并在 OpenAI SDK 初始化时显式传入，避免空环境变量导致请求 URL 缺少协议。
- `SearchTool` 和 `VisitTool` 不再直接读取系统环境变量，统一使用 `Settings` 传入的配置，避免绕过占位符过滤。
- 搜索工具从 Serper.dev 通用网页搜索改为 SerpAPI Google Scholar 学术搜索：
  - 移除 `SERPER_API_KEY` 配置依赖。
  - 本地 `.env` 中原先误填在 `SERPER_API_KEY` 的 SerpAPI key 已迁移为 `SERPAPI_API_KEY`。
  - `SearchTool` 改为调用 `https://serpapi.com/search`，默认 `engine=google_scholar`。
  - 搜索结果解析改为读取 `organic_results`，并保留标题、URL、摘要、发表信息和引用数。
  - `/api/readiness` 的搜索工具状态现在返回搜索 Provider 和学术搜索引擎。
- 真实 Provider 研究流程增加证据门槛：没有 `search` 前不能生成最终报告，deep / expert 模式还需要至少一次 `visit`。
- Runtime 会对工具来源去重并分配 `citation_id`，以 `[1]`、`[2]` 形式注入给模型，要求最终报告使用引用角标。
- 前端来源展示从纯链接升级为来源卡片，包含 favicon、引用编号、域名、标题、摘要和 URL。
- 前端报告正文会把 `[n]` 渲染成可 hover 的引用角标，并在来源区展示 APA 风格参考文献兜底列表。
- 排查 GitHub 推送超过 100MB 文件的问题：
  - 确认 `PZ Deep Research/frontend/node_modules/@next/swc-darwin-arm64/next-swc.darwin-arm64.node` 为 117MB，但属于 `node_modules` 生成物，已被忽略。
  - 确认 `PZ Deep Research/frontend/.next/dev/cache/turbopack/411c455d/00000045.sst` 为 94MB，属于 Next.js 构建缓存，已被忽略。
  - 确认 `Qwen Deep Research/WebAgent/WebWatcher/browsecomp-vl/images/level2.tar` 为 58MB，属于上游参考项目数据包，不应推送到 PZ 产品仓库。
  - 根目录新增 `.gitignore`，明确忽略 `Qwen Deep Research/`、PZ 的 `node_modules`、`.next`、后端虚拟环境和本地缓存。
  - 通过 `git add --dry-run 'PZ Deep Research' .gitignore` 验证不会添加上述大文件。

### 影响文件

- `.env.example`
- `.gitignore`
- `README.md`
- `backend/app/api/routes.py`
- `backend/app/config.py`
- `backend/app/agent/providers/openai_provider.py`
- `backend/app/agent/runtime.py`
- `backend/app/agent/schemas.py`
- `backend/app/agent/tools/search.py`
- `backend/app/agent/tools/visit.py`
- `backend/app/agent/tools/utils.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_provider_factory.py`
- `backend/tests/test_config.py`
- `backend/tests/test_tools.py`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/app/globals.css`
- `project-docs/api-key-setup.md`
- `project-docs/project-plan.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 先补测试后实现，阶段 2 新测试在实现前失败，完成实现后通过。
- 先补测试后实现，阶段 3 新测试在实现前失败，完成实现后通过。
- 后端 pytest 通过：25 个用例通过，包含模型候选列表、OpenAI 模型查询配置错误、中文占位符过滤、默认 Base URL 检查和真实 Provider 证据门槛检查；仍有 Starlette/TestClient deprecation warning，不影响当前功能。
- 后端 `compileall` 通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- 使用本地 `.env` 中的 OpenAI Key 查询模型列表成功：账号返回 118 个模型，项目配置的 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano`、`gpt-5-mini`、`gpt-5-nano` 均可见。
- 使用本地 `.env` 中的 SerpAPI Key 真实调用 Google Scholar 搜索成功：`retrieval augmented generation survey` 返回 10 条学术来源。
- 使用本地 `.env` 中的 Jina API Key 真实调用 Jina Reader 成功：`https://example.com` 可以返回 LLM 友好的网页正文。

### 备注

- 阶段 2 已关闭，但真实 OpenAI、Claude、Gemini API Key 联调仍需后续作为可选集成测试补充。
- 阶段 3 已关闭，SerpAPI Google Scholar 和 Jina 的真实线上联调已进入后续持续验证范围。
- 下一步建议进入阶段 4：网页端 MVP 体验增强，重点包括前端展示 `llm_result` 用量、失败/重试状态、来源质量，以及更完整的任务结果页。

## 2026-06-02

### 新增

- 创建 `PZ Deep Research/project-docs/` 作为项目协作文档目录。
- 新增 `project-plan.md`，用于记录项目目标、实现方案、阶段规划和工程原则。
- 新增 `product-doc.md`，用于记录产品愿景、目标用户、核心流程、MVP 功能和体验要求。
- 新增 `changelog.md`，用于记录后续每次重要修改。
- 在 `project-plan.md` 中新增项目协作角色分工，明确用户、Codex、Claude Opus 4.8 和 Gemini 的角色。
- 在 `product-doc.md` 中新增模型和协作使用策略，明确 Gemini 暂不参与核心工程协作，优先作为产品模型 Provider 和后续评测对象。
- 新增 `technical-architecture.md`，记录技术架构、方案选择、模块职责、当前状态、风险和后续替换点。
- 新增 `testing-guide.md`，记录测试策略、自动化测试命令、手动端到端测试流程和后续测试优先级。
- 新增 `dependency-management.md`，记录运行时版本、依赖升级策略、安全审计状态和兼容性判断。
- 新增后端 pytest 测试用例：
  - `backend/tests/test_agent_runtime.py`
  - `backend/tests/test_api.py`
- 新增 PZ 项目第一批工程骨架：
  - `backend/`：FastAPI API、Agent Runtime、Provider 抽象、工具抽象、内存任务存储。
  - `frontend/`：Next.js 研究工作台第一屏。
  - `.env.example`：统一环境变量模板。
  - `.gitignore`：PZ 项目忽略规则。
  - `README.md`：项目启动和协作文档说明。

### 修改

- 将三份协作文档统一改为中文，方便阅读和协作。
- 在 `project-plan.md`、`product-doc.md`、`changelog.md` 中加入文档维护规则，提醒后续参与者在修改项目时同步记录变更。
- 明确当前协作主线为：用户负责产品决策，Codex 负责主工程实施，Claude Opus 4.8 负责架构和 prompt 顾问，Gemini 作为产品模型能力和评测对象。
- 明确后续工程实施采用测试优先原则：新功能先定义测试用例或验收标准，再开始实现。
- 明确依赖不默认向下兼容，major 版本必须单独验证后再采用。
- 前端工程采用 Next.js App Router 方向，第一屏直接进入研究工作台，不做营销 landing。
- 后端默认使用 `mock` Provider，便于在未配置模型 API Key 时先跑通任务流。
- `project-plan.md` 增加阶段 1 和阶段 2 的当前实施状态。
- 后端类型标注改为 Python 3.9 兼容写法，避免系统 Python 3.9 无法解析 `| None` 类型。
- 前端 ESLint 配置改为 Next.js 16 的 flat config 方式，解决 `FlatCompat` 导致的 circular structure 报错。
- Next.js build 自动补充了 `tsconfig.json` 中的 `.next/dev/types/**/*.ts` include，并将 `jsx` 调整为 `react-jsx`。
- 升级后端虚拟环境工具：`pip` 升至 `26.0.1`，`setuptools` 升至 `82.0.1`。
- 按 `requirements.txt` 复查并升级后端依赖，当前 `pip list --outdated` 为空。
- 升级前端依赖并同步 `package.json` / `package-lock.json`：
  - `next` 16.2.7
  - `react` 19.2.7
  - `react-dom` 19.2.7
  - `lucide-react` 1.17.0
  - `typescript` 6.0.3
  - `eslint-config-next` 16.2.7
  - `eslint` 9.39.4
  - `@types/node` 22.19.19
  - `@types/react` 19.2.16
  - `@types/react-dom` 19.2.3
- 尝试升级 `eslint@latest` 到 10.4.1，但与当前 Next.js 16 / eslint-config-next 插件链不兼容，已恢复为 9.39.4。
- 未采用 `@types/node@latest` 25.9.1，因为当前本机 Node.js 为 22.22.3，类型包应匹配运行时大版本。
- `npm audit` 仍报告 2 个 moderate，来自 Next/PostCSS 依赖链；npm 给出的自动修复方案会将 Next 降到 9.3.3，属于破坏性倒退，暂不执行。
- 记录 `npm ls --depth=0` 中 `@emnapi/runtime@1.10.0 extraneous` 的现象：它来自 Next.js / sharp 图像依赖链，`npm ci` 后仍出现，但不影响 lint/build。
- 按用户要求将本机全局环境和项目环境统一：
  - 全局 Python 更新为 3.14.5。
  - 全局 Node.js 通过 nvm default 固定为 24.16.0 LTS。
  - 全局 npm 更新为 11.16.0。
  - 后端 `backend/.venv/` 已用 Python 3.14.5 重建。
- 新增项目运行时声明：
  - `.python-version`
  - `.nvmrc`
  - `frontend/.npmrc`
- 前端 `package.json` 新增 `packageManager` 和 `engines`，要求 Node.js 24 / npm 11，并通过 `engine-strict=true` 阻止错误版本安装。
- 前端 `@types/node` 从 22 系列升级为 24.12.4，使类型定义与 Node.js 24 LTS 对齐。
- 新增 `backend/requirements-lock.txt`，记录当前 Python 3.14.5 后端环境的精确依赖版本，便于复现已验证环境。
- 更新 `README.md`、`technical-architecture.md`、`testing-guide.md`、`dependency-management.md`，补充统一运行环境、安装方式、验证要求和依赖锁定策略。
- 重新联网检查依赖状态：
  - `pip list --outdated` 只提示 `pydantic_core 2.46.4 -> 2.47.0`，因其为 `pydantic` 底层依赖，暂不单独升级。
  - `npm outdated` 只提示 `@types/node` 25 和 ESLint 10 两个未采用的 major latest。
  - `pip check` 显示无破损依赖。

### 影响文件

- `README.md`
- `.env.example`
- `.gitignore`
- `.python-version`
- `.nvmrc`
- `backend/`
- `backend/requirements-lock.txt`
- `frontend/`
- `frontend/.npmrc`
- `frontend/package-lock.json`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/dependency-management.md`
- `project-docs/changelog.md`

### 验证

- 后端通过 `compileall` 语法检查。
- 后端 app 可以成功导入，标题为 `PZ Deep Research API`。
- 后端 pytest 测试通过：共 5 个用例，覆盖 Agent Runtime、工具调用顺序、健康检查、任务创建和输入校验。
- 前端依赖安装完成。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- 依赖升级后后端 `compileall` 通过。
- 环境统一后再次验证：
  - 交互式 Node.js 为 `v24.16.0`。
  - 交互式 npm 为 `11.16.0`。
  - 全局 `python3` 为 `Python 3.14.5`。
  - 后端 `backend/.venv/bin/python` 为 `Python 3.14.5`。
  - `pip check` 显示无破损依赖。
  - 后端 pytest 通过：共 5 个用例，另有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。
  - 后端 `compileall` 通过。
  - 前端 `npm run lint` 通过。
  - 前端 `npm run build` 通过。
- FastAPI 在 `http://127.0.0.1:8000` 成功启动。
- Next.js 在 `http://localhost:3000` 成功启动。
- `/health` 返回 `{"status":"ok"}`。
- mock 研究任务成功完成，事件包含 `status`、`llm_start`、`tool_start`、`tool_result`、`completed`。
- 浏览器自动化 CLI 当前不可用，已用本地 HTTP 响应和 HTML 内容验证前端页面加载。

### 备注

- `Qwen Deep Research` 只作为上游参考代码。
- 新产品开发应在 `PZ Deep Research` 中进行。
- 后续每次在 PZ 项目中做实质修改，都应同步更新本变更日志。
- 当前版本已安装前端和后端依赖，但真实模型调用尚未联调。
- `npm install` 报告 2 个 moderate 级别漏洞，暂未执行 `npm audit fix --force`，避免自动升级引入破坏性变更。

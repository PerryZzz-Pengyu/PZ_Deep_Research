# PZ Deep Research 技术方案与架构说明

## 文档维护规则

这份文档用于记录 PZ Deep Research 的技术架构、方案选择、模块职责和关键工程决策。

只要修改了后端架构、前端架构、Agent Runtime、模型 Provider、工具层、数据存储、部署方案、依赖选择或接口设计，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`，说明修改时间、修改内容、影响文件和修改原因。changelog 新记录使用 `YYYY-MM-DD HH:mm 时区`，同一天多次修改也不要合并。

## 当前总体架构

当前项目采用“前端工作台 + 后端 Agent 服务 + 多模型 Provider + 工具层”的结构。

```text
用户浏览器
  ↓
Next.js 前端工作台
  ↓ HTTP / SSE
FastAPI 后端 API
  ↓
Agent Runtime
  ↓
LLM Provider 层
  ├─ mock
  ├─ OpenAI / ChatGPT API
  ├─ Anthropic / Claude API
  └─ Gemini API
  ↓
工具层
  ├─ search
  └─ visit
```

这样设计的原因是：C 端产品需要稳定的网页体验、可观察的任务进度、可替换的模型能力，以及后续可以扩展搜索、网页访问、文件解析、支付、登录等功能。

## 项目目录说明

```text
PZ Deep Research/
  backend/              # 后端服务和 Agent Runtime
  frontend/             # 前端网页工作台
  project-docs/         # 项目计划、产品文档、架构文档、变更日志
  README.md             # 项目入口说明
  .python-version       # Python 运行时声明
  .nvmrc                # Node.js 运行时声明
  .env.example          # 环境变量模板
  .gitignore            # 忽略规则
```

## 运行时基线

当前项目和本机全局环境统一为：

```text
Python 3.14.5
Node.js 24.16.0
npm 11.16.0
```

方案选择：

- Python 使用官方稳定发行版，后端虚拟环境也使用同一版本。
- Node.js 使用官方生产推荐的 LTS 线，当前通过 nvm 固定到 `v24.16.0`。
- 前端在 `package.json` 中声明 `engines` 和 `packageManager`，并通过 `frontend/.npmrc` 开启 `engine-strict=true`。
- 后端保留 `requirements.txt` 和 `requirements-lock.txt`，前者用于升级，后者用于复现当前验证过的环境。

选择原因：

- C 端产品后续要部署和持续迭代，运行时漂移会放大调试成本。
- 统一全局和项目环境可以减少本机调试、文档命令、CI/部署环境之间的不一致。
- 仍然保留范围依赖文件，方便未来按测试节奏升级。

## 后端方案

### 使用 FastAPI

位置：`backend/app/main.py`、`backend/app/api/routes.py`

当前方案：后端使用 FastAPI 提供 API 服务。

选择原因：

- Python 生态更适合承接原 Qwen Deep Research 中的 Agent、搜索、网页解析和文件解析逻辑。
- FastAPI 原生支持异步接口，适合长任务、SSE 事件流和模型 API 调用。
- Pydantic 类型校验清晰，便于后续扩展接口。
- 启动和本地调试成本低。

当前状态：

- 已实现 `/health` 健康检查。
- 已实现 `/api/readiness` 配置体检，返回 Provider、默认模型、缺失环境变量和工具配置状态。
- 已实现 research job 创建、查询、事件查询和 SSE 流接口。
- 创建真实 Provider 任务前会检查必要环境变量，避免任务创建后才失败。
- 当前任务存储为内存存储，适合开发阶段，不适合生产。

后续可替换点：

- 任务存储从内存改为 Postgres。
- 任务执行从 FastAPI background task 改为 Celery、RQ、Arq 或独立 worker。
- SSE 可按需要升级为 WebSocket。

## 前端方案

### 使用 Next.js App Router

位置：`frontend/src/app/`、`frontend/src/components/research-workspace.tsx`

当前方案：前端使用 Next.js App Router，第一屏直接是研究工作台。

选择原因：

- 后续适合部署到 Vercel。
- App Router 适合构建产品型界面和后续服务端页面。
- React 组件生态成熟，适合做任务进度、报告、来源、历史记录等交互界面。
- C 端产品第一版不需要营销首页，应该直接进入可用体验。

当前状态：

- 已实现研究问题输入。
- 已实现研究模式选择。
- 已实现 Provider 选择。
- 已实现进度事件展示。
- 已实现最终报告展示。
- 已实现来源卡片展示，包含引用编号、favicon、域名、标题、摘要和 URL。
- 已实现报告正文中的 `[n]` 引用角标 hover 提示来源。
- 已在来源区补充 APA 风格参考文献兜底展示。
- 已使用 `react-markdown` 和 `remark-gfm` 渲染最终报告，支持 Markdown 标题、列表、表格、链接和 GFM 格式。
- 已实现模型实时输出区域，展示后端 `llm_delta` 流式事件。
- 已实现工具返回正文展示，`tool_result` 可展开查看 search / visit 原始内容。
- 已实现引用 hover 卡片，展示来源标题、域名、URL 和证据强度。
- 来源卡片已展示证据强度标签，例如全文证据、部分正文、题录摘要、访问受限。

后续可替换点：

- UI 可升级为 shadcn/ui 组件体系。
- 状态管理可从本地 state 升级为 SWR 或 React Query。
- 历史记录、登录态和用户额度需要接入后端真实数据。

## Agent Runtime 方案

### 使用模型无关 Runtime

位置：`backend/app/agent/runtime.py`

当前方案：Agent Runtime 不直接依赖 Qwen、OpenAI、Claude 或 Gemini，而是通过 ProviderFactory 获取模型 Provider。

选择原因：

- 用户明确要求不使用 Qwen 模型。
- C 端产品需要多模型切换和后续模型路由。
- 不把模型调用写死在 Agent 循环里，后续维护成本更低。
- 可以单独测试 Agent 逻辑、模型 Provider 和工具层。

当前状态：

- 已实现基础循环：
  - 系统提示词
  - 用户问题
  - 模型生成
  - 解析 `<tool_call>`
  - 调用工具
  - 注入 `<tool_response>`
  - 解析 `<answer>`
- 已按研究模式限制最大轮数，并使用英文生产 Prompt 搭配三个模式策略块：
  - quick：8 轮，给 search、visit、answer 和必要格式修复留出空间。
  - deep：18 轮，允许 10 个来源访问在模型分批调用时仍能完成。
  - expert：32 轮，支持两段搜索、两段访问和最终长报告。
- 三个模式共享固定流水线，但研究强度不同：
  - quick：1 个高命中英文搜索词，最终选择 3 个来源，正文 400-500 字。
  - deep：3 个高命中英文搜索词，最终选择 10 个来源，正文 1300-1500 字。
  - expert：每次搜索 5 个高命中英文搜索词，先搜索/访问，再基于第一阶段证据卡片审查缺口后二次搜索/访问；最终选择 20 个来源，正文 3000-3500 字。
- Runtime 对真实 Provider 的证据门槛不再只判断是否调用过工具，而是按搜索次数和已访问来源 URL 数量判断是否可以进入最终报告。
- 已实现模型调用超时控制，默认 `LLM_TIMEOUT_SECONDS=60`。
- 已实现模型调用失败重试，默认 `LLM_MAX_RETRIES=1`。
- 已实现 `llm_result` 事件，用于记录模型名、输入 token、输出 token、单轮估算成本和累计用量。
- 已实现 `llm_delta` 事件，用于把支持原生 streaming 的 Provider 输出实时推送给前端。
- 已实现报告级真流式输出：证据门槛满足后，如果模型开始输出 `<answer>`，Runtime 会在模型仍在生成时同步发送 `report_delta`。
- 如果流式报告草稿后续没有通过引用或参考文献格式校验，Runtime 会发送 `report_reset`，前端清空草稿并等待重写。
- 模型调用最终失败时 Runtime 会产出 `failed` 事件，让任务状态可以被存储层正确更新。
- 研究流程为「Runtime 驱动的访问漏斗」：模型只负责输出 `search` 查询和最终报告，**访问由 Runtime 驱动，模型不再输出 `visit` 调用**。
- 访问漏斗（`_visit_funnel`）：search 候选按搜索原生相关性序，用并发 `visit` 滚动访问；full_text 数达到阶段目标（quick 3 / deep 10；expert 第一阶段 10、最终 20）即早停，否则访问完该次搜索返回的有限候选。候选耗尽即退出，不重复搜索或重访，因此不会因全文不足卡死。
- 证据卡片裁剪：每条已访问来源由便宜模型（`EVIDENCE_EXTRACTION_MODEL`，默认 `gpt-5-nano`）抽成紧凑证据卡片，原文按 url 在任务级内存暂存、不进模型上下文；模型只读卡片写报告，单轮请求 token 不随轮数膨胀。抽取调用带超时和重试，单条抽取失败时退回截断原文卡片，不使整项研究失败。
- 选源（`selection.select_sources`）：「质量优先 → 数量补足 → 逃生降级」。按 `full_text > partial_text > metadata > failed` 排序后取前 N；总数不足则有多少用多少。最终来源重新连续编号 1..N。quick / deep / expert 的全文质量最低线分别为 1 / 3 / 5，低于最低线时通过 `full_text_shortfall` 要求报告说明证据局限，但不阻止任务完成。
- expert 模式强制跑两轮 `search`。第一阶段访问和抽卡后，Runtime 把证据卡片交给模型审查缺口，再执行第二轮补充检索；最终选源覆盖两轮访问并集。
- 搜索词按模式上限裁剪（quick 1 / deep 3 / expert 5）。
- Runtime 可以从未闭合但 JSON 完整的 `<tool_call>` 中恢复工具调用，也可以从未闭合但内容完整的 `<answer>` 中恢复报告正文。
- 来源分级：`search` 返回的是候选来源（`source_kind=search_result`），使用罗马编号 `(i)`、`(ii)`、`(iii)`，只在中间「工具返回」展示、不能被引用；访问过程也只在中间展示。质量筛选完成后，`source_selected` 与 `completed` 仅携带最终入选来源并连续编号，右侧来源区只读取这两个事件。
- 新增事件：`visit_progress`（访问进度 n/目标、全文证据数）、`evidence_ready`（已抽取卡片数）、`source_selected`（最终选中来源 + 降级标志）。
- 真实 Provider 的最终报告需要包含阿拉伯 `[n]` 引用角标和 References / 参考文献章节；缺失、出现 `[^n]` 脚注、或引用了未在证据卡片中的来源时，Runtime 会产出 `citation_required` 并要求模型重写。
- 真实 Provider 报告还会校验正文长度：quick 400-500、deep 1300-1500、expert 3000-3500；References / 参考文献整节和 `[n]` 引用标记不计入。重写两次仍不合格时任务明确失败，不无限重试。
- 最终报告会通过 `report_delta` 事件实时推送给前端，前端可以逐步显示报告内容；`report_delta` 不再写入历史事件存储，避免 token 级报告片段撑爆任务记录。

后续可替换点：

- XML 工具协议可以升级为各模型原生 tool calling。
- Agent 轮数、搜索数量、访问数量当前写在 `MODE_POLICIES`，后续可以改为配置化或管理员后台可调。
- 增加任务取消、暂停、恢复。
- 增加 token 预算和成本预算控制，目前只有用量记录和成本字段透传。
- 增加引用生成、来源去重和证据评分。

## 工具调用协议

### 当前使用 XML 风格协议

当前工具调用格式：

```text
<tool_call>
{"name":"search","arguments":{"query":["搜索词"]}}
</tool_call>
```

提示词文件位置：

```text
backend/app/agent/prompt_templates/system_prompt.en.md      # 英文生产和测试提示词，Runtime 实际使用
backend/app/agent/prompt_templates/system_prompt.zh-CN.md   # 中文对照提示词，仅用于人工审阅
```

选择英文生产提示词的原因：

- OpenAI、Claude、Gemini 在英文工具协议和结构化约束上通常更稳定。
- 中文对照文件方便项目协作时检查策略内容，两份文件需要保持结构和数字规格一致。
- Runtime 中的 `build_user_prompt` 也使用英文执行说明，只保留用户原始问题不翻译。

最终答案格式：

```text
<answer>
最终研究报告
</answer>
```

选择原因：

- OpenAI、Claude、Gemini 都能理解文本格式协议。
- 第一版适配成本低，不需要分别处理三家模型不同的 tool calling 协议。
- 更接近 Qwen Deep Research 原始 ReAct 风格，迁移思路更直接。

当前风险：

- 文本协议依赖模型遵守格式，真实模型可能输出不标准 JSON。
- 当前已有基础容错和流程纠偏，但仍不如各家模型原生 tool calling 稳定。
- 当前执行策略只接受每轮第一个工具调用；如果后续要支持批量工具调用，需要增加更严格的依赖判断和人工可观察性。
- 原生 tool calling 的稳定性通常更好，后续应逐步升级。

后续方向：

- 当前 MVP 阶段继续使用 XML 协议跑通多模型闭环。
- 后续模型深度适配阶段再为 OpenAI、Claude、Gemini 分别实现原生工具调用。
- 保留 XML 协议作为 fallback。

## 模型 Provider 方案

### Provider 抽象

位置：`backend/app/agent/providers/`

当前 Provider：

- `mock_provider.py`
- `openai_provider.py`
- `anthropic_provider.py`
- `gemini_provider.py`
- `factory.py`

选择原因：

- 避免 Agent Runtime 直接依赖某一家模型 SDK。
- 后续可以按成本、质量、速度做模型路由。
- 方便加入更多 Provider，例如 OpenRouter、本地模型或企业私有模型。

### mock Provider

用途：开发阶段跑通完整任务流。

选择原因：

- 不需要 API Key。
- 不依赖外部模型服务。
- 方便验证前端、后端、SSE、工具调用和报告展示。

当前状态：

- 已能模拟 search、visit 和最终报告。

### OpenAI Provider

用途：接入 OpenAI / ChatGPT API。

当前状态：

- 已使用 OpenAI Responses API 调用结构。
- 已接入 OpenAI Responses API 原生 streaming，使用 `response.output_text.delta` 生成 `llm_delta`，并处理 completed、failed、incomplete 和 error 事件。
- 已能返回模型名、输入 token 和输出 token。
- 已通过 ProviderFactory 测试覆盖默认模型和专属模型选择。
- 当前默认模型为 `gpt-5.4-mini`。
- 当前候选模型列表为 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano`、`gpt-5-mini`、`gpt-5-nano`。
- 已新增 `/api/models` 返回项目配置的模型候选列表，供前端模型下拉使用。
- 已新增 `/api/models/openai` 使用后端保存的 `OPENAI_API_KEY` 查询当前账号实际可访问的模型 ID，用于人工联调和排查模型不可用问题。

后续注意：

- 需要补充真实 API Key 下的可选集成测试。
- 需要补充更细的 token / 成本统计和长任务预算控制。

### Anthropic Provider

用途：接入 Claude API。

当前状态：

- 已有基础 SDK 调用结构。
- 已处理 system message 和 user/assistant message 分离。
- 已能返回模型名、输入 token 和输出 token。
- 已通过 ProviderFactory 测试覆盖默认模型和专属模型选择。
- 当前默认模型为 `claude-sonnet-4-6`。
- 尚未做真实 API Key 联调。

后续注意：

- 需要根据 Claude 模型实际输出优化 prompt。
- 后续可接入 Claude 原生 tool use。

### Gemini Provider

用途：接入 Gemini API。

当前状态：

- 已有基础 SDK 调用结构。
- 已通过 ProviderFactory 测试覆盖默认模型和专属模型选择。
- 当前默认模型为 `gemini-2.5-flash`。
- 尚未做真实 API Key 联调。

后续注意：

- 后续需要评估 Gemini 在长上下文、搜索推理、引用生成上的稳定性。
- Gemini 目前不进入核心工程协作链路，但作为产品模型能力保留。

## 工具层方案

### search 工具

位置：`backend/app/agent/tools/search.py`

当前方案：使用 SerpAPI 的 Google Scholar API 做学术搜索。

选择原因：

- 当前产品第一版聚焦学术资料检索，Google Scholar 比通用网页搜索更贴近论文、引用和研究来源。
- SerpAPI 官方支持 `engine=google_scholar`，可以按 query、作者、来源、年份和引用关系做检索。
- 返回结果可以转为来源列表，并交给 Jina Reader 继续读取正文。

当前状态：

- 未配置 `SERPAPI_API_KEY` 时返回开发模式占位结果。
- 配置后会调用 `https://serpapi.com/search`，默认参数为 `engine=google_scholar`。
- 已支持 query 清洗、空值过滤和重复 query 去重。
- 已支持来源 URL 去重，并在来源中记录 title、url、snippet 和 query。
- 已支持解析 Google Scholar 返回的发表信息和引用数。
- 搜索来源会标记为 `read_status=search_result`、`evidence_level=metadata`，提醒模型和前端这只是题录/摘要证据。
- 已支持 HTTP transport 注入，便于离线单元测试。
- 上游搜索失败时返回工具失败内容，不直接抛异常中断整个 Agent Runtime。

后续可替换点：

- 可补充 Semantic Scholar、Crossref、arXiv、PubMed 等更学术化的数据源。
- 需要加入搜索结果缓存。
- 需要加入年份、语言、引用量、来源可信度等过滤和排序策略。

### visit 工具

位置：`backend/app/agent/tools/visit.py`

当前方案：优先使用 Jina Reader 读取网页内容。

选择原因：

- 读取网页正文比直接抓 HTML 更适合 Agent 消化。
- 和 Qwen Deep Research 中使用 Jina 读页的思路接近。
- MVP 阶段可以快速得到可读内容。

当前状态：

- 对 `example.com` 开发占位 URL 返回 mock 内容。
- 其他 URL 会调用 `https://r.jina.ai/{url}`。
- 已支持 url 清洗、空值过滤和重复 URL 去重。
- 已限制只允许 `http` / `https` 网页，拒绝 `file` 等非网页 scheme。
- 已支持 HTTP transport 注入，便于离线单元测试。
- 上游网页读取失败时返回工具失败内容，不直接抛异常中断整个 Agent Runtime。
- 已支持读取状态和证据强度分级：`full_text`、`partial_text`、`metadata_only`、`unavailable`。
- 如果 Jina Reader 返回 403、Forbidden、CAPTCHA 或 `Are you a robot` 页面，来源会标记为 `blocked` / `metadata_only`，不能当作已阅读全文。

后续可替换点：

- 增加 HTML fallback。
- 增加网页内容摘要模型。
- 增加 PDF、新闻站、动态网页和反爬处理。
- 增加来源可信度评分。

## 数据存储方案

### 当前使用内存存储

位置：`backend/app/storage/memory.py`

当前方案：使用 `InMemoryJobStore` 保存任务和事件。

选择原因：

- 第一版开发最快。
- 方便验证 Agent Runtime 和前端事件流。
- 不需要先配置数据库。

当前限制：

- 服务重启后任务丢失。
- 无法支持多进程或多 worker。
- 不适合生产环境。

后续方案：

- Postgres 保存用户、任务、事件、报告、来源、用量。
- Redis 保存队列、临时状态和流式事件缓冲。
- 对大报告和上传文件可接对象存储。

## 实时进度方案

### 当前使用 SSE

位置：`backend/app/api/routes.py`、`frontend/src/lib/api.ts`

当前方案：前端用 `EventSource` 连接后端 `/stream` 接口。

选择原因：

- 深度研究任务主要是服务端向客户端推送进度，SSE 足够。
- 实现比 WebSocket 简单。
- 适合 MVP 阶段做任务进度、工具结果和最终报告推送。

当前状态：

- API 已提供 SSE stream。
- 前端已实现 EventSource 连接和事件展示。
- 前端已支持 `llm_delta` 模型实时输出、`report_delta` 报告分段渲染、`tool_result` 来源卡片渲染、Markdown 报告渲染和引用 hover。
- `llm_delta` 和 `report_delta` 使用实时队列推送给当前连接的 SSE 客户端，不写入历史事件存储，避免 token 级日志撑爆任务记录。
- 历史事件仍保留 `llm_result`、流程纠偏、工具调用、工具结果和完成/失败状态；刷新后通过 `completed.final_report` 恢复最终报告。
- `report_delta` 当前只承担在线连接期的打字机式报告流，不再承担历史分段回放。

后续可替换点：

- OpenAI 已接入模型 token 级 streaming；Claude 和 Gemini 当前使用兼容封装，后续需要接入各自 SDK 的原生 streaming。
- 如果需要双向实时控制，例如暂停、继续、人工确认，可以升级 WebSocket。
- 如果部署平台对 SSE 支持有限，需要改成轮询或 WebSocket。

## 环境变量方案

位置：`.env.example`、`backend/app/config.py`、`frontend/src/lib/api.ts`

当前方案：使用环境变量配置 Provider、模型、搜索工具和前端 API 地址。

选择原因：

- API Key 不能写进代码。
- 多环境部署时可以区分本地、测试、生产配置。
- 默认 `mock` Provider 可以无 Key 启动。

当前关键变量：

```text
DEFAULT_PROVIDER=mock
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.4-mini
OPENAI_MODEL_OPTIONS=gpt-5.4-mini,gpt-5.5,gpt-5.4,gpt-5.4-nano,gpt-5-mini,gpt-5-nano
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
SEARCH_PROVIDER=serpapi
ACADEMIC_SEARCH_ENGINE=google_scholar
SERPAPI_API_KEY=
JINA_API_KEY=
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

后续注意：

- 生产环境需要密钥管理。
- 前端只能暴露 `NEXT_PUBLIC_` 开头的非敏感变量。
- 模型 API Key 必须只保存在后端。

## 依赖管理方案

依赖升级策略、运行时版本、安全审计和兼容性判断统一记录在 `project-docs/dependency-management.md`。

当前原则：

- 项目内依赖保持较新，但必须通过测试验证。
- major 版本不默认视为向下兼容。
- 系统级 Python、Node.js、npm 不直接强制升级。
- 对已验证不兼容的 latest 版本，需要记录原因并暂缓采用。

## 验证方案

当前已验证：

- 后端 Python 语法检查通过。
- 后端 app 导入通过。
- 后端 pytest 自动化测试通过，当前为 64 个用例。
- 前端 lint 通过。
- 前端 build 通过。
- FastAPI 本地服务启动成功。
- Next.js 本地服务启动成功。
- mock 研究任务流跑通。

测试说明统一记录在 `project-docs/testing-guide.md`。

后续工程实施采用测试优先原则：新增功能前先明确测试用例或手动验收标准，再进入实现。后端优先使用 pytest，前端交互复杂后再引入 Playwright。

当前未完成：

- 真实 OpenAI 完整研究任务质量联调。
- 真实 Claude、Gemini API 联调。
- 浏览器自动化视觉截图验证。
- 生产数据库和任务队列验证。
- 文件上传和文件解析验证。

## 当前技术风险

- 真实模型可能不稳定遵守 XML 工具调用格式。
- 内存任务存储不能用于生产。
- FastAPI background task 不适合长时间高并发任务。
- 搜索和网页读取依赖第三方服务，可能受 QPS、费用和可用性影响。
- 前端当前是 MVP UI，还没有登录、历史记录和错误恢复能力。
- npm 当前报告 2 个 moderate 级别漏洞，暂未执行强制修复。

## 后续技术优先级

1. 真实 Provider 联调：继续验证 OpenAI 完整研究质量，再接 Claude 和 Gemini。
2. 为 Claude 和 Gemini 接入原生 streaming。
3. 增加真实 tool calling 或增强 XML 解析容错。
4. 将任务存储迁移到 Postgres。
5. 将后台任务迁移到 worker 队列。
6. 增加来源去重、引用格式和报告结构化输出。
7. 增加前端任务历史和报告详情页。
8. 增加部署方案和环境配置说明。

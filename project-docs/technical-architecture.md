# PZ Deep Research 技术方案与架构说明

## 文档维护规则

这份文档用于记录 PZ Deep Research 的技术架构、方案选择、模块职责和关键工程决策。

只要修改了后端架构、前端架构、Agent Runtime、模型 Provider、工具层、数据存储、部署方案、依赖选择或接口设计，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`，说明修改时间、修改内容、影响文件和修改原因。changelog 新记录使用 `YYYY-MM-DD HH:mm 时区`，同一天多次修改也不要合并。

## 当前总体架构

当前项目采用“前端工作台 + 后端研究任务服务 + Runtime 驱动的研究漏斗 + 多模型 Provider + 工具层”的结构。

```text
用户浏览器
  ↓
Next.js 前端工作台 + Clerk 会话
  ↓ HTTP / SSE
FastAPI 后端 API + Clerk JWT 本地验签
  ↓
Agent Runtime
  ├─ LLM Provider：生成搜索词、证据缺口和最终报告
  │   ├─ mock
  │   ├─ OpenAI / ChatGPT API
  │   ├─ Anthropic / Claude API
  │   └─ Gemini API
  ├─ search：获取候选来源
  ├─ visit：Runtime 并发访问候选来源
  ├─ evidence：把访问正文压缩为证据卡片
  └─ selection：质量优先选源并连续编号
```

这样设计的原因是：C 端产品需要稳定的网页体验、可观察的任务进度、可替换的模型能力，以及后续可以扩展搜索、网页访问、文件解析、支付、登录等功能。

额度、支付和成本保护属于后续产品化能力。公开架构只保留接口边界；具体定价、额度参数、成本阈值、供应商预算和结算策略在本地私有文档中维护，不写入公开仓库。

## 多领域架构

随着美股金融、社媒、行业分析和法律等领域加入，项目将保持模块化单体，并从单一学术 Runtime 演进为“共享研究内核 + 领域注册表 + 领域实现”。当前不拆微服务，不引入通用工作流 DSL。

```text
前端共享工作台
  ↓ HTTP / SSE
任务、鉴权、存储、Provider、事件和导出内核
  ↓
DomainRegistry
  ├─ academic：Scholar 检索、论文证据、文献综述
  ├─ finance：SEC、市场数据、新闻、筛选和验证
  ├─ social：平台内容、传播、情绪和偏差
  ├─ industry：市场规模、产业链和竞争格局
  └─ legal：法域、法条、判例、效力与时效
```

实施顺序和兼容边界见 `project-docs/multi-domain-refactor-plan.md`；美股领域产品边界见 `project-docs/finance-research-prd.md`。

当前已完成第一阶段领域接缝：

- `ResearchRequest` 和 `ResearchJob` 新增 `domain`，未传时默认 `academic`。
- `research_jobs.domain` 通过 Alembic `20260628_06` 持久化，历史任务回填为 `academic`。
- `app.research.registry.DomainRegistry` 以延迟 resolver 解析领域 Runtime；路由层不再在执行时直接假定全局 Runtime。
- 当前请求 Schema 只接受 `academic`；`finance` 在 Runtime、数据和验证就绪前不会提前暴露半成品 API。
- 学术 Runtime、Prompt、证据抽取、选源策略、Scholar 搜索和工具组装已归入 `app.research.domains.academic`。`app.agent.runtime/prompts/evidence/selection` 和 `app.agent.tools.search` 仅保留兼容导出。

### 美股金融领域骨架

位置：`backend/app/research/domains/finance/`

当前阶段 C 只建立领域数据契约和离线闭环，不注册公开 API：

- `schemas.py`：定义美股选项、Ticker/Exchange/CIK、SEC filing/fact、市场快照、新闻、金融证据、候选卡和版本化结果。数值使用 `Decimal`，所有时效时间必须带时区。
- `security.py`：只做精确 Ticker/公司名解析，标准化点号/连字符股份类别，对重名报错，并以有界 TTL 缓存 SEC 证券目录。
- `connectors/sec.py`：适配 SEC `company_tickers_exchange.json`、Submissions 和 Company Facts；请求必须提供识别性 `User-Agent`。
- `connectors/google_finance.py` / `google_news.py`：将 SerpApi JSON 收敛为领域模型，不将供应商元数据渗透到 Runtime 或证据层。
- `runtime.py`：当前只支持明确证券的 fixture 级证据组装，输出 filing、fundamental、market 和 news 证据。它不包含 Planner、候选筛选、估值、排名或投资结论。

实现依据：[SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces)、[SEC 证券目录](https://www.sec.gov/files/company_tickers_exchange.json)、[SerpApi Google Finance](https://serpapi.com/google-finance-api) 和 [SerpApi Google News](https://serpapi.com/google-news-api)。

当前 `ResearchDomain` 和 `DomainRegistry` 仍只接受/注册 `academic`。等阶段 D 完成研究漏斗、验证和产品输出后，才会开放 `finance`。

## 项目目录说明

```text
PZ_Deep_Research/
  backend/              # 后端服务和 Agent Runtime
  frontend/             # 前端：营销落地页 (/) + 研究工作台 (/workbench)
  project-docs/         # 项目计划、产品文档、架构文档、变更日志
  README.md             # 英文项目入口说明
  README.zh-CN.md       # 简体中文项目入口说明
  LICENSE               # Apache License 2.0
  NOTICE                # 项目归属、上游参考和非官方关系说明
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
- `/api/readiness` 同时执行数据库 `SELECT 1`，只返回 `ready` 和数据库类型，不暴露主机、用户名或连接密码。
- 已实现 research job 创建、查询、取消、事件查询和 SSE 流接口。
- 已实现按匿名访客归属过滤的研究历史列表和任务详情接口。
- 已实现 Clerk Bearer JWT 本地验签、账号级任务过滤和当前浏览器匿名历史自动认领。
- 创建真实 Provider 任务前会检查必要环境变量，避免任务创建后才失败。
- 运行任务会登记当前 `asyncio.Task`。取消接口先原子更新状态并记录 `cancelled` 事件，再取消后台协程，防止任务取消后仍写入 `completed`。
- 任务、事件、报告草稿和最终报告已写入 SQLite/PostgreSQL 兼容存储。
- 用量账本：`research_jobs` 增加每任务用量聚合列（输入/输出 token、LLM 调用数、工具调用数），由 `run_research_job` 在 `llm_result`/`tool_result` 流式事件中累计并经 `record_usage` 持久化（取消/失败也保留部分用量）；`GET /api/usage` 按访客/账号归属返回聚合（`aggregate_usage`）。这是社区版"用量展示"与云端"额度/计费"的共用地基；**公开仓只存原始计数，成本与定价计算属于私有 Cloud**。
- 应用启动时会把上次异常退出遗留的 queued/running 任务标记为中断失败。

后续可替换点：

- 任务执行从 FastAPI background task 改为 Celery、RQ、Arq 或独立 worker。
- SSE 可按需要升级为 WebSocket。

## 前端方案

### 使用 Next.js App Router

位置：`frontend/src/app/`、`frontend/src/components/research-workspace.tsx`、`frontend/src/components/home-page.tsx`

当前方案：前端使用 Next.js App Router，分为两条路由：

- `/`：营销落地页（`app/page.tsx` + `home-page.tsx`），含 Hero、研究领域、工作原理、模式、报告预览、FAQ、CTA 和页脚。
- `/workbench`：研究工作台（`app/workbench/page.tsx` + `research-workspace.tsx`），承载真实研究流程。
- 落地页提问后通过 `localStorage` 一次性 handoff（`frontend/src/lib/handoff.ts`）跳转工作台并自动开跑。

选择原因：

- 后续适合部署到 Vercel。
- App Router 适合构建产品型界面和后续服务端页面。
- React 组件生态成熟，适合做任务进度、报告、来源、历史记录等交互界面。
- 落地页负责对外讲清楚产品价值与能力边界，工作台保持纯粹的研究体验，两者职责分离。

当前状态：

- 已实现研究问题输入。
- 已实现研究模式选择。
- 生产界面已隐藏 Provider/模型选择；设置 `MODEL_ROUTING_MODE=manual` 时可为内部测试恢复选择器。
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
- 已实现运行中停止按钮和任务状态标签。
- 已使用 `localStorage` 保存当前任务 ID；刷新后重新获取任务与持久事件，并恢复问题、模式、Provider、时间线、来源、报告草稿或最终报告。
- 已实现历史视图：访客按浏览器 ID 加载；登录后按 Clerk `user_id` 加载并支持跨设备访问。
- 已实现终态任务重新运行，新任务保留原研究配置并记录来源任务血缘。
- 已实现失败任务产品化重试：用户只看到统一错误提示和一个“重试”按钮；成功或取消任务详情仍保留“重新运行”。
- 已实现 Markdown 导出：浏览器使用 `Blob` 和临时下载链接导出当前原始报告，文件名由研究问题生成并清理非法字符。
- 已实现正式 PDF 导出：前端请求受访客权限保护的后端接口，由 Playwright Chromium 输出 A4 PDF。
- 已落地营销首页（`/`）：品牌、研究领域、工作原理、模式对比、报告预览、FAQ 和 CTA，并支持提问后 handoff 进工作台。
- 已实现中 / 英多语言切换（默认中文）：见下「设计系统与多语言」。
- 当前仍没有追问、Word/品牌模板导出、额度和支付交互。

### 设计系统与多语言

- 前端正式使用 HeroUI v3.1.0 与 Tailwind CSS v4。`globals.css` 按官方顺序导入 `tailwindcss` 和 `@heroui/styles`，HeroUI v3 不使用 `HeroUIProvider`。
- `Button`、`Tabs`、`Card`、`TextArea`、`Modal`、`Tooltip`、`Spinner`、`Accordion` 等基础交互直接来自 `@heroui/react`；PZ 只保留品牌色、深色玻璃视觉、页面布局、报告排版和研究业务组件。
- 基础层在 `frontend/src/app/globals.css`：PZ 品牌 token、玻璃 / 流光边框、渐变文字、chip、报告 Markdown 与来源样式；落地页和工作台布局分别位于 `app/home.css` 与 `app/workbench/workbench.css`，不再维护通用按钮、Tab、Tooltip、Modal 或 Spinner 状态机。
- HeroUI 设计参考目录和 `heroui-mark*.svg` 已在正式接入后删除；PZ 使用 `components/brand-mark.tsx` 中自己的品牌标志。
- 字体使用 Inter（UI/展示）与 Fira Code（代码/等宽），来源于 HeroUI，存放在 `frontend/public/fonts/`，均为 SIL OFL 1.1（可商用、嵌入、再分发），目录内附 `LICENSE.txt`。
- 多语言由 `frontend/src/lib/i18n.tsx` 提供：`I18nProvider` + `useI18n` + 中英词典（中文为准、英文镜像），`localStorage` 持久化、SSR 安全、自动同步 `<html lang>`；切换器（`components/language-switch.tsx`）布置在首页导航栏与工作台顶栏。新增文案需中英同时补齐，否则 `Dict` 结构不一致会触发类型错误。

后续可替换点：

- 状态管理可从本地 state 升级为 SWR 或 React Query。
- 多语言可在引入更多语种或服务端渲染需求时升级为成熟 i18n 框架（如 next-intl）。
- 用户额度、套餐和账号删除后的数据生命周期仍需产品化设计。

Markdown 导出选择纯前端实现，位置为 `frontend/src/lib/markdown-export.ts`。原因是最终报告已经完整存在于前端状态和数据库恢复结果中，导出不需要后端重新生成文件，也不应产生新的模型调用或引用变化。当前文件使用 UTF-8 `text/markdown` Blob，内容与页面当前报告一致，末尾保证至少一个换行。

PDF 导出位置：

- `backend/app/reporting/pdf_export.py`
- `GET /api/research-jobs/{job_id}/export/pdf`
- `frontend/src/lib/api.ts`

方案：

- API 先使用当前访客 ID 查询任务，避免通过任务 ID 越权导出。
- 后端用 `markdown-it-py` 渲染 Markdown，关闭原始 HTML、图片规则和 linkify。
- Chromium Context 拦截并终止所有网络请求，不加载外部图片、脚本、字体或跟踪资源。
- 打印 HTML 使用 A4 样式、任务元数据、表格/代码块样式和页码 footer。
- PDF 导出默认最多并发 2 个，总超时 45 秒；可通过环境变量调整。
- Chromium 默认复用 Playwright 用户缓存，也可用 `PDF_CHROMIUM_EXECUTABLE_PATH` 指定生产浏览器路径。
- 选择后端生成而非 `window.print()`，是为了获得一致分页、可测试文件输出和受控的生产排版。

## Agent Runtime 方案

### 使用模型无关 Runtime

实现位置：`backend/app/research/domains/academic/runtime.py`

兼容位置：`backend/app/agent/runtime.py`，仅将历史 `AgentRuntime` 名称指向 `AcademicRuntime`。

当前方案：Agent Runtime 不直接依赖 Qwen、OpenAI、Claude 或 Gemini，而是通过 ProviderFactory 获取模型 Provider。

选择原因：

- 用户明确要求不使用 Qwen 模型。
- 后台需要保留多 Provider 能力，以支持分阶段模型路由、成本控制和故障降级；C 端不暴露模型切换。
- 不把模型调用写死在 Agent 循环里，后续维护成本更低。
- 可以单独测试 Agent 逻辑、模型 Provider 和工具层。

版本接缝（open-core）：

- `PZ_EDITION`（默认 `community`）在 `Settings` 与 `resolve_model_route` 中决定路由策略：
  - `community`：尊重客户端 Provider/模型（`routing_version=community`、`selection_enabled=True`），并支持模型、SerpAPI、Jina 的请求级 BYOK。敏感字段均标记 `exclude=True`，每个任务单独构建 Provider 与工具实例，绝不落库/日志/SSE。
  - `cloud`：忽略客户端选择与全部 BYOK Key。公开仓只定义扩展接缝，具体路由和运营参数由私有 Cloud 仓库注入。
- `/api/readiness` 返回当前 `edition`，前端据此决定是否暴露 Provider/模型选择与 BYOK 输入。

模型路由状态（云端版）：

- 公开仓的 Cloud 默认值为 `cloud-unconfigured`，不会携带可直接上线的模型组合。
- 私有 Cloud 仓库负责提供 Provider、模型、证据模型、路由版本和故障切换配置；路由版本仍写入 `research_jobs.routing_version`。
- `MODEL_ROUTING_MODE=manual` 仅用于 mock E2E 和内部联调。

当前状态：

- 当前不是由模型每轮自行决定 `search` / `visit` 的开放式 ReAct Agent，而是有明确边界的 Runtime 编排流程。
- 模型只负责三个受限任务：
  - 生成符合模式数量限制的英文搜索词。
  - expert 第一阶段完成后，根据证据卡片生成补充搜索词。
  - 根据最终选中的证据卡片生成带引用的研究报告。
- `visit` 不再由模型调用。Runtime 按搜索结果原生相关性顺序并发访问有限候选，达到目标后早停，候选耗尽后必须退出。
- 三个模式共享同一条确定性流水线，但研究强度不同：
  - quick：1 个高命中英文搜索词，最终选择 3 个来源，正文 350-900 字。
  - deep：3 个高命中英文搜索词，最终选择 10 个来源，正文 1100-2600 字。
  - expert：每次搜索 5 个高命中英文搜索词，先搜索/访问，再基于第一阶段证据卡片审查缺口后二次搜索/访问；最终选择 20 个来源，正文 2700-5200 字。
- `MODE_POLICIES` 中仍保留 `max_rounds` 兼容字段，但当前访问漏斗不依赖模型轮数驱动，该字段不再是 visit 调度或防死循环机制，后续应清理或重命名。
- 已实现模型调用超时控制，默认 `LLM_TIMEOUT_SECONDS=60`。
- 已实现临时模型错误重试，默认 `LLM_MAX_RETRIES=3`、`LLM_RETRY_BASE_DELAY_SECONDS=2`。仅对超时、429、408/409、5xx、`UNAVAILABLE`、`RESOURCE_EXHAUSTED`、过载和连接重置等可恢复错误按 2、4、8 秒指数退避；400 配置错误等永久错误直接失败。
- 已实现 `llm_result` 事件，用于记录模型名、输入 token、输出 token、单轮估算成本和累计用量。
- 已实现 `llm_delta` 事件，用于把支持原生 streaming 的 Provider 输出实时推送给前端。
- 已实现报告级真流式输出：证据门槛满足后，如果模型开始输出 `<answer>`，Runtime 会在模型仍在生成时同步发送 `report_delta`。
- 如果流式报告草稿后续没有通过引用或参考文献格式校验，Runtime 会发送 `report_reset`，前端清空草稿并等待重写。
- 模型调用最终失败时 Runtime 会产出 `failed` 事件，让任务状态可以被存储层正确更新。报告阶段的临时错误重试始终复用已选来源、证据卡片和报告上下文，`llm_retry` 标记 `resume_from=selected_evidence`，不会重新调用 search 或 visit。
- Runtime 在完成选源后生成私有 `report_checkpoint`，包含最终来源、证据卡片和选源降级状态。API 层只把该检查点写入任务数据库，不写历史事件、不发送给前端。任务若在报告阶段最终失败，用户点击“重试”会创建独立新任务并从检查点继续报告；搜索、访问或证据阶段失败则执行完整研究重试。
- 主流程固定为「生成搜索词 → search → Runtime visit → 证据卡片 → 选源 → 最终报告」；expert 在两轮检索之间额外执行一次证据缺口分析。
- 访问漏斗（`_visit_funnel`）：search 候选按搜索原生相关性序，用并发 `visit` 滚动访问；full_text 数达到阶段目标（quick 3 / deep 10；expert 第一阶段 10、最终 20）即早停，否则访问完该次搜索返回的有限候选。候选耗尽即退出，不重复搜索或重访，因此不会因全文不足卡死。
- 证据卡片裁剪：每条已访问来源由当前 Provider 的轻量模型抽取为紧凑证据卡片；社区版默认值可由操作者调整，Cloud 的实际模型组合位于私有配置。原文按 url 在任务级内存暂存、不进模型上下文；模型只读卡片写报告。报告阶段使用独立上下文，不携带搜索历史；每次格式/字数重写重新构造固定大小的 system/user 消息，只包含当前稿、证据卡片和校验要求，避免旧稿累计造成 token 膨胀。抽取调用带超时和重试，单条抽取失败时退回截断原文卡片，不使整项研究失败。
- 选源（`selection.select_sources`）：「质量优先 → 数量补足 → 逃生降级」。按 `full_text > partial_text > metadata > failed` 排序后取前 N；总数不足则有多少用多少。最终来源重新连续编号 1..N。quick / deep / expert 的全文质量最低线分别为 1 / 3 / 5，低于最低线时通过 `full_text_shortfall` 要求报告说明证据局限，但不阻止任务完成。
- expert 模式强制跑两轮 `search`。第一阶段访问和抽卡后，Runtime 把证据卡片交给模型审查缺口，再执行第二轮补充检索；最终选源覆盖两轮访问并集。
- 搜索词按模式上限裁剪（quick 1 / deep 3 / expert 5）。
- Runtime 可以从未闭合但 JSON 完整的 `<tool_call>` 中恢复工具调用，也可以从未闭合但内容完整的 `<answer>` 中恢复报告正文。
- 来源分级：`search` 返回的是候选来源（`source_kind=search_result`），使用罗马编号 `(i)`、`(ii)`、`(iii)`，只在中间「工具返回」展示、不能被引用；访问过程也只在中间展示。质量筛选完成后，`source_selected` 与 `completed` 仅携带最终入选来源并连续编号，右侧来源区只读取这两个事件。
- 新增事件：`visit_progress`（访问进度 n/目标、全文证据数）、`evidence_ready`（已抽取卡片数）、`source_selected`（最终选中来源 + 降级标志）。
- 真实 Provider 的最终报告需要包含阿拉伯 `[n]` 引用角标和 References / 参考文献章节；缺失、出现 `[^n]` 脚注、或引用了未在证据卡片中的来源时，Runtime 会产出 `citation_required` 并要求模型重写。
- 真实 Provider 报告还会校验正文长度：quick 350-900、deep 1100-2600、expert 2700-5200；References / 参考文献整节和 `[n]` 引用标记不计入。只有 `report_too_long` 时进入纯编辑压缩路径，仅提供上一稿并禁止新增事实或来源，根据当前计数给出目标保留比例和最少删除量；过短或同时存在其他格式问题时使用证据卡片重写。重写两次仍不合格时：若此时仅剩字数问题（`report_too_short` / `report_too_long`）而格式、引用均合格，则发出 `report_length_warning` 并采用最后一版草稿优雅收尾（避免因字数差一点而整单失败）；若仍存在格式或引用问题，才判定任务明确失败，不无限重试。
- 最终报告会通过 `report_delta` 事件实时推送给前端，前端可以逐步显示报告内容；`report_delta` 不再写入历史事件存储，避免 token 级报告片段撑爆任务记录。

后续可替换点：

- 搜索词的 XML 输出协议可以升级为结构化输出或各模型原生 tool calling。
- 搜索数量、访问目标、选源数量和报告字数当前写在 `MODE_POLICIES`，后续可以改为配置化或管理员后台可调。
- 在现有取消和刷新恢复基础上增加暂停、继续及跨进程恢复。
- 增加 token 预算和成本预算控制，目前只有用量记录和成本字段透传。
- 加强语义来源去重、论文元数据、事实级引用验证和来源可信度评分。

### 商业化技术边界

- 额度、支付、退款和任务结算必须由后端执行，前端不能作为账务事实来源。
- 所有写操作需要事务和幂等保护，避免并发任务或重复回调造成重复结算。
- 商业参数应通过服务端配置和版本化管理，不写死在公开前端代码或公开文档中。
- 任务需要保留必要的用量与异常观测能力，但公开仓库不记录成本公式、利润目标或内部阈值。

## 模型结构化输出协议

### 当前使用 XML 风格搜索词协议

模型生成搜索词时使用：

```text
<tool_call>
{"name":"search","arguments":{"query":["搜索词"]}}
</tool_call>
```

提示词文件位置：

```text
backend/app/research/domains/academic/prompt_templates/system_prompt.en.md      # 英文生产和测试提示词
backend/app/research/domains/academic/prompt_templates/system_prompt.zh-CN.md   # 中文对照提示词，仅用于人工审阅
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
- 保留了早期原型已经验证过的标签解析方式，跨 Provider 的实现成本较低。

Runtime 收到搜索词后会自行调用 `search`，并根据候选结果调用 `visit`。模型不能输出 `visit` 调用，也不能绕过选源流程直接把搜索摘要作为最终证据。

当前风险：

- 文本协议依赖模型遵守格式，真实模型可能输出不标准 JSON。
- 当前已有未闭合标签恢复和 JSON 容错，但仍不如结构化输出或各家模型原生 tool calling 稳定。
- 每个搜索生成阶段只接受第一个合法 `search` 调用，并由 Runtime 按模式裁剪搜索词数量。
- 原生 tool calling 的稳定性通常更好，后续应逐步升级。

后续方向：

- 当前 MVP 阶段继续使用 XML 协议生成受限搜索词。
- 后续模型深度适配阶段优先改为统一结构化输出；是否采用各 Provider 原生工具调用，需要以跨模型维护成本和稳定性测试决定。
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

- 已能模拟搜索词生成、证据流程所需响应和最终报告。

### OpenAI Provider

用途：接入 OpenAI / ChatGPT API。

当前状态：

- 已使用 OpenAI Responses API 调用结构。
- 已接入 OpenAI Responses API 原生 streaming，使用 `response.output_text.delta` 生成 `llm_delta`，并处理 completed、failed、incomplete 和 error 事件。
- 已能返回模型名、输入 token 和输出 token。
- 已通过 ProviderFactory 测试覆盖默认模型和专属模型选择。
- 当前默认模型为 `gpt-5.4-mini`。
- 当前候选模型列表为 `gpt-5.4-mini`、`gpt-5.5`、`gpt-5.4`、`gpt-5.4-nano`、`gpt-5-mini`、`gpt-5-nano`。
- 已新增 `/api/models` 返回项目配置的模型候选列表，当前供内部开发界面的模型下拉和质量测试使用；正式 C 端不暴露该入口。
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
- 当前候选模型为 `claude-sonnet-4-6`、`claude-opus-4-8`、`claude-opus-4-7`、`claude-opus-4-6`、`claude-haiku-4-5-20251001`。
- 已新增 `/api/models/anthropic`，使用服务端 Key 查询当前账号实际可用模型，并与项目候选列表求交集。
- 已使用本地 API Key 完成 Models API 联调，确认上述候选模型均在当前账号模型列表中。
- 已使用默认 `claude-sonnet-4-6` 完成最小真实生成测试；无 system message 时省略 `system` 字段，兼容新版 Messages API 校验。
- 尚未接入 Anthropic SDK 原生 streaming，当前通过兼容封装在完整响应后发送结果。

后续注意：

- 需要根据 Claude 模型实际输出优化 prompt。
- 后续可接入 Claude 原生 tool use。

### Gemini Provider

用途：接入 Gemini API。

当前状态：

- 已有基础 SDK 调用结构。
- 已通过 ProviderFactory 测试覆盖默认模型和专属模型选择。
- 当前默认模型为 `gemini-3.5-flash`。
- 当前候选模型为 `gemini-3.5-flash`、`gemini-3.1-pro-preview`、`gemini-3-flash-preview`、`gemini-3.1-flash-lite`、`gemini-2.5-pro`、`gemini-2.5-flash`、`gemini-2.5-flash-lite`。
- 已新增 `/api/models/gemini`，使用服务端 Key 查询支持 `generateContent` 的模型，移除 `models/` 前缀后与项目候选列表求交集。
- 已使用本地 API Key 完成 Models API 联调，确认上述候选模型均在当前账号模型列表中。
- 已使用默认 `gemini-3.5-flash` 完成最小真实生成测试。
- 尚未接入 Gemini SDK 原生 streaming。
- 尚未补齐与 OpenAI、Anthropic 一致的 token 用量采集。

后续注意：

- 后续需要评估 Gemini 在长上下文、搜索推理、引用生成上的稳定性。
- Gemini 目前不进入核心工程协作链路，但作为产品模型能力保留。

## 工具层方案

### search 工具

实现位置：`backend/app/research/domains/academic/search.py`

学术工具组装：`backend/app/research/domains/academic/tools.py`。`backend/app/agent/tools/search.py` 和旧 `build_default_tool_registry` 名称仅作兼容导出。

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

## 错误处理方案

位置：

- `backend/app/error_handling.py`
- `backend/app/api/routes.py`
- `frontend/src/lib/api.ts`
- `frontend/src/components/research-workspace.tsx`

错误分为两层：

| 工程错误 | 产品错误码 | C 端提示 | 默认可重试 |
| --- | --- | --- | --- |
| DNS、连接重置、fetch/网络异常 | `network_error` | 网络连接不稳定，请检查网络后重试 | 是 |
| 429、5xx、Provider 过载、服务重启 | `service_unavailable` | 研究服务暂时繁忙，请稍后重试 | 是 |
| 模型或任务超时 | `task_timeout` | 本次研究未能在规定时间内完成，请重试 | 是 |
| search、visit、Reader 无法取得足够资料 | `source_unavailable` | 暂时无法获取足够的可用资料 | 是 |
| 产品积分余额不足 | `insufficient_credits` | 当前积分不足，无法继续研究 | 否 |
| 内容安全或暂不支持的内容 | `content_unsupported` | 当前问题暂时无法处理 | 否 |
| 未分类异常、报告校验最终失败 | `system_error` | 研究过程中出现异常，请稍后重试 | 是 |

工程日志记录 `job_id`、Provider、模型、阶段、原始异常和事件 payload，便于排查；日志写入前会遮蔽疑似 API Key。普通任务 API、SSE、历史记录和前端不返回原始异常、堆栈、Provider 响应正文或环境变量名称。

失败任务保存 `error_code`、`error_retryable` 和 `error_stage`。前端只在 `failed + error_retryable=true` 时显示错误旁的单一“重试”按钮。HTTP 请求层也会把断网和非 JSON 服务器错误映射为产品化提示，不再直接显示 `response.text()`。

## 数据存储方案

### SQLAlchemy + SQLite/PostgreSQL

位置：

- `backend/app/storage/sql.py`
- `backend/migrations/`
- `backend/alembic.ini`

当前方案：

- 本地默认使用 `data/pz_deep_research.db`。
- 通过 `DATABASE_URL` 可以切换 PostgreSQL；普通 `postgresql://` URL 会规范化为 `postgresql+psycopg://`。
- 托管 PostgreSQL 可以把应用连接地址填入 `DATABASE_URL`，把迁移直连地址填入 `DATABASE_MIGRATION_URL`。
- PostgreSQL 默认启用 `pool_pre_ping`，并提供 `DATABASE_POOL_SIZE`、`DATABASE_MAX_OVERFLOW`、`DATABASE_POOL_TIMEOUT_SECONDS`、`DATABASE_POOL_RECYCLE_SECONDS`。
- `research_jobs` 保存任务状态、报告草稿、最终报告、产品错误元数据、报告重试检查点、`routing_version`、归属字段和可空的 `rerun_of_job_id` 来源任务。
- `research_events` 保存持久进度事件，使用任务外键和级联删除。
- Alembic 是应用启动时的正式建表和升级路径；`create_all` 只用于独立存储单元测试，不参与产品数据库初始化。

归属模型：

- 前端始终保留浏览器随机匿名访客 ID，并通过 `X-PZ-Visitor-ID` 发送。未登录时任务写入 `anonymous_id`。
- 配置 Clerk 后，前端通过 `ClerkProvider` 获取会话 token，并在受保护 API 与 SSE 请求中发送 `Authorization: Bearer <token>`。
- FastAPI 使用 `CLERK_JWT_KEY` 对 RS256 会话 JWT 本地验签，校验有效期、`sub` 和可选 `azp`；可信 `sub` 写入或查询 `user_id`。
- 登录请求同时携带当前浏览器访客 ID。后端在处理请求前调用 `claim_anonymous_jobs`，把该访客尚未归属账号的任务原子更新为当前 `user_id`。
- 归并是单向的：任务一旦写入 `user_id`，退出登录后不会退回匿名历史；同一账号在其他设备登录后可以查询。
- 历史、详情、事件、取消、重跑、失败重试、PDF 导出和 SSE 都按当前身份过滤。其他账号或访客使用任务 ID 访问时返回 404。
- 未配置 Clerk 时保留访客模式。匿名访客 ID 仍不是安全凭证，公网部署应启用 Clerk 并配置生产域名 `CLERK_AUTHORIZED_PARTIES`。

认证模块位置：

- `backend/app/auth.py`
- `frontend/src/components/app-auth-provider.tsx`
- `frontend/src/lib/api.ts`

选择 Clerk 的原因：

- Next.js App Router 有成熟 SDK 和现成登录/账号组件，能较快完成 C 端身份体验。
- 后端不需要持有 Clerk Secret Key 即可用公钥本地验证会话 JWT，模型和数据库密钥仍只存在服务端。
- 业务表只保存稳定 `user_id`，没有把存储层绑定到 Clerk 专有数据库，因此未来可以迁移到其他 OIDC/身份服务。
- 当前不建立本地用户资料表；额度、套餐、偏好和账号删除审计需要时再增加 `users` 业务表，并以 Clerk `sub` 作为外部身份键。

重新运行语义：

- 只有 `completed`、`failed`、`cancelled` 终态任务可以重新运行；`queued` / `running` 返回 409，避免同一运行任务被重复复制。
- 当前后端从数据库读取原任务的研究问题、模式、Provider、模型和 `routing_version`，前端不能在重跑请求里篡改这些字段。
- 新任务拥有独立 ID、独立事件流和独立报告，并通过 `rerun_of_job_id` 保留来源任务血缘。
- 第二个 Alembic 迁移为现有数据库增加血缘列和索引；旧的无版本数据库若已由最新 Metadata 建表，迁移会识别已有列并安全跳过重复创建。
- 第三个 Alembic 迁移增加 `error_code`、`error_retryable`、`error_stage` 和 `retry_context`，支持产品化错误与报告检查点恢复。
- 第四个 Alembic 迁移增加 `routing_version`，用于路由回溯与重跑一致性。

PostgreSQL 可迁移性：

- 项目没有使用特定托管厂商的专有 SQL 或 ORM API。
- 切换托管 PostgreSQL 或自建 PostgreSQL 时，只需提供新的 PostgreSQL URL、迁移数据并运行 Alembic；业务模型和 SQLAlchemy 存储层不需要重写。
- `backend/scripts/check_database.py` 只执行连接检查并输出 `database=ready` 与数据库类型，不打印 URL 或密码。
- 托管数据库实例、备份恢复记录、连接容量和生产演练属于 Cloud 运营资产，在私有仓库维护。

重启语义：

- 已完成、失败、取消任务及其报告和事件可以跨后端重启恢复。
- queued/running 任务的完整 Runtime 执行现场尚未持久化；服务启动时将其标记为可重试的服务异常，避免永久显示“研究中”。报告选源后的证据检查点已经单独持久化。

后续方案：

- 真实 PostgreSQL 实例验证连接池、迁移、备份和恢复。
- 独立 Worker 保存可恢复执行状态，Redis 或消息队列承载任务调度和跨进程取消信号。
- 增加业务用户表，为额度、套餐、偏好和删除状态提供真实外键；Clerk 继续作为外部身份源。
- 对大报告和上传文件可接对象存储。

## 实时进度方案

### 当前使用 SSE

位置：`backend/app/api/routes.py`、`frontend/src/lib/api.ts`

前端不再使用浏览器原生 `EventSource`，而是使用基于 `fetch` + ReadableStream 的 SSE 客户端。原因是原生 `EventSource` 无法添加 Bearer Authorization 请求头。自定义客户端保留 `Last-Event-ID` 等价游标、断线重连、`close()` 和消息回调语义，同时避免把会话 token 放进 URL。

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
- 历史事件保留 `llm_result`、工具调用、工具结果、报告重置和完成/失败/取消状态。
- 后端在 `ResearchJob.draft_report` 中累计当前报告草稿，但不把每个 token 作为历史事件保存；每个实时 `report_delta` 同时携带累计草稿，前端以累计值校正内容，避免重连竞态导致重复字符。
- SSE 输出持久事件 ID，支持 `after` 查询参数和 `Last-Event-ID` 游标；连接建立时先发送 `job_snapshot`，再重放游标后的持久事件。
- 浏览器通过 `localStorage` 记住当前任务，刷新后先读取任务和事件，再从最后一个持久事件继续订阅 SSE。
- 用户取消任务时，取消事件会进入持久事件和实时队列，SSE 随后正常结束。
- 已完成任务、持久事件和报告可以跨后端重启恢复；运行中任务仍需要独立 Worker 和可恢复执行状态才能真正续跑。

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
- 设置 `MODEL_ROUTING_MODE=manual`、`DEFAULT_PROVIDER=mock`、`SEARCH_PROVIDER=mock` 后可以无 Key 启动离线测试。

当前关键变量：

```text
DEFAULT_PROVIDER=mock
MODEL_ROUTING_MODE=production
PRODUCTION_PROVIDER=
PRODUCTION_MODEL=
MODEL_ROUTING_VERSION=cloud-unconfigured
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY_SECONDS=2
LLM_TIMEOUT_SECONDS=60
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-5.4-mini
OPENAI_MODEL_OPTIONS=gpt-5.4-mini,gpt-5.5,gpt-5.4,gpt-5.4-nano,gpt-5-mini,gpt-5-nano
EVIDENCE_EXTRACTION_MODEL=gpt-5-nano
ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MODEL_OPTIONS=claude-sonnet-4-6,claude-opus-4-8,claude-opus-4-7,claude-opus-4-6,claude-haiku-4-5-20251001
ANTHROPIC_EVIDENCE_MODEL=claude-haiku-4-5-20251001
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MODEL_OPTIONS=gemini-3.5-flash,gemini-3.1-pro-preview,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite
GEMINI_EVIDENCE_MODEL=gemini-2.5-flash-lite
SEARCH_PROVIDER=serpapi
ACADEMIC_SEARCH_ENGINE=google_scholar
SERPAPI_API_KEY=
JINA_API_KEY=
DATABASE_URL=
PDF_EXPORT_TIMEOUT_SECONDS=45
PDF_EXPORT_MAX_CONCURRENCY=2
PDF_CHROMIUM_EXECUTABLE_PATH=
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
- 后端 pytest 自动化测试通过，当前为 203 个用例。
- 前端 lint 通过。
- 前端 build 通过。
- Playwright Chromium 已建立 12 个端到端用例，覆盖任务取消、刷新续跑、完成后报告恢复、历史报告详情、重新运行、产品化错误重试、BYOK、移动端来源弹窗、Markdown 下载和正式 PDF 下载。
- SQLite 跨 Store 持久化、访客隔离、重启中断处理和匿名历史账号归并测试通过。
- Alembic 三个版本迁移已在 SQLite 执行通过，包含任务历史、重跑血缘、产品错误和报告检查点字段。
- FastAPI 本地服务启动成功。
- Next.js 本地服务启动成功。
- mock 研究任务流跑通。

测试说明统一记录在 `project-docs/testing-guide.md`。

后续工程实施采用测试优先原则：新增功能前先明确测试用例或手动验收标准，再进入实现。后端优先使用 pytest，前端核心交互使用 Playwright。

当前未完成：

- OpenAI、Claude、Gemini 已完成不同程度的人工真实调用，但尚未形成覆盖四类任务职责的可重复质量测试集。
- Claude、Gemini 原生 streaming 和真实模型成本计算。（Gemini token 用量已从 `usage_metadata` 接入账本）
- 关键桌面/移动视口视觉回归验证。
- Clerk 真实环境下的注册、登录、退出、匿名历史认领和跨设备浏览器验收。
- 真实 PostgreSQL、备份恢复和独立任务队列验证。
- 文件上传和文件解析验证。

## 当前技术风险

- 真实模型可能不稳定遵守 XML 工具调用格式。
- FastAPI background task 不适合长时间高并发任务。
- 访客模式仍依赖客户端匿名 ID，不能作为公网环境的强认证或付费权益边界。
- SQLite 不支持多实例共享和高并发写入，生产多实例需要 PostgreSQL。
- 搜索和网页读取依赖第三方服务，可能受 QPS、费用和可用性影响。
- 前端已经支持取消、刷新恢复、访客/账号历史、报告详情、重跑和 Markdown/PDF 导出，但还没有追问、额度和支付。
- 当前引用校验能验证格式、编号和来源存在性，但不能证明每个事实都被对应来源支持。
- APA 参考文献依赖搜索元数据和模型输出，缺少作者、年份、期刊等字段时只能降级展示。
- 当前只有 SerpAPI + Jina 主链路，缺少搜索和正文读取的生产级备用服务。
- npm 当前报告 2 个 moderate 级别漏洞，暂未执行强制修复。

## 后续技术优先级

1. Cloud 私有仓库完成托管 PostgreSQL 备份/时间点恢复演练，并记录恢复目标和数据完整性结果。
2. 增加关键视口视觉回归、真实断线恢复和 Worker 任务恢复测试。
3. 模型质量测试暂缓；Cloud 路由基线与后续版本在私有仓库评测和发布。
4. 补齐 Claude/Gemini 原生 streaming、Gemini 用量和成本计算。
5. 增加搜索与网页访问备用链路、结构化学术元数据、语义去重和事实级引用校验。
6. 把后台任务迁移到独立 Worker 队列，支持多实例和可恢复执行。
7. 完成 Clerk 生产验收，并增加限流、额度、成本预算、内容安全和可观测性。
8. 增加 CI/CD、生产密钥管理、备份、部署和回滚说明。

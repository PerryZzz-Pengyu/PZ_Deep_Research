# PZ Deep Research 变更日志

## 文档维护规则

这份文档用于记录 PZ Deep Research 项目的所有重要变化。只要修改了代码、架构、产品定义、项目计划、配置、依赖、接口、页面或协作规范，都需要在这里记录。

每条记录建议说明：

- 修改时间（精确到分钟并包含时区，例如 `2026-06-03 14:07 CST +0800`）
- 修改内容
- 影响文件
- 修改原因
- 后续注意事项

后续新增记录必须使用 `YYYY-MM-DD HH:mm 时区` 作为二级标题；同一天内多次修改也不要按天合并。历史按日期记录可以保留，但新的修改需要单独记录到分钟。

公开仓库安全规则：涉及具体定价、单位成本、利润、预算、额度参数、投放数据、增长假设或其他商业机密的修改，只能在 changelog 中记录高层能力边界，不得写入具体数字、公式或可反推出经营策略的细节。

## 2026-06-13 20:23 CST +0800

### open-core 分离 Phase 3a：社区版 Docker 一键运行

- 新增根目录 `docker-compose.yml` + `backend/Dockerfile` + `frontend/Dockerfile` 及两份 `.dockerignore`：`docker compose up --build` 即可拉起社区版整栈。
- 社区默认零密钥可跑：compose 默认 `PZ_EDITION=community`、`DEFAULT_PROVIDER=mock`、`SEARCH_PROVIDER=mock`，SQLite 落在命名卷 `pz_data:/data`；要用真实模型可在 compose 写服务端 Key，或在工作台用 BYOK 自带 Key。
- 后端镜像安装 Playwright Chromium 以支持服务端 PDF 导出；前端镜像在构建期注入 `NEXT_PUBLIC_API_BASE_URL`，Clerk publishable key 可选（缺省走访客模式）。
- 镜像不内置任何密钥；`.dockerignore` 排除 `.env`、`.venv`、`node_modules`、本地数据库等。
- 验证：本机未安装 docker，仅用 YAML 解析校验 `docker-compose.yml` 语法通过；完整 `docker compose up --build` 冒烟需在装有 Docker 的环境执行。
- 影响文件：新增 `docker-compose.yml`、`backend/Dockerfile`、`backend/.dockerignore`、`frontend/Dockerfile`、`frontend/.dockerignore`。
- 后续：Phase 3b 前端在社区版补 BYOK API Key 输入（provider/model 选择已随 `selection_enabled` 自动暴露）。

## 2026-06-13 17:21 CST +0800

### open-core 分离 Phase 2：社区版 BYOK（自带 API Key）

- `ResearchRequest` 新增 `api_key`/`base_url` 字段，均标记 `Field(exclude=True, repr=False)`，使 `model_dump()/model_dump_json()` 默认不含凭据 → 天然不进数据库持久化与 SSE payload。
- `ProviderFactory.create` 新增 `api_key`/`base_url` 覆盖参数，为空时回退服务端 `Settings`；`AgentRuntime.run` 与报告续跑路径都把请求凭据透传给工厂。
- `missing_provider_requirements` 新增 `api_key_override`：社区版用户自带 Key 时即视为该 Provider 已就绪。
- `create_research_job`：仅 community 版读取客户端 `api_key`/`base_url` 作为覆盖并据此判定就绪；cloud 版强制剥离，维持版本化生产路由与服务端密钥。
- 测试先行：`backend/tests/test_byok.py` 覆盖工厂覆盖/回退、`ResearchRequest` 序列化不含凭据、Runtime 透传、community 透传且不落库/不进响应体、cloud 忽略客户端 Key、无服务端 Key 时社区版凭自带 Key 创建成功；并补齐 runtime 测试桩 `create` 的新签名。后端 pytest 全绿（137 通过）。
- 影响文件：`backend/app/agent/schemas.py`、`backend/app/agent/providers/factory.py`、`backend/app/agent/runtime.py`、`backend/app/config.py`、`backend/app/api/routes.py`、`backend/tests/test_byok.py`、`backend/tests/test_agent_runtime.py`、`project-docs/testing-guide.md`。
- 安全红线：BYOK 凭据全程仅在请求体与内存流转，`exclude=True` + `redact_sensitive` 双保险；现有「数据库/SSE/日志不得出现 API Key」约束持续生效。
- 后续：Phase 3 提供 Docker 一键运行与前端按 edition 暴露 provider/model/Key 输入。

## 2026-06-13 16:02 CST +0800

### open-core 分离 Phase 1：引入 `PZ_EDITION` 接缝

- `Settings` 新增 `edition` 字段，`get_settings` 读取 `PZ_EDITION` 环境变量（小写，非法值回退 `community`，默认 `community`）。
- `resolve_model_route` 新增 community 分支：社区版作为单用户自托管工具，始终尊重客户端 provider/model（`routing_version=community`、`selection_enabled=True`）；cloud 版维持版本化生产路由，仅内部 `manual` 模式可用于 mock/联调。
- `/api/readiness` 返回当前 `edition`，便于前端按版切换 UI；不泄露任何密钥。
- `.env.example` 默认 `PZ_EDITION=community` 并注释两版差异；本地 `.env`（gitignored）设 `PZ_EDITION=cloud` 以保持现有云端行为不变。
- 测试先行：`test_config.py` 新增 edition 默认/读取/非法回退/community 路由用例，并把生产路由用例显式标 `edition=cloud` 去除对 `.env` 的隐式依赖；`test_api.py` 新增社区版尊重客户端 provider 的创建用例与 readiness `edition` 断言。后端 pytest 全绿（130 通过）。
- 影响文件：`backend/app/config.py`、`backend/app/api/routes.py`、`backend/tests/test_config.py`、`backend/tests/test_api.py`、`.env`、`.env.example`、`project-docs/testing-guide.md`。
- 后续：Phase 2 基于社区版接缝实现 BYOK（用户自带 API Key，绝不落库/日志/SSE）。

## 2026-06-13 15:54 CST +0800

### open-core 分离 Phase 0：私有商业文档泄露守卫

- 新增 `backend/scripts/check_no_secrets_tracked.py`：当 `project-docs/business-model.md` 或 `project-docs/private/` 被 git 跟踪或暂存时报错退出（退出码 1），正常时退出码 0。守卫路径常量与 `.gitignore` 的「Private business planning」段保持同步，可用于 CI 或可选 pre-commit。
- 先写测试 `backend/tests/test_secret_guard.py`（在临时 git 仓中验证 force-add 商业文档触发失败、干净仓库通过），确认未实现前失败、实现后通过。
- 复核确认 `backend/app` 与 `frontend/src` 无任何源码引用商业机密路径。
- 背景：此前商业资料仅靠 `.gitignore` 隔离，属「侥幸而非隔离」，本守卫为 open-core 社区/云端分离的第一道防泄露闸。
- 影响文件：新增 `backend/scripts/check_no_secrets_tracked.py`、`backend/tests/test_secret_guard.py`；更新 `project-docs/testing-guide.md`。
- 后续：Phase 1 引入 `PZ_EDITION` 接缝，Phase 2 实现 BYOK。

## 2026-06-13 15:04 CST +0800

### 正式接入 HeroUI v3，并修复认证阻塞

- 按官方 HeroUI v3.1.0 方案安装并接入 `@heroui/react`、`@heroui/styles` 与 Tailwind CSS v4；`globals.css` 按要求先导入 Tailwind，再导入 HeroUI styles，不增加旧版 `HeroUIProvider`。
- 首页和研究工作台的基础交互迁移到 HeroUI `Button`、`Tabs`、`Card`、`TextArea`、`Modal`、`Tooltip`、`Spinner`、`Accordion`。
- 删除原自定义通用按钮 CSS；PZ 样式只负责品牌 token、玻璃视觉、页面布局、报告排版和研究业务组件。
- 抽出 `research-sources.tsx` 与 `research-workspace-panels.tsx`，集中维护来源解析、来源卡片、引用 Tooltip、侧栏、桌面来源栏和移动端来源 Modal，降低 `ResearchWorkspace` 的职责。
- 修复 Clerk 初始化 fail-open：应用先以访客模式可用，Clerk 控件动态加载并在 3 秒后降级；认证状态更新改为幂等，`onReady` 回调保持稳定，避免 React 最大更新深度错误。
- 修复活动任务恢复请求挂起导致提交永久锁定的问题，4 秒后自动清理失效任务并恢复输入。
- 修复 HeroUI Tabs 指示器拦截相邻 Tab 点击的问题，装饰 indicator 不再接收 pointer events。
- Playwright 增加 Clerk 失败、访客降级、Tabs 和恢复超时测试；测试端口可配置，并支持把浏览器 API 请求路由到隔离 mock 后端。
- 正式接入后删除根目录 `HeroUI Design System/` 参考资料，以及未使用的 `frontend/public/heroui-mark*.svg`；PZ 品牌标志继续使用自有 `BrandMark`。

### 依赖

- `@heroui/react 3.1.0`
- `@heroui/styles 3.1.0`
- `tailwindcss 4.3.1`
- `@tailwindcss/postcss 4.3.1`
- `postcss 8.5.15`

### 验证

- `npm run lint` 通过。
- `npx tsc --noEmit` 通过。
- Clerk 失败与恢复超时 Playwright：3 个用例通过。
- Playwright Chromium 完整套件通过：11 个用例，覆盖取消、刷新恢复、历史、重跑、Markdown/PDF 导出、失败重试、Clerk 失败降级、HeroUI Tabs、恢复超时和移动端来源 HeroUI Modal。

### 影响文件

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/postcss.config.mjs`
- `frontend/playwright.config.ts`
- `frontend/src/app/globals.css`
- `frontend/src/app/home.css`
- `frontend/src/app/workbench/workbench.css`
- `frontend/src/components/app-auth-provider.tsx`
- `frontend/src/components/auth-controls.tsx`
- `frontend/src/components/clerk-controls.tsx`
- `frontend/src/components/home-page.tsx`
- `frontend/src/components/research-mode-tabs.tsx`
- `frontend/src/components/research-sources.tsx`
- `frontend/src/components/research-workspace-panels.tsx`
- `frontend/src/components/research-workspace.tsx`
- `frontend/e2e/research-flow.spec.ts`
- `frontend/e2e/ui-resilience.spec.ts`
- `README.md`
- `README.zh-CN.md`
- `project-docs/`

## 2026-06-13 13:41 CST +0800

### 接入 HeroUI / Prism 设计系统，替换临时前端

- 用 Claude Design 产出的 Prism 设计（深色"液态玻璃"质感 + 光谱渐变 + 三棱镜标志）替换原临时前端，品牌名沿用 **PZ Deep Research**（设计稿中的 Prism 文案已全部替换/翻译）。
- 引入 HeroUI 的 Inter（UI/展示）与 Fira Code（代码/等宽）网络字体，复制到 `frontend/public/fonts/` 并附 `LICENSE.txt`（两款均 SIL OFL 1.1，可免费商用、嵌入与再分发）。
- `globals.css` 重写为 Prism 基础层：玻璃/流光边框（flow-ring）/渐变文字/按钮/chip/shimmer 等基元，以及研究报告 Markdown 渲染与行内引用悬浮卡样式。设计仅依赖纯 CSS 类，**未引入 `@heroui/react` 运行时依赖**。
- 新增**多语言切换（中 / 英）**：`I18nProvider` + `useI18n` + 完整中英词典，localStorage 持久化、SSR 安全、自动同步 `<html lang>`；语言切换器布置在首页导航栏与工作台顶栏。默认中文。
- 新增**营销落地页**（路由 `/`）：Hero / 研究领域 / 工作原理 / 模式 / 报告预览 / FAQ / CTA / 页脚，全部接入 i18n。
- **研究工作台移至 `/workbench`**，组件重写为 empty / run / report / failed 状态机布局 + 侧栏常驻历史 + 右侧来源栏，并**完整保留原有功能逻辑**：SSE 鉴权流式、Clerk 登录、任务取消 / 重跑 / 失败重试、刷新恢复、Markdown / PDF 导出、模型 provider 选择。
- 首页 → 工作台的查询/模式 handoff：首页提问后跳转工作台自动开跑（localStorage 一次性传递）。
- `AccountControl` 适配新侧栏 user-card 样式，并接入 i18n。

### 依赖

- 无新增运行时依赖（设计为纯 CSS；未引入 HeroUI React 组件库）。

### 验证

- 前端 `npx tsc --noEmit` 通过；`npm run lint` 通过；`npm run build` 通过（`/` 与 `/workbench` 两路由静态产出）。
- 双语可视化冒烟：首页与工作台在中/英下渲染正常，字体与玻璃质感生效，`document.documentElement.lang` 随切换更新。
- Playwright Chromium：E2E 套件按新 UI/路由重写，**重点覆盖英文界面**（中文为同词典翻译，不再重复测），7 个用例全部通过 —— 取消、刷新恢复、历史、重跑、Markdown/PDF 导出、失败重试均未回归。报告正文断言仍校验 mock 后端生成的 `核心结论`。

### 影响文件

- `frontend/src/app/globals.css`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/home.css`
- `frontend/src/app/workbench/page.tsx`
- `frontend/src/app/workbench/workbench.css`
- `frontend/src/components/home-page.tsx`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/components/brand-mark.tsx`
- `frontend/src/components/language-switch.tsx`
- `frontend/src/components/app-auth-provider.tsx`
- `frontend/src/lib/i18n.tsx`
- `frontend/src/lib/handoff.ts`
- `frontend/public/fonts/`（Inter ×6、Fira Code ×4、`LICENSE.txt`）
- `frontend/public/heroui-mark.svg`、`frontend/public/heroui-mark-white.svg`
- `frontend/e2e/research-flow.spec.ts`

### 后续注意事项

- 工作台路由已从 `/` 改为 `/workbench`；任何外部链接、书签或文档若指向旧的根工作台需同步更新。
- 词典是中文为准、英文镜像（`frontend/src/lib/i18n.tsx`）：新增文案需两种语言同时补齐，否则 `Dict` 结构不一致会触发类型错误。
- 设计原始素材目录 `HeroUI Design System/` 暂保留在仓库根（未纳入构建），待审查确认后再决定移除；如保留需注意它不应被打包或泄露。
- 营销首页的"研究领域"中除"学术"外均为占位（SOON），尚未接后端字段路由。

## 2026-06-13 12:50 CST +0800

### 私有商业资料与公开仓库隔离

- 将商业规划文档加入 `.gitignore`，避免定价、成本、利润、预算、投放和增长假设进入公开 Git 历史。
- 清理公开协作文档中的具体经营参数，只保留额度、支付、成本保护和账务一致性等产品与工程方向。
- README 不链接本地私有资料，避免 GitHub 出现无效链接或泄露内部资料结构。
- 后续 changelog 只记录商业化能力边界和工程变化，不记录具体价格、成本、阈值、毛利或投放数据。

### 影响文件

- `.gitignore`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/changelog.md`

## 2026-06-11 11:43 CST +0800

### Clerk 登录与账号历史绑定

- 按测试优先原则新增 Clerk JWT 和账号历史测试，再实现登录链路。
- 后端新增 `ClerkAuthenticator`：
  - 本地验证 RS256 会话 JWT 的签名、有效期、`sub` 和 `azp`。
  - 支持 `CLERK_JWT_KEY`、`CLERK_AUTHORIZED_PARTIES` 和时钟偏差配置。
  - 未登录请求继续使用浏览器匿名访客 ID；登录请求使用 Clerk `sub` 作为可信 `user_id`。
- 登录后的首个受保护请求会自动调用 `claim_anonymous_jobs`，把当前浏览器尚未归属账号的任务单向认领到用户。
- 历史、详情、事件、取消、重跑、失败重试、PDF 导出和 SSE 全部按访客或账号身份过滤；其他账号访问返回 404。
- 前端接入可选 `ClerkProvider`、登录弹窗和账号按钮。未配置 Clerk 时保持访客模式，不阻塞现有本地开发和 E2E。
- 所有受保护 API 请求会同时携带匿名访客 ID 和可选 Bearer token。
- 原生 `EventSource` 替换为基于 `fetch` / ReadableStream 的鉴权 SSE 客户端，支持 Authorization 请求头、事件游标和断线重连，不把会话 token 放进 URL。
- 账号切换后自动恢复当前任务并刷新历史；已归并任务退出登录后不会退回访客历史。
- 新增 `project-docs/auth-setup.md`，记录 Clerk Dashboard、本地环境变量、匿名历史归并规则和生产注意事项。
- 本地 `.env` 与 `frontend/.env.local` 已预留 Clerk 配置位置，当前为空，因此运行界面显示访客模式。

### 依赖

- 前端新增 `@clerk/nextjs 7.5.1`。
- 后端新增 `PyJWT 2.13.0` 与 crypto 支持。

### 验证

- 后端 pytest：122 个用例通过。
- 身份、API 和配置定向 pytest：44 个用例通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- Playwright Chromium：7 个 E2E 用例通过，取消、刷新恢复、历史、重跑、错误重试和 Markdown/PDF 导出未回归。
- Chromium 页面冒烟检查：访客账号区正常显示，控制台错误为 0。
- Neon readiness：数据库 `ready=true`；因 Clerk 公钥尚未填写，认证 `ready=false`，符合预期。

### 影响文件

- `.env.example`
- `README.md`
- `README.zh-CN.md`
- `backend/app/auth.py`
- `backend/app/api/routes.py`
- `backend/app/config.py`
- `backend/app/storage/`
- `backend/requirements*.txt`
- `backend/tests/`
- `frontend/.env.example`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/app/`
- `frontend/src/components/`
- `frontend/src/lib/api.ts`
- `project-docs/`

## 2026-06-11 11:18 CST +0800

### Neon 恢复分支演练通过

- 从 `production` 当前时刻创建 `restore-drill-20260611`，设置 1 天后自动删除。
- 在本地 `.env` 使用独立临时变量保存恢复分支 pooled/direct 连接，没有覆盖正式 `DATABASE_URL` 或 `DATABASE_MIGRATION_URL`。
- 只读检查确认恢复分支与 production 是不同连接目标，pooled 和 direct 连接均正常。
- 数据完整性对比通过：
  - 两边均有 2 个研究任务。
  - Alembic 版本均为 `20260611_04`。
  - 最新报告均为 `completed`、3298 字、16 条事件。
- `restore_snapshot_matches=true`。
- 本次当前时刻分支恢复的 RPO 近似为 0，从创建分支到验证通过约 5 分钟。
- 指定历史时间点恢复和 `pg_dump` / `pg_restore` 独立恢复仍待后续演练。

### 影响文件

- `.env`（仅本地临时变量，不提交）
- `project-docs/neon-backup-restore.md`
- `project-docs/changelog.md`

## 2026-06-11 11:04 CST +0800

### GPT 生产路由与 Neon 重启恢复验收

- 按“先测试、后实现”增加生产路由测试，确认生产模式忽略客户端 Provider/模型参数，内部手动模式仍可用于 mock 和模型联调。
- 默认生产路由固定为 `openai-default-v1`：
  - 搜索词规划和最终报告：OpenAI `gpt-5.4-mini`
  - 证据卡片：OpenAI `gpt-5-nano`
- 新增 `MODEL_ROUTING_MODE`、`PRODUCTION_PROVIDER`、`PRODUCTION_MODEL`、`MODEL_ROUTING_VERSION`。
- 生产模式下前端不提交 Provider/模型，并隐藏研究页、历史列表和报告详情中的模型选择或实现信息。
- 新增 `research_jobs.routing_version` 和 Alembic `20260611_04`；重跑与失败重试复用原任务路由版本。
- 内部手动模式使用 `MODEL_ROUTING_MODE=manual`；Playwright mock E2E 已显式切换为该模式。
- Playwright 服务同时覆盖 `DATABASE_URL` 与 `DATABASE_MIGRATION_URL` 到同一个临时 SQLite，避免测试运行库与迁移库分离、误连接 Neon。
- 在真实 Neon PostgreSQL 执行 `20260611_04` 迁移并重启后端。
- 重启恢复验证通过：任务 `c5db24ca5f5c4ffcbf9166b2e019272a` 保持 `completed`，3298 字报告和 16 条事件均可通过 API 完整恢复。
- 新增 `project-docs/neon-backup-restore.md`，规定使用非生产恢复分支进行时间点恢复演练，并预留 `pg_dump` 独立备份方案。
- 模型质量测试暂缓；后续恢复时以 `openai-default-v1` 为基线发布新路由版本。

### 验证

- 后端 pytest：114 个用例通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- Playwright Chromium：7 个 E2E 用例通过。
- Chromium 冒烟验证：研究界面正常，Provider/模型选择器为 0，控制台错误为 0。
- `/api/models` 返回 `selection_enabled=false`、`routing_version=openai-default-v1`、默认 Provider `openai`。
- `backend/scripts/check_database.py` 返回 `database=ready`、`backend=postgresql`。

### 影响文件

- `.env.example`
- `README.md`
- `README.zh-CN.md`
- `backend/app/config.py`
- `backend/app/agent/schemas.py`
- `backend/app/api/routes.py`
- `backend/app/storage/memory.py`
- `backend/app/storage/sql.py`
- `backend/migrations/versions/20260611_04_add_model_routing_version.py`
- `backend/tests/`
- `frontend/playwright.config.ts`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `project-docs/`

## 2026-06-10 23:58 CST +0800

### Neon PostgreSQL 已启用

- 在本地 `.env` 中补充 Neon 运行连接、迁移连接和连接池配置项；连接字符串及密码不进入版本控制或文档。
- 使用 pooled URL 作为 `DATABASE_URL`，使用 direct URL 作为 `DATABASE_MIGRATION_URL`。
- 已在 Neon 执行全部 Alembic 迁移，数据库版本升级至 `20260610_03`。
- 已验证 `/health`、`/api/readiness` 和 `backend/scripts/check_database.py`；数据库状态为 `ready`，后端类型为 `postgresql`。
- 当前 Neon 为全新数据库，原本地 SQLite 测试历史未自动迁移。

### 影响文件

- `.env`（仅本地，不提交）
- `project-docs/changelog.md`

## 2026-06-10 21:23 CST +0800

### 产品化错误、失败重试与 PostgreSQL 生产准备

- 按“先测试、后实现”补充错误分类、API 重试、Runtime 检查点、数据库配置和 Playwright E2E 用例；新测试先验证失败，再完成实现。
- 新增统一产品错误层，把网络异常、服务过载、超时、资料不足、积分不足、内容不支持和系统异常映射为稳定错误码与 C 端文案。
- Runtime 或 Provider 的原始异常不再进入用户 API、SSE 和历史错误字段；工程日志保留任务、Provider、模型、阶段和原始异常，并在写日志前遮蔽疑似 API Key。
- `research_jobs` 新增 `error_code`、`error_retryable`、`error_stage` 和 `retry_context`，并增加 Alembic `20260610_03` 迁移。
- Runtime 在完成最终选源后生成私有报告检查点。API 只把检查点写数据库，不写历史事件、不推送前端。
- 新增 `POST /api/research-jobs/{job_id}/retry`：
  - 仅接受 `failed + error_retryable=true` 的任务。
  - 报告阶段且存在检查点时，从已选来源和证据卡片重新生成报告，不重复 search / visit。
  - 其他阶段或检查点缺失时，创建独立新任务并完整重新研究。
- 前端 API 层不再直接展示 `response.text()`；断网和非 JSON 服务错误会转为产品化提示。
- 失败任务只在错误提示旁显示一个“重试”按钮；成功或取消任务详情继续使用“重新运行”，两种语义不混用。
- 数据库配置新增：
  - `DATABASE_MIGRATION_URL`
  - `DATABASE_POOL_SIZE`
  - `DATABASE_MAX_OVERFLOW`
  - `DATABASE_POOL_TIMEOUT_SECONDS`
  - `DATABASE_POOL_RECYCLE_SECONDS`
- Neon/PostgreSQL 使用 pooled URL 承载应用请求、direct URL 执行 Alembic 迁移；PostgreSQL 连接池启用 `pool_pre_ping`。
- `/api/readiness` 新增数据库 `SELECT 1` 检查，只返回可用状态和数据库类型。
- 新增 `backend/scripts/check_database.py`，用于安全检查数据库连接，不打印 URL 或密码。
- Playwright 配置新增 `PLAYWRIGHT_REUSE_SERVERS=1`，需要时可复用当前唯一的 `8000/3000` 服务，避免测试再启动第二套进程。

### 影响文件

- `.env.example`
- `README.md`
- `README.zh-CN.md`
- `backend/app/error_handling.py`
- `backend/app/agent/runtime.py`
- `backend/app/agent/schemas.py`
- `backend/app/api/routes.py`
- `backend/app/config.py`
- `backend/app/storage/memory.py`
- `backend/app/storage/sql.py`
- `backend/migrations/versions/20260610_03_add_product_errors_and_retry_context.py`
- `backend/scripts/check_database.py`
- `backend/tests/`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `frontend/e2e/research-flow.spec.ts`
- `frontend/playwright.config.ts`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 后端 pytest：111 个用例通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。
- Playwright Chromium：7 个 E2E 用例通过。
- 本地 Alembic 已升级到 `20260610_03`。
- `backend/scripts/check_database.py` 返回 `database=ready`、`backend=sqlite`。
- `/health` 返回正常；`/api/readiness` 返回数据库 `ready=true`。

### 用户需要完成

- 当前本地 SQLite 已可直接使用，不需要额外操作。
- 准备切换 Neon 时，在 Neon 控制台创建项目并把 pooled connection string 填入 `.env` 的 `DATABASE_URL`，把 direct connection string 填入 `DATABASE_MIGRATION_URL`。
- 填写后重启后端；启动时会自动运行 Alembic。再执行 `cd backend && PYTHONPATH=. .venv/bin/python scripts/check_database.py` 验证连接。
- Neon 账号、项目和连接串需要由用户创建；不要把数据库密码提交到 Git。

## 2026-06-10 19:26 CST +0800

### 全量文档一致性更新

- 统一中英文 README 的产品定位：后台保留 OpenAI、Claude、Gemini，多模型能力不直接暴露给正式 C 端。
- 明确当前 MVP 的 Provider/模型选择器仅用于开发联调和质量评测；分阶段生产模型路由已经进入计划，但尚未实现。
- 将后续模型测试从全面 Provider/模式回归矩阵调整为四类任务质量测试：
  - 意图识别与追问
  - 搜索词与工具规划
  - 证据卡片生成
  - 最终报告撰写
- 重写测试指南中的旧 ReAct 工具纠偏描述，使其与当前 Runtime 驱动的有界访问漏斗一致。
- 更新当前验证状态：后端 pytest 100 个用例通过，Playwright Chromium 6 个 E2E 用例通过。
- 更新 OpenAI、Claude、Gemini 的真实调用状态：三家已完成不同程度的人工验证，但尚未形成可重复分阶段质量测试集。
- 明确当前重新运行沿用内部 Provider/模型配置；生产路由完成后需要保存并复用 `routing_version` 和各阶段实际模型。
- API Key 文档区分当前单主模型开发联调与未来后台多阶段路由所需的部署配置。
- 更新依赖文档中的真实 Provider 联调状态，并保留 SDK 升级后重新验证的要求。
- 明确当前只有 OpenAI 接入原生 token streaming，Claude/Gemini 仍使用兼容封装。

### 影响文件

- `README.md`
- `README.zh-CN.md`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/dependency-management.md`
- `project-docs/api-key-setup.md`
- `project-docs/changelog.md`

### 未修改文件

- `LICENSE`：本次没有许可变更。
- `NOTICE`：本次没有上游参考、归属或第三方声明变更。
- `.env.example`：分阶段模型路由尚未工程实现，本次不提前增加无效环境变量。

## 2026-06-10 19:18 CST +0800

### 前端端到端验证

- 使用 mock Provider 在固定端口 `8000/3000` 运行 Playwright Chromium 测试。
- 6 个用例全部通过，覆盖任务取消、刷新续跑、完成报告恢复、历史详情、重新运行、Markdown 导出和 PDF 导出。
- 本轮测试不调用真实模型、SerpAPI 或 Jina，不产生第三方 API 费用。
- 测试结束后已恢复真实开发服务：后端 `http://127.0.0.1:8000`，前端 `http://127.0.0.1:3000`。
- 对恢复后的页面完成 Chromium 冒烟检查：页面有有效内容、核心工作台正常渲染，无 Next.js 错误覆盖层或浏览器控制台错误。

## 2026-06-10 19:12 CST +0800

### 产品与测试策略调整

- 暂不实施以“所有 Provider × 所有研究模式”为中心的全面回归测试矩阵。
- 下一阶段改为分职责质量测试，分别评估意图识别与追问、搜索词与工具规划、证据卡片生成、最终报告撰写。
- 每个环节根据准确率、结构化输出稳定性、引用与格式服从度、延迟和成本选择生产模型。
- 正式 C 端产品目标是不提供 Provider 或模型切换；用户只选择研究模式，后续由 Runtime 在后台自动完成模型编排。该路由能力尚未工程实现。
- 当前前端的 Provider/模型下拉框继续作为开发联调工具，后续从生产界面移除；内部测试、管理员配置和故障降级仍保留多 Provider 能力。
- Provider、模型和路由版本继续写入任务日志，用于质量追踪、成本分析和问题回溯。

### 影响文件

- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/changelog.md`

## 2026-06-09 16:57 CST +0800

### 问题来源

- 任务 `6d27a3fb230948fa89f3e43053163053` 已完成搜索、10 个全文来源访问、证据卡片和来源筛选。
- 最终报告调用 `gemini-3.5-flash` 时连续返回 `503 UNAVAILABLE / high demand`；旧配置仅重试 1 次且没有退避，因此任务失败。
- Gemini 和 Claude 的证据抽取此前回退到前端选择的主模型，成本较高，也会增加主模型的负载与临时过载概率。

### 修改

- 默认 `LLM_MAX_RETRIES` 从 1 调整为 3，新增 `LLM_RETRY_BASE_DELAY_SECONDS=2`。
- Runtime 新增临时错误分类，只对超时、429、408/409、5xx、`UNAVAILABLE`、`RESOURCE_EXHAUSTED`、过载和连接重置等错误重试，默认指数退避 2、4、8 秒。
- 400 模型名错误、参数错误等永久错误不再重复请求。
- 报告生成的临时错误重试复用已选来源和证据卡片；`llm_retry` 事件记录 `stage=report`、`resume_from=selected_evidence`，不会重新搜索或访问。
- 流式报告中途失败时先发送 `report_reset`，清除不完整草稿后从同一证据上下文重新生成。

### 证据模型

- OpenAI：`EVIDENCE_EXTRACTION_MODEL=gpt-5-nano`。
- Claude：新增 `ANTHROPIC_EVIDENCE_MODEL=claude-haiku-4-5-20251001`。
- Gemini：新增 `GEMINI_EVIDENCE_MODEL=gemini-2.5-flash-lite`。
- 前端选择的模型只用于搜索词与最终报告，证据抽取固定使用各 Provider 的低成本模型；并发数保持不变。

### 测试

- 新增 503 报告重试测试，确认 search 和 visit 均只执行一次，报告从 `selected_evidence` 继续。
- 新增永久错误不重试测试。
- 新增三家 Provider 证据模型选择测试。
- 重试与证据模型定向测试通过。
- Gemini Models API 虽仍列出 `gemini-2.0-flash-lite`，但真实生成接口返回 404 已下线；因此没有采用这个更便宜但不可调用的旧型号，改用当前可调用的最低成本稳定型号 `gemini-2.5-flash-lite`。
- 使用真实 API Key 完成证据抽取冒烟测试：
  - `claude-haiku-4-5-20251001` 成功返回非空证据卡片。
  - `gemini-2.5-flash-lite` 成功返回非空证据卡片。
- 后端全量 pytest：100 个通过，另有 1 个既有 Starlette/TestClient 弃用警告。
- 重启后端并确认运行配置已加载：`LLM_MAX_RETRIES=3`、退避基数 2 秒，以及三家低成本证据抽取模型均已生效。
- `http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`，前端可以继续连接现有 8000 后端测试。

### 影响文件

- `.env`
- `.env.example`
- `backend/app/config.py`
- `backend/app/api/routes.py`
- `backend/app/agent/runtime.py`
- `backend/tests/test_config.py`
- `backend/tests/test_agent_runtime.py`
- `project-docs/api-key-setup.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

## 2026-06-09 16:35 CST +0800

### 问题定位

- 检查重跑任务 `6540b86bc608495eb4b916b90cd8154f`：
  - 3 个英文搜索词、13 条滚动访问、13 张证据卡片均正常。
  - 最终选择 10 个来源，全部为 `full_text`，无降级或全文不足。
  - 修复后的报告上下文已不再无限累积：报告轮输入 token 为 6943、9683、9571，明显低于旧任务后两轮的 17600、26728。
  - Claude 三稿正文仍为 1778、1662、1665，唯一失败项仍是 `report_too_long`。
- 原因是普通重写请求仍附带完整证据卡片，Claude倾向根据证据重新扩写整篇报告，而不是只编辑上一稿。

### 修复

- 新增仅针对单一 `report_too_long` 的纯编辑压缩路径：
  - 只提供上一稿，不再重复注入证据卡片。
  - 禁止新增事实、案例、章节、来源或参考文献。
  - 要求保留原引用编号和 References 整节。
  - 根据当前正文计数动态计算目标保留比例和必须删除的最少字符数。
  - 明确要求删除引言套话、重复定义、次要案例、重复结论和冗余过渡句。
- 其他格式错误、引用错误或过短报告仍使用证据卡片重写路径，避免丢失事实依据。

### 验证

- 报告相关定向测试：8 个通过。
- 使用真实 `claude-sonnet-4-6` 验证纯压缩提示：
  - 1835 字样稿压缩为 1379 字，落入 deep 模式 1300-1500 区间。
  - `## References` 和 `[1]`、`[2]` 引用均保留。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/tests/test_agent_runtime.py`
- `project-docs/changelog.md`

## 2026-06-09 16:24 CST +0800

### 问题定位

- 检查任务 `a1f1ee1a6d604f44b7a3e1c8b2fed9f8` 的持久日志：
  - deep 模式完成 3 个搜索词、10 个来源访问、10 张证据卡片和 10 个最终来源筛选。
  - 9 个来源为全文证据，来源数量与最低全文证据线均达标。
  - 任务唯一失败项为 `report_too_long`；三次报告正文分别计数 1685、1820、1759，超过 1300-1500 的要求。
  - 报告重写把旧稿和整套证据持续追加进同一消息历史，单轮输入 token 从 8606 增至 17600、26728，导致费用和指令稀释同步增加。

### 修复

- 报告生成阶段改用独立上下文，不再携带搜索对话和工具候选历史。
- 每次报告重写都重新构造固定大小的 system/user 消息，不累计此前失败稿。
- 重写请求只保留当前待编辑稿、证据卡片和校验要求。
- 超长报告会明确给出超出量、至少删减量和区间中点目标；过短报告会给出缺少量和扩写目标。
- 字数提示与 Runtime 的实际计数口径对齐：汉字、英文字母和数字计入，Markdown 标记、标点、引用标记和 References 不计入。

### 测试

- 新增报告上下文有界回归测试，确认初稿和重写调用都只有独立的 system/user 消息。
- 验证报告阶段不再包含 `<tool_response>` 搜索历史。
- 验证 1600 字 deep 报告会收到“至少删减 200 个计数字符、压缩到约 1400 字”的定向要求。
- 报告与重写相关测试：8 个通过。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/tests/test_agent_runtime.py`
- `project-docs/technical-architecture.md`
- `project-docs/changelog.md`

## 2026-06-09 16:14 CST +0800

### 修改

- Claude 模型配置扩展为“默认模型 + 候选列表”：
  - 默认模型保持 `claude-sonnet-4-6`。
  - 新增 `ANTHROPIC_MODEL_OPTIONS`，候选包含 Sonnet 4.6、Opus 4.8 / 4.7 / 4.6 和 Haiku 4.5。
- Gemini 默认模型从 `gemini-2.5-flash` 升级为 `gemini-3.5-flash`。
- 新增 `GEMINI_MODEL_OPTIONS`，候选覆盖 Gemini 3.5 Flash、3.1 Pro Preview、3 Flash Preview、3.1 Flash-Lite 和 2.5 稳定系列。
- `/api/models` 现在向前端返回三家 Provider 的完整候选列表，Claude 和 Gemini 不再只有单一选项。
- 前端离线回退模型列表与后端默认配置同步。

### 新增

- 新增 `/api/models/anthropic`，通过 Anthropic Models API 查询当前账号实际可见模型。
- 新增 `/api/models/gemini`，通过 Gemini Models API 查询当前账号中支持 `generateContent` 的模型。
- 两个接口均返回 `configured`、`available` 和 `configured_available`，不输出 API Key。
- 新增 Claude、Gemini 候选配置和缺少 API Key 的接口测试。
- 新增 Anthropic Provider 请求结构测试，覆盖无 system message 时省略 `system` 字段，以及多条 system message 合并发送。

### 修复

- Anthropic Provider 不再向新版 Messages API 发送 `system=None`，修复无 system message 时真实调用返回 400 的问题。
- Claude、Gemini SDK 临时客户端在请求结束后显式关闭，避免连接泄漏和事件循环关闭警告。
- 修复 Gemini Models API 异步分页结果收集方式，避免 `/api/models/gemini` 返回 502。

### 联调

- 使用本地 `.env` 中的 Key 查询模型列表成功，未输出或修改 Key。
- Anthropic 当前账号确认可见 `claude-opus-4-8`、`claude-opus-4-7`、`claude-sonnet-4-6`、`claude-opus-4-6` 和 `claude-haiku-4-5-20251001`。
- Gemini 当前账号确认可见 `gemini-3.5-flash`、`gemini-3.1-pro-preview`、`gemini-3-flash-preview`、`gemini-3.1-flash-lite` 和 Gemini 2.5 系列候选。
- `/api/models/anthropic` 与 `/api/models/gemini` 真实接口均返回 200，配置候选全部出现在 `configured_available`。
- `claude-sonnet-4-6` 和 `gemini-3.5-flash` 均完成最小真实生成冒烟测试并返回 `OK`。
- 后端全量 pytest：96 个通过；前端 ESLint 和 Next.js 生产构建通过。
- 使用项目 Playwright Chromium 打开 `http://127.0.0.1:3000`，确认 Claude 5 个、Gemini 7 个模型选项完整显示，页面无 console error 或 page error。
- 8000 后端已重启并加载新 `.env`，`/health` 正常，`/api/models` 默认 Gemini 已更新为 `gemini-3.5-flash`；3000 前端保持运行。

### 影响文件

- `.env`
- `.env.example`
- `backend/app/agent/providers/anthropic_provider.py`
- `backend/app/agent/providers/gemini_provider.py`
- `backend/app/config.py`
- `backend/app/api/routes.py`
- `backend/tests/test_anthropic_provider.py`
- `backend/tests/test_config.py`
- `backend/tests/test_api.py`
- `frontend/src/components/research-workspace.tsx`
- `project-docs/api-key-setup.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

## 2026-06-09 14:53 CST +0800

### 新增

- 新增受访客权限保护的 PDF 导出接口：`GET /api/research-jobs/{job_id}/export/pdf`。
- 新增后端 `PdfExporter`：
  - 使用 `markdown-it-py 4.2.0` 将报告转换为安全打印 HTML。
  - 使用 Playwright `1.60.0` 和用户目录 Chromium 生成 A4 PDF。
  - PDF 包含产品名、研究问题、研究模式、模型、生成时间、任务 ID、分页和页码。
  - 原始 HTML 不执行，图片规则禁用，Chromium Context 阻断全部网络请求。
  - 默认并发上限 2、总超时 45 秒。
- 新增前端 PDF 下载按钮、生成中状态和错误提示。
- 新增 PDF 文件名清理、API 权限、空报告、渲染失败、安全 HTML 和真实 Chromium 文件测试。

### 修改

- CORS 暴露 `Content-Disposition`，前端可以读取 UTF-8 下载文件名。
- `.env.example` 新增 PDF 并发、超时和可选 Chromium 路径配置。
- 后端锁定 `playwright 1.60.0`、`markdown-it-py 4.2.0`、`pyee 13.0.1` 和 `mdurl 0.1.2`。
- README 启动命令增加 Chromium 安装，并把 Uvicorn reload 范围收窄到 `backend/app`，避免依赖安装触发重复热重载。
- 更新产品文档、项目计划、技术架构、测试指南和依赖管理。

### 验证

- 后端全量 pytest：92 个通过，包含真实 Chromium PDF 生成。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Playwright Chromium：6 个 E2E 全部通过，包含正式 PDF 下载。
- `pip check`：无破损依赖。
- 使用真实 Chromium 生成中文样例 PDF 并完成首屏视觉检查；标题、任务元数据、列表、表格、References、页边距和页码显示正常。

### 当前边界

- 每次 PDF 导出会启动一个短生命周期 Chromium；当前以并发上限控制资源，后续高并发部署可改为浏览器池或独立导出 Worker。
- 生产环境必须安装与 Playwright 版本匹配的 Chromium 和系统依赖。
- 当前 PDF 使用固定 PZ Deep Research 样式，尚未提供用户自定义封面、品牌模板或 Word 导出。

### 影响文件

- `.env.example`
- `backend/app/reporting/`
- `backend/app/api/routes.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/requirements.txt`
- `backend/requirements-lock.txt`
- `backend/tests/`
- `frontend/src/lib/`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `frontend/e2e/research-flow.spec.ts`
- `README.md`
- `README.zh-CN.md`
- `project-docs/`

## 2026-06-09 14:18 CST +0800

### 新增

- 新增研究报告 Markdown 导出按钮，报告为空时禁用，存在报告时可直接下载。
- 新增 `frontend/src/lib/markdown-export.ts`：
  - 使用 UTF-8 `text/markdown` Blob 导出当前原始报告。
  - 文件名根据研究问题生成，保留中文并清理跨平台非法字符。
  - 报告末尾保证至少一个换行。
- 新增 Playwright Markdown 下载测试，校验按钮状态、文件名、扩展名、中文内容、Markdown 标题和换行。

### 修改

- ESLint 忽略 `playwright-report/` 和 `test-results/`，避免失败测试生成的第三方报告代码污染项目 lint。
- 更新中英文 README、产品文档、项目计划、技术架构和测试指南，将 Markdown 导出标记为阶段 4 已完成能力。

### 方案说明

- 导出采用纯前端实现，不新增后端 API，不重新调用模型，也不修改当前报告中的引用和参考文献。
- 历史详情恢复出的报告与刚完成的报告共用同一导出入口。

### 验证

- 后端全量 pytest：85 个通过。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Playwright Chromium：5 个 E2E 全部通过，包含历史详情恢复后的 Markdown 下载。

### 影响文件

- `frontend/src/lib/markdown-export.ts`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `frontend/e2e/research-flow.spec.ts`
- `frontend/eslint.config.mjs`
- `README.md`
- `README.zh-CN.md`
- `project-docs/`

## 2026-06-09 10:03 CST +0800

### 新增

- 新增终态研究任务重新运行 API：按原问题、模式、Provider 和模型创建独立任务。
- 新增 `rerun_of_job_id` 任务血缘字段、数据库索引和第二个 Alembic 迁移。
- 新增报告详情视图，展示状态、研究模式、模型、创建/更新时间、完整任务 ID、来源任务 ID 和研究日志。
- 新增前端“重新运行”交互，新任务创建后自动切回研究页并续接 SSE。
- 新增后端重跑、访客隔离、运行中拒绝重跑和 SQL 血缘持久化测试。
- 新增 Playwright 报告详情与重新运行端到端验收。

### 修改

- 历史记录点击行为从“直接回填研究表单”改为进入独立报告详情。
- 重新运行只允许 `completed`、`failed`、`cancelled` 终态任务；`queued` / `running` 返回 409。
- 初始 Alembic 基线校验改为要求必需列子集，允许旧数据库已包含后续迁移列，避免重复迁移卡住。
- 更新中英文 README、产品文档、项目计划、技术架构和测试指南。

### 验证

- 后端全量 pytest：85 个通过。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Playwright Chromium：4 个 E2E 全部通过。
- Alembic SQLite 升级和离线 SQL 生成通过。

### 当前边界

- 当前历史仍绑定浏览器匿名访客 ID，不是账号体系；未来登录后需要把匿名任务归并到可信 `user_id`。
- 重新运行会创建全新任务，不覆盖原报告；原任务和新任务都保留在历史中。
- 阶段 4 仍需完成 Markdown 导出、真实多模型回归、真实 PostgreSQL 验收和关键视口视觉回归。

### 影响文件

- `backend/app/agent/schemas.py`
- `backend/app/api/routes.py`
- `backend/app/storage/`
- `backend/migrations/`
- `backend/tests/`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/lib/`
- `frontend/src/app/globals.css`
- `frontend/e2e/research-flow.spec.ts`
- `README.md`
- `README.zh-CN.md`
- `project-docs/`

## 2026-06-08 20:21 CST +0800

### 新增

- 新增 SQLAlchemy 异步持久化存储 `SqlJobStore`：
  - 本地默认使用 SQLite。
  - 通过 `DATABASE_URL` 支持 PostgreSQL/psycopg。
  - 持久化任务、事件、报告草稿、最终报告和错误状态。
- 新增 `research_jobs` / `research_events` 数据模型与索引。
- 新增 Alembic 初始迁移，支持 SQLite 执行和 PostgreSQL SQL 生成。
- 应用启动时自动执行 Alembic `upgrade head`；产品数据库不使用 `create_all` 建表，避免迁移版本缺失。
- 新增按匿名访客隔离的研究历史 API 和前端历史视图。
- 新增匿名历史归并到未来账号 `user_id` 的存储层能力。
- 新增服务重启恢复规则：遗留 queued/running 任务标记为失败并记录 `service_restarted` 事件。
- 新增 6 个数据库测试和历史 API/归属测试。
- Playwright 新增历史记录端到端用例。

### 修改

- 前端首次使用时生成随机匿名访客 ID；REST 请求使用 `X-PZ-Visitor-ID`，SSE 使用 `visitor_id` 查询参数。
- 任务详情、事件、取消、SSE 和历史列表均校验匿名访客归属。
- `InMemoryJobStore` 保留为测试替身，并补齐与 SQL 存储一致的归属、历史、恢复和账号归并接口。
- 后端新增 SQLAlchemy、aiosqlite、psycopg、greenlet 和 Alembic 依赖并更新锁文件。
- 更新中英文 README、产品文档、项目计划、技术架构、测试说明和依赖管理。

### 验证

- 后端全量 pytest：81 个通过，1 个 Starlette/TestClient deprecation warning。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Playwright Chromium：3 个 E2E 全部通过。
- SQLite Alembic `upgrade head` 执行成功。
- PostgreSQL Alembic 离线 SQL 编译成功。
- `pip check`：无破损依赖。

### 当前边界

- 匿名访客 ID 只是无登录 MVP 的数据分区键，不是认证凭证；公网部署前必须接入账号鉴权。
- 清除浏览器本地存储后，浏览器会生成新的匿名 ID，旧匿名历史仍在数据库中但不会自动展示。
- 已完成任务可跨后端重启恢复；运行中任务尚不能续跑，重启后会明确标记为中断失败。
- PostgreSQL 已完成代码和迁移兼容验证，尚未连接真实 PostgreSQL 实例做部署、备份和恢复验收。

### 影响文件

- `.env.example`
- `.gitignore`
- `README.md`
- `README.zh-CN.md`
- `backend/alembic.ini`
- `backend/migrations/`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/api/routes.py`
- `backend/app/storage/`
- `backend/requirements.txt`
- `backend/requirements-lock.txt`
- `backend/tests/`
- `frontend/src/lib/api.ts`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `frontend/e2e/research-flow.spec.ts`
- `frontend/playwright.config.ts`
- `project-docs/`

## 2026-06-08 19:57 CST +0800

### 新增

- 在前端项目中加入 `@playwright/test 1.60.0`。
- 新增 `frontend/playwright.config.ts`，端到端测试固定使用 `127.0.0.1:8000` 和 `127.0.0.1:3000`，自动启动 Mock 后端和 Next.js 前端。
- 新增 `frontend/e2e/research-flow.spec.ts`，覆盖：
  - 运行中取消任务，并确认取消后不会进入完成状态。
  - 运行中刷新页面，恢复任务 ID、研究问题、进度和 SSE 连接。
  - 任务完成后再次刷新，恢复最终报告。
- Mock Provider 新增 `MOCK_PROVIDER_DELAY_SECONDS` 测试配置，默认值为 0；E2E 使用可控延迟避免任务瞬间完成导致取消/刷新测试偶发失败。
- Playwright Chromium `148.0.7778.96` 安装到用户缓存 `~/Library/Caches/ms-playwright`，不写入项目仓库或系统 `/Applications`。

### 修改

- 前端新增 `npm run test:e2e` 和 `npm run test:e2e:headed`。
- `.gitignore` 新增 Playwright 报告和测试结果目录。
- 更新项目计划、技术架构和测试指南，标记核心 Playwright 流程已完成，并保留持久化、历史、重跑、导出、真实多模型验收和视觉回归等阶段 4 待办。

### 验证

- 后端全量 pytest：72 个通过，1 个 Starlette/TestClient deprecation warning。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Playwright 使用系统 Chrome 回退验证：2 个 E2E 通过。
- Playwright 使用用户目录 Chromium 最终验证：2 个 E2E 通过。
- Playwright 能识别用户缓存中的 `chromium-1223` 和 `chromium_headless_shell-1223`。

### 影响文件

- `.gitignore`
- `backend/app/config.py`
- `backend/app/agent/providers/factory.py`
- `backend/app/agent/providers/mock_provider.py`
- `backend/tests/test_config.py`
- `backend/tests/test_provider_factory.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/playwright.config.ts`
- `frontend/e2e/research-flow.spec.ts`
- `project-docs/project-plan.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

## 2026-06-08 19:41 CST +0800

### 新增

- 新增 `POST /api/research-jobs/{job_id}/cancel`：
  - 排队或运行中的任务可取消。
  - 重复取消保持幂等。
  - 已完成或失败任务返回 409。
- 新增运行任务注册表，取消请求会中断对应的后台 `asyncio.Task`，避免取消后继续写入完成状态。
- `ResearchJob` 新增 `draft_report`，用于在不保存 token 级事件的情况下保留当前报告草稿。
- SSE 新增：
  - `job_snapshot` 初始快照。
  - `after` 和 `Last-Event-ID` 持久事件游标。
  - 持久事件 `id:` 字段。
  - 报告 delta 的累计草稿校正。
- 前端新增：
  - 运行中“停止”按钮。
  - 当前任务状态标签。
  - 使用 `localStorage` 记住当前任务 ID。
  - 刷新后恢复问题、模式、Provider、时间线、来源、报告草稿和最终报告。
  - SSE 临时断线自动重连和事件 ID 去重。

### 测试

- 先新增失败测试，再完成实现。
- 后端测试从 65 个增加到 70 个，新增覆盖：
  - 报告草稿累计与重置。
  - 取消接口、幂等取消和已完成任务冲突。
  - 后台协程真实中断。
  - SSE 快照和事件游标续接。
- 后端全量 pytest：70 个通过。
- 前端 ESLint 通过。
- 前端 Next.js 生产构建通过。
- Python `compileall` 通过。
- `git diff --check` 通过。
- 本地标准端口验证：
  - FastAPI：`http://127.0.0.1:8000`
  - Next.js：`http://127.0.0.1:3000`
  - 已完成任务从最后持久事件续接时，只返回 `job_snapshot`，没有重复重放历史事件。

### 当前边界

- 刷新恢复目前依赖后端进程内存；后端重启后任务仍会丢失。
- 当前环境没有可用的内置浏览器、`agent-browser` 或 Playwright，因此取消与刷新恢复的浏览器自动化视觉验证尚未执行。
- 下一步建议在 `frontend` 项目内安装 Playwright，并把取消、刷新恢复和 SSE 重连写成可重复 E2E 测试。

### 影响文件

- `backend/app/agent/schemas.py`
- `backend/app/api/routes.py`
- `backend/app/storage/memory.py`
- `backend/tests/test_api.py`
- `frontend/src/app/globals.css`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

## 2026-06-08 19:24 CST +0800

### 修改

- 对照当前代码、测试和产品定义重新审计项目实施进度。
- 更新 `project-plan.md`：
  - 将阶段 2 调整为“Provider 抽象和 Runtime 工程闭环完成，真实多模型产品联调未全部完成”。
  - 将阶段 3 调整为“MVP 工具层完成，生产级检索质量和备用链路未完成”。
  - 将阶段 4 明确为“部分完成”，补充任务取消、历史、持久化、断线恢复、重跑、导出和 Playwright 等退出条件。
  - 将阶段 5 明确为“尚未开始正式实施”，补充认证、数据库、Worker、配额、安全、可观测性和部署范围。
  - 增加实施进度总览和下一里程碑，避免协作者把核心研究链路完成误判为完整 C 端 MVP 完成。
  - 更新推荐目录结构，使其与当前 `evidence.py`、`selection.py`、`prompt_templates/`、`memory.py` 和前端 `src/` 结构一致。
- 更新 `technical-architecture.md`：
  - 删除旧的“模型每轮自行选择 search/visit”的 ReAct 流程描述。
  - 明确当前为 Runtime 驱动的有界访问漏斗，模型只生成搜索词、专家模式证据缺口和最终报告，`visit` 由 Runtime 调度。
  - 说明 `max_rounds` 仅为遗留兼容字段，不再承担访问调度和防死循环职责。
  - 补充 Claude/Gemini 非原生流式、Gemini 用量、成本计算、内存存储、取消、断线恢复、引用验证和备用检索链路等真实边界。
  - 将当前后端测试数量从 64 更新为 65。
  - 重排后续技术优先级，以阶段 4 产品闭环和测试验收为先。

### 修改原因

- 项目已经从早期 ReAct 原型切换为 Runtime 驱动的访问漏斗，但部分文档仍保留旧流程和偏乐观的阶段状态，可能误导后续协作者。
- 先统一项目计划和技术架构，确保接下来的代码实现、测试和外部评审基于同一套事实。

### 影响文件

- `project-docs/project-plan.md`
- `project-docs/technical-architecture.md`
- `project-docs/changelog.md`

### 验证

- 已逐项对照后端 API、Runtime、Provider、存储、前端交互和现有 65 个测试的实际实现。
- 已检查阶段状态、Runtime 流程、研究模式数字规格和后续优先级在两份文档中保持一致。

## 2026-06-08 12:16 CST +0800

### 修改

- 将公开仓库 README 拆分为内容相互对应的中英文两版：
  - 根 `README.md` 使用英文，便于 GitHub 国际用户直接阅读。
  - 新增 `README.zh-CN.md`，保留完整简体中文版。
- 两版 README 顶部增加语言切换链接。
- 中英文版本保持相同的信息结构，包括产品能力、研究流程、研究模式、技术栈、项目结构、安装启动、测试、安全风险、上游参考和许可证说明。
- 项目结构示例同步列出两份 README。

### 影响文件

- `README.md`
- `README.zh-CN.md`
- `project-docs/project-plan.md`
- `project-docs/technical-architecture.md`
- `project-docs/changelog.md`

### 验证

- 两份 README 的互相跳转链接和项目内相对链接均已检查。
- 中英文版本中的命令、模式参数、安全边界和许可证信息保持一致。

## 2026-06-08 12:11 CST +0800

### 修改

- 按 GitHub 公开仓库的标准结构，将原 `PZ Deep Research/` 子目录中的产品代码整体提升到仓库根目录：
  - `backend/`
  - `frontend/`
  - `project-docs/`
  - `.env.example`
  - `.nvmrc`
  - `.python-version`
  - `README.md`
- 合并并更新根 `.gitignore`，继续忽略真实 `.env`、`frontend/.env.local`、虚拟环境、pytest 缓存、Next.js 构建产物、`node_modules` 和本地 `Qwen Deep Research/` 参考目录。
- 本机真实 `.env` 已安全移动到仓库根目录，仍保持 Git 忽略；公开仓库只包含无密钥的 `.env.example`。
- 重写根 `README.md`，补充：
  - 产品定位、核心能力、研究流程和三种研究模式。
  - 技术栈、标准目录结构和从克隆到启动的完整步骤。
  - 测试命令、隐私说明、第三方 API 费用风险和公网部署安全边界。
  - 当前内存存储、模型准确性和高风险场景限制。
  - 上游参考关系、独立实现说明和非官方/非背书声明。
- 新增 `LICENSE`，项目采用 Apache License 2.0。
- 新增 `NOTICE`，说明项目对 Alibaba-NLP/DeepResearch 的早期设计参考、独立实现范围、未分发的上游资产和商标归属。
- 更新项目计划、技术架构、测试说明和 API Key 配置文档，使目录结构和运行命令与新的仓库根路径一致。
- 清理目录提升后仅剩 `.DS_Store` 和 pytest 缓存的旧 `PZ Deep Research/` 空壳目录。
- 修复本机 `backend/.venv` 中 `pip`、`pytest`、`uvicorn` 等入口脚本残留的旧绝对路径；该虚拟环境不进入 Git。

### 公开发布检查

- 当前 `main` 仅包含 PZ 项目自己的 4 个历史提交，不继承 Qwen 上游提交历史。
- `Qwen Deep Research/` 继续作为本地参考目录并被 Git 忽略，不会进入普通 `main` 推送。
- 真实 `.env` 和 `frontend/.env.local` 均未被 Git 跟踪。
- 当前追踪文件中未发现真实 OpenAI、Anthropic、Gemini、SerpAPI、Jina 或 GitHub 密钥。
- 当前 `main` 不包含 GitHub 100MB 限制附近的大文件；最大的产品追踪文件为前端 lockfile。

### 验证

- 后端全量测试通过：65 个用例通过，保留 1 个 Starlette/TestClient 弃用警告。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过，Next.js 16.2.7 成功完成生产构建和静态页面生成。
- `git diff --check` 通过。
- 根目录结构、`README.md`、`LICENSE`、`NOTICE`、`backend/`、`frontend/` 和 `project-docs/` 均存在。

### 影响文件

- 根目录结构
- `.gitignore`
- `README.md`
- `LICENSE`
- `NOTICE`
- `project-docs/project-plan.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/api-key-setup.md`
- `project-docs/changelog.md`

## 2026-06-07 22:24 CST +0800

### 修复

- 修复从 `http://127.0.0.1:3000` 打开前端时，后端只允许 `http://localhost:3000` 导致 `/api/models` 与 `/api/research-jobs` 预检返回 `400 Disallowed CORS origin`、前端显示 `Failed to fetch` 的问题。
- 配置层现在会自动补齐 `localhost:3000` 与 `127.0.0.1:3000` 两个本地等价来源；`.env.example` 同步列出两者。
- 新增配置回归测试，确保本地 CORS 别名始终同时可用。

### 验证

- 修复前复现：`127.0.0.1:3000` 的 OPTIONS 预检返回 400，`localhost:3000` 返回 200。
- 修复后要求两个来源的 OPTIONS 预检均返回 200，并通过后端全量测试。

### 影响文件

- `backend/app/config.py`
- `backend/tests/test_config.py`
- `.env.example`
- `project-docs/changelog.md`

## 2026-06-07 18:09 CST +0800

### 修改

- 保持既定的 Runtime 驱动研究流程：模型只负责生成 search 查询和最终报告，visit 继续由 Runtime 在有限候选队列中滚动并发执行。full_text 达到阶段目标时早停；全文不足时访问完本轮有限候选后立即退出并降级选源，不重复访问、不无限补轮，避免卡死。
- quick / deep / expert 最终分别质量优先选择 3 / 10 / 20 个来源。访问过程来源只在中间工具结果展示；最终来源重新连续编号 1..N，右侧来源区只读取 `source_selected` / `completed` 的最终入选来源。
- expert 强制执行两轮搜索。第一阶段完成访问和证据卡片抽取后，Runtime 将卡片交给模型审查证据缺口，再执行第二轮补充搜索；最终从两轮访问并集中选源。
- 新增报告正文硬校验：quick 400-500 字、deep 1300-1500 字、expert 3000-3500 字；References / 参考文献章节和 `[n]` 引用标记不计入。格式、引用或字数不合格时清空流式草稿并要求重写，最多两次，仍不合格则明确失败而非无限循环。
- 证据卡片抽取增加单次超时、一次重试和逐来源降级：抽取模型失败时使用截断原文生成 fallback 卡片，其他来源和整个任务继续执行。
- 前端完整任务 ID 保持展示；来源聚合改为只展示最终入选来源。
- 将 `frontend/.env.local` 纳入忽略规则，新增不含密钥的 `frontend/.env.example`，避免本地环境配置继续进入版本控制。
- 修复项目迁移后本地 `backend/.venv/bin/{python工具}` 入口残留旧目录的问题；`pytest`、`pip`、`uvicorn` 已可从真实 Git 项目路径直接运行。该虚拟环境目录保持忽略，不进入 Git。
- 同步更新英文生产提示词、中文审阅提示词、产品文档、技术架构、测试说明、项目计划书和 README。

### 测试

- 新增/调整测试覆盖：有界候选耗尽降级、全文最低质量告警、最终来源质量优先与连续编号、expert 两阶段、报告正文计数与范围、证据抽取失败重试降级。
- 后端全量测试 64 个通过；Python `compileall`、前端 `npm run lint` 与 `npm run build` 通过。仍有 1 个 Starlette/TestClient 弃用警告，不影响当前功能。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/app/agent/selection.py`
- `backend/app/agent/evidence.py`
- `backend/app/agent/prompts.py`
- `backend/app/agent/prompt_templates/system_prompt.en.md`
- `backend/app/agent/prompt_templates/system_prompt.zh-CN.md`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_selection.py`
- `backend/tests/test_evidence.py`
- `frontend/src/components/research-workspace.tsx`
- `frontend/.env.example`
- `.gitignore`
- `README.md`
- `project-docs/`

## 2026-06-03 23:22 CST +0800

### 修改

- 研究流程从「模型每轮自行选择 search/visit」重构为「Runtime 驱动的访问漏斗」（解决此前任务因 full_text 硬门槛 + 模型反复重访导致的死循环与 token 膨胀）。新流程：
  - 模型只负责输出 search 查询和最终报告；访问由 Runtime 驱动，模型不再输出 visit 调用。
  - search 候选按搜索原生相关性序，用并发 visit 滚动访问；full_text 数达到本模式目标即早停，否则访问完所有候选（来源有限，天然有界，不会死循环）。
  - 每条已访问来源抽成证据卡片（便宜模型），原文按 url 在任务级内存暂存、不进上下文；模型只读卡片写报告，单轮请求 token 不再随轮数膨胀。
  - 选源采用「质量优先 → 数量补足 → 逃生降级」：full_text 达标取前 N；不足按 `full_text>相关性` 取前 N；总数不足则逃生降级，有多少用多少，并在报告中标注证据受限。
  - expert 模式跑两轮 search（第二轮审查缺口补充检索），选源覆盖两轮并集。
- 移除旧的证据门槛/工具顺序纠偏逻辑（`_missing_evidence_requirements`、`_expected_tool`、参数裁剪 protocol_warning 等），因为访问改由 Runtime 驱动，模型已无越界空间。
- 新增事件类型：`visit_progress`（访问进度 n/目标、全文证据数）、`evidence_ready`（已抽取卡片数）、`source_selected`（最终选中来源 + `degraded` / `full_text_shortfall` 标志）。
- 同步更新中英文系统提示词：明确「模型只发 search，系统负责访问并返回证据卡片，模型基于卡片写报告」的分工。
- 新增可配置项 `EVIDENCE_EXTRACTION_MODEL`（默认 `gpt-5-nano`），由 `Settings.evidence_extraction_model` 透传到 Runtime；非 OpenAI Provider 退回主模型。
- 前端新增 `visit_progress` / `evidence_ready` / `source_selected` 事件的可读展示，并提示证据降级原因。
- mock provider 改为「未被要求出报告时输出 search，收到出报告指令时输出 <answer>」，适配新流程。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/app/agent/prompts.py`
- `backend/app/agent/prompt_templates/system_prompt.en.md`
- `backend/app/agent/prompt_templates/system_prompt.zh-CN.md`
- `backend/app/agent/providers/mock_provider.py`
- `backend/app/config.py`
- `backend/app/api/routes.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_api.py`
- `frontend/src/components/research-workspace.tsx`
- `project-docs/changelog.md`、`project-docs/technical-architecture.md`、`project-docs/testing-guide.md`

### 验证

- 重写/新增 Runtime 测试覆盖新流程：Runtime 驱动 search→visit→报告、quick 搜索词裁剪、无全文证据时降级出报告、总是先 search 后 visit、expert 两轮 search、用量跨轮累加、流式报告、重试。
- 修复 `test_create_mock_research_job` 依赖真实网络的问题：改用离线 mock 搜索 runtime（此前 mock 任务在 TestClient 内同步打了真实 SerpAPI/Jina，耗时 30s）。
- 后端全量 pytest 通过：58 个用例通过（耗时回到约 1s）。前端 `npm run lint` 与 `npm run build` 通过。

### 备注

- 这是「研究流程重构」四阶段中的阶段 D（Runtime 访问漏斗整合），至此四阶段全部完成（A 并发 / B 选源漏斗 / C 证据卡片 / D 整合）。
- 行为变化提醒：provider=mock（开发模式）现在也会走 Runtime 驱动访问；若配置了真实 SerpAPI/Jina key，mock 任务会触发真实搜索与访问。如需让开发模式完全离线，可将 `SEARCH_PROVIDER` 设为 `mock`。

## 2026-06-03 22:13 CST +0800

### 新增

- 新增证据卡片抽取模块 `backend/app/agent/evidence.py`：把每条已访问来源的正文压成紧凑「证据卡片」，用于替代原文进入模型上下文，解决多轮重发全文导致的 token 膨胀（上次失败任务单轮请求一度达 6 万 token、累计 30 万、撞上 OpenAI TPM 上限）。
  - `EvidenceExtractor`：长正文（默认 ≥800 字）走便宜模型（默认 `gpt-5-nano`，可配）抽取，短摘要/题录/受限/失败来源直接透传、不调用模型省成本；`extract_many` 并发抽取且保序。
  - `build_extraction_prompt`：硬约束「只依据正文、逐字摘录关键数字、禁止编造、用来源编号引用」，保住学术引用准确性。
  - `render_card`：把卡片渲染成注入上下文的紧凑文本（含来源编号、标题、URL、证据强度）。
- `ToolResult` 新增 `source_texts` 字段（url→完整正文）：仅供 Runtime 抽取卡片使用，不写入事件快照或前端，避免污染事件流。visit 工具在并发访问时填充该字段。

### 影响文件

- `backend/app/agent/evidence.py`
- `backend/app/agent/schemas.py`
- `backend/app/agent/tools/visit.py`
- `backend/tests/test_evidence.py`
- `backend/tests/test_tools.py`
- `project-docs/changelog.md`

### 验证

- 新增 5 个证据卡片测试（先红后绿）：提示词含目标/原文/编号/约束、长全文走模型抽取、短摘要透传不调用模型、批量抽取保序且只抽长文、卡片渲染含编号与证据强度。
- 新增 1 个 visit 测试：`source_texts` 暴露完整正文而 `sources` 仅保留 500 字预览。
- 后端全量 pytest 通过：59 个用例通过。

### 备注

- 这是「研究流程重构」四阶段中的阶段 C（证据卡片抽取 + 上下文裁剪原料）。卡片如何真正替换原文进入上下文、原文按来源编号在内存暂存，由阶段 D（runtime 整合）接入。
- 抽取模型可配置项将在阶段 D 接入 env（计划 `EVIDENCE_EXTRACTION_MODEL`，默认 `gpt-5-nano`）。

## 2026-06-03 22:09 CST +0800

### 新增

- 新增选源漏斗纯函数模块 `backend/app/agent/selection.py`，实现「质量优先 → 数量补足 → 逃生降级」的选源逻辑：
  - `should_stop_visiting(full_text_count, target)`：访问队列早停判据，全文证据数达到本模式目标即短路。
  - `select_sources(sources, target)`：按「全文证据优先 > 相关性（输入即搜索原生序）」排序；总数 ≥ 目标取前 N，总数 < 目标则逃生降级（全部返回），并返回 `degraded`（数量不足）和 `full_text_shortfall`（全文证据不足）两个标志，供报告降级声明使用。
  - 证据分层 full_text > partial_text > metadata/metadata_only > failed/unavailable。

### 影响文件

- `backend/app/agent/selection.py`
- `backend/tests/test_selection.py`
- `project-docs/changelog.md`

### 验证

- 新增 6 个选源漏斗测试（先红后绿）：全文计数、早停判据、全文优先保序、全文充足不标短缺、总数不足逃生降级、可用来源排在失败来源之前。
- 后端全量 pytest 通过：53 个用例通过。

### 备注

- 这是「研究流程重构」四阶段中的阶段 B（选源漏斗纯函数）。该模块为纯函数、不依赖运行时，阶段 D 整合时直接复用。target 由 runtime 传入（对应 `MODE_POLICIES[mode]["visit_source_count"]` = 快速 3 / 深度 10 / 专家 20）。

## 2026-06-03 22:07 CST +0800

### 修改

- visit 工具从「逐个 URL 串行访问」改为「滚动队列并发访问」：用 `asyncio.Semaphore` 限制同时访问数（默认 5），其余排队，完成一个补一个；`asyncio.gather` 按传入顺序返回，保证来源顺序 = URL 输入顺序，引用编号不乱；单条访问失败被本协程兜住，标记 `failed / unavailable`，不影响其它来源。
- 新增可配置项 `VISIT_MAX_CONCURRENCY`（默认 5），由 `Settings.visit_max_concurrency` 透传到 `VisitTool`。

### 影响文件

- `backend/app/agent/tools/visit.py`
- `backend/app/agent/tools/registry.py`
- `backend/app/config.py`
- `backend/tests/test_tools.py`
- `project-docs/changelog.md`

### 验证

- 新增 4 个 visit 并发测试（先红后绿）：并发峰值达到上限、可配置上限、完成顺序打乱但来源保序、单条失败隔离。
- 后端全量 pytest 通过：47 个用例通过（原 43 + 4 新），仍有 1 个 Starlette/TestClient deprecation warning。

### 备注

- 这是「研究流程重构」四阶段中的阶段 A（visit 并发）。后续阶段：B 选源漏斗（full_text 早停 / full_text 优先 + 相关性选前 N / 逃生降级）、C 证据卡片抽取 + 上下文裁剪、D runtime 访问漏斗整合。
- 并发只优化墙上时间，不改变 token 用量与选源逻辑，后者由阶段 B/C/D 处理。

## 2026-06-03 20:35 CST +0800

### 新增

- 新增前端环境变量文件 `frontend/.env.local`，固化 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`，把前端调用的后端地址锁定到项目默认端口 8000。

### 修改

- 统一本地开发端口：后端默认运行在 `127.0.0.1:8000`，前端默认调用 `http://localhost:8000`，与 README、`.env.example`、技术架构和测试说明保持一致。

### 备注

- 此前一次本地调试中前端 dev server 曾被临时 `export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010` 注入，导致前端请求 8010、后端在 8000，出现 `Failed to fetch`。该值未落盘（不在 shell profile 也不在任何 env 文件），现通过 `frontend/.env.local` 显式锁定到 8000，避免再次错位。
- Next.js dev 只读取 `frontend/` 目录下的 `.env*`，不会读取仓库根目录的 `.env`；根 `.env` 里的 `NEXT_PUBLIC_API_BASE_URL` 对前端 dev server 不生效，需要时应放在 `frontend/.env.local`。

## 2026-06-03 19:34 CST +0800

### 修改

- 来源分级拆分为“候选来源”和“引用来源”：`search` 返回的是候选来源（`source_kind=search_result`），使用罗马编号 `(i)`、`(ii)`、`(iii)`，只能作为 `visit` 候选，不能被引用；只有 `visit` 后的来源（`source_kind=visited_source`）才分配阿拉伯 `citation_id` 并作为 `[1]`、`[2]` 可引用来源。
- 前端右侧来源区只展示 `visit` 后的来源；`search` 候选来源只在中间“工具返回”里展示，不再进入右侧来源区。
- 注入给模型的来源上下文：`visit` 之后只喂已访问来源，确保最终报告只基于 `visit` 返回的正文内容；`completed` 事件的 `sources` 也只返回已访问来源。
- 最终报告如果引用了未 `visit` 的候选来源、出现罗马编号或 `[^n]` 脚注，Runtime 会产出 `citation_required` 并触发重写。
- quick / deep / expert 增加 full_text 全文证据门槛：分别至少 1 / 3 / 5 个已访问来源必须是 full_text，未满足时继续要求 `visit`。
- 修复 `search` 事件的来源被后续 `visit` 结果污染的问题，确保进度里每个工具事件展示的是该步骤自身的来源。
- 前端“当前任务” ID 改为显示完整 ID，不再截断，方便复制到接口测试。
- 同步中文对照提示词 `system_prompt.zh-CN.md` 与英文生产版 `system_prompt.en.md`：补齐候选来源罗马编号、引用来源阿拉伯编号、full_text 门槛等规则（11 条规则对齐）。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/app/agent/tools/search.py`
- `backend/app/agent/tools/visit.py`
- `backend/app/agent/tools/utils.py`
- `backend/app/agent/providers/base.py`
- `backend/app/agent/providers/openai_provider.py`
- `backend/app/agent/schemas.py`
- `backend/app/agent/prompts.py`
- `backend/app/agent/prompt_templates/system_prompt.en.md`
- `backend/app/agent/prompt_templates/system_prompt.zh-CN.md`
- `backend/app/api/routes.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_api.py`
- `backend/tests/test_tools.py`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 后端全量 pytest 通过：43 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响功能。
- 提示词文件测试通过，确认英文生产版和中文对照版仍包含固定流程和三种模式策略。

### 备注

- 英文生产提示词和中文对照提示词必须同步维护；改一个就要同步另一个并更新本 changelog。
- Agent 当前为“固定流程 + 模型选参”混合模式：流程 `search -> visit -> answer`（expert 为 `search -> visit -> search -> visit -> answer`）由 Runtime 强制，搜索词、访问 URL 和报告组织由模型决定，Runtime 负责越界纠偏（早答、访问不足、引用未访问来源、全文证据不足）。

## 2026-06-03 16:26 CST +0800

### 新增

- 新增英文生产提示词文件 `backend/app/agent/prompt_templates/system_prompt.en.md`，Runtime 实际使用该文件。
- 新增中文对照提示词文件 `backend/app/agent/prompt_templates/system_prompt.zh-CN.md`，用于人工检查提示词内容。
- 新增 Runtime 模式规格测试，覆盖 quick / deep / expert 的搜索词数量、访问来源数量和报告字数目标。
- 新增提示词文件测试，确认英文生产版和中文对照版都包含固定流程和三种模式策略。
- 新增 References 标题识别测试，允许模型输出加粗的 `**References**`，避免仅因 Markdown 加粗触发无意义重写。
- 新增 quick 参数裁剪测试：模型返回超过策略数量的搜索词或 URL 时，Runtime 会裁剪并记录 `protocol_warning`。
- 新增 expert 流程测试：专家模式必须完成第二次 `search`，并总共访问 20 个来源后才允许输出最终报告。

### 修改

- 分析任务 `e2fa3f2a1dea4644af5870f9e529bce0`：quick 模式触达上限的原因是模型第 3/4 轮报告被 References 格式拦截，同时旧 quick 只要求访问 1 个来源且最大轮数只有 4。
- quick 模式调整为：联网搜索 -> 访问 -> 出结果；使用 1 个高命中英文搜索词，访问 3 个关键来源，生成 500 字以内 essay 风格报告。
- deep 模式调整为：联网搜索 -> 访问 -> 深度思考 -> 出结果；使用 3 个高命中英文搜索词，访问 10 个关键来源，生成 1500 字以内文献综述风格报告。
- expert 模式调整为：联网搜索 -> 访问 -> 深度思考 -> 初步研究 -> 审查缺口 -> 再次搜索 -> 再次访问 -> 最终报告；每次搜索使用 5 个高命中英文搜索词，总共访问 20 个关键来源，生成 3000 字以上论文风格报告。
- Runtime 的证据门槛从“是否调用过工具”升级为“搜索次数 + 已访问来源 URL 数量 + expert 二次搜索阶段”。
- Runtime 会按模式策略裁剪工具参数，避免模型超额搜索或超额访问导致成本失控。
- Runtime 最大轮数调整为 quick 8、deep 18、expert 32，给多来源访问和格式修复留出空间。
- `build_user_prompt` 改为英文执行说明，与英文生产提示词保持一致。
- 前端模式文案调整为“3源短文 / 10源综述 / 20源论文”。
- 产品文档、项目计划书、技术架构和测试说明同步更新新模式规格。

### 影响文件

- `backend/app/agent/prompts.py`
- `backend/app/agent/prompt_templates/system_prompt.en.md`
- `backend/app/agent/prompt_templates/system_prompt.zh-CN.md`
- `backend/app/agent/runtime.py`
- `backend/tests/test_agent_runtime.py`
- `frontend/src/components/research-workspace.tsx`
- `project-docs/project-plan.md`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 新增 Runtime 测试先失败，确认能覆盖缺失的双语提示词和模式策略行为。
- 完成实现后，后端全量 pytest 通过：40 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。

### 备注

- 英文生产提示词和中文对照提示词需要同步维护；后续改一个文件时必须同步改另一个文件，并更新本 changelog。
- 当前专家模式的“初步研究”和“审查缺口”由 Prompt 指导模型在内部完成，Runtime 负责强制第二次搜索和总访问数量。后续如果需要前端显式展示初步研究和审查阶段，可以新增结构化事件。

## 2026-06-03 15:52 CST +0800

### 新增

- 新增固定研究流程回归测试：quick 模式也必须在最终报告前完成 `visit`。
- 新增工具顺序回归测试：真实 Provider 如果在 `search` 前返回 `visit`，Runtime 必须纠偏且不能执行错误顺序的工具。
- 新增多工具调用回归测试：模型同一轮返回多个 `<tool_call>` 时，Runtime 记录 `protocol_warning` 并只执行第一个。
- 新增 API 事件历史测试：`report_delta` 和 `llm_delta` 一样只走实时 SSE，不写入历史事件存储。
- 前端新增 `protocol_warning` 事件说明展示，用户可以看到 Runtime 对模型协议错误的纠偏原因。

### 修改

- Runtime 将真实 Provider 的研究流程收紧为固定流水线：必须先 `search`，再 `visit`，最后才能输出 `<answer>`；quick / deep / expert 都不能跳过 `visit`。
- Runtime 新增阶段校验：当前阶段只接受预期工具，错误工具会被忽略并要求模型重写。
- Runtime 新增同轮多工具调用告警：只执行第一个工具调用，其余忽略，避免模型一次串联搜索和访问造成不可控流程。
- 系统 Prompt 明确“每轮最多一个工具调用”，并写入 quick / deep / expert 三个模式策略。
- `build_user_prompt` 改为同一个主提示词搭配模式策略块，而不是三套完全独立 Prompt。
- API 持久化策略调整：`report_delta` 不再写入历史事件，只通过实时队列推给当前 SSE 连接，减少任务日志膨胀。
- 前端模式说明从泛化描述调整为更贴近实际策略：快速“1源快读”、深度“多源研究”、专家“交叉验证”。
- 产品文档、技术架构和测试说明同步更新固定流程、模式策略和 `report_delta` 实时事件策略。

### 影响文件

- `backend/app/agent/prompts.py`
- `backend/app/agent/runtime.py`
- `backend/app/api/routes.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_api.py`
- `frontend/src/components/research-workspace.tsx`
- `project-docs/product-doc.md`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 新增测试先失败，确认能覆盖本次目标问题。
- 完成实现后，相关后端测试通过：21 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。

### 备注

- 当前 quick / deep / expert 使用“主 Prompt + 模式策略块”的方案。这样比维护三份完整 Prompt 更稳，后续如果某个模式需要明显不同的报告结构，再拆成独立模板。
- 当前同轮多个工具调用只执行第一个。后续如果要支持批量访问，需要增加工具依赖判断、并发限制和更明确的前端可观察性。

## 2026-06-03 15:30 CST +0800

### 新增

- 新增 Runtime 结构化输出容错能力：
  - 支持从未闭合的 `<tool_call>` 中提取完整 JSON 对象。
  - 支持从未闭合但内容完整的 `<answer>` 中提取报告正文。
- 新增最终报告真正流式输出：当证据门槛已满足且模型开始输出 `<answer>`，Runtime 会在模型生成过程中同步发送 `report_delta`，前端报告区可以呈现打字机式更新。
- 新增 `report_reset` 事件：如果流式报告草稿后续没有通过引用/参考文献校验，前端会清空草稿并等待重写结果。
- `search` 来源新增证据状态字段：`read_status=search_result`、`evidence_level=metadata`、`evidence_note`。
- `visit` 来源新增读取状态和证据强度分级：
  - `full_text`：Reader 返回可用正文。
  - `partial_text`：Reader 返回正文较短，只能作为部分证据。
  - `metadata_only` / `blocked`：遇到 403、Forbidden、CAPTCHA 等访问限制，不能当作已阅读全文。
  - `unavailable`：Reader 请求失败，不能作为证据使用。
- 前端工具结果新增可展开“查看工具返回”，可以直接看到 search / visit 的原始返回内容。
- 前端来源卡片新增证据强度标签。
- 报告引用 `[n]` 的 hover 从浏览器 title 升级为卡片样式，展示来源标题、域名、URL 和证据强度。
- 新增后端测试：
  - 未闭合 `<tool_call>` 容错。
  - 未闭合 `<answer>` 容错。
  - `report_delta` 在 `llm_result` 前出现，验证报告真流式。
  - `search` 题录来源证据分级。
  - `visit` full_text / blocked 分级。

### 修改

- 系统 Prompt 明确要求引用只能用 `[1]`、`[2]`，禁止 Markdown 脚注 `[^1]`。
- Runtime 的引用格式校验新增 `footnote_citations`，检测到 `[^1]` 会要求模型重写。
- Runtime 给模型的来源上下文会包含读取状态、证据强度和证据说明，避免 blocked / metadata_only 来源被误写成已阅读全文。
- Runtime 合并来源时，如果 `visit` 返回了已有 URL 的读取状态，会更新同一 citation，而不是因为 URL 已存在就丢掉 visit 元数据。
- 前端 `tool_result` 不再只展示来源卡片，也展示工具返回正文，方便人工检查模型有没有用到工具结果。

### 影响文件

- `backend/app/agent/prompts.py`
- `backend/app/agent/runtime.py`
- `backend/app/agent/tools/search.py`
- `backend/app/agent/tools/visit.py`
- `backend/app/agent/tools/utils.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_tools.py`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 后端 pytest 通过：32 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。
- 后端 `compileall` 通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。

### 备注

- 当前选择保留 `[n]` 引用格式，因为它更适合行内 hover、来源卡片映射和普通 Markdown 渲染；`[^n]` 是脚注语义，容易被 Markdown 渲染器改写到底部脚注，不适合当前产品的来源交互。
- 对 blocked / metadata_only 来源，模型仍可引用其题录或摘要信息，但不能声称已经阅读全文。

## 2026-06-03 14:56 CST +0800

### 新增

- 新增回归测试 `test_real_provider_prefers_tool_call_when_answer_and_tool_call_are_mixed`，覆盖模型同时输出 `<tool_call>` 和 `<answer>` 时，证据不足阶段必须优先执行工具调用。
- 新增回归测试 `test_run_research_job_does_not_persist_llm_delta`，覆盖 token 级 `llm_delta` 不写入历史事件存储。

### 修改

- Runtime 解析模型输出时，如果同一轮同时包含 `<tool_call>` 和 `<answer>`，且真实 Provider 证据门槛尚未满足，会优先执行 `<tool_call>`，避免反复触发 `evidence_required` 浪费轮次。
- API SSE 改为“实时队列 + 历史存储”两层分发：
  - `llm_delta` 只进入实时队列，通过 `/stream` 推给前端。
  - `llm_delta` 不再写入 `GET /events` 历史记录，避免单个任务生成数千条 token 级日志。
  - `llm_result`、`tool_start`、`tool_result`、`report_delta`、`completed`、`failed` 等关键事件继续持久保存在内存任务存储中。
- SSE 流接口会先发送已存历史事件，再消费实时队列；如果任务已结束且队列为空，会正常关闭连接。

### 影响文件

- `backend/app/agent/runtime.py`
- `backend/app/api/routes.py`
- `backend/tests/test_agent_runtime.py`
- `backend/tests/test_api.py`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 新增测试先失败，完成实现后通过。
- 后端 pytest 通过：29 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。
- 后端 `compileall` 通过。
- 前端 `npm run lint` 通过。

### 备注

- 这次修改解决了任务 `c9099eed84f649c4b0c0c9835a808c86` 暴露出的两个问题：历史日志被 `llm_delta` 撑爆，以及模型混合输出时没有优先执行 `visit`。
- 当前 `llm_delta` 是连接期实时事件；如果用户刷新页面，历史中不会回放 token 级过程，但会保留关键进度、工具结果和最终报告。

## 2026-06-03 14:07 CST +0800

### 新增

- 新增 `LLMStreamEvent`，作为模型流式输出的统一事件结构。
- Provider 基类新增 `stream_generate` 默认实现，Claude、Gemini 和 mock 在未单独接入原生 streaming 前仍可兼容现有非流式调用。
- OpenAI Provider 接入 Responses API 原生 streaming，支持把 `response.output_text.delta` 转为后端 `llm_delta` 事件。
- Agent Runtime 新增 `llm_delta` SSE 事件，前端可以实时看到模型输出过程。
- Agent Runtime 新增 `citation_required` 事件：真实 Provider 生成最终报告前，如果缺少引用角标或 References / 参考文献章节，会要求模型重写。
- 前端新增“模型实时输出”区域，用于展示当前轮模型流式返回内容。
- 前端报告区新增 Markdown 渲染能力，使用 `react-markdown` 和 `remark-gfm` 支持标题、列表、表格、链接和 GFM 格式。
- 新增 Runtime 测试：
  - `test_runtime_emits_llm_delta_events_for_streaming_provider`
  - `test_real_provider_must_rewrite_report_with_references`
- 前端新增依赖：
  - `react-markdown`
  - `remark-gfm`

### 修改

- OpenAI Provider 的流式调用现在会处理 completed、failed、incomplete 和 error 事件，避免上游异常被吞掉。
- Runtime 在最终报告输出前会检查来源引用和参考文献格式，降低模型没有使用搜索结果就直接写报告的风险。
- 前端不再把 `llm_delta` 和 `report_delta` 当作普通进度卡片堆进时间线，而是分别进入实时输出区域和报告区域。
- 报告正文中的 `[1]`、`[2]` 会先转换为 Markdown citation link，再由 Markdown 渲染器输出 hover 引用角标。
- 引用转换规则避免重复改写已经是 Markdown 链接的 `[1](https://example.com)`。
- 更新技术架构和测试说明，补充流式输出、Markdown 渲染、引用校验和新增测试。

### 影响文件

- `backend/app/agent/providers/base.py`
- `backend/app/agent/providers/openai_provider.py`
- `backend/app/agent/runtime.py`
- `backend/app/agent/schemas.py`
- `backend/tests/test_agent_runtime.py`
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/src/components/research-workspace.tsx`
- `frontend/src/app/globals.css`
- `project-docs/technical-architecture.md`
- `project-docs/testing-guide.md`
- `project-docs/changelog.md`

### 验证

- 后端 pytest 通过：27 个用例通过，仍有 1 个 Starlette/TestClient deprecation warning，不影响当前功能。
- 后端 `compileall` 通过。
- 前端 `npm run lint` 通过。
- 前端 `npm run build` 通过。

### 备注

- OpenAI 已接入原生流式输出；Claude 和 Gemini 当前仍使用 Provider 基类的兼容流式封装，后续可以分别接入各自 SDK 的原生 streaming。
- 当前引用校验是格式门槛，能要求模型引用已有来源，但还不是逐句事实核验；后续可以增加证据评分和引用一致性检查。
- 旧的 `2026-06-03` 按天记录作为历史保留；之后新增记录按分钟级时间戳单独追加。

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

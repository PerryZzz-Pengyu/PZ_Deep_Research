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
- 引用转换规则避免重复改写已经是 Markdown 链接的 `[1](url)`。
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

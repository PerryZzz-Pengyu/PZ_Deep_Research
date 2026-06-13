# PZ Deep Research — 社区版发布就绪清单

## 文档维护规则

这份文档跟踪「把社区版（Community Edition）作为获客与验证渠道公开发布」需要做的事。
每完成或调整一项，更新本文档并在 `project-docs/changelog.md` 记录。

## 目标与不做

- **目标**：让任何人能在 5 分钟内本地跑起社区版、用自己的 Key 完成一次真实研究，并愿意 star / 反馈 / 贡献。
- **现在不做**：支付、额度、托管多租户（属于 Cloud 版与后续里程碑）。
- 验证信号优先于功能堆叠：先把"能用、可信、易上手"做扎实，再投入云端变现。

## 现状（已具备）

- `PZ_EDITION=community` 默认；BYOK（模型 / SerpAPI / Jina）；SQLite + 访客模式；`docker compose up` 一键栈。
- README（中/英）含 Editions 小节与 Quickstart；`CONTRIBUTING.md` + `CLA.md`；Community CI（守卫 + 后端测试 + 前端 lint/typecheck/build）。
- 泄露守卫保护商业资料；Cloud 商业资产已迁出公开仓。

## 待办（按优先级；owner：U=用户 Owner，C=Codex 实施，K=Claude 顾问）

### P0 — 真正开箱即用（阻塞发布）
- [ ] **干净机器冷启动验证**：在未克隆过的环境 `git clone` → `docker compose up --build`，确认 mock 零密钥跑通一次研究、前端 `/workbench` 可用。（C；验收：录一遍过程）
- [ ] **BYOK 上手文档**：README/Quickstart 增加"如何在工作台填自己的 OpenAI/SerpAPI/Jina Key 并跑一次"的图文步骤。（C/K）
- [ ] **零依赖最短路径**：明确"只想试用 → 用 mock"与"要真实结果 → BYOK"两条路径，避免新用户卡在缺 Key。（C）

### P1 — 可信与可读（影响转化）
- [ ] **演示素材**：一段真实 BYOK 研究的 GIF/短视频（含搜索→访问→证据→带引用报告→导出）。（U/C）
- [ ] **README 顶部价值主张**：一句话讲清"证据优先、带可追溯引用的深度研究工具"，并放演示图。（K/C）
- [ ] **示例报告**：仓库内放 1–2 份导出的 Markdown 示例报告（quick + deep），让人不跑也能看质量。（C）
- [ ] **LICENSE/NOTICE/商标声明复核**：确认非官方关系声明清晰，避免与 OpenAI/Anthropic/Google/Qwen 的品牌混淆。（U/K）

### P2 — 接纳贡献与可见度
- [ ] **good-first-issue 集**：基于 CONTRIBUTING 列 5–8 个明确小任务（如新增 Reader 备链、来源去重增强、i18n 校对）。（C）
- [ ] **ISSUE/PR 模板**：`.github/ISSUE_TEMPLATE` + PR 模板。（C）
- [ ] **CI 徽章 + 截图**：README 加 CI 状态徽章与界面截图。（C）
- [ ] **发布动作**：GitHub Release v0.1.0（社区版）、可选 Show HN / 社区帖；记录来源以便看获客渠道。（U）

### P3 — 可选增强
- [ ] **公开 demo**：mock 或限流模式的在线体验（依赖 Tier 2 的限流/成本保护，建议放到那之后）。（U/C）
- [ ] **一键脚本**：非 Docker 用户的 `make dev` / 脚本化本地启动。（C）

## 验收（达成即可发布 v0.1.0）

- 新用户在干净机器上 ≤5 分钟跑通一次研究（mock 与 BYOK 各验证一次）。
- README 首屏能让人明白这是什么、好在哪、怎么跑。
- CI 绿、守卫绿、CONTRIBUTING/CLA/issue 模板就位。

## 关联

- 用量展示依赖 [usage ledger]（见 changelog 与架构文档的用量账本），可在发布后补"我的用量"视图。
- 公开 demo 与任何托管形态都需要先有服务端**限流 + 成本上限**（Tier 2）。

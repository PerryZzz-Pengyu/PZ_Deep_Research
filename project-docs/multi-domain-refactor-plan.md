# PZ Deep Research 多领域架构重构计划

## 1. 目标

在不改变现有学术研究行为的前提下，把当前的单领域实现收敛为“共享研究内核 + 领域注册表 + 领域实现”，为美股金融、社媒、行业分析和法律研究提供明确接缝。

本次不做：

- 不拆微服务。
- 不引入通用工作流 DSL。
- 不在底层重构同时实现完整金融业务。
- 不改变当前 academic 默认行为、API 路径、SSE 协议或历史任务读取方式。

## 2. 目标形态

```text
API / Workbench
      ↓
Research Job Core
      ↓
DomainRegistry
      ├─ academic → AcademicRuntime + academic tools/prompts/validators
      ├─ finance  → FinanceRuntime + finance tools/prompts/validators
      ├─ social   → future
      ├─ industry → future
      └─ legal    → future
```

共享内核保留：鉴权、任务归属、任务状态、存储、SSE、Provider、路由、取消、重试、用量、错误脱敏和导出。

领域实现负责：请求选项、策略、工具集、Prompt、证据载荷、分析流程、结果 Schema 和验证规则。

## 3. 阶段化实施

### 阶段 A：文档和领域接缝（已完成）

验收条件：

- 完成美股金融 PRD、本重构计划和目标技术架构。
- `ResearchRequest` 和 `ResearchJob` 具备 `domain`，未传时默认 `academic`。
- 历史 API 客户端无需修改仍可创建学术任务。
- 数据库能持久化 `domain`，旧数据回填 `academic`。
- 未注册领域被请求 Schema 或注册表明确拒绝。
- 路由层通过 `DomainRegistry` 取得 Runtime，不再假设所有任务都直接使用一个全局 academic Runtime。
- 学术 Runtime 输出、重试检查点和流式事件保持不变。

### 阶段 B：学术领域归位（已完成）

验收条件：

- 当前 Runtime、Prompt、学术工具组装和证据策略在 `domains/academic/` 形成清晰所有权。
- 现有 `app.agent.*` 路径在过渡期保留兼容导出，避免一次性修改全部测试和外部导入。
- 共享内核不包含 Scholar 、论文字数或文献综述等领域语义。

### 阶段 C：美股金融骨架（已完成）

验收条件：

- 建立 `FinanceOptions`、`FinancialEvidence`、`FinanceResearchResult` 和版本化方法字段。
- 建立 Ticker/Exchange/CIK 实体解析和缓存边界。
- 建立 SEC submissions/companyfacts 连接器的离线 fixture 和合同测试。
- 建立 Google Finance/News 适配器协议，不将供应商原始 JSON 渗透到领域层。
- Finance Runtime 可使用 mock/fixture 完成一次端到端任务。

实施记录：

- `FinanceOptions`、`SecurityIdentifier`、`FinancialEvidence`、`CandidateResearch` 和 `FinanceResearchResult` 已建立，结果与方法版本分别为 `finance-result-v1` / `finance-methodology-v1`。
- 证券解析只接受精确 Ticker 或精确公司名，对重名明确报错；SEC 证券目录在有界内存 TTL 内只拉取一次。
- SEC 连接器已归一化证券目录、近期 filings 和 XBRL company facts，并要求识别性 `User-Agent`。
- Google Finance/News 连接器只输出市场快照和新闻领域模型，不将 `search_metadata` 或供应商原始 JSON 带入证据层。
- 所有行情、新闻、证据和报告时间必须带时区；naive datetime 在 Schema 层被拒绝。
- `FinanceRuntime.research` 可在离线 fixture 中将明确 Ticker 组装为 filing、fundamental、market 和 news 证据包。该 Runtime 尚未注册进公开 `DomainRegistry`。

### 阶段 D：金融 MVP 研究漏斗

验收条件：

- Planner 能将四类输入转为结构化计划。
- 候选漏斗按 5–10 → 3–5 → 0–3 有界退出。
- 财务数字由确定性代码计算，保留原始值、公式和方法版本。
- Verifier 使用结构化问题清单驱动最多有界重写，不与分析 Agent 自由对话。
- 前端提供美股候选卡片、完整报告、数据时点和方法限制。

### 阶段 E：其他领域

只在 academic 和 finance 两个实现产生真实重复后再抽象更高层的通用组件。社媒、行业和法律领域不得通过在 academic Runtime 中堆条件分支实现。

## 4. 阶段 A 实施记录

本轮只完成阶段 A，具体交付为：

1. 产品与架构文档。
2. `domain=academic` 的 API、Schema、存储和数据库迁移。
3. 最小 `DomainRegistry` 与 Runtime 解析接缝。
4. 学术任务兼容性和未知领域拒绝测试。
5. 不实现 SEC、Google Finance、Google News 或金融 Agent。

## 5. 阶段 B 实施记录

1. `AcademicRuntime` 实现已迁入 `app.research.domains.academic.runtime`。
2. Prompt 及模板、证据抽取、选源策略、Google Scholar 搜索和学术工具组装已归入同一领域包。
3. `app.agent.*` 历史路径保留薄兼容导出，`AgentRuntime` 与新 `AcademicRuntime` 为同一类对象。
4. API 正式组装直接使用 `AcademicRuntime` 和 `build_academic_tool_registry`。
5. 新增所有权与兼容合同测试，后端全套 190 项通过。

## 6. TDD 顺序

1. 先为默认 `academic`、显式 `academic`、未知领域和 Job 持久化编写失败测试。
2. 再为注册表的已注册/未注册解析编写失败测试。
3. 实现最小字段、迁移和注册表，使新测试通过。
4. 运行现有后端全套测试，确认学术研究无回归。
5. 代码稳定后才更新当前状态文档、测试指南和 changelog。

## 7. 风险与缓解

- **历史数据兼容**：新增列使用非空默认 `academic`，并通过迁移回填。
- **一次性移动大量文件**：阶段 A 只增加注册接缝；阶段 B 使用兼容导出保留历史导入路径。
- **过度抽象**：注册表只解析 Runtime，不先构建通用节点 DSL 或可配置 Agent 图。
- **领域选项污染通用 Schema**：当前只增 `domain`；金融选项在阶段 C 以判别联合或领域专属 Schema 引入。
- **并行改动冲突**：保留工作区已有未提交修改，对重叠文件只做局部补丁。

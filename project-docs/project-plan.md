# PZ Deep Research 项目计划书

## 文档维护规则

这份文档不是一次性说明书。只要项目目标、技术架构、实现阶段、工程原则或关键决策发生变化，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`，说明修改日期、修改内容、影响文件和修改原因。

## 项目目标

PZ Deep Research 的目标是做一个面向 C 端用户的深度研究网页产品。它会参考 `Qwen Deep Research` 中有价值的 Agent 推理流程和工具设计，但新项目本身不依赖 Qwen 模型，也不依赖本地 vLLM 部署。

第一版产品需要支持用户输入一个研究问题，系统自动进行搜索、访问网页、分析证据，并最终生成一份结构化、有来源的研究报告。

## 项目边界

### 第一阶段要做

- 在本 Git 仓库根目录建立独立产品项目。
- 支持 Claude、OpenAI/ChatGPT API、Gemini API。
- 抽象统一的模型 Provider 层，避免绑定某一家模型。
- 复用 Qwen Deep Research 的核心思路：
  - 规划问题
  - 搜索资料
  - 访问来源网页
  - 提取证据
  - 生成最终答案或报告
- 建立网页端产品体验。
- 记录研究任务状态、来源、过程事件和最终报告。
- 每次开发后更新协作文档和 changelog。

### 第一阶段暂不做

- 模型训练或微调。
- 本地部署 Qwen 模型服务。
- 复现论文评测脚本。
- 企业团队协作功能。
- 在核心研究流程跑通前接入付费系统。

## 推荐项目结构

```text
PZ_Deep_Research/
  backend/
    app/
      agent/
        runtime.py
        prompts.py
        schemas.py
        providers/
          base.py
          openai_provider.py
          anthropic_provider.py
          gemini_provider.py
        tools/
          search.py
          visit.py
          file_parser.py
      api/
        routes.py
      storage/
        models.py
    tests/
  frontend/
    app/
    components/
    lib/
  project-docs/
    project-plan.md
    product-doc.md
    technical-architecture.md
    testing-guide.md
    dependency-management.md
    api-key-setup.md
    changelog.md
  README.md
  README.zh-CN.md
  LICENSE
  NOTICE
  .env.example
```

技术架构、方案选择、模块职责和关键工程决策统一记录在 `project-docs/technical-architecture.md`。只要实现方案发生变化，需要同步更新该文档和 `project-docs/changelog.md`。

测试范围、测试命令和手动测试流程统一记录在 `project-docs/testing-guide.md`。只要测试方式或测试覆盖范围发生变化，需要同步更新该文档和 `project-docs/changelog.md`。

运行时版本、依赖升级策略、安全审计和兼容性判断统一记录在 `project-docs/dependency-management.md`。只要依赖或运行时策略发生变化，需要同步更新该文档和 `project-docs/changelog.md`。

真实模型、搜索工具和网页读取工具的 API Key 配置统一记录在 `project-docs/api-key-setup.md`。只要 Provider、默认模型或 Key 名称发生变化，需要同步更新该文档和 `project-docs/changelog.md`。

## 实现阶段

### 阶段 1：项目基础

- 创建 PZ 项目基础结构。
- 建立后端和前端骨架。
- 增加环境变量示例文件。
- 固定文档协作规范和 changelog 机制。

当前状态：已完成。2026-06-03 已确认阶段 1 可以关闭。

完成内容：

- 已完成第一批工程骨架，包括 `backend/`、`frontend/`、`.env.example`、`.gitignore` 和根目录 `README.md`。
- 已建立项目协作文档、测试说明、依赖管理和 changelog 机制。
- 已将本机全局环境和项目环境统一到 Python 3.14.5、Node.js 24.16.0、npm 11.16.0，并在项目中增加运行时声明和依赖锁定文件。

### 阶段 2：模型无关的 Agent Runtime

- 建立不依赖 Qwen 专属包的 Agent Runtime。
- 实现 OpenAI、Anthropic、Gemini 三个 Provider。
- 第一版保留 XML 风格工具调用协议，降低多模型适配难度。
- 增加重试、超时、token 统计和成本统计的基础接口。

当前状态：已完成。2026-06-03 已完成阶段 2 的工程化补齐。

完成内容：

- 已完成 Agent Runtime、Provider 抽象、`mock` Provider，以及 OpenAI、Anthropic、Gemini Provider 的基础接口。
- 已加入 Runtime 级别的模型调用超时控制。
- 已加入 Runtime 级别的模型调用失败重试。
- 已加入 `llm_result` 事件，用于记录模型、输入 token、输出 token 和累计用量。
- 已为 ProviderFactory 增加测试，覆盖默认 Provider、共享默认模型、Provider 专属模型和未知 Provider。
- 真实 API Key 联调仍作为后续可选集成测试，不阻塞阶段 2 关闭。

### 阶段 3：工具层

- 迁移搜索能力，当前优先使用 SerpAPI Google Scholar 做学术搜索。
- 迁移网页访问能力，可使用 Jina 或直接抓取加内容抽取。
- 文件解析作为高级能力，先不阻塞 MVP。
- 所有工具结果需要能被记录为来源或证据。

当前状态：已完成。2026-06-03 已完成阶段 3 的 MVP 工具层补齐。

完成内容：

- `search` 工具支持 SerpAPI Google Scholar、开发模式占位结果、query 清洗、去重和来源记录。
- `search` 工具遇到上游失败时返回工具失败内容，不直接抛异常中断整个研究任务。
- `visit` 工具支持 Jina Reader、开发模式占位内容、URL 清洗、安全 scheme 过滤和来源记录。
- `visit` 工具遇到访问失败时返回工具失败内容，不直接抛异常中断整个研究任务。
- 工具层支持注入 HTTP transport，便于不联网做单元测试。
- 已新增工具层 pytest 覆盖搜索解析、来源去重、失败兜底、网页读取、URL 过滤和未知工具。

### 阶段 4：网页端 MVP

- 实现研究输入页。
- 实现研究模式选择。
  - 快速模式：1 个高命中英文搜索词，最终选择 3 个关键来源，正文 400-500 字。
  - 深度模式：3 个高命中英文搜索词，最终选择 10 个关键来源，正文 1300-1500 字。
  - 专家模式：强制两次搜索，每次 5 个高命中英文搜索词，从两轮访问并集中最终选择 20 个关键来源，正文 3000-3500 字。
- 实现实时研究进度时间线。
- 实现最终报告展示。
- 实现来源列表和引用展示。
- 后端提供任务创建、任务状态、事件流、报告获取等 API。

当前状态：核心 MVP 已完成，正在进行真实 Provider 联调与体验收尾。研究输入、模式选择、SSE 进度、工具结果、Markdown 报告、引用卡片、最终来源列表和完整任务 ID 已落地。

### 阶段 5：产品化

- 增加用户登录。
- 增加历史记录。
- 增加额度和使用量统计。
- 支持导出 Markdown 或 PDF。
- 增加内容安全和滥用控制。
- 增加部署配置。

## 工程原则

- `Qwen Deep Research` 只作为上游参考代码，不在里面继续做产品开发。
- 所有产品实现都放在本仓库根目录的 `backend/`、`frontend/` 和相关产品目录中。
- 新项目避免引入 Qwen 专属依赖。
- 模块要小而清晰，方便测试和替换。
- 后续功能开发默认先定义测试或验收标准，再开始实现，避免写完功能后再补测。
- 每次重要修改都要记录到 `project-docs/changelog.md`。
- 产品方向或技术方案变化时，要同步更新 `project-plan.md` 和 `product-doc.md`。

## 项目协作角色分工

### 用户

用户是产品 Owner，负责决定产品方向、业务优先级、目标用户、功能取舍和最终发布节奏。

### Codex

Codex 是主工程实施者，负责在本地项目中完成工程化落地，包括：

- 阅读和理解现有项目结构。
- 设计并实现后端、前端和 Agent Runtime。
- 迁移和改造 Qwen Deep Research 中可复用的思路。
- 维护项目文档和 changelog。
- 运行测试、排查报错、修复联调问题。
- 保持项目实现和当前本地代码状态一致。

### Claude Opus 4.8

Claude Opus 4.8 适合作为外部顾问或关键评审角色，不作为主施工方。推荐使用场景：

- 评审 Agent Runtime 架构。
- 评审复杂模块设计。
- 优化 deep research prompt。
- 帮助检查报告结构、产品体验和推理流程。
- 对关键代码或方案做第二意见评估。

### Gemini

Gemini 暂不加入核心工程协作链路。它更适合作为产品中的模型 Provider 和后续评测对照对象。

推荐使用场景：

- 作为 PZ Deep Research 支持的第三方模型 API。
- 用于和 Claude、OpenAI/ChatGPT API 做输出质量、速度、成本对比。
- 后续在多模型路由、多模型评审或结果交叉验证中使用。

当前协作主线建议保持为：

```text
用户：产品 Owner
Codex：主工程实施者
Claude Opus 4.8：架构顾问 / Prompt 顾问 / 关键评审
Gemini：产品模型 Provider / 后续评测对象
```

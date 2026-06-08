# PZ Deep Research

面向 C 端用户的多模型深度研究网页应用。系统通过学术搜索、网页访问、证据抽取、来源筛选和引用校验，生成带来源的结构化研究报告。

> [!WARNING]
> 当前项目处于实验性 MVP 阶段。模型输出可能包含遗漏、错误或不准确引用，不应直接用于医疗、法律、金融等高风险决策。

## 核心能力

- 支持 OpenAI、Anthropic Claude、Google Gemini 和离线 mock Provider。
- 使用 SerpAPI Google Scholar 检索学术资料。
- 使用 Jina Reader 访问网页正文并判断证据可用性。
- 提供快速、深度、专家三种研究模式。
- 实时展示模型输出、搜索、访问和证据处理进度。
- 使用证据卡片控制上下文长度，降低长任务的 token 膨胀风险。
- 最终报告支持 Markdown、阿拉伯数字行内引用、来源悬浮卡片和 APA 风格参考文献。
- 来源不足或全文证据不足时有界退出并明确降级，不重复访问造成死循环。

## 研究流程

```text
用户问题
  -> 模型生成英文搜索词
  -> SerpAPI Google Scholar 搜索
  -> Runtime 并发访问候选来源
  -> Jina Reader 返回网页内容
  -> 抽取证据卡片并评估证据强度
  -> 按质量和相关性筛选最终来源
  -> 模型基于证据卡片生成报告
  -> Runtime 校验字数、引用和 References
  -> SSE 流式展示结果
```

访问流程由 Runtime 控制。模型只负责生成搜索词和最终报告，不自行循环调用 `visit`，从而保证任务有界、来源编号稳定，并减少重复访问。

## 研究模式

| 模式 | 搜索策略 | 最终来源目标 | 报告正文 |
| --- | --- | ---: | ---: |
| 快速 | 1 个高命中英文搜索词 | 3 | 400-500 字 |
| 深度 | 3 个高命中英文搜索词 | 10 | 1300-1500 字 |
| 专家 | 两轮搜索，每轮 5 个英文搜索词 | 20 | 3000-3500 字 |

来源数量受实际搜索结果和网页可访问性影响。系统无法达到目标时会使用已有证据完成降级报告，并提示证据局限。

## 技术栈

- 前端：Next.js 16、React 19、TypeScript
- 后端：FastAPI、Python
- 模型：OpenAI API、Anthropic API、Google Gemini API
- 搜索：SerpAPI Google Scholar
- 网页读取：Jina Reader
- 实时通信：Server-Sent Events
- 测试：pytest、ESLint、Next.js production build

## 项目结构

```text
.
├── backend/              # FastAPI、Agent Runtime、Provider、工具与测试
├── frontend/             # Next.js 研究工作台
├── project-docs/         # 计划、产品、架构、测试与变更记录
├── .env.example          # 环境变量模板，不包含真实密钥
├── .nvmrc                # Node.js 版本声明
├── .python-version       # Python 版本声明
├── LICENSE               # Apache License 2.0
├── NOTICE                # 项目归属与上游参考说明
└── README.md
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/PerryZzz-Pengyu/PZ_Deep_Research.git
cd PZ_Deep_Research
```

### 2. 准备环境

当前已验证环境：

```text
Python 3.14.5
Node.js 24.16.0
npm 11.16.0
```

```bash
nvm use
python3 --version
node -v
npm -v
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

不配置真实 API Key 时，可以保持：

```text
DEFAULT_PROVIDER=mock
SEARCH_PROVIDER=mock
```

真实研究至少需要：

- OpenAI、Anthropic 或 Gemini 中任意一个模型 API Key。
- `SERPAPI_API_KEY`。
- 推荐配置 `JINA_API_KEY`，提高网页读取稳定性和额度。

不要提交 `.env`、`frontend/.env.local` 或任何真实 API Key。完整说明见 [API Key 配置](project-docs/api-key-setup.md)。

### 4. 启动后端

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/readiness
```

### 5. 启动前端

打开另一个终端：

```bash
cd frontend
nvm use
npm ci
npm run dev
```

访问 <http://localhost:3000>。

## 测试

后端：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

完整测试策略和手动验收流程见 [测试说明](project-docs/testing-guide.md)。

## 隐私、费用与安全

- 用户问题会发送给所选模型 Provider。
- 搜索词会发送给 SerpAPI，访问的 URL 和网页内容会经过 Jina Reader。
- API 调用费用和第三方服务额度由部署者承担。
- 公网部署前应增加身份验证、用户额度、请求限流、滥用防护和费用告警。
- 当前任务存储为进程内内存存储，服务重启后任务记录可能丢失。
- 不要在客户端代码中暴露模型、搜索或网页读取 API Key。

## 上游参考与独立性

PZ Deep Research 在早期设计阶段参考了 [Alibaba-NLP/DeepResearch](https://github.com/Alibaba-NLP/DeepResearch) 中的深度研究 Agent、`search` / `visit` 工具和 XML 工具协议思路。

当前项目采用独立实现的 Runtime、Provider、证据卡片、来源筛选、引用校验、FastAPI 服务和 Next.js 产品界面；不依赖 Qwen 模型或 `qwen-agent` 包，也不分发上游模型权重、数据集或大型资产。

本项目不是 Alibaba-NLP、Qwen、OpenAI、Anthropic、Google、SerpAPI 或 Jina AI 的官方产品，也不代表上述组织对本项目的认可或背书。更多说明见 [NOTICE](NOTICE)。

## 项目文档

- [项目计划书](project-docs/project-plan.md)
- [产品文档](project-docs/product-doc.md)
- [技术架构](project-docs/technical-architecture.md)
- [测试说明](project-docs/testing-guide.md)
- [依赖管理](project-docs/dependency-management.md)
- [API Key 配置](project-docs/api-key-setup.md)
- [变更日志](project-docs/changelog.md)

## 贡献与文档维护

提交代码前请运行后端测试、前端 lint 和生产构建。每次修改代码、架构、配置、依赖、接口或产品行为时，需要同步更新 `project-docs/changelog.md`，并按影响范围更新其他项目文档。

## License

本项目采用 [Apache License 2.0](LICENSE)。

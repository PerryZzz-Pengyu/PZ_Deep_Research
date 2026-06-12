# PZ Deep Research

[English](README.md) | **简体中文**

面向 C 端用户的深度研究网页应用。后台兼容 OpenAI、Claude 和 Gemini，通过学术搜索、网页访问、证据抽取、来源筛选和引用校验，生成带来源的结构化研究报告。

正式产品界面只向用户提供研究问题和快速、深度、专家三种模式，不展示 Provider 或模型选择。当前生产路由固定使用 OpenAI `gpt-5.4-mini` 生成搜索词和最终报告，证据卡片使用 `gpt-5-nano`；只有显式开启内部手动模式时才显示模型选择器。

> [!WARNING]
> 当前项目处于实验性 MVP 阶段。模型输出可能包含遗漏、错误或不准确引用，不应直接用于医疗、法律、金融等高风险决策。

## 核心能力

- 后台支持 OpenAI、Anthropic Claude、Google Gemini 和离线 mock Provider。
- 使用 SerpAPI Google Scholar 检索学术资料。
- 使用 Jina Reader 访问网页正文并判断证据可用性。
- 提供快速、深度、专家三种研究模式。
- 实时展示模型输出、搜索、访问和证据处理进度。
- 使用证据卡片控制上下文长度，降低长任务的 token 膨胀风险。
- 最终报告支持 Markdown、阿拉伯数字行内引用、来源悬浮卡片和 APA 风格参考文献。
- 来源不足或全文证据不足时有界退出并明确降级，不重复访问造成死循环。
- 使用 SQLite/PostgreSQL 持久化研究任务、事件、报告草稿和最终报告。
- 支持 Clerk 登录、匿名历史自动归并、账号级历史和跨设备同步；未配置 Clerk 时仍可使用访客模式。
- 支持将当前报告直接导出为 UTF-8 Markdown 文件。
- 支持由后端 Chromium 生成带任务信息、分页和页码的 A4 PDF 报告。

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

当前生产路由版本为 `openai-default-v1`。生产模式会忽略客户端提交的 Provider/模型参数；内部开发可以通过环境变量切换到手动路由。

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
- 数据库：SQLite（本地默认）、PostgreSQL（生产可选）、SQLAlchemy、Alembic
- 身份认证：Clerk（可选，后端本地验证会话 JWT）
- 文档导出：Markdown Blob、Playwright Chromium PDF
- 测试：pytest、Playwright、ESLint、Next.js production build

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
├── README.md             # English
└── README.zh-CN.md       # 简体中文
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
MODEL_ROUTING_MODE=manual
DEFAULT_PROVIDER=mock
SEARCH_PROVIDER=mock
```

真实研究至少需要：

- OpenAI、Anthropic 或 Gemini 中任意一个模型 API Key。
- `SERPAPI_API_KEY`。
- 推荐配置 `JINA_API_KEY`，提高网页读取稳定性和额度。

不要提交 `.env`、`frontend/.env.local` 或任何真实 API Key。完整说明见 [API Key 配置](project-docs/api-key-setup.md)。

账号登录为可选能力。启用时还需要配置：

```text
# frontend/.env.local
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=

# .env
CLERK_JWT_KEY=
CLERK_AUTHORIZED_PARTIES=http://localhost:3000,http://127.0.0.1:3000
```

完整步骤见 [登录与历史绑定配置](project-docs/auth-setup.md)。没有配置 Clerk 时，应用继续以当前浏览器访客 ID 保存历史。

默认生产路由配置：

```text
MODEL_ROUTING_MODE=production
PRODUCTION_PROVIDER=openai
PRODUCTION_MODEL=gpt-5.4-mini
MODEL_ROUTING_VERSION=openai-default-v1
EVIDENCE_EXTRACTION_MODEL=gpt-5-nano
```

本地默认把数据保存到 `data/pz_deep_research.db`。生产推荐使用 Neon PostgreSQL：应用使用 pooled URL，迁移和备份使用 direct URL。

```text
DATABASE_URL=postgresql://user:password@pooled-host/database?sslmode=require
DATABASE_MIGRATION_URL=postgresql://user:password@direct-host/database?sslmode=require
```

填好后可运行 `cd backend && PYTHONPATH=. .venv/bin/python scripts/check_database.py` 验证连接。Neon 是标准 PostgreSQL，后续可以迁移到其他托管或自建 PostgreSQL，不需要重写业务存储层。

### 4. 启动后端

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
backend/.venv/bin/playwright install chromium
cd backend && PYTHONPATH=. .venv/bin/alembic upgrade head && cd ..
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --reload-dir backend/app --port 8000
```

Linux 生产镜像可使用 `backend/.venv/bin/playwright install --with-deps chromium` 安装 Chromium 及系统依赖。浏览器默认安装到 Playwright 用户缓存，不进入 Git 仓库。

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
npm run test:e2e
```

完整测试策略和手动验收流程见 [测试说明](project-docs/testing-guide.md)。

最近一次本地验证（2026-06-11）：

- 后端 pytest：122 个用例通过。
- Playwright Chromium：7 个端到端用例通过。
- 本地 `8000/3000` 服务和前端页面冒烟检查通过，无 Next.js 错误覆盖层或浏览器控制台错误。

## 隐私、费用与安全

- 用户问题会发送给后台任务配置或模型路由选择的 Provider；当前开发界面允许人工选择，正式 C 端产品计划隐藏该能力。
- 搜索词会发送给 SerpAPI，访问的 URL 和网页内容会经过 Jina Reader。
- API 调用费用和第三方服务额度由部署者承担。
- 已支持可选 Clerk 登录。登录请求使用 Clerk 会话 JWT，后端本地验签后以 `sub` 作为可信 `user_id`。
- 首次登录会把当前浏览器访客 ID 下的匿名任务自动归并到账号；归并后可跨设备查看，退出登录不会把任务退回访客。
- 未配置 Clerk 时仍使用匿名访客模式；匿名访客 ID 不是安全凭证，不适合直接作为公网产品的唯一授权机制。
- 公网部署还需要用户额度、请求限流、滥用防护、费用告警，以及正确配置生产域名的 `CLERK_AUTHORIZED_PARTIES`。
- SQLite 适合本地和单实例部署；多实例生产环境应使用 PostgreSQL、备份和独立任务 Worker。
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
- [登录与历史绑定配置](project-docs/auth-setup.md)
- [变更日志](project-docs/changelog.md)

## 贡献与文档维护

提交代码前请运行后端测试、前端 lint 和生产构建。每次修改代码、架构、配置、依赖、接口或产品行为时，需要同步更新 `project-docs/changelog.md`，并按影响范围更新其他项目文档。

## License

本项目采用 [Apache License 2.0](LICENSE)。

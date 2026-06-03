# PZ Deep Research

PZ Deep Research 是一个面向 C 端用户的深度研究网页产品。当前项目从工程上独立于 `Qwen Deep Research`，后者只作为上游参考代码。

## 当前状态

第一批工程骨架已经建立：

- `backend/`：FastAPI 后端、Agent Runtime、Provider 抽象、工具抽象、内存任务流。
- `frontend/`：Next.js 前端研究工作台。
- `project-docs/`：项目计划书、产品文档、变更日志。

默认 Provider 是 `mock`，用于在没有模型 API Key 的情况下跑通任务创建、事件流、工具调用和报告展示。

## 项目文档

- `project-docs/project-plan.md`：项目目标、阶段规划和协作角色分工。
- `project-docs/product-doc.md`：产品愿景、目标用户、核心流程和 MVP 功能。
- `project-docs/technical-architecture.md`：技术架构、方案选择、模块职责和关键工程决策。
- `project-docs/testing-guide.md`：测试范围、测试命令和手动测试流程。
- `project-docs/dependency-management.md`：运行时、依赖升级策略、安全审计和兼容性说明。
- `project-docs/api-key-setup.md`：真实模型和搜索工具 API Key 配置说明。
- `project-docs/changelog.md`：所有重要修改记录。

## 统一运行环境

当前全局环境和项目环境统一为：

```text
Python 3.14.5
Node.js 24.16.0
npm 11.16.0
```

项目根目录提供：

```text
.python-version
.nvmrc
```

进入项目后建议先执行：

```bash
nvm use
python3 --version
node -v
npm -v
```

更多依赖策略见 `project-docs/dependency-management.md`。

## 后端启动

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
PYTHONPATH=backend backend/.venv/bin/uvicorn app.main:app --reload --port 8000
```

健康检查：

```bash
curl http://localhost:8000/health
```

## 前端启动

```bash
cd frontend
nvm use
npm install
npm run dev
```

默认访问：

```text
http://localhost:3000
```

## 环境变量

复制 `.env.example` 后按需配置：

```bash
cp .env.example .env
```

开发模式可以保持：

```text
DEFAULT_PROVIDER=mock
```

当需要接入真实模型时，再配置对应 Provider 的 API Key 和模型名。

真实研究至少需要：

```text
一个模型 Provider 的 API Key
SERPER_API_KEY
```

项目已经内置默认模型名：

```text
OPENAI_MODEL=gpt-5-mini
ANTHROPIC_MODEL=claude-sonnet-4-6
GEMINI_MODEL=gemini-2.5-flash
```

配置完成并重启后端后，可以检查：

```bash
curl http://127.0.0.1:8000/api/readiness
```

更完整说明见 `project-docs/api-key-setup.md`。

## 文档协作要求

每次修改代码、架构、产品方向、配置、依赖或接口，都需要同步更新：

- `project-docs/changelog.md`
- 必要时更新 `project-docs/project-plan.md`
- 必要时更新 `project-docs/product-doc.md`
- 必要时更新 `project-docs/technical-architecture.md`
- 必要时更新 `project-docs/testing-guide.md`
- 必要时更新 `project-docs/dependency-management.md`
- 必要时更新 `project-docs/api-key-setup.md`

## 测试

后端自动化测试：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
```

前端检查：

```bash
cd frontend
npm run lint
npm run build
```

更完整的测试说明见 `project-docs/testing-guide.md`。

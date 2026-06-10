# PZ Deep Research 依赖管理说明

## 文档维护规则

这份文档用于记录项目依赖、运行时版本、升级策略、兼容性判断和已知风险。

只要修改 Python、Node、npm、后端依赖、前端依赖、锁文件、包管理策略或安全审计处理方式，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。

## 核心原则

依赖不是越新越安全，也不是所有 latest 都向下兼容。尤其是运行时和工具链大版本，可能引入破坏性变化。

当前项目采用以下原则：

- 本机全局运行时和项目运行时保持一致，减少“我这里能跑、项目里不能跑”的问题。
- Node.js 使用官方推荐的生产 LTS 线，不追 Current。
- Python 使用官方稳定发行版。
- 项目内写明运行时版本，方便后续新终端、新成员或部署环境复现。
- patch/minor 版本可以积极升级，但必须跑测试。
- major 版本需要先验证兼容性，不能只因为有 latest 就升级。
- 后端保留范围依赖文件和锁定依赖文件：一个方便升级，一个方便复现。
- 每次依赖变更后必须跑后端测试和前端检查。

## 当前统一运行时版本

当前本机全局环境和项目环境已统一为：

```text
Python: 3.14.5
Node.js: 24.16.0
npm: 11.16.0
```

本机路径检查结果：

```text
python3: /usr/local/bin/python3
node: /Users/perry/.nvm/versions/node/v24.16.0/bin/node
npm: /Users/perry/.nvm/versions/node/v24.16.0/bin/npm
```

项目声明文件：

```text
.python-version
.nvmrc
frontend/package.json engines
frontend/package.json packageManager
frontend/.npmrc
```

当前项目约束：

- `.python-version` 固定为 `3.14.5`。
- `.nvmrc` 固定为 `v24.16.0`。
- `frontend/package.json` 声明 `npm@11.16.0`。
- `frontend/package.json` 要求 `node >=24.16.0 <25`、`npm >=11.16.0 <12`。
- `frontend/.npmrc` 开启 `engine-strict=true`，避免用错误 Node/npm 版本安装依赖。

注意：

- 交互式新终端会通过 `~/.zshrc` 使用 nvm default，也就是 Node.js 24.16.0。
- 非交互式 shell 不一定读取 `~/.zshrc`，脚本中应显式执行 `nvm use` 或使用 `.nvmrc`。

## 后端依赖状态

位置：

```text
backend/requirements.txt
backend/requirements-lock.txt
backend/.venv/
```

当前处理：

- 已用 Python 3.14.5 重建 `backend/.venv/`。
- 已升级项目虚拟环境内的 `pip` 到 `26.1.2`。
- 已升级项目虚拟环境内的 `setuptools` 到 `82.0.1`。
- `backend/requirements.txt` 继续记录项目需要的依赖范围。
- `backend/requirements-lock.txt` 记录当前已验证环境的精确依赖版本。

当前主要后端依赖：

```text
fastapi 0.136.3
uvicorn 0.48.0
pydantic 2.13.4
pydantic_core 2.46.4
httpx 0.28.1
openai 2.40.0
anthropic 0.105.2
google-genai 2.7.0
pytest 9.0.3
SQLAlchemy 2.0.50
aiosqlite 0.22.1
psycopg 3.3.4
greenlet 3.5.1
alembic 1.18.4
markdown-it-py 4.2.0
playwright 1.60.0
```

安装建议：

```bash
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install --upgrade pip setuptools
backend/.venv/bin/python -m pip install -r backend/requirements-lock.txt
backend/.venv/bin/playwright install chromium
```

如果是主动做依赖升级，可以改用：

```bash
backend/.venv/bin/python -m pip install -r backend/requirements.txt
```

注意：

- `backend/.venv/` 是本地生成物，不提交到仓库。
- OpenAI、Claude、Gemini 已完成不同程度的真实 API Key 人工联调和最小生成验证，但尚未形成可重复执行的分阶段质量测试集；SDK 升级后仍需要重新做真实调用验证。
- SQLAlchemy 异步接口在当前 Python 3.14 环境需要显式安装 `greenlet`，已写入范围依赖和锁文件。
- SQLite 使用 `aiosqlite`，PostgreSQL 使用 psycopg 3；Alembic 负责两种数据库的结构迁移。
- 后端 Playwright 与前端 `@playwright/test` 均固定为 1.60.0，共用用户缓存 Chromium；`markdown-it-py` 用于安全生成 PDF 打印 HTML。
- 当前 `pip check` 无破损依赖。

## 前端依赖状态

位置：

```text
frontend/package.json
frontend/package-lock.json
frontend/.npmrc
```

当前已升级并验证目标为 Node.js 24 LTS：

```text
next 16.2.7
react 19.2.7
react-dom 19.2.7
lucide-react 1.17.0
typescript 6.0.3
eslint-config-next 16.2.7
eslint 9.39.4
@types/node 24.12.4
@types/react 19.2.16
@types/react-dom 19.2.3
@playwright/test 1.60.0
```

## 未采用 latest 的依赖

### ESLint 10

`npm outdated` 显示：

```text
eslint current 9.39.4
eslint latest 10.4.1
```

处理结果：暂不采用。

原因：

- 已尝试安装 `eslint@latest`。
- `npm run lint` 报错：
  - `Error while loading rule 'react/display-name'`
  - `contextOrFilename.getFilename is not a function`
- 判断为 ESLint 10 与当前 Next.js 16 / eslint-config-next 插件链不兼容。

后续动作：

- 等 Next.js / eslint-config-next 明确支持 ESLint 10 后再升级。

### @types/node 25

`npm outdated` 显示：

```text
@types/node current 24.12.4
@types/node latest 25.9.1
```

处理结果：暂不采用。

原因：

- 当前项目运行时是 Node.js 24.16.0 LTS。
- `@types/node` 应匹配运行时大版本，而不是盲目追最新。
- 使用 Node 25 类型可能让代码误用当前 Node 24 不支持的 API。

后续动作：

- 如果项目运行时升级到 Node 25，再同步升级 `@types/node`。

## 安全审计状态

`npm audit` 当前仍报告 2 个 moderate：

- `next`
- `postcss`

原因：

- 漏洞来自 Next 依赖链中的 PostCSS。
- npm 给出的自动修复方案是将 Next 改为 `9.3.3`，属于破坏性倒退，不应执行。

当前处理：

- 不执行 `npm audit fix --force`。
- 保持 Next.js 16.2.7。
- 后续等待 Next.js 官方依赖链修复，再升级 Next。

## npm 11 安装脚本提示

使用 npm 11 安装依赖时，当前会出现 allow-scripts 提示：

```text
sharp@0.34.5
unrs-resolver@1.12.2
```

当前处理：

- 暂不直接执行 `npm approve-scripts`。
- 先以 `npm run lint` 和 `npm run build` 验证当前依赖是否可用。
- 如果后续生产构建明确需要批准安装脚本，再单独评估并记录原因。

## 升级后验证要求

依赖或运行时变更后至少执行：

```bash
PYTHONPATH=backend backend/.venv/bin/pytest backend/tests
PYTHONPYCACHEPREFIX=/tmp/pz_deep_research_pycache backend/.venv/bin/python -m compileall backend/app
cd backend && DATABASE_URL=sqlite+aiosqlite:////private/tmp/pz-migration-check.db PYTHONPATH=. .venv/bin/alembic upgrade head
cd frontend
npm run lint
npm run build
npm run test:e2e
```

结果需要同步记录到 `project-docs/changelog.md`。

## 后续依赖升级流程

每次依赖升级建议按以下流程：

1. 先跑测试，确认升级前是绿的。
2. 检查 `pip list --outdated`、`npm outdated`、`npm audit`。
3. 区分 patch/minor/major。
4. patch/minor 可以优先升级。
5. major 必须单独升级、单独验证。
6. 如果验证失败，回到兼容版本，并记录原因。
7. 升级后重新跑测试。
8. 更新 `backend/requirements-lock.txt`、本文档和 changelog。

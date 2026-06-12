# PZ Deep Research API Key 配置说明

## 文档维护规则

这份文档用于记录项目真实模型和真实研究工具需要哪些 API Key、环境变量应该怎么填、如何检查配置是否生效。

只要修改模型 Provider、默认模型、搜索工具、网页读取工具、环境变量名称或配置校验逻辑，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。

用户登录使用 Clerk 的独立配置，不属于模型 API Key。登录与历史绑定说明见 `project-docs/auth-setup.md`。

## 结论

如果只跑开发模式，不需要任何 API Key。

当前开发版本以单个主 Provider 运行一次研究任务。如果要测试真实深度研究，至少需要：

```text
当前任务所选模型 Provider 的 API Key
SERPAPI_API_KEY
```

`SERPAPI_API_KEY` 用于 Google Scholar 学术搜索。没有它，项目只能返回开发模式占位搜索结果，不算真正完成学术资料检索。

`JINA_API_KEY` 不是强制必填，但建议配置。它用于 Jina Reader 网页正文读取；不配置时工具仍会尝试读取，但稳定性和额度可能受限。

当前搜索链路为：SerpAPI Google Scholar 负责找论文和学术来源，Jina Reader 负责读取搜索结果 URL 的正文内容。

正式 C 端产品不会让用户选择 Provider 或模型。后续完成分阶段质量测试后，后台会分别为意图识别与追问、搜索词与工具规划、证据卡片生成和最终报告撰写配置模型。届时部署环境需要提供实际生产路由和故障降级所涉及 Provider 的 Key，而不是由用户自行选择使用哪一家。

## 按 Provider 配置

### OpenAI / ChatGPT API

至少填写：

```text
OPENAI_API_KEY=你的 OpenAI API Key
SERPAPI_API_KEY=你的 SerpAPI API Key
```

项目已内置默认模型：

```text
OPENAI_MODEL=gpt-5.4-mini
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_OPTIONS=gpt-5.4-mini,gpt-5.5,gpt-5.4,gpt-5.4-nano,gpt-5-mini,gpt-5-nano
```

说明：OpenAI 当前官方文档建议复杂推理和 coding 从 `gpt-5.5` 开始；如果优先考虑延迟和成本，可以使用 `gpt-5.4-mini` 或 `gpt-5.4-nano`。本项目开发默认先使用成本更可控的 `gpt-5.4-mini`，候选列表仅用于内部联调和质量测试，不代表正式 C 端会开放切换。

可选：

```text
OPENAI_BASE_URL=
OPENAI_MODEL=
OPENAI_MODEL_OPTIONS=
SEARCH_PROVIDER=serpapi
ACADEMIC_SEARCH_ENGINE=google_scholar
JINA_API_KEY=
```

`OPENAI_BASE_URL` 默认使用 OpenAI 官方 API 地址。只有在你使用代理、网关或兼容 OpenAI 协议的第三方服务时，才需要改成对应地址。

### Claude API

至少填写：

```text
ANTHROPIC_API_KEY=你的 Anthropic API Key
SERPAPI_API_KEY=你的 SerpAPI API Key
```

项目已内置默认模型：

```text
ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_MODEL_OPTIONS=claude-sonnet-4-6,claude-opus-4-8,claude-opus-4-7,claude-opus-4-6,claude-haiku-4-5-20251001
ANTHROPIC_EVIDENCE_MODEL=claude-haiku-4-5-20251001
```

说明：默认使用速度、质量和成本较均衡的 Sonnet 4.6。需要最高研究质量时可测试 Opus 4.8；Haiku 4.5 用于低成本和低延迟对照。

可选：

```text
ANTHROPIC_MODEL=
ANTHROPIC_MODEL_OPTIONS=
ANTHROPIC_EVIDENCE_MODEL=
JINA_API_KEY=
```

### Gemini API

至少填写：

```text
GEMINI_API_KEY=你的 Google Gemini API Key
SERPAPI_API_KEY=你的 SerpAPI API Key
```

项目已内置默认模型：

```text
GEMINI_MODEL=gemini-3.5-flash
GEMINI_MODEL_OPTIONS=gemini-3.5-flash,gemini-3.1-pro-preview,gemini-3-flash-preview,gemini-3.1-flash-lite,gemini-2.5-pro,gemini-2.5-flash,gemini-2.5-flash-lite
GEMINI_EVIDENCE_MODEL=gemini-2.5-flash-lite
```

说明：默认使用当前账号已确认可调用的 Gemini 3.5 Flash。候选列表同时保留 3.x 预览模型和 2.5 稳定模型，便于比较质量、速度、成本以及预览版本的稳定性。

可选：

```text
GEMINI_MODEL=
GEMINI_MODEL_OPTIONS=
GEMINI_EVIDENCE_MODEL=
JINA_API_KEY=
```

证据抽取模型只负责把单篇网页正文整理成紧凑证据卡片，不负责生成搜索词或最终报告。当前生产路由固定使用 OpenAI `gpt-5-nano` 抽取证据；内部手动模式选择 Claude 或 Gemini 时，分别使用低成本 Haiku 4.5 和 Gemini 2.5 Flash-Lite，切换主模型不会改变证据抽取模型。

模型调用的临时错误重试配置：

```text
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY_SECONDS=2
LLM_TIMEOUT_SECONDS=60
```

系统只对超时、429、5xx、`UNAVAILABLE`、`RESOURCE_EXHAUSTED` 等临时错误重试，等待时间默认依次为 2、4、8 秒。报告阶段重试会保留已经选定的来源和证据卡片，不重新执行搜索与访问。

## 如果要启用三家后台候选模型

建议填写：

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
SEARCH_PROVIDER=serpapi
ACADEMIC_SEARCH_ENGINE=google_scholar
SERPAPI_API_KEY=
JINA_API_KEY=
```

这些配置适用于内部对比测试，也为后续生产后台路由和 Provider 故障降级做准备。模型名可以先使用项目默认值；如果要按质量、延迟或成本调整，再改：

```text
OPENAI_MODEL=
ANTHROPIC_MODEL=
GEMINI_MODEL=
```

## 配置文件位置

在项目根目录复制环境变量文件：

```bash
cp .env.example .env
```

然后编辑：

```text
.env
```

后端现在会自动读取项目根目录的 `.env`。

修改 `.env` 后需要重启后端服务。

## 配置体检接口

启动后端后，可以访问：

```bash
curl http://127.0.0.1:8000/api/readiness
```

返回内容会告诉你：

- 每个 Provider 是否 ready。
- 缺少哪些环境变量。
- 当前使用哪个默认模型。
- 搜索工具是否配置了 `SERPAPI_API_KEY`，以及当前搜索 Provider / 学术搜索引擎。
- 网页读取工具是否配置了可选的 `JINA_API_KEY`。

## 模型列表接口

启动后端后，可以访问项目内置候选模型列表：

```bash
curl http://127.0.0.1:8000/api/models
```

如果已经填写对应 API Key，可以查询当前账号实际可访问的模型 ID：

```bash
curl http://127.0.0.1:8000/api/models/openai
curl http://127.0.0.1:8000/api/models/anthropic
curl http://127.0.0.1:8000/api/models/gemini
```

该接口只返回模型 ID，不会输出你的 API Key。返回里的 `configured_available` 用来判断项目候选模型里哪些在当前账号下可见。

## 当前开发默认模型

当前开发默认模型遵循“可调用、成本相对可控、适合 Agent / 深度研究”的原则：

- OpenAI：`gpt-5.4-mini`
- Claude：`claude-sonnet-4-6`
- Gemini：`gemini-3.5-flash`

这些值用于当前单主模型联调，并不是最终生产路由结论。下一阶段会通过四类质量测试分别确定意图识别与追问、搜索词与工具规划、证据卡片生成、最终报告撰写所使用的模型。只要调整默认模型或生产路由，需要同步更新本文档和 `project-docs/changelog.md`。

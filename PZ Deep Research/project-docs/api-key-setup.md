# PZ Deep Research API Key 配置说明

## 文档维护规则

这份文档用于记录项目真实模型和真实研究工具需要哪些 API Key、环境变量应该怎么填、如何检查配置是否生效。

只要修改模型 Provider、默认模型、搜索工具、网页读取工具、环境变量名称或配置校验逻辑，都需要同步更新本文档。

每次做了实质修改，还需要同步更新 `project-docs/changelog.md`。

## 结论

如果只跑开发模式，不需要任何 API Key。

如果要跑真实深度研究，至少需要：

```text
一个模型 Provider 的 API Key
SERPER_API_KEY
```

`SERPER_API_KEY` 用于真实网页搜索。没有它，项目只能返回开发模式占位搜索结果，不算真正完成网页研究。

`JINA_API_KEY` 不是强制必填，但建议配置。它用于 Jina Reader 网页正文读取；不配置时工具仍会尝试读取，但稳定性和额度可能受限。

## 按 Provider 配置

### OpenAI / ChatGPT API

至少填写：

```text
OPENAI_API_KEY=你的 OpenAI API Key
SERPER_API_KEY=你的 Serper API Key
```

项目已内置默认模型：

```text
OPENAI_MODEL=gpt-5-mini
```

可选：

```text
OPENAI_BASE_URL=
OPENAI_MODEL=
JINA_API_KEY=
```

`OPENAI_BASE_URL` 只在你使用代理、网关或兼容 OpenAI 协议的第三方服务时填写。

### Claude API

至少填写：

```text
ANTHROPIC_API_KEY=你的 Anthropic API Key
SERPER_API_KEY=你的 Serper API Key
```

项目已内置默认模型：

```text
ANTHROPIC_MODEL=claude-sonnet-4-6
```

可选：

```text
ANTHROPIC_MODEL=
JINA_API_KEY=
```

### Gemini API

至少填写：

```text
GEMINI_API_KEY=你的 Google Gemini API Key
SERPER_API_KEY=你的 Serper API Key
```

项目已内置默认模型：

```text
GEMINI_MODEL=gemini-2.5-flash
```

可选：

```text
GEMINI_MODEL=
JINA_API_KEY=
```

## 如果三家模型都要在前端可选

建议填写：

```text
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
SERPER_API_KEY=
JINA_API_KEY=
```

模型名可以先使用项目默认值。后续如果要按成本或效果调整，再改：

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
PZ Deep Research/.env
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
- 搜索工具是否配置了 `SERPER_API_KEY`。
- 网页读取工具是否配置了可选的 `JINA_API_KEY`。

## 当前默认模型来源

当前默认模型选择遵循“能用于生产、成本相对可控、适合 Agent / 深度研究”的原则：

- OpenAI：`gpt-5-mini`
- Claude：`claude-sonnet-4-6`
- Gemini：`gemini-2.5-flash`

这些默认值后续可以根据成本、质量和账号可用额度调整。只要调整默认模型，需要同步更新本文档和 `project-docs/changelog.md`。

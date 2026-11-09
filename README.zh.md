# GeekCubo

**一个网关，对接所有 AI 模型。**
**开源 AI 网关与智能 LLM 路由器。** 兼容 OpenAI，BYOK，自托管。支持流式传输与 `model="auto"` 路由。
兼容 OpenAI。BYOK。单工作区。流式传输。`model="auto"`。

![GeekCubo](design/brand/geekcubo-logo.png)

[![tests](https://img.shields.io/badge/tests-passing-brightgreen)](./README.md#testing)
[![models](https://img.shields.io/badge/models-100%2B-blue)](#模型目录)
[![license](https://img.shields.io/badge/license-MIT-blue)](#许可证)

## 语言

- [English](./README.md)
- [日本語](./README.ja.md)
- [中文](./README.zh.md)
- [한국어](./README.ko.md)
- [Deutsch](./README.de.md)
- [Français](./README.fr.md)
- [Español](./README.es.md)
- [Italiano](./README.it.md)
- [Русский](./README.ru.md)
- [Português](./README.pt.md)
- [Tiếng Việt](./README.vi.md)
- [हिन्दी](./README.hi.md)

GeekCubo 是一个自托管、兼容 OpenAI 的网关：自带 provider 密钥，`model="auto"` 会为每个请求选择一个合适的模型，并提供故障转移与成本追踪。

> **它适合放在哪里。** LiteLLM 是需要嵌入的库；OpenRouter 仅限托管；Ollama 仅限本地。GeekCubo 是你自己运行的服务器 —— 内置路由、故障转移与计费。

## GeekCubo 为什么存在

自动模型路由应当给开发者带来掌控，而不是不确定。

GeekCubo 源于一个实际问题：即使使用自己的 AI 提供商密钥，也不一定清楚哪个提供商会处理请求、回退是否可能用到单独计费的服务，或者为什么选中了某个模型。

我们想要一个自托管的替代方案，让路由策略、可用的提供商、模型能力、价格假设和回退行为都清晰可见、可以配置。

GeekCubo 正是基于这一原则：**你的密钥，你的基础设施，你的路由决策。**

没有强制的托管路由钱包。由你配置路由器可用的提供商和模型，并且可以查看自动路由是如何做出决策的。

### 开源渊源

GeekCubo 基于 [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite)，一个以 MIT 许可证发布的开源项目。感谢其原始开发者提供了 GeekCubo 得以发展的基础。

GeekCubo 独立开发和维护，拥有自己的功能、架构和产品方向。它与 OrcaRouter 的原始开发者没有关联，也未获其认可。

署名与许可证详情见 [许可证](#许可证)。

## 60 秒快速开始

### 自托管 (BYOK)

在你自己的机器上运行 GeekCubo；自带 provider 密钥。

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

该脚本会检查 Docker 和 Compose、验证配置、执行 `docker compose up -d --build`、等待真正的 `/health` 端点，并在全新安装时显示管理员的一次性设置令牌。重复运行是安全的：数据卷、`.env`、管理员账户、provider 凭据、加密密钥和 API 密钥都会保留。

手动安装（使用相同的 Compose 配置）：

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # 仅在尚无管理员时
```

Base URL：`http://127.0.0.1:8787/v1`。使用在仪表板中生成的 `sk-geek-*` 密钥。设置令牌仅可使用一次，创建管理员后即失效，应像密码一样保管。端口仅绑定到回环地址；远程访问请使用 SSH 隧道或 TLS 反向代理。

在 VPS 上，把 `.env` 中的 `PUBLIC_BASE_URL` 设为你自己的地址——根域名（如 `https://example.com`）或子域名（如 `https://api.example.com`）均可。GeekCubo 完全运行在你的基础设施上，不依赖任何由 GeekCubo 运营的主机；参见 [DEPLOYMENT.md](./DEPLOYMENT.md)。

### 然后从任意 OpenAI SDK 调用

下面的示例使用本地 Docker base URL `http://127.0.0.1:8787/v1`。

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # 或 "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)
```
</details>

<details>
<summary><b>Node.js</b></summary>

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8787/v1",
  apiKey: "sk-geek-abc123...",
});

const r = await client.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(r.choices[0].message.content);
```
</details>

<details>
<summary><b>curl</b></summary>

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-geek-abc123..." \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```
</details>

下面的示例使用本地 Docker base URL `http://127.0.0.1:8787/v1`。

## 为什么？

| | GeekCubo | LiteLLM 库 | OpenRouter | Ollama |
|---|---|---|---|---|
| 自托管服务器 | ✓ | 作为库 | ✗ | ✓ |
| 兼容 OpenAI | ✓ | ✓ | ✓ | ✓ |
| 多 provider（OpenAI/Anthropic/Google/…）| ✓ | ✓ | ✓ | ✗ |
| 内置仪表板 | ✓ | ✗ | ✓ | ✗ |
| `model="auto"`（按策略选择） | ✓ | ✗ | ✗ | n/a |
| 流式传输 | ✓ | ✓ | ✓ | ✓ |
| BYOK | ✓ | ✓ | ✗ | n/a |
| 不需要 Postgres / 不需要 Redis | ✓ | n/a | n/a | ✓ |

## `model="auto"` —— 招牌特性

发送 `model="auto"` 后，GeekCubo 会把可参与 Auto 的模型筛选为能处理该请求的模型，用你在 **Routing** 中选择的策略排序并调用最佳模型，后面还有一条有上限的回退链。无需手写路由规则，应用代码中也无需成本优化逻辑。

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → 只有 Vision 能力为“支持”的模型才会被考虑；
#   由当前策略决定顺序
```

被选中的模型会通过 `x-geek-resolved-model` 响应头回传给调用方，方便你记录或展示实际使用的模型。

### Auto 可以使用哪些模型

每个 Auto 请求按以下顺序筛选候选；任何一步不通过的模型都不会被选中，作为回退也不会：

1. **可用** — 带有有效密钥的内置提供商，或已启用且 *纳入 Auto* 的自定义提供商；模型本身已启用。
2. **已确认价格** — 公开标价或你设置的价格。未知价格绝不视为免费；参考估价只有在你允许时才计入。
3. **具备能力** — 请求所需的每项能力（Tools、Vision、JSON 模式、JSON Schema）均为 **支持**。“未知”不满足任何要求。
4. **上下文可容纳** — 估算的提示词能放进已知的上下文窗口。窗口未知的模型不会因此被排除。
5. **允许** — API 密钥的允许列表，以及路由配置文件的限制。

### 策略

| 策略 | 剩余候选的排序方式 | 缺少数据时 |
|---|---|---|
| **Balanced**（默认） | 质量分与加权价格同等权重；设置质量下限时先排除较弱的模型。只有有质量分的模型参与。 | 没有分数时按价格排序，并在路由备注中说明。 |
| **Cheapest** | 加权价格最低（输入 30%、输出 70%）；同价按模型 id 排序。 | 价格全部未知：没有候选，返回诊断而不是猜测。 |
| **Quality First** | 质量分最高；手动分数优先于 Artificial Analysis。 | 没有分数时以价格为替代（最贵在前），并说明。 |
| **Adaptive** | 依据本安装请求日志（7 天）中观测到的成功率，其次是延迟重新排序。 | 每个模型不足 20 次请求时按 Balanced 运行，并报告样本数。 |
| **Adaptive-Gated** | 把请求分为 *Mundane* 或 *Hard*（工具、图片、长提示词、多条消息、较大的 `max_tokens`），只在对应池中排序。 | 池中没有可用模型：使用 *Fallback* 池，若允许则困难请求再用 *Mundane*；绝不扩大到整个目录。 |
| **Fastest**（旧版） | 基准测试的吞吐量和首个 token 延迟；没有测量数据的模型被排除。 | 没有测量数据时按价格排序，并说明。 |

**使用 Auto：**发送 `model="auto"`，或在聊天中选择 **自动（由路由器选择）**。**指定模型：**发送完整 id，或在聊天中选择。**更改策略：**在 Routing 页面点击策略卡片（立即保存）。**让模型不参与 Auto：**禁用该模型、在其提供商上选择 *从 Auto 排除*，或移除已确认价格。**为什么选这个模型：****测试路由决策**、`x-geek-routing-*` 响应头或 Analytics。**没有可用模型：**返回附带原因的 422，而不是猜测。Auto *模型*路由与预留的网络搜索“自动”模式无关。

仪表板的 Routing 页面提供完整的 Auto 策略：**回退、升级与连续性**（回退尝试次数、升级模式与阈值、目标池、影子模式、粘性），以及**测试路由决策**——一个 dry-run，展示所选模型、层级、策略以及每个淘汰候选的过滤阶段。不会向上游发送任何内容。

## 原生聊天：网络搜索与上下文预算

仪表板的**聊天**标签页会按所选模型的上下文窗口裁剪对话历史。每条回复都会报告
估算 token 数、预算以及省略了多少条较早的消息，因此被缩短的回答不会被误认为
模型故障。

网络搜索是可选的，默认关闭。在**设置 → 聊天 → 网络搜索**中配置 SearXNG
（自托管）、Brave 或 Tavily。SearXNG 可由 `./install.sh` 或
`docker compose --profile search up -d` 启动。搜索密钥加密保存，与推理密钥分开；
引用只针对后端实际返回的页面显示。`auto` 搜索模式为保留项，尚未实现。

## 原生聊天：附件

输入框支持三种方式添加文件：回形针按钮、拖放到对话区域、以及粘贴。粘贴图片会
变成附件，粘贴纯文本仍按原生行为插入。

| 类型 | 格式 | 模型看到的内容 |
|---|---|---|
| `image` | PNG、JPEG、WebP、GIF、BMP、TIFF | 以图像片段发送给支持视觉的模型 |
| `document` | PDF、DOCX、RTF | 提取的文本，带分隔标记 |
| `spreadsheet` | XLSX、XLS、ODS、CSV、TSV | 逐工作表的文本，有长度上限 |
| `text` / `code` | TXT、MD、JSON、YAML、源码 | 原始文本，带分隔标记 |
| `archive` | ZIP、tar、gzip | 条目列表加上有上限的读取；绝不解压到磁盘 |
| `video` / `audio` | MP4、WebM、MOV、MP3、WAV 等 | 视频：元数据加等间隔帧；音频：仅元数据 |

文本类附件总会降级为带分隔标记的文本块，任何模型都能读取。图片只在当前轮次
作为真正的图像片段发送；更早的历史会折叠为 `[attached: name]` 标记，以免虚报
上下文窗口。如果固定的模型不能接收图片，发送会被拒绝并给出 `no_vision`
诊断，而不是静默丢弃文件。

服务器端限制（可通过环境变量调整：`ATTACHMENTS_ENABLED`、
`ATTACHMENT_MAX_MB`、`ATTACHMENT_DIR`，见 `.env.example`）：

- 每条消息最多 8 个附件。
- 每个文件默认 25 MB，并受硬上限约束。
- 未绑定到消息的上传会在 24 小时后清理。

提取失败会按文件单独提示，且不会阻塞你输入的文本。
`GET /api/chat/attachments/limits` 会告知浏览器允许上传的内容，因此界面在发送
前执行同样的规则。

视频帧需要 `PATH` 中有 `ffmpeg`/`ffprobe`；没有时视频仍可上传，但会告知模型
无法读取。音频仅以元数据形式提供给模型——自动语音转写被有意禁用，模型不会被告知
它听到了实际并未听到的内容。

## 本地 AI 接入

把运行在你自己机器上的模型（笔记本上的 Ollama、工作站上的 LM Studio、GPU 机器上
的 vLLM）接入同一个目录、同一套策略和同一条 `model="auto"` 路由。连接器只主动
**向外**拨号：它通过 WebSocket 连接到 GeekCubo，上报能看到的本地模型并响应聊天
请求。无需开放入站端口、隧道、VPN 或云账号。

**仪表板 → 本地 AI 接入 → 连接一台机器** 会引导你完成八个步骤：生成一次性注册码、
运行连接器、批准机器、启用需要的模型，并确认它们已可用于 Auto。

```bash
# 在运行模型的机器上（Python 3.11+，在本仓库检出目录内）
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

连接器会自动探测常见的本地运行时：

| 适配器 | 默认基础 URL | 协议 |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | 原生 `/api/tags`、`/api/show`、`/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | OpenAI 兼容 `/v1` |
| `vllm` | `http://127.0.0.1:8000` | OpenAI 兼容 `/v1` |
| `llamacpp` | `http://127.0.0.1:8080` | OpenAI 兼容 `/v1` |
| `custom` | 无（用 `--url` 指定） | 任意 OpenAI 兼容 `/v1` 服务（Bearer 令牌用 `--api-key`） |

用 `--adapter` 限定探测范围，用 `--url adapter=URL` 指向非默认端口。仪表板提供
现成的 systemd、launchd 和 Windows 服务文件，让连接器随机器启动。

注册码一次性使用，默认 30 分钟后过期，且在管理员批准机器之前不授予任何权限。
批准后本地模型以 `local/<machine>/<model>` 出现在目录中，可直接固定或纳入
`model="auto"`。

本地模型是否参与 Auto 由路由策略的 `local` 段控制：

- `enabled` — 允许已批准的本地模型参与 Auto。
- `no_cloud_fallback` — Auto 选中本地模型而该机器离线时，直接失败而不是静默改用云
  提供商。
- `machines` — 把 Auto 限定在特定机器 id；留空表示所有已批准且允许自动的机器。

本地模型的价格是已确认的零（运行在你自己的硬件上），因此总能通过 Auto 的价格检查，在 **Cheapest** 下排在最前。可以用机器的 Auto 开关或 `local` 策略块把它排除在 Auto 之外。当前链路支持：所有适配器的模型发现、流式文本和自动重连（退避上限 30 秒）；对 Ollama 报告为支持视觉的模型提供图像输入（其他适配器原样转发）。**工具调用不会通过连接器返回**，因此本地模型以不含 Tools 的形式发布，Auto 也不会把需要工具的请求发给它们。

配置（全部可选，见 `.env.example`）：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | 总开关；设为 `false` 会关闭代理端点并隐藏本地模型。 |
| `LOCAL_CONNECT_PUBLIC_URL` | 空 | 写入安装命令和服务文件的公共 URL；为空时显示占位符 `https://your-geekcubo-host`。 |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | 已连接机器上报的间隔（更新最后在线时间）。 |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | 注册码有效期。 |

代理套接字是 `/api/local-connect/agent` 上的 WebSocket，因此前置的反向代理必须
转发 HTTP `Upgrade` 头。`./install.sh` 生成的 Nginx 配置已包含所需的 `map`，
Caddy 会自动处理 WebSocket。内存中的连接中心假定**单个服务进程**；不要让多个
worker 共享负载，重启会断开连接器，直到它们自动重连（退避上限 30 秒）。机器
凭据是持有即可用的秘密：服务端以哈希保存，模型主机上以 `0600` 权限写入，可随时
在仪表板中撤销或轮换。 不支持多个 worker 或多副本；设置 `REDIS_URL` 也不会改变这一点。

## 流式传输

兼容 OpenAI 的 SSE 格式，使用标准的 `data: ... \n\n` 帧格式以及结尾的 `[DONE]` 标记 —— 任何已经从 OpenAI 流式读取的 SDK 都可以即插即用。

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## 原生协议端点（Anthropic + Gemini）

GeekCubo 用同一条路由流水线对外支持三种入站协议。只使用 Anthropic 或 Gemini 传输格式的客户端可以直接连接 —— 无需 OpenAI SDK：

```bash
# Claude Code 指向 GeekCubo（base URL 不带 /v1 后缀）
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN`（以 `Authorization: Bearer` 发送）同样可用；GeekCubo 接受这两种请求头。

```python
# google-genai SDK 指向 GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

请求在边缘层被转换进同一条内部流水线，因此 `model="auto"`、跨 provider 提示缓存（跨协议共享）、路由策略和分析仪表板全都以完全相同的方式工作。指南：[integrations/claude-code.md](./integrations/claude-code.md)、[integrations/gemini-sdk.md](./integrations/gemini-sdk.md)。

## 模型目录

内置目录（受支持提供商的数百个聊天模型）在启动时从 LiteLLM 自带的 [社区维护定价数据库](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) 副本加载 —— 没有需要手动维护的模型清单。每条记录都包含：

- `id`（如 `gpt-4o`、`claude-3-5-sonnet-latest`）
- `provider`（映射到你已配置的密钥）
- 能力标志：`supports_tools`、`supports_vision`、`supports_json_mode`、`supports_json_schema`
- 每 token 的输入/输出成本（驱动节省组件 + `model="auto"`）

`GET /v1/models` 以 OpenAI 格式返回 `auto`、已启用的路由配置文件和完整目录（带 `anthropic-version` 请求头时返回 Anthropic 格式）。

对于自定义提供商的模型，在 **Fetch → Select → Add Selected Models** 时，会从 LiteLLM、Models.dev 和 Portkey 按字段自动解析 Tools、Vision、JSON 模式、JSON Schema、上下文和参考价格，并显示每个字段的来源。只有可靠匹配且有明确值时才标记为支持/不支持，否则保持未知；价格未知不会阻止能力解析。存在歧义的模型在你从可搜索的候选列表中选择目录键之前，不会借用其他模型的元数据。管理员覆盖（包括“未知”）在刷新后保留；选择“使用目录”可取消覆盖。Auto、Chat 和路由配置使用相同的已存储能力。 JSON 模式（json_object）与 JSON Schema／结构化输出（json_schema）是两个独立解析的能力；目录中的结构化输出证据只会映射到 JSON Schema，绝不会当作 JSON 模式的证据。

## 部署到其他平台

GeekCubo 是单个 Docker 容器。不使用 Compose 时，从代码检出构建镜像，并把数据放在命名卷上：

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

带标签的发布已配置为把多架构镜像发布到 `ghcr.io/geekcubo/geekcubo-ai-router`（`.github/workflows/release.yml`）；发布之后即可使用该名称。VPS 与反向代理：[DEPLOYMENT.md](./DEPLOYMENT.md)。

## 盒子里都有什么

- `POST /v1/chat/completions` —— 代理 + 流式传输 + `model="auto"` + 跨 provider 提示缓存
- `POST /v1/messages` —— **Anthropic Messages API 入口**（Claude Code / Anthropic SDK 可直接连接；`+ /count_tokens`）
- `POST /v1beta/models/{model}:generateContent` —— **Gemini API 入口**（google-genai SDK 可直接连接；`+ :streamGenerateContent`、`GET /v1beta/models`）
- `GET  /v1/models` —— `auto`、路由配置文件和模型目录（来自 `litellm.model_cost` 的内置模型，以及自定义和本地模型）
- `GET/PUT/DELETE /v1/providers/{provider}` —— 设置 / 列出 / 撤销加密的 provider 密钥
- `GET/PUT /v1/routing` —— 策略（`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`；旧版 `fastest`）与路由策略；`/v1/routing-profiles` —— 命名的 Auto 配置文件
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` —— 本地分析数据，没有任何遥测离开容器
- `GET/POST/DELETE /v1/keys/...` —— 列出 / 轮换 / 撤销 API 密钥
- `/api/local-connect/*` —— **本地 AI 接入**：注册码、机器批准/撤销/轮换、模型开关、服务文件生成，以及 `/api/local-connect/agent` 上的出站代理 WebSocket（`local/<machine>/<model>` 路由 ID；本地推理仅支持文本）
- `POST /api/chat/attachments` —— 上传/提取/删除聊天附件；`GET /api/chat/attachments/limits` 报告服务器强制执行的限制，界面据此保持一致
- 单页仪表板挂在 `/`
- 仪表板内置**聊天**标签页 — 直接在浏览器里与已部署的模型对话；请求与 SDK 流量一样经过路由、缓存与成本记录（历史仅保存在本地数据库，保留期可配置。每轮都会报告上下文裁剪情况，可选的网络搜索（SearXNG、Brave 或 Tavily）会附加引用）
- 默认 SQLite；可通过 `DATABASE_URL` 切换 Postgres；Redis 可选
- 以 **单个服务进程** 运行。`REDIS_URL` 会把提示词缓存移到 Redis，但 Local AI Connect、Auto 会话状态和 Adaptive 数据不会在进程间共享；不支持多 worker 部署。

### 节省组件

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` 报告你的流量如果使用基准模型会花多少，对比实际花费（按基准模型的公开标价）。价格未知的请求不计为节省。

## ❤️ 支持 GeekCubo

GeekCubo 免费、开源，并且独立开发。你可以通过了解能完善你 AI 环境的服务来支持它的持续开发。

- [**AI API 提供商**](https://geekcubo.com/providers/) — 发现兼容的 AI 模型提供商。
- [**VPS 与云主机**](https://geekcubo.com/hosting/) — 了解适合自托管部署的主机方案。
- [**VPN 与隐私**](https://geekcubo.com/vpn/) — 了解可选的隐私与安全网络工具。

**推广链接说明：** 部分链接可能会为我们带来佣金，你无需支付额外费用。是否使用完全自愿，也不会影响 GeekCubo 的模型路由或提供商兼容性。

## 许可证

MIT。参见 [LICENSE](./LICENSE)。

GeekCubo 派生自 OrcaRouter Lite。原始 MIT 许可证及其版权声明（“Copyright (c) 2026 OrcaRouter contributors”）保留在 [LICENSE](./LICENSE) 中，必须包含在软件的所有副本或主要部分中。

第三方素材遵循各自的许可证：标志中使用的字体轮廓（Inter，SIL Open Font License 1.1）说明见 [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt)。

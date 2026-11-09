# GeekCubo

**Um gateway. Todos os modelos de IA.**
Compatível com OpenAI. BYOK. Auto-hospedado. Streaming e roteamento `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![tests](https://img.shields.io/badge/tests-passing-brightgreen)](./README.md#testing)
[![models](https://img.shields.io/badge/models-100%2B-blue)](#catálogo-de-modelos)
[![license](https://img.shields.io/badge/license-MIT-blue)](#licença)

## Idiomas

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

O GeekCubo é um gateway auto-hospedado e compatível com OpenAI: traga suas próprias chaves de provedor e `model="auto"` escolhe um modelo capaz para cada solicitação, com fallback e rastreamento de custos.

## Por que o GeekCubo existe

O roteamento automático de modelos deveria dar controle aos desenvolvedores, não incerteza.

O GeekCubo nasceu de um problema prático: ao usar suas próprias chaves de provedores de IA, nem sempre é óbvio qual provedor vai atender uma requisição, se um fallback pode usar um serviço cobrado à parte ou por que um determinado modelo foi escolhido.

Queríamos uma alternativa auto-hospedada em que políticas de roteamento, provedores elegíveis, capacidades dos modelos, premissas de preço e comportamento de fallback fossem visíveis e configuráveis.

O GeekCubo é construído sobre esse princípio: **suas chaves, sua infraestrutura, suas decisões de roteamento.**

Não existe carteira de roteamento hospedada obrigatória. Você configura os provedores e modelos disponíveis para o roteador e pode inspecionar como o roteamento automático toma suas decisões.

### Origens open source

O GeekCubo é baseado no [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), um projeto open source publicado sob a licença MIT. Agradecemos aos seus desenvolvedores originais pela base sobre a qual o GeekCubo evoluiu.

O GeekCubo é desenvolvido e mantido de forma independente, com recursos, arquitetura e direção de produto próprios. Não é afiliado nem endossado pelos desenvolvedores originais do OrcaRouter.

Veja [Licença](#licença) para atribuição e detalhes de licenciamento.

## Quickstart de 60 segundos

Rode o GeekCubo na sua própria máquina; traga suas próprias chaves de provider.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

O script verifica Docker e Compose, valida a configuração, executa `docker compose up -d --build`, aguarda o endpoint `/health` real e, em uma instalação nova, mostra o token de configuração de uso único do administrador. Executá-lo novamente é seguro: o volume de dados, `.env`, a conta de administrador, as credenciais dos provedores, os segredos de criptografia e as chaves de API são preservados.

Instalação manual (mesma configuração do Compose):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # apenas enquanto não existir um administrador
```

URL base: `http://127.0.0.1:8787/v1`. Use uma chave `sk-geek-*` gerada no painel. O token de configuração é de uso único, deixa de ser válido quando o administrador é criado e deve ser tratado como uma senha. A porta escuta apenas em loopback; para acesso remoto use um túnel SSH ou um proxy reverso TLS.

Em um VPS, defina `PUBLIC_BASE_URL` no `.env` com o seu próprio endereço — um domínio raiz como `https://example.com` ou um subdomínio como `https://api.example.com`, à sua escolha. O GeekCubo roda inteiramente na sua infraestrutura e não depende de nenhum host operado pelo GeekCubo; veja [DEPLOYMENT.md](./DEPLOYMENT.md).

### Depois chame de qualquer SDK OpenAI

Os exemplos abaixo usam a URL base local do Docker `http://127.0.0.1:8787/v1`.

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # ou "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
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

Os exemplos abaixo usam a URL base local do Docker `http://127.0.0.1:8787/v1`.

## Por quê?

| | GeekCubo | Biblioteca LiteLLM | OpenRouter | Ollama |
|---|---|---|---|---|
| Compatível com OpenAI | ✓ | ✓ | ✓ | ✓ |
| Multi-provider (OpenAI/Anthropic/Google/…) | ✓ | ✓ | ✓ | ✗ |
| Dashboard embutido | ✓ | ✗ | ✓ | ✗ |
| `model="auto"` (seleção por política) | ✓ | ✗ | ✗ | n/a |
| Streaming | ✓ | ✓ | ✓ | ✓ |
| BYOK | ✓ | ✓ | ✗ | n/a |
| Sem Postgres / sem Redis necessário | ✓ | n/a | n/a | ✓ |

## `model="auto"` — a feature destaque

Envie `model="auto"` e o GeekCubo reduz os modelos elegíveis ao Auto aos que podem atender a requisição, ordena-os com a estratégia escolhida em **Routing** e chama o melhor, com uma cadeia de fallback limitada. Sem regras de roteamento manuais nem código de otimização de custos na sua aplicação.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → só entram modelos cuja capacidade Vision é «Suportada»;
#   a estratégia ativa os ordena
```

O modelo resolvido é exposto de volta para quem chamou via header de resposta `x-geek-resolved-model`, para que você possa logar/exibir o que foi realmente usado.

### Quais modelos o Auto pode usar

Cada requisição Auto filtra nesta ordem; um modelo que falha em uma etapa nunca é escolhido, nem como fallback:

1. **Elegível** — um provedor integrado com chave válida, ou um provedor personalizado ativado e *incluído no Auto*; o próprio modelo está ativado.
2. **Preço confirmado** — um preço de tabela ou um preço que você definiu. Um preço desconhecido nunca é tratado como gratuito; uma estimativa de referência só conta se você permitir.
3. **Capaz** — toda capacidade exigida (Tools, Vision, modo JSON, JSON Schema) é **Suportada**. «Desconhecido» nunca satisfaz um requisito.
4. **Cabe** — o prompt estimado cabe em uma janela de contexto conhecida. Uma janela desconhecida não exclui o modelo.
5. **Permitido** — a allowlist da chave de API e, se houver, as restrições de um perfil de roteamento.

### Estratégias

| Estratégia | Como ordena os candidatos restantes | Quando faltam dados |
|---|---|---|
| **Balanced** (padrão) | Peso igual para pontuação de qualidade e preço combinado; um piso de qualidade remove antes os modelos mais fracos. Só participam modelos com pontuação. | Sem pontuações: ordena por preço e informa nas notas de roteamento. |
| **Cheapest** | Menor preço combinado (30 % entrada, 70 % saída); empates por id do modelo. | Todos os preços desconhecidos: nenhum candidato, diagnóstico em vez de chute. |
| **Quality First** | Maior pontuação de qualidade; pontuações manuais substituem a Artificial Analysis. | Sem pontuações: usa o preço como aproximação (o mais caro primeiro) e informa. |
| **Adaptive** | Taxa de sucesso observada e depois latência, do seu próprio log (7 dias). | Menos de 20 requisições por modelo: comporta-se como Balanced e informa. |
| **Adaptive-Gated** | Classifica a requisição como *Mundane* ou *Hard* (ferramentas, imagens, prompts longos, muitas mensagens, `max_tokens` alto) e ordena só esse pool. | Pool sem modelo capaz: pool *Fallback*, depois *Mundane* para requisições difíceis se permitido; nunca o catálogo inteiro. |
| **Fastest** (legado) | Vazão e latência do primeiro token medidas; modelos sem medições são excluídos. | Sem medições: ordena por preço e informa. |

**Usar o Auto:** envie `model="auto"` ou escolha **Auto (o roteador escolhe)** no Chat. **Um modelo específico:** envie o id completo ou escolha no Chat. **Mudar a estratégia:** clique em um cartão em Routing (salvo na hora). **Tirar um modelo do Auto:** desative o modelo, escolha *Excluir do Auto* no provedor ou remova o preço confirmado. **Por que este modelo?** **Testar uma decisão de roteamento**, os cabeçalhos `x-geek-routing-*` ou Analytics. **Nenhum modelo elegível:** um 422 explica o motivo. O roteamento Auto de *modelos* não tem relação com o modo Auto reservado da pesquisa na web.

No painel, a página Routing expõe toda a política do Auto: **Fallback, escalonamento e continuidade** (tentativas de fallback, modo e limites de escalonamento, pool de destino, modo shadow, stickiness) e **Testar uma decisão de roteamento**, um dry-run que mostra o modelo, o tier, a estratégia e cada etapa de filtro que removeu candidatos. Nada é enviado ao provedor.

## Chat nativo: pesquisa na web e orçamento de contexto

A aba **Chat** do painel reduz o histórico da conversa à janela de contexto do
modelo escolhido. Cada resposta informa os tokens estimados, o orçamento e
quantas mensagens antigas foram omitidas, para que uma resposta encurtada nunca
seja confundida com uma falha do modelo.

A pesquisa na web é opcional e desativada por padrão. Configure-a em
**Configurações → Chat → Pesquisa na web** com SearXNG (auto-hospedado), Brave
ou Tavily. O SearXNG pode ser iniciado por `./install.sh` ou com `docker compose
--profile search up -d`. As chaves de pesquisa são armazenadas criptografadas,
separadas das chaves de inferência, e as citações só aparecem para páginas que o
backend realmente retornou. O modo `auto` está reservado e ainda não foi
implementado.

## Chat nativo: anexos

O compositor aceita arquivos de três formas: o clipe, arrastar e soltar sobre a
conversa e colar. Uma imagem colada vira anexo; texto simples colado continua
nativo.

| Tipo | Formatos | O que o modelo vê |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Enviada como partes de imagem a um modelo com visão |
| `document` | PDF, DOCX, RTF | Texto extraído, delimitado |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Texto planilha por planilha, limitado |
| `text` / `code` | TXT, MD, JSON, YAML, código-fonte | Texto bruto, delimitado |
| `archive` | ZIP, tar, gzip | Lista de entradas e leituras limitadas; nunca extraído para o disco |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Vídeo: metadados e quadros igualmente espaçados. Áudio: apenas metadados |

Anexos textuais sempre degradam para um bloco delimitado na mensagem do usuário,
legível por qualquer modelo. Imagens só se tornam partes de imagem reais no turno
atual; no histórico anterior colapsam para um marcador `[attached: name]` para
não falsear a janela de contexto. Se você fixar um modelo sem visão, o envio é
recusado com um diagnóstico `no_vision` em vez de descartar o arquivo em
silêncio.

Limites do servidor (ajustáveis por env: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; veja `.env.example`):

- Até 8 anexos por mensagem.
- 25 MB por arquivo por padrão, com um teto máximo.
- Uploads não vinculados são removidos após 24 horas.

Falhas de extração são exibidas por arquivo e nunca bloqueiam o texto digitado.
`GET /api/chat/attachments/limits` informa ao navegador o que pode ser enviado,
para que a interface aplique as mesmas regras antes de enviar.

Quadros de vídeo precisam de `ffmpeg`/`ffprobe` no `PATH`; sem eles o vídeo ainda
é enviado e o modelo é avisado de que não pode ser lido. O áudio é descrito ao
modelo apenas como metadados — a transcrição automática está deliberadamente
desativada, e nunca se diz ao modelo que ele ouviu algo que não ouviu.

## Conexão de IA local

Traga os modelos que já rodam no seu próprio hardware para o mesmo catálogo, as
mesmas políticas e o mesmo roteamento `model="auto"` dos seus provedores de nuvem.
O conector é um agente somente de saída: ele disca para a sua instância do
GeekCubo via WebSocket, anuncia os modelos locais que encontra e responde pedidos
de chat. Sem porta de entrada, túnel, VPN ou conta de nuvem no meio.

**Painel → Conexão de IA local → Conectar uma máquina** guia oito passos: gerar um
código de inscrição de uso único, executar o conector, aprovar a máquina, habilitar
os modelos desejados e confirmar que estão disponíveis para o Auto.

```bash
# Na máquina que executa os modelos (Python 3.11+), a partir de um checkout deste repositório
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

O conector sonda automaticamente os runtimes locais comuns:

| Adaptador | URL base padrão | Protocolo |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Nativo `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | `/v1` compatível com OpenAI |
| `vllm` | `http://127.0.0.1:8000` | `/v1` compatível com OpenAI |
| `llamacpp` | `http://127.0.0.1:8080` | `/v1` compatível com OpenAI |
| `custom` | nenhuma (use `--url`) | Qualquer servidor `/v1` compatível com OpenAI (`--api-key` para token Bearer) |

Use `--adapter` para limitar a sondagem e `--url adapter=URL` para apontar um
adaptador para uma porta não padrão. `python -m geekcubo_connector ...` equivale
ao script `geekcubo-connector`. O painel oferece arquivos de serviço prontos para
systemd, launchd e Windows, para que o conector reinicie junto com a máquina.

Códigos de inscrição são de uso único, expiram em 30 minutos por padrão e não
concedem nada até que um administrador aprove a máquina. Depois de aprovada, os
modelos locais aparecem no catálogo como `local/<máquina>/<modelo>` e podem ser
fixados diretamente ou incluídos em `model="auto"`.

O roteamento local é regido pelo bloco `local` da política de roteamento:

- `enabled` — inclui modelos locais aprovados no Auto.
- `no_cloud_fallback` — quando o Auto escolhe um modelo local e essa máquina está
  offline, a requisição falha em vez de tentar novamente na nuvem em silêncio.
- `machines` — restringe o Auto a ids de máquina específicos; vazio significa
  todas as aprovadas e elegíveis.

Um modelo local tem preço confirmado zero (roda no seu hardware), por isso sempre passa no filtro de preço do Auto e fica em primeiro no **Cheapest**. Use o interruptor Auto da máquina ou o bloco `local` para excluí-lo. O que o caminho suporta hoje: descoberta de modelos, texto em streaming e reconexão automática (backoff até 30 s) em todos os adaptadores; imagens para modelos que o Ollama informa como compatíveis com visão (os outros adaptadores as recebem sem alteração). **Chamadas de ferramentas não são devolvidas pelo conector**, por isso os modelos locais são anunciados sem Tools e o Auto não lhes envia requisições com ferramentas.

Configuração (tudo opcional, veja `.env.example`):

| Variável | Padrão | Finalidade |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Chave mestra; `false` fecha o endpoint do agente e oculta modelos locais. |
| `LOCAL_CONNECT_PUBLIC_URL` | vazio | URL pública escrita no comando de instalação e nos arquivos de serviço; vazio = marcador `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Com que frequência uma máquina conectada se reporta (atualiza o último contato). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Tempo de vida de um código de inscrição. |

O socket do agente é um WebSocket em `/api/local-connect/agent`, então qualquer
proxy reverso na frente do GeekCubo deve repassar o cabeçalho `Upgrade`. A
configuração do Nginx gerada por `./install.sh` inclui o `map` necessário e o
Caddy trata WebSockets automaticamente. O hub de conexões em memória pressupõe
**um único processo** de servidor; um reinício derruba os conectores até que eles
se reconectem (com recuo de até 30 s). Credenciais de máquina são segredos
portadores: armazenadas com hash no servidor, gravadas com permissão `0600` no
host do modelo, e revogáveis ou rotacionáveis pelo painel a qualquer momento. Vários workers ou réplicas não são suportados; `REDIS_URL` não muda isso.

## Streaming

Formato SSE compatível com OpenAI, com framing padrão `data: ... \n\n` e um sentinel terminal `[DONE]` — drop-in para qualquer SDK que já faz streaming a partir da OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Endpoints de protocolo nativos (Anthropic + Gemini)

O GeekCubo fala três protocolos de entrada sobre um único pipeline de roteamento. Clientes que só falam os wire formats da Anthropic ou do Gemini se conectam diretamente — sem necessidade de SDK OpenAI:

```bash
# Claude Code, apontado para o GeekCubo (sem o sufixo /v1 na URL base)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN` (enviado como `Authorization: Bearer`) também funciona; o GeekCubo aceita os dois cabeçalhos.

```python
# SDK google-genai, apontado para o GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

As requisições são traduzidas na borda para o mesmo pipeline interno, então `model="auto"`, o cache de prompt cross-provider (compartilhado entre protocolos), as estratégias de roteamento e o dashboard de analytics funcionam de forma idêntica. Guias: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Catálogo de modelos

O catálogo integrado (várias centenas de modelos de chat dos provedores suportados) é carregado na inicialização a partir da cópia do [banco de preços da comunidade](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) incluída no LiteLLM; não há lista de modelos para manter. Cada entrada expõe:

- `id` (ex.: `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mapeado para suas chaves configuradas)
- Flags de capacidade: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Custo por token de entrada/saída (alimenta o widget de economia + `model="auto"`)

`GET /v1/models` retorna `auto`, os perfis de roteamento ativos e o catálogo completo no formato OpenAI (no formato Anthropic com o cabeçalho `anthropic-version`).

Para modelos de provedores personalizados, Tools, Vision, modo JSON, esquema JSON, contexto e preços de referência são resolvidos automaticamente, campo a campo, a partir de LiteLLM, Models.dev e Portkey em **Buscar → Selecionar → Adicionar modelos selecionados**, com a fonte de cada campo exibida. Um valor só fica suportado/não suportado com uma correspondência confiável e explícita; caso contrário, permanece Desconhecido, e um preço desconhecido não bloqueia as capacidades. Modelos ambíguos não recebem valores emprestados até que você escolha a chave de catálogo no seletor pesquisável. Substituições do administrador (incluindo «Desconhecido») são mantidas nas atualizações; «Usar catálogo» as remove. Auto, Chat e perfis usam as mesmas capacidades salvas. O modo JSON (json_object) e JSON Schema / saídas estruturadas (json_schema) são capacidades independentes, resolvidas separadamente; evidências de saídas estruturadas do catálogo contam apenas para JSON Schema, nunca para o modo JSON.

## Deploy em outro lugar

O GeekCubo é um único container Docker. Sem Compose, construa a imagem a partir de um checkout e mantenha os dados em um volume nomeado:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

As versões com tag estão preparadas para publicar uma imagem multiarquitetura em `ghcr.io/geekcubo/geekcubo-ai-router` (`.github/workflows/release.yml`); use esse nome quando uma versão tiver sido publicada. VPS e proxy reverso: [DEPLOYMENT.md](./DEPLOYMENT.md).

## O que vem na caixa

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + cache de prompt cross-provider
- `POST /v1/messages` — **ingress da Anthropic Messages API** (Claude Code / SDKs Anthropic se conectam diretamente; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **ingress da Gemini API** (o SDK google-genai se conecta diretamente; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, perfis de roteamento e catálogo de modelos (integrado de `litellm.model_cost`, mais modelos personalizados e locais)
- `GET/PUT/DELETE /v1/providers/{provider}` — define / lista / revoga chaves de provider criptografadas
- `GET/PUT /v1/routing` — estratégia (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; legado `fastest`) e política; `/v1/routing-profiles` — perfis Auto nomeados
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — analytics locais, nenhuma telemetria sai da caixa
- `GET/POST/DELETE /v1/keys/...` — lista / rotaciona / revoga chaves API
- `/api/local-connect/*` — **Conexão de IA local**: códigos de inscrição, aprovação/revogação/rotação de máquinas, alternância de modelos, geração de arquivos de serviço e o WebSocket do agente de saída em `/api/local-connect/agent` (ids de roteamento `local/<machine>/<model>`; inferência local somente texto)
- `POST /api/chat/attachments` — envia/extrai/exclui anexos do chat; `GET /api/chat/attachments/limits` informa os limites impostos pelo servidor para que a UI os respeite
- Dashboard single-page em `/`
- Aba **Chat** integrada no painel — converse com seus modelos implantados pelo navegador; as requisições são roteadas, cacheadas e cobradas exatamente como o tráfego do SDK (o histórico fica no banco de dados local, com retenção configurável; o corte de contexto é informado a cada turno, e a pesquisa na web opcional (SearXNG, Brave ou Tavily) adiciona citações)
- SQLite por padrão; Postgres opt-in via `DATABASE_URL`; Redis opcional
- Roda como **um único processo de servidor**. `REDIS_URL` move o cache de prompts para o Redis, mas não compartilha entre processos o Local AI Connect, o estado de conversa do Auto nem os dados do Adaptive; multi-worker não é suportado.

### Widget de economias

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` informa quanto seu tráfego teria custado com o modelo de referência versus o custo real (preço de tabela da referência). Requisições com preço desconhecido não contam como economia.

## ❤️ Apoie o GeekCubo

O GeekCubo é gratuito, open source e desenvolvido de forma independente. Você pode apoiar o desenvolvimento conhecendo serviços que complementam sua configuração de IA.

- [**Provedores de API de IA**](https://geekcubo.com/providers/) — Descubra provedores de modelos de IA compatíveis.
- [**VPS e hospedagem em nuvem**](https://geekcubo.com/hosting/) — Explore opções de hospedagem para instalações auto-hospedadas.
- [**VPN e privacidade**](https://geekcubo.com/vpn/) — Explore ferramentas opcionais de privacidade e rede segura.

**Aviso de afiliados:** alguns links podem nos render uma comissão sem custo adicional para você. Usá-los é opcional e não influencia o roteamento de modelos do GeekCubo nem a compatibilidade de provedores.

## Licença

MIT. Consulte [LICENSE](./LICENSE).

O GeekCubo deriva do OrcaRouter Lite. A licença MIT original e seu aviso de copyright ("Copyright (c) 2026 OrcaRouter contributors") são preservados em [LICENSE](./LICENSE) e devem ser mantidos em todas as cópias ou partes substanciais do software.

Recursos de terceiros mantêm suas próprias licenças: os contornos de fonte usados no logotipo (Inter, SIL Open Font License 1.1) estão descritos em [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).

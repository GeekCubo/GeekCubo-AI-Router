# GeekCubo

**하나의 게이트웨이. 모든 AI 모델.**
**오픈소스 AI 게이트웨이 및 지능형 LLM 라우터.** OpenAI 호환, BYOK, 자체 호스팅. 스트리밍 및 `model="auto"` 라우팅.
OpenAI 호환. BYOK. 단일 작업 공간. 스트리밍. `모델="자동"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![테스트](https://img.shields.io/badge/tests-passing-brightgreen)](./README.md#testing)
[![모델](https://img.shields.io/badge/models-100%2B-blue)](#모델-카탈로그)
[![라이센스](https://img.shields.io/badge/license-MIT-blue)](#라이선스)

## 언어

- [한국어](./README.md)
- [일본어](./README.ja.md)
- [중국어](./README.zh.md)
- [한국어](./README.ko.md)
- [독일어](./README.de.md)
- [프랑스어](./README.fr.md)
- [스페인어](./README.es.md)
- [이탈리아어](./README.it.md)
- [Русский](./README.ru.md)
- [포르투갈어](./README.pt.md)
- [Tiếng Viet](./README.vi.md)
- [힌디어](./README.hi.md)

GeekCubo는 자체 호스팅되는 OpenAI 호환 게이트웨이입니다. 자체 공급자 키를 가져오면 `model="auto"`가 각 요청에 적합한 모델을 선택하고, 폴백과 비용 추적도 처리합니다.

> **어디에 맞나요?** LiteLLM은 내장하는 라이브러리이고, OpenRouter는 호스팅 전용, Ollama는 로컬 전용입니다. GeekCubo는 라우팅, 폴백, 회계가 내장된 직접 운영하는 서버입니다.

## GeekCubo가 존재하는 이유

자동 모델 라우팅은 개발자에게 불확실성이 아니라 통제권을 주어야 합니다.

GeekCubo는 실제 문제에서 출발했습니다. 자신의 AI 공급자 키를 사용해도 어떤 공급자가 요청을 처리할지, 폴백이 별도로 청구되는 서비스를 사용할 수 있는지, 왜 특정 모델이 선택되었는지가 항상 분명하지는 않습니다.

우리는 라우팅 정책, 사용 가능한 공급자, 모델 기능, 가격 가정, 폴백 동작을 보고 설정할 수 있는 자체 호스팅 대안을 원했습니다.

GeekCubo는 이 원칙 위에 만들어졌습니다: **당신의 키, 당신의 인프라, 당신의 라우팅 결정.**

필수 호스팅 라우팅 지갑은 없습니다. 라우터가 사용할 공급자와 모델은 직접 구성하며, 자동 라우팅이 어떻게 결정하는지 확인할 수 있습니다.

### 오픈소스 기원

GeekCubo는 MIT 라이선스로 공개된 오픈소스 프로젝트 [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite)를 기반으로 합니다. GeekCubo가 발전할 수 있는 토대를 마련해 준 원래 개발자들께 감사드립니다.

GeekCubo는 고유한 기능, 아키텍처, 제품 방향을 갖고 독립적으로 개발·유지됩니다. 원래 OrcaRouter 개발자와 제휴 관계가 없으며 보증을 받지도 않았습니다.

저작자 표시와 라이선스 세부 사항은 [라이선스](#라이선스)를 참조하세요.

## 60초 빠른 시작

### 자체 호스팅(BYOK)

자신의 컴퓨터에서 GeekCubo를 실행하세요. 자신의 공급자 키를 가져오세요.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

이 스크립트는 Docker와 Compose를 확인하고, 구성을 검증하고, `docker compose up -d --build`를 실행하고, 실제 `/health` 엔드포인트를 기다립니다. 새 설치에서는 관리자용 일회성 설정 토큰도 표시합니다. 다시 실행해도 안전합니다. 데이터 볼륨, `.env`, 관리자 계정, 공급자 자격 증명, 암호화 비밀, API 키가 유지됩니다.

수동 설치(동일한 Compose 구성):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # 관리자가 없을 때만
```

기본 URL: `http://127.0.0.1:8787/v1`. 대시보드에서 생성한 `sk-geek-*` 키를 사용하세요. 설정 토큰은 일회용이며 관리자 생성 후 무효가 되고, 비밀번호처럼 다뤄야 합니다. 포트는 루프백에만 바인딩됩니다. 원격 액세스에는 SSH 터널이나 TLS 리버스 프록시를 사용하세요.

VPS에서는 `.env`의 `PUBLIC_BASE_URL`을 자신의 주소로 설정하세요. `https://example.com` 같은 루트 도메인이든 `https://api.example.com` 같은 서브도메인이든 상관없습니다. GeekCubo는 전적으로 자신의 인프라에서 실행되며 GeekCubo가 운영하는 호스트에 의존하지 않습니다. [DEPLOYMENT.md](./DEPLOYMENT.md)를 참조하세요.

### 그런 다음 OpenAI SDK에서 호출하세요.

아래 예에서는 로컬 Docker 기본 URL `http://127.0.0.1:8787/v1`을 사용합니다.

<상세>
<summary><b>파이썬</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # or "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)
```
</details>

<상세>
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

<상세>
<summary><b>컬</b></summary>

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-geek-abc123..." \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```
</details>

아래 예에서는 로컬 Docker 기본 URL `http://127.0.0.1:8787/v1`을 사용합니다.

## 왜?

| | GeekCubo | LiteLLM 라이브러리 | 오픈라우터 | 올라마 |
|---|---|---|---|---|
| 자체 호스팅 서버 | ✓ | 도서관으로 | ✗ | ✓ |
| OpenAI 호환 | ✓ | ✓ | ✓ | ✓ |
| 다중 제공자(OpenAI/Anthropic/Google/…) | ✓ | ✓ | ✓ | ✗ |
| 내장 대시보드 | ✓ | ✗ | ✓ | ✗ |
| `model="auto"` (정책 기반 선택) | ✓ | ✗ | ✗ | 해당 없음 |
| 스트리밍 | ✓ | ✓ | ✓ | ✓ |
| BYOK | ✓ | ✓ | ✗ | 해당 없음 |
| Postgres 없음/Redis 필요 없음 | ✓ | 해당 없음 | 해당 없음 | ✓ |

## `model="auto"` — 헤드라인 기능

`model="auto"`를 보내면 GeekCubo는 Auto 대상 모델 중 요청을 처리할 수 있는 모델만 남기고, **Routing**에서 선택한 전략으로 순위를 매겨 가장 좋은 모델을 호출합니다. 그 뒤에는 제한된 폴백 체인이 있습니다. 수동 라우팅 규칙이나 애플리케이션 내 비용 최적화 코드는 필요 없습니다.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → Vision 기능이 '지원'인 모델만 후보가 되며,
#   활성 전략이 순위를 정합니다
```

해결된 모델은 'x-geek-resolved-model' 응답 헤더를 통해 호출자에게 다시 노출되므로 실제로 사용된 내용을 기록/표시할 수 있습니다.

### Auto가 사용할 수 있는 모델

모든 Auto 요청은 다음 순서로 후보를 거릅니다. 한 단계라도 통과하지 못한 모델은 폴백으로도 선택되지 않습니다.

1. **대상** — 유효한 키가 있는 기본 공급자, 또는 활성화되고 *Auto에 포함*된 사용자 지정 공급자이며 모델 자체도 활성화됨.
2. **확정 가격** — 공개 가격 또는 직접 설정한 가격. 알 수 없는 가격은 무료로 취급되지 않으며, 참조 추정치는 허용한 경우에만 사용됩니다.
3. **기능** — 필요한 모든 기능(Tools, Vision, JSON 모드, JSON Schema)이 **지원**. '알 수 없음'은 요구 사항을 충족하지 않습니다.
4. **컨텍스트** — 추정 프롬프트가 알려진 컨텍스트 창에 들어감. 창을 모르는 모델은 제외되지 않습니다.
5. **허용** — API 키의 허용 목록과 라우팅 프로필의 제한.

### 전략

| 전략 | 남은 후보의 순위 | 데이터가 없을 때 |
|---|---|---|
| **Balanced** (기본) | 품질 점수와 가중 가격에 같은 가중치. 품질 하한이 있으면 약한 모델을 먼저 제외. 점수가 있는 모델만 참여. | 점수가 없으면 가격순으로 정렬하고 라우팅 노트에 표시. |
| **Cheapest** | 가장 낮은 가중 가격(입력 30%, 출력 70%). 동점은 모델 id 순. | 모든 가격을 모르면 후보 없음. 추측 대신 진단을 반환. |
| **Quality First** | 가장 높은 품질 점수. 수동 점수가 Artificial Analysis보다 우선. | 점수가 없으면 가격을 대리 지표로(비싼 순) 사용하고 표시. |
| **Adaptive** | 이 설치의 요청 로그(7일)에서 관측된 성공률, 그다음 지연 시간으로 재정렬. | 모델당 20건 미만이면 Balanced로 동작하고 그 사실을 표시. |
| **Adaptive-Gated** | 요청을 *Mundane* 또는 *Hard*(도구, 이미지, 긴 프롬프트, 많은 메시지, 큰 `max_tokens`)로 분류해 해당 풀에서만 순위 지정. | 풀에 가능한 모델이 없으면 *Fallback* 풀, 허용된 경우 Hard 요청에 *Mundane*. 전체 카탈로그로 넓히지 않음. |
| **Fastest** (레거시) | 벤치마크 처리량과 첫 토큰 시간. 측정값 없는 모델은 제외. | 측정값이 없으면 가격순으로 정렬하고 표시. |

**Auto 사용:** `model="auto"`를 보내거나 채팅에서 **자동(라우터가 선택)** 을 고릅니다. **특정 모델:** 전체 id를 보내거나 채팅에서 선택합니다. **전략 변경:** Routing 페이지에서 전략 카드를 클릭(즉시 저장). **Auto에서 제외:** 모델을 비활성화하거나, 공급자에서 *Auto에서 제외*를 선택하거나, 확정 가격을 지웁니다. **선택 이유:** **라우팅 결정 테스트**, `x-geek-routing-*` 헤더 또는 Analytics. **대상 모델 없음:** 추측 대신 이유가 담긴 422를 반환합니다. Auto *모델* 라우팅은 예약된 웹 검색 '자동' 모드와 관계가 없습니다.

대시보드의 Routing 페이지는 Auto 정책 전체를 제공합니다: **Fallback, 에스컬레이션 및 연속성**(폴백 시도, 에스컬레이션 모드와 임계값, 대상 풀, 섀도 모드, 스티키니스)과 **라우팅 결정 테스트**(선택된 모델, 티어, 전략, 후보를 제거한 각 필터 단계를 보여 주는 드라이런). 프로바이더로는 아무것도 전송되지 않습니다.

## 네이티브 채팅: 웹 검색과 컨텍스트 예산

대시보드의 **채팅** 탭은 대화 기록을 선택한 모델의 컨텍스트 창에 맞게 줄입니다.
각 응답은 추정 토큰 수, 예산, 생략된 이전 메시지 수를 알려 주므로 짧아진
응답을 모델 오류로 오해하지 않습니다.

웹 검색은 선택 사항이며 기본적으로 꺼져 있습니다. **설정 → 채팅 → 웹 검색**에서
SearXNG(자체 호스팅), Brave 또는 Tavily로 구성하세요. SearXNG는
`./install.sh` 또는 `docker compose --profile search up -d`로 시작할 수
있습니다. 검색 키는 추론 키와 분리되어 암호화 저장되며, 인용은 백엔드가 실제로
반환한 페이지에만 표시됩니다. `auto` 검색 모드는 예약되어 있으며 아직 구현되지
않았습니다.

## 네이티브 채팅: 첨부 파일

작성기는 세 가지 방법으로 파일을 받습니다. 클립 버튼, 대화 영역으로 끌어다 놓기,
붙여넣기입니다. 붙여넣은 이미지는 첨부가 되고, 붙여넣은 일반 텍스트는 기존처럼
동작합니다.

| 종류 | 형식 | 모델이 보는 내용 |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | 비전 지원 모델에 이미지 파트로 전송 |
| `document` | PDF, DOCX, RTF | 추출된 텍스트(구분자 포함) |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | 시트별 텍스트, 길이 제한 |
| `text` / `code` | TXT, MD, JSON, YAML, 소스 코드 | 원본 텍스트(구분자 포함) |
| `archive` | ZIP, tar, gzip | 항목 목록과 제한된 읽기. 디스크로 풀지 않습니다 |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV 등 | 비디오: 메타데이터와 균등 간격 프레임. 오디오: 메타데이터만 |

텍스트 첨부는 항상 구분자 블록으로 사용자 메시지에 포함되므로 어떤 모델이든 읽을
수 있습니다. 이미지는 현재 턴에서만 실제 이미지 파트가 되고, 이전 기록에서는
`[attached: name]` 표시로 축약되어 컨텍스트 창을 속이지 않습니다. 비전을 지원하지
않는 모델을 고정하면 파일을 조용히 버리는 대신 `no_vision` 진단과 함께 전송을
거부합니다.

서버 측 제한(환경 변수로 조정: `ATTACHMENTS_ENABLED`, `ATTACHMENT_MAX_MB`,
`ATTACHMENT_DIR`; `.env.example` 참고):

- 메시지당 최대 8개 첨부.
- 기본 파일당 25 MB, 절대 상한으로 제한.
- 메시지에 연결되지 않은 업로드는 24시간 후 정리됩니다.

추출 실패는 파일별로 표시되며 입력한 텍스트를 막지 않습니다.
`GET /api/chat/attachments/limits`가 브라우저에 허용 범위를 알려 주므로 UI는 전송
전에 같은 규칙을 적용합니다.

비디오 프레임에는 `PATH`의 `ffmpeg`/`ffprobe`가 필요합니다. 없어도 업로드는
되지만 읽을 수 없다는 사실이 모델에 전달됩니다. 오디오는 메타데이터로만 모델에
설명됩니다 — 자동 음성 인식은 의도적으로 비활성화되어 있으며, 실제로 듣지 못한
내용을 들었다고 모델에 알리지 않습니다.

## 로컬 AI 연결

이미 내 하드웨어에서 실행 중인 모델을 클라우드 제공자와 동일한 카탈로그, 동일한
정책, 동일한 `model="auto"` 라우팅에 연결합니다. 커넥터는 외부로만 연결하는
에이전트입니다. WebSocket으로 GeekCubo 인스턴스에 접속해 발견한 로컬 모델을
알리고 채팅 요청에 응답합니다. 인바운드 포트, 터널, VPN, 클라우드 계정이 필요
없습니다.

**대시보드 → 로컬 AI 연결 → 머신 연결** 은 여덟 단계로 안내합니다. 일회용 등록
코드를 만들고, 커넥터를 실행하고, 머신을 승인하고, 사용할 모델을 활성화한 뒤
Auto에서 사용 가능한지 확인합니다.

```bash
# 모델이 실행되는 머신에서 (Python 3.11 이상, 이 저장소 체크아웃 기준)
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

커넥터는 일반적인 로컬 런타임을 자동으로 탐지합니다.

| 어댑터 | 기본 베이스 URL | 프로토콜 |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | 네이티브 `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | OpenAI 호환 `/v1` |
| `vllm` | `http://127.0.0.1:8000` | OpenAI 호환 `/v1` |
| `llamacpp` | `http://127.0.0.1:8080` | OpenAI 호환 `/v1` |
| `custom` | 없음 (`--url`로 지정) | 모든 OpenAI 호환 `/v1` 서버(Bearer 토큰은 `--api-key`) |

`--adapter`로 탐지 범위를 제한하고 `--url adapter=URL`로 기본이 아닌 포트를
지정합니다. `python -m geekcubo_connector ...` 는 `geekcubo-connector`
스크립트와 같습니다. 대시보드는 systemd, launchd, Windows 서비스 파일을
제공하므로 커넥터가 머신과 함께 다시 시작됩니다.

등록 코드는 일회용이며 기본 30분 후 만료되고, 관리자가 머신을 승인하기 전까지
아무 권한도 주지 않습니다. 승인 후 로컬 모델은 `local/<머신>/<모델>` 로
카탈로그에 나타나며 직접 고정하거나 `model="auto"` 에 포함할 수 있습니다.

로컬 라우팅은 라우팅 정책의 `local` 블록으로 제어합니다.

- `enabled` — 승인된 로컬 모델을 Auto에 포함합니다.
- `no_cloud_fallback` — Auto가 로컬 모델을 골랐는데 머신이 오프라인이면 조용히
  클라우드로 재시도하지 않고 요청을 실패시킵니다.
- `machines` — Auto를 특정 머신 id로 제한합니다. 비어 있으면 승인되었고 자동
  대상인 모든 머신입니다.

로컬 모델의 가격은 확정된 0(자신의 하드웨어에서 실행)이므로 Auto의 가격 검사를 항상 통과하고 **Cheapest**에서 가장 앞에 옵니다. 머신의 Auto 스위치나 `local` 블록으로 Auto에서 제외할 수 있습니다. 현재 경로가 지원하는 것: 모든 어댑터에서 모델 검색, 스트리밍 텍스트, 자동 재연결(최대 30초 백오프). Ollama가 비전 지원으로 보고한 모델에 대한 이미지 입력(다른 어댑터에는 그대로 전달). **도구 호출은 커넥터를 통해 반환되지 않으므로** 로컬 모델은 Tools 없이 게시되며 Auto는 도구가 필요한 요청을 보내지 않습니다.

설정(모두 선택 사항, `.env.example` 참고):

| 변수 | 기본값 | 용도 |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | 마스터 스위치. `false`면 에이전트 엔드포인트를 닫고 로컬 모델을 숨깁니다. |
| `LOCAL_CONNECT_PUBLIC_URL` | 비어 있음 | 설치 명령과 서비스 파일에 쓰이는 공개 URL. 비어 있으면 `https://your-geekcubo-host` 자리 표시자. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | 연결된 머신이 보고하는 간격(마지막 확인 시각 갱신). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | 등록 코드 유효 기간. |

에이전트 소켓은 `/api/local-connect/agent` 의 WebSocket이므로 GeekCubo 앞의
모든 리버스 프록시는 HTTP `Upgrade` 헤더를 전달해야 합니다. `./install.sh`가
생성하는 Nginx 설정에는 필요한 `map`이 포함되어 있고 Caddy는 WebSocket을
자동으로 처리합니다. 메모리 내 연결 허브는 **단일 서버 프로세스** 를
전제합니다. 재시작하면 커넥터가 끊기고 다시 연결될 때까지(최대 30초 백오프)
복구되지 않습니다. 머신 자격 증명은 베어러 비밀입니다. 서버에는 해시로
저장되고, 모델 호스트에는 `0600` 권한으로 기록되며, 대시보드에서 언제든지
해지하거나 회전할 수 있습니다. 여러 워커나 레플리카는 지원되지 않으며 `REDIS_URL`도 이를 바꾸지 않습니다.

## 스트리밍

표준 `data: ... \n\n` 프레이밍 및 터미널 `[DONE]` 센티널을 갖춘 OpenAI 호환 SSE 형식 — 이미 OpenAI에서 스트리밍하는 모든 SDK에 대한 드롭인입니다.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## 네이티브 프로토콜 엔드포인트(Anthropic + Gemini)

GeekCubo는 하나의 라우팅 파이프라인에 대해 세 가지 수신 프로토콜을 말합니다. Anthropic 또는 Gemini 와이어 형식만 말하는 클라이언트도 직접 연결됩니다. OpenAI SDK가 필요하지 않습니다:

```bash
# Claude Code, pointed at GeekCubo (no /v1 suffix in the base URL)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN`(`Authorization: Bearer`로 전송)도 동작합니다. GeekCubo는 두 헤더를 모두 받습니다.

```python
# google-genai SDK, pointed at GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

요청은 에지에서 동일한 내부 파이프라인으로 변환되므로 `model="auto"`, 교차 제공자 프롬프트 캐시(프로토콜 간 공유), 라우팅 전략, 분석 대시보드가 모두 동일하게 작동합니다. 가이드: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md)를 참조하세요.

## 모델 카탈로그

기본 카탈로그(지원 공급자의 수백 개 채팅 모델)는 LiteLLM에 포함된 [커뮤니티 가격 데이터베이스](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) 사본에서 시작 시 로드됩니다. 모델 목록을 직접 관리할 필요가 없습니다. 각 항목에는 다음이 포함됩니다:

- `id`(예: `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider`(구성된 키에 매핑됨)
- 기능 플래그: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- 토큰당 입/출력 비용(절감 위젯 + `model="auto"` 구동)

`GET /v1/models`는 `auto`, 활성화된 라우팅 프로필, 전체 카탈로그를 OpenAI 형식으로 반환합니다(`anthropic-version` 헤더가 있으면 Anthropic 형식).

커스텀 프로바이더 모델은 **Fetch → Select → Add Selected Models** 시점에 Tools, Vision, JSON 모드, JSON Schema, 컨텍스트, 참고 가격이 LiteLLM·Models.dev·Portkey에서 필드별로 자동 확인되며 각 필드의 출처가 표시됩니다. 신뢰할 수 있는 일치에 명시적 값이 있을 때만 지원/미지원으로 설정되고, 그렇지 않으면 알 수 없음으로 남습니다. 가격을 알 수 없어도 기능 확인은 막히지 않습니다. 모호한 모델은 검색 가능한 후보 목록에서 카탈로그 키를 선택할 때까지 다른 모델의 값을 빌려오지 않습니다. 관리자 재정의("알 수 없음" 포함)는 새로고침 후에도 유지되며 "카탈로그 사용"으로 해제합니다. Auto, Chat, 프로필은 같은 저장된 기능을 사용합니다. JSON 모드(json_object)와 JSON Schema / 구조화된 출력(json_schema)은 독립적으로 해석되는 별개의 기능입니다. 카탈로그의 구조화 출력 증거는 JSON Schema에만 적용되며 JSON 모드의 증거로 사용되지 않습니다.

## 다른 곳에 배포

GeekCubo는 단일 Docker 컨테이너입니다. Compose 없이 사용할 때는 체크아웃에서 이미지를 빌드하고 데이터를 이름 있는 볼륨에 둡니다.

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

태그된 릴리스는 `ghcr.io/geekcubo/geekcubo-ai-router`에 멀티 아키텍처 이미지를 게시하도록 설정되어 있습니다(`.github/workflows/release.yml`). 릴리스가 게시된 뒤 그 이름을 사용하세요. VPS와 리버스 프록시: [DEPLOYMENT.md](./DEPLOYMENT.md).

## 상자 안에 무엇이 들어있나요?

- `POST /v1/chat/completions` — 프록시 + 스트리밍 + `model="auto"` + 교차 제공자 프롬프트 캐시
- `POST /v1/messages` — **Anthropic Messages API 인그레스**(Claude Code / Anthropic SDK가 직접 연결, `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **Gemini API 인그레스**(google-genai SDK가 직접 연결, `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, 라우팅 프로필, 모델 카탈로그(`litellm.model_cost` 기반 기본 모델과 사용자 지정·로컬 모델)
- `GET/PUT/DELETE /v1/providers/{provider}` — 암호화된 공급자 키 설정/목록/해지
- `GET/PUT /v1/routing` — 전략(`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`, 레거시 `fastest`)과 정책. `/v1/routing-profiles` — 이름 있는 Auto 프로필
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — 로컬 분석, 원격 분석은 외부로 나가지 않음
- `GET/POST/DELETE /v1/keys/...` — API 키 나열 / 회전 / 취소
- `/api/local-connect/*` — **로컬 AI 연결**: 등록 코드, 머신 승인/취소/회전, 모델 토글, 서비스 파일 생성, 그리고 `/api/local-connect/agent`의 아웃바운드 에이전트 WebSocket (`local/<machine>/<model>` 라우팅 ID, 로컬 추론은 텍스트 전용)
- `POST /api/chat/attachments` — 채팅 첨부 업로드/추출/삭제; `GET /api/chat/attachments/limits`가 서버가 강제하는 제한을 알려 주어 UI가 같은 규칙을 적용합니다
- `/`의 단일 페이지 대시보드
- 대시보드 내장 **채팅** 탭 — 브라우저에서 배포된 모델과 대화합니다. 요청은 SDK 트래픽과 동일하게 라우팅·캐시·비용 추적됩니다(기록은 로컬 DB에만 저장되며 보관 기간을 설정할 수 있습니다. 컨텍스트 축약은 매 턴 보고되며, 선택적 웹 검색(SearXNG, Brave, Tavily)이 인용을 추가합니다)
- 기본적으로 SQLite; Postgres는 `DATABASE_URL`을 통해 선택합니다. Redis 선택 사항
- **하나의 서버 프로세스**로 실행됩니다. `REDIS_URL`은 프롬프트 캐시를 Redis로 옮기지만 Local AI Connect, Auto 대화 상태, Adaptive 데이터는 프로세스 간에 공유되지 않습니다. 다중 워커 구성은 지원되지 않습니다.

### 저축 위젯

`GET /v1/analytics/savings?baseline=gpt-4o&days=7`은 트래픽을 기준 모델로 처리했을 때의 비용과 실제 비용을 비교합니다(기준 모델의 공개 가격 사용). 가격을 모르는 요청은 절감액에 포함하지 않습니다.

## ❤️ GeekCubo 후원하기

GeekCubo는 무료 오픈소스이며 독립적으로 개발됩니다. AI 환경을 보완하는 서비스를 살펴보는 것으로 지속적인 개발을 후원할 수 있습니다.

- [**AI API 공급자**](https://geekcubo.com/providers/) — 호환되는 AI 모델 공급자를 찾아보세요.
- [**VPS 및 클라우드 호스팅**](https://geekcubo.com/hosting/) — 자체 호스팅 배포를 위한 호스팅 옵션을 살펴보세요.
- [**VPN 및 개인정보 보호**](https://geekcubo.com/vpn/) — 선택적인 개인정보 보호 및 보안 네트워킹 도구를 살펴보세요.

**제휴 링크 고지:** 일부 링크를 통해 추가 비용 없이 저희가 수수료를 받을 수 있습니다. 이용은 선택 사항이며 GeekCubo의 모델 라우팅이나 공급자 호환성에 영향을 주지 않습니다.

## 라이선스

MIT. [LICENSE](./LICENSE)를 참조하세요.

GeekCubo는 OrcaRouter Lite에서 파생되었습니다. 원래의 MIT 라이선스와 저작권 고지("Copyright (c) 2026 OrcaRouter contributors")는 [LICENSE](./LICENSE)에 보존되어 있으며, 소프트웨어의 모든 사본이나 상당 부분에 포함되어야 합니다.

제3자 자산은 각자의 라이선스를 따릅니다. 로고에 사용된 글꼴 윤곽선(Inter, SIL Open Font License 1.1)은 [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt)에 설명되어 있습니다.

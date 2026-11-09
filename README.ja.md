# GeekCubo

**ひとつのゲートウェイ。すべての AI モデル。**
**オープンソースの AI ゲートウェイ＆インテリジェント LLM ルーター。** OpenAI 互換、BYOK、セルフホスト。ストリーミングと `model="auto"` ルーティング。
OpenAI対応。ビヨク。単一のワークスペース。ストリーミング中。 `モデル="自動"`。

![GeekCubo](design/brand/geekcubo-logo.png)

[![テスト](https://img.shields.io/badge/tests-passing-brightgreen)](./README.md#testing)
[![モデル](https://img.shields.io/badge/models-100%2B-blue)](#モデルカタログ)
[![ライセンス](https://img.shields.io/badge/license-MIT-blue)](#ライセンス)

## 言語

- [英語](./README.md)
- [日本語](./README.ja.md)
- [中文](./README.zh.md)
- [한국어](./README.ko.md)
- [ドイツ語](./README.de.md)
- [フランス語](./README.fr.md)
- [スペイン語](./README.es.md)
- [イタリア語](./README.it.md)
- [Русский](./README.ru.md)
- [ポルトガル語](./README.pt.md)
- [Tiếng Việt](./README.vi.md)
- [हिन्दी](./README.hi.md)

GeekCubo は、セルフホスト型で OpenAI 互換のゲートウェイです。独自のプロバイダー キーを持ち込めば、`model="auto"` が各リクエストに適切なモデルを選択し、フォールバックとコスト追跡も行います。

> **位置づけ。** LiteLLM は組み込むライブラリ、OpenRouter はホスト型のみ、Ollama はローカルのみ。GeekCubo は、ルーティング・フォールバック・会計が組み込まれた、自分で運用するサーバーです。

## GeekCubo が存在する理由

自動モデルルーティングは、開発者に不確実性ではなく制御をもたらすべきです。

GeekCubo は実際の問題から生まれました。自分の AI プロバイダーキーを使っていても、どのプロバイダーがリクエストを処理するのか、フォールバックが別料金のサービスを使うことがあるのか、なぜ特定のモデルが選ばれたのかが、必ずしも明らかではありません。

私たちは、ルーティングポリシー、対象となるプロバイダー、モデルの機能、価格の前提、フォールバックの動作が見えて設定できる、セルフホスト型の選択肢を求めていました。

GeekCubo はその原則に基づいています: **あなたのキー、あなたのインフラ、あなたのルーティング判断。**

必須のホスト型ルーティングウォレットはありません。ルーターが使えるプロバイダーとモデルはあなたが設定し、自動ルーティングがどのように判断したかを確認できます。

### オープンソースの起源

GeekCubo は、MIT ライセンスで公開されたオープンソースプロジェクト [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite) を基盤としています。GeekCubo が発展する土台を提供してくれた元の開発者の皆さんに感謝します。

GeekCubo は独自の機能、アーキテクチャ、製品方針のもとで独立して開発・保守されています。元の OrcaRouter 開発者とは提携しておらず、承認も受けていません。

帰属表示とライセンスの詳細は [ライセンス](#ライセンス) を参照してください。

## 60 秒のクイックスタート

### セルフホスト型 (BYOK)

自分のマシンで GeekCubo を実行します。独自のプロバイダー キーを持参してください。

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

このスクリプトは Docker と Compose を確認し、設定を検証して `docker compose up -d --build` を実行し、実際の `/health` エンドポイントを待機します。新規インストールでは管理者用のワンタイムセットアップトークンも表示します。再実行しても安全です。データボリューム、`.env`、管理者アカウント、プロバイダー認証情報、暗号化シークレット、API キーは保持されます。

手動インストール（同じ Compose 設定を使用）:

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # 管理者が存在しない間のみ
```

ベース URL: `http://127.0.0.1:8787/v1`。ダッシュボードで生成した `sk-geek-*` キーを使用してください。セットアップトークンは 1 回限り有効で、管理者の作成後は無効になります。パスワードと同様に扱ってください。ポートはループバックにのみ公開されます。リモートアクセスには SSH トンネルまたは TLS リバースプロキシを使用してください。

VPS では `.env` の `PUBLIC_BASE_URL` に自分のアドレスを設定します。`https://example.com` のようなルートドメインでも `https://api.example.com` のようなサブドメインでも構いません。GeekCubo は完全に自分のインフラ上で動作し、GeekCubo が運営するホストには依存しません。詳しくは [DEPLOYMENT.md](./DEPLOYMENT.md) を参照してください。

### 次に、任意の OpenAI SDK から呼び出します。

以下の例では、ローカルの Docker ベース URL `http://127.0.0.1:8787/v1` を使います。

<詳細>
<概要><b>Python</b></summary>

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

<詳細>
<概要><b>Node.js</b></summary>

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

<詳細>
<概要><b>カール</b></summary>

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer sk-geek-abc123..." \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```
</details>

以下の例では、ローカルの Docker ベース URL `http://127.0.0.1:8787/v1` を使います。

＃＃ なぜ？

| | GeekCubo | LiteLLM ライブラリ |オープンルーター |オラマ |
|---|---|---|---|---|
|セルフホスト型サーバー | ✓ |図書館として | ✗ | ✓ |
| OpenAI対応 | ✓ | ✓ | ✓ | ✓ |
|マルチプロバイダー (OpenAI/Anthropic/Google/…) | ✓ | ✓ | ✓ | ✗ |
|内蔵ダッシュボード | ✓ | ✗ | ✓ | ✗ |
| `model="auto"`（ポリシーに基づく選択） | ✓ | ✗ | ✗ |該当なし |
|ストリーミング | ✓ | ✓ | ✓ | ✓ |
|ビヨク | ✓ | ✓ | ✗ |該当なし |
| Postgres や Redis は不要 | ✓ |該当なし |該当なし | ✓ |

## `model="auto"` — 見出し機能

`model="auto"` を送ると、GeekCubo は Auto 対象のモデルをリクエストに対応できるものに絞り込み、**Routing** で選んだ戦略で順位付けして最上位を呼び出します。その後ろには上限付きのフォールバックが続きます。手動のルーティングルールも、アプリケーション側のコスト最適化コードも不要です。

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → Vision 機能が「対応」のモデルだけが候補になり、
#   有効な戦略が順位を決めます
```

解決されたモデルは「x-geek-resolved-model」応答ヘッダーを介して呼び出し元に公開されるため、実際に使用されたものをログ/表示できます。

### Auto が使えるモデル

Auto リクエストは次の順に候補を絞ります。どこかで外れたモデルは、フォールバックとしても選ばれません。

1. **対象** — 有効なキーを持つ組み込みプロバイダー、または有効化され *Auto に含める* 設定のカスタムプロバイダーで、モデル自体も有効。
2. **確定価格** — 公開価格、または管理者が設定した価格。不明な価格は無料扱いされず、参照見積もりは許可した場合のみ使われます。
3. **機能** — 必要な機能（Tools、Vision、JSON モード、JSON Schema）がすべて **対応**。「不明」は要件を満たしません。
4. **コンテキスト** — 推定プロンプトが既知のコンテキストウィンドウに収まる。ウィンドウ不明のモデルは除外されません。
5. **許可** — API キーの許可リストと、ルーティングプロファイルの制限。

### 戦略

| 戦略 | 残った候補の順位付け | データがない場合 |
|---|---|---|
| **Balanced**（既定） | 品質スコアと加重価格を同じ重みで評価。品質下限があれば弱いモデルを先に除外。スコアのあるモデルのみ対象。 | スコアがない場合は価格順にし、ルーティングノートに明記。 |
| **Cheapest** | 加重価格（入力 30%、出力 70%）が最安。同点はモデル id 順。 | すべて価格不明なら候補なし。推測せず診断を返す。 |
| **Quality First** | 品質スコアが最高。手動スコアが Artificial Analysis より優先。 | スコアがない場合は価格を代替指標に（高い順）し、明記。 |
| **Adaptive** | このインストールのリクエストログ（7 日間）の成功率、次にレイテンシで再順位付け。 | 1 モデルあたり 20 件未満なら Balanced として動作し、その旨を表示。 |
| **Adaptive-Gated** | リクエストを *Mundane* か *Hard*（ツール、画像、長いプロンプト、多数のメッセージ、大きな `max_tokens`）に分類し、そのプールだけで順位付け。 | プールに対応モデルがなければ *Fallback* プール、許可されていれば Hard 要求に *Mundane*。カタログ全体には広げません。 |
| **Fastest**（レガシー） | ベンチマークのスループットと初回トークン時間。測定値のないモデルは除外。 | 測定値がない場合は価格順にし、明記。 |

**Auto を使う:** `model="auto"` を送るか、チャットで **自動（ルーターが選択）** を選びます。**特定のモデル:** 完全な id を送るか、チャットで選びます。**戦略の変更:** Routing ページで戦略カードをクリック（即保存）。**Auto から外す:** モデルを無効にする、プロバイダーで *Auto から除外* を選ぶ、または確定価格を削除。**選ばれた理由:** **ルーティング決定をテスト**、`x-geek-routing-*` ヘッダー、または Analytics。**対象モデルがない:** 推測せず理由付きの 422 を返します。Auto の *モデル* ルーティングは、予約済みの Web 検索「自動」モードとは無関係です。

ダッシュボードの Routing ページでは Auto ポリシー全体を操作できます: **Fallback・エスカレーション・継続性**（フォールバック試行、エスカレーションモードとしきい値、宛先プール、シャドウモード、スティッキネス）と、**ルーティング決定をテスト**（選択モデル、ティア、戦略、候補を除外した各フィルター段階を示すドライラン）。プロバイダーには何も送信されません。

## ネイティブチャット: Web 検索とコンテキスト予算

ダッシュボードの**チャット**タブは、会話履歴を選択したモデルのコンテキスト
ウィンドウに収まるよう切り詰めます。各応答は推定トークン数、予算、省略された
古いメッセージ数を示すため、短くなった応答をモデルの障害と取り違えることは
ありません。

Web 検索は任意で、既定では無効です。**設定 → チャット → Web 検索**で
SearXNG(セルフホスト)、Brave、Tavily を構成します。SearXNG は
`./install.sh` または `docker compose --profile search up -d` で起動できます。
検索キーは推論キーとは別に暗号化して保存され、引用はバックエンドが実際に
返したページにのみ表示されます。`auto` 検索モードは予約済みで、まだ実装
されていません。

## ネイティブチャット: 添付ファイル

コンポーザーは 3 通りでファイルを受け付けます。クリップボタン、会話領域への
ドラッグ＆ドロップ、貼り付けです。貼り付けた画像は添付ファイルになり、貼り付けた
プレーンテキストは従来どおりの動作をします。

| 種類 | 形式 | モデルが受け取る内容 |
|---|---|---|
| `image` | PNG、JPEG、WebP、GIF、BMP、TIFF | 視覚対応モデルへ画像パートとして送信 |
| `document` | PDF、DOCX、RTF | 抽出したテキスト（区切り付き） |
| `spreadsheet` | XLSX、XLS、ODS、CSV、TSV | シートごとのテキスト（上限あり） |
| `text` / `code` | TXT、MD、JSON、YAML、ソースコード | 生テキスト（区切り付き） |
| `archive` | ZIP、tar、gzip | エントリ一覧と上限付きの読み取り。ディスクへ展開はしません |
| `video` / `audio` | MP4、WebM、MOV、MP3、WAV など | 動画: メタデータと等間隔のフレーム。音声: メタデータのみ |

テキスト系の添付は常に区切り付きブロックとしてユーザーメッセージに含まれるため、
どのモデルでも読めます。画像が実際の画像パートになるのは現在のターンだけで、
過去の履歴では `[attached: name]` のマーカーに畳まれ、コンテキストウィンドウを
偽らないようにします。視覚非対応のモデルを固定している場合、ファイルを黙って
捨てるのではなく `no_vision` 診断付きで送信を拒否します。

サーバー側の制限（環境変数で調整: `ATTACHMENTS_ENABLED`、
`ATTACHMENT_MAX_MB`、`ATTACHMENT_DIR`。`.env.example` 参照）:

- 1 メッセージあたり最大 8 個の添付。
- 既定で 1 ファイル 25 MB、上限でクランプ。
- メッセージに紐付いていないアップロードは 24 時間後に削除。

抽出の失敗はファイル単位で通知され、入力したテキストを妨げることはありません。
`GET /api/chat/attachments/limits` がブラウザに許可内容を伝えるため、UI は送信前
に同じルールを適用します。

動画のフレームには `PATH` 上の `ffmpeg`/`ffprobe` が必要です。無い場合でも
アップロードは成功し、読み取れないことがモデルに伝えられます。音声はメタデータ
としてのみモデルに説明されます — 自動文字起こしは意図的に無効で、実際には
聞いていない内容を聞いたとは伝えません。

## ローカル AI コネクト

自分のハードウェアで動いているモデルを、クラウドプロバイダと同じカタログ、同じ
ポリシー、同じ `model="auto"` ルーティングに参加させます。コネクタは外向き専用の
エージェントです。WebSocket で GeekCubo に接続し、見つけたローカルモデルを通知し、
チャット要求に応答します。受信ポート、トンネル、VPN、クラウドアカウントは不要です。

**ダッシュボード → ローカル AI コネクト → マシンを接続** は 8 ステップで案内
します。1 回限りの登録コードを発行し、コネクタを実行し、マシンを承認し、使う
モデルを有効化して、Auto で利用できることを確認します。

```bash
# モデルを動かすマシンで（Python 3.11 以上、このリポジトリのチェックアウト内）
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

コネクタは一般的なローカルランタイムを自動検出します。

| アダプター | 既定のベース URL | プロトコル |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | ネイティブ `/api/tags`、`/api/show`、`/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | OpenAI 互換 `/v1` |
| `vllm` | `http://127.0.0.1:8000` | OpenAI 互換 `/v1` |
| `llamacpp` | `http://127.0.0.1:8080` | OpenAI 互換 `/v1` |
| `custom` | なし（`--url` で指定） | 任意の OpenAI 互換 `/v1` サーバー（Bearer トークンは `--api-key`） |

`--adapter` で検出対象を絞り、`--url adapter=URL` で既定以外のポートを指定します。
`python -m geekcubo_connector ...` は `geekcubo-connector` スクリプトと同じです。
ダッシュボードは systemd、launchd、Windows のサービスファイルを生成するので、
コネクタをマシンと一緒に起動できます。

登録コードは 1 回限りで、既定では 30 分で失効し、管理者がマシンを承認するまで
何の権限も与えません。承認後、ローカルモデルは
`local/<マシン>/<モデル>` としてカタログに現れ、直接固定したり
`model="auto"` に含めたりできます。

ローカルのルーティングはルーティングポリシーの `local` ブロックで制御します。

- `enabled` — 承認済みのローカルモデルを Auto に含めます。
- `no_cloud_fallback` — Auto がローカルモデルを選んだのにマシンがオフラインの
  場合、黙ってクラウドで再試行せず要求を失敗させます。
- `machines` — Auto を特定のマシン id に限定します。空なら承認済みで自動対象の
  すべてのマシンです。

ローカルモデルの価格は確定済みのゼロ（自分のハードウェアで動作）なので、Auto の価格チェックを常に通過し、**Cheapest** では先頭になります。マシンの Auto スイッチまたは `local` ブロックで Auto から外せます。現在の経路で対応しているもの: すべてのアダプターでモデル検出、ストリーミングテキスト、自動再接続（最大 30 秒のバックオフ）。Ollama がビジョン対応と報告したモデルへの画像入力（他のアダプターにはそのまま渡されます）。**ツール呼び出しはコネクター経由で返されない** ため、ローカルモデルは Tools なしで公開され、Auto はツールを要するリクエストを送りません。

設定（すべて任意、`.env.example` 参照）:

| 変数 | 既定値 | 用途 |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | マスタースイッチ。`false` でエージェントのエンドポイントを閉じ、ローカルモデルを隠します。 |
| `LOCAL_CONNECT_PUBLIC_URL` | 空 | インストールコマンドとサービスファイルに書き込む公開 URL。空の場合は `https://your-geekcubo-host` のプレースホルダー。 |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | 接続中のマシンが報告する間隔（最終確認時刻を更新）。 |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | 登録コードの有効期間。 |

エージェントのソケットは `/api/local-connect/agent` の WebSocket なので、
GeekCubo の前段のリバースプロキシは HTTP `Upgrade` ヘッダーを転送する必要が
あります。`./install.sh` が生成する Nginx 設定には必要な `map` が含まれ、Caddy は
WebSocket を自動で扱います。メモリ内の接続ハブは **単一のサーバープロセス** を
前提とします。再起動するとコネクタは切断され、再接続（最大 30 秒のバックオフ）
まで復旧しません。マシンの資格情報は bearer シークレットで、サーバー側では
ハッシュとして保存され、モデルホストでは `0600` で書き込まれ、ダッシュボードから
いつでも失効・ローテーションできます。 複数ワーカーやレプリカはサポートされていません。`REDIS_URL` を設定しても変わりません。

## ストリーミング

標準の `data: ... \n\n` フレーミングとターミナル `[DONE]` センチネルを備えた OpenAI 互換の SSE 形式 — OpenAI からすでにストリーミングしている SDK のドロップイン。

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## ネイティブ プロトコル エンドポイント (Anthropic + Gemini)

GeekCubo は 1 つのルーティング パイプラインに対して 3 つのインバウンド プロトコルを話します。Anthropic または Gemini のワイヤー フォーマットしか話さないクライアントも直接接続できます。OpenAI SDK は不要です:

```bash
# Claude Code, pointed at GeekCubo (no /v1 suffix in the base URL)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN`（`Authorization: Bearer` として送信）も使えます。GeekCubo はどちらのヘッダーも受け付けます。

```python
# google-genai SDK, pointed at GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

リクエストはエッジで同じ内部パイプラインに変換されるため、`model="auto"`、クロスプロバイダー プロンプト キャッシュ (プロトコル間で共有)、ルーティング戦略、分析ダッシュボードはすべて同じように機能します。ガイド: [integrations/claude-code.md](./integrations/claude-code.md)、[integrations/gemini-sdk.md](./integrations/gemini-sdk.md) を参照してください。

## モデルカタログ

組み込みカタログ（対応プロバイダーの数百のチャットモデル）は、LiteLLM に同梱された [コミュニティ管理の価格データベース](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) のコピーから起動時に読み込まれます。モデル一覧を手作業で管理する必要はありません。各エントリには次の情報があります:

- `id` (例: `gpt-4o`、`claude-3-5-sonnet-latest`)
- `provider` (設定されたキーにマッピングされます)
- 機能フラグ: `supports_tools`、`supports_vision`、`supports_json_mode`、`supports_json_schema`
- トークンごとの入出力コスト (節約ウィジェット + `model="auto"` を推進)

`GET /v1/models` は `auto`、有効なルーティングプロファイル、カタログ全体を OpenAI 形式で返します（`anthropic-version` ヘッダー付きの場合は Anthropic 形式）。

カスタムプロバイダーのモデルでは、**Fetch → Select → Add Selected Models** の時点で Tools、Vision、JSONモード、JSON Schema、コンテキスト、参考価格が LiteLLM・Models.dev・Portkey からフィールドごとに自動解決され、各フィールドのソースが表示されます。確実な一致で明示的な値がある場合のみ対応/非対応となり、それ以外は不明のままです。価格が不明でも機能の解決は妨げられません。曖昧なモデルは、検索可能な候補リストからカタログキーを選ぶまで他モデルの値を借用しません。管理者の上書き（「不明」を含む）は更新後も保持され、「カタログを使用」で解除できます。Auto、Chat、プロファイルは同じ保存済み機能を使用します。 JSONモード（json_object）と JSON Schema／構造化出力（json_schema）は独立して解決される別の能力です。カタログの構造化出力の証拠は JSON Schema にのみ適用され、JSONモードの証拠として使われることはありません。

## 別の場所にデプロイする

GeekCubo は単一の Docker コンテナです。Compose を使わない場合は、チェックアウトからイメージをビルドし、データを名前付きボリュームに置きます。

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

タグ付きリリースでは `ghcr.io/geekcubo/geekcubo-ai-router` にマルチアーキテクチャイメージを公開する設定になっています（`.github/workflows/release.yml`）。リリース公開後はその名前を使えます。VPS とリバースプロキシ: [DEPLOYMENT.md](./DEPLOYMENT.md)。

## 箱の中身は何ですか

- `POST /v1/chat/completions` — プロキシ + ストリーミング + `model="auto"` + クロスプロバイダー プロンプト キャッシュ
- `POST /v1/messages` — **Anthropic Messages API イングレス** (Claude Code / Anthropic SDK が直接接続。`+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **Gemini API イングレス** (google-genai SDK が直接接続。`+ :streamGenerateContent`、`GET /v1beta/models`)
- `GET  /v1/models` — `auto`、ルーティングプロファイル、モデルカタログ（`litellm.model_cost` 由来の組み込みモデルと、カスタム・ローカルモデル）
- `GET/PUT/DELETE /v1/providers/{provider}` — 暗号化されたプロバイダー キーを設定 / リスト / 取り消し
- `GET/PUT /v1/routing` — 戦略（`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`、レガシー `fastest`）とポリシー。`/v1/routing-profiles` — 名前付き Auto プロファイル
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — ローカル分析。テレメトリは外部に送信されません
- `GET/POST/DELETE /v1/keys/...` — API キーのリスト化、回転、取り消し
- `/api/local-connect/*` — **ローカル AI コネクト**: 登録コード、マシンの承認/取り消し/ローテーション、モデルの切り替え、サービスファイル生成、および `/api/local-connect/agent` のアウトバウンドエージェント WebSocket (`local/<machine>/<model>` ルーティング ID、ローカル推論はテキストのみ)
- `POST /api/chat/attachments` — チャット添付ファイルのアップロード/抽出/削除。`GET /api/chat/attachments/limits` がサーバー側の制限を返し、UI はそれに合わせます
- `/` の単一ページのダッシュボード
- ダッシュボード内蔵の**チャット**タブ — ブラウザーからデプロイ済みモデルと対話。リクエストはSDKトラフィックと同じくルーティング・キャッシュ・課金の対象になります（履歴はローカルDBのみに保存、保持期間は設定可能。コンテキストの切り詰めはターンごとに報告され、任意の Web 検索（SearXNG、Brave、Tavily）で引用が付きます）
- デフォルトでは SQLite。 Postgres は「DATABASE_URL」経由でオプトインします。 Redis はオプション
- **単一のサーバープロセス** で動作します。`REDIS_URL` はプロンプトキャッシュを Redis に移しますが、Local AI Connect、Auto の会話状態、Adaptive のデータはプロセス間で共有されません。複数ワーカー構成はサポートされていません。

### 節約ウィジェット

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` は、トラフィックを基準モデルで処理した場合の費用と実際の費用を比較します（基準モデルの公開価格を使用）。価格不明のリクエストは節約額に含めません。

## ❤️ GeekCubo を支援する

GeekCubo は無料のオープンソースで、独立して開発されています。AI 環境を補完するサービスを見ていただくことで、継続的な開発を支援できます。

- [**AI API プロバイダー**](https://geekcubo.com/providers/) — 互換性のある AI モデルプロバイダーを探す。
- [**VPS とクラウドホスティング**](https://geekcubo.com/hosting/) — セルフホスト導入向けのホスティングを探す。
- [**VPN とプライバシー**](https://geekcubo.com/vpn/) — 任意のプライバシー・セキュアネットワークツールを探す。

**アフィリエイトに関する開示:** 一部のリンクでは、利用者の追加負担なしに当方が手数料を受け取る場合があります。利用は任意であり、GeekCubo のモデルルーティングやプロバイダー互換性には影響しません。

## ライセンス

MIT。[LICENSE](./LICENSE) を参照してください。

GeekCubo は OrcaRouter Lite から派生しています。元の MIT ライセンスとその著作権表示（「Copyright (c) 2026 OrcaRouter contributors」）は [LICENSE](./LICENSE) に保持されており、ソフトウェアのすべての複製または重要な部分に含める必要があります。

第三者の素材はそれぞれのライセンスに従います。ロゴに使われているフォントのアウトライン（Inter、SIL Open Font License 1.1）は [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt) に記載しています。

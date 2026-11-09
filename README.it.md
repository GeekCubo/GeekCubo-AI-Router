# GeekCubo

**Un gateway. Ogni modello di IA.**
Compatibile con OpenAI. BYOK. Self-hosted. Streaming e routing `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![ci](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](#licenza)
[![website](https://img.shields.io/badge/website-geekcubo.com-2563eb)](https://geekcubo.com)

[English](./README.md) | [日本語](./README.ja.md) | [中文](./README.zh.md) | [한국어](./README.ko.md) | [Deutsch](./README.de.md) | [Français](./README.fr.md) | [Español](./README.es.md) | [Italiano](./README.it.md) | [Русский](./README.ru.md) | [Português](./README.pt.md) | [Tiếng Việt](./README.vi.md) | [हिन्दी](./README.hi.md)

> **Documentazione dettagliata** (in inglese): sicurezza, sessioni e chiavi API, routing, collegamento degli strumenti incluso OpenCode, deployment — vedi [docs/](./docs/README.md). In caso di differenze vale il [README in inglese](./README.md).

GeekCubo è un gateway self-hosted compatibile con OpenAI: porta le tue chiavi provider e `model="auto"` sceglie un modello capace per ogni richiesta, con fallback e monitoraggio dei costi.

## Perché esiste GeekCubo

Il routing automatico dei modelli dovrebbe dare controllo agli sviluppatori, non incertezza.

GeekCubo nasce da un problema pratico: usando le proprie chiavi dei provider di IA non è sempre chiaro quale provider gestirà una richiesta, se un fallback potrebbe usare un servizio fatturato separatamente o perché sia stato scelto un certo modello.

Volevamo un'alternativa self-hosted in cui politiche di routing, provider idonei, capacità dei modelli, ipotesi di prezzo e comportamento di fallback fossero visibili e configurabili.

GeekCubo si basa su questo principio: **le tue chiavi, la tua infrastruttura, le tue decisioni di routing.**

Non esiste alcun portafoglio di routing ospitato obbligatorio. Configuri tu i provider e i modelli disponibili al router e puoi verificare come il routing automatico prende le sue decisioni.

### Origini open source

GeekCubo si basa su [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), un progetto open source rilasciato con licenza MIT. Ringraziamo i suoi sviluppatori originali per aver fornito le fondamenta su cui GeekCubo si è evoluto.

GeekCubo è sviluppato e mantenuto in modo indipendente, con funzionalità, architettura e direzione di prodotto proprie. Non è affiliato né approvato dagli sviluppatori originali di OrcaRouter.

Vedi [Licenza](#licenza) per attribuzione e dettagli di licenza.

## Quickstart in 60 secondi

Esegui GeekCubo sulla tua macchina; porta le tue chiavi provider.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

Lo script verifica Docker e Compose, convalida la configurazione, esegue `docker compose up -d --build`, attende il vero endpoint `/health` e, su un'installazione nuova, mostra il token di configurazione monouso per l'amministratore. Eseguirlo di nuovo è sicuro: volume dati, `.env`, account amministratore, credenziali dei provider, segreti di cifratura e chiavi API restano invariati.

Installazione manuale (stessa configurazione Compose):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # solo finché non esiste un amministratore
```

URL base: `http://127.0.0.1:8787/v1`. Usa una chiave `sk-geek-*` generata nella dashboard. Il token di configurazione è monouso, diventa invalido quando l'amministratore viene creato e va trattato come una password. La porta è in ascolto solo su loopback; per l'accesso remoto usa un tunnel SSH o un reverse proxy TLS.

Su un VPS imposta `PUBLIC_BASE_URL` in `.env` con il tuo indirizzo: un dominio principale come `https://example.com` o un sottodominio come `https://api.example.com`, a tua scelta. GeekCubo gira interamente sulla tua infrastruttura e non dipende da alcun host gestito da GeekCubo; vedi [DEPLOYMENT.md](./DEPLOYMENT.md).

### Poi chiamalo da qualsiasi SDK OpenAI

Gli esempi qui sotto usano l'URL base Docker locale `http://127.0.0.1:8787/v1`.

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # o "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
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

Gli esempi qui sotto usano l'URL base Docker locale `http://127.0.0.1:8787/v1`.

## `model="auto"` — la feature di punta

Invia `model="auto"`: GeekCubo restringe i modelli idonei ad Auto a quelli che possono servire la richiesta, li ordina con la strategia scelta in **Routing** e chiama il migliore, con una catena di fallback limitata. Nessuna regola di routing manuale né codice di ottimizzazione dei costi nella tua applicazione.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → sono considerati solo i modelli con capacità Vision «Supportata»;
#   la strategia attiva li ordina
```

Il modello risolto viene esposto a chi chiama tramite l'header di risposta `x-geek-resolved-model`, così puoi loggare/mostrare cosa è stato effettivamente usato.

### Quali modelli può usare Auto

Ogni richiesta Auto filtra in quest'ordine; un modello che non supera un passaggio non viene mai scelto, nemmeno come fallback:

1. **Idoneo** — un provider integrato con chiave valida, o un provider personalizzato attivo e *incluso in Auto*; il modello stesso è attivo.
2. **Prezzo confermato** — un prezzo di listino o un prezzo impostato da te. Un prezzo sconosciuto non è mai considerato gratuito; una stima di riferimento conta solo se la consenti.
3. **Capace** — ogni capacità richiesta (Tools, Vision, modalità JSON, JSON Schema) è **Supportata**. «Sconosciuto» non soddisfa mai un requisito.
4. **Contesto** — il prompt stimato entra in una finestra di contesto nota. Una finestra sconosciuta non esclude il modello.
5. **Consentito** — l'allowlist della chiave API e, se presenti, le restrizioni di un profilo di routing.

### Strategie

| Strategia | Come ordina i candidati rimasti | Se mancano i dati |
|---|---|---|
| **Balanced** (predefinita) | Peso uguale a punteggio di qualità e prezzo combinato; una soglia di qualità rimuove prima i modelli più deboli. Partecipano solo i modelli con punteggio. | Senza punteggi: ordina per prezzo e lo segnala nelle note di routing. |
| **Cheapest** | Prezzo combinato più basso (30 % input, 70 % output); parità per id modello. | Tutti i prezzi sconosciuti: nessun candidato, diagnosi invece di tirare a indovinare. |
| **Quality First** | Punteggio di qualità più alto; i punteggi manuali sostituiscono Artificial Analysis. | Senza punteggi: usa il prezzo come indicatore (il più caro prima) e lo segnala. |
| **Adaptive** | Tasso di successo osservato, poi latenza, dal tuo registro richieste (7 giorni). | Meno di 20 richieste per modello: si comporta come Balanced e lo segnala. |
| **Adaptive-Gated** | Classifica la richiesta *Mundane* o *Hard* (strumenti, immagini, prompt lunghi, molti messaggi, `max_tokens` elevato) e ordina solo quel pool. | Pool senza modello capace: pool *Fallback*, poi *Mundane* per le richieste difficili se consentito; mai l'intero catalogo. |
| **Fastest** (legacy) | Throughput e latenza del primo token misurati; i modelli senza misure sono esclusi. | Senza misure: ordina per prezzo e lo segnala. |

**Usare Auto:** invia `model="auto"` o scegli **Auto (sceglie il router)** nella Chat. **Un modello preciso:** invia il suo id completo o sceglilo nella Chat. **Cambiare strategia:** clicca una scheda in Routing (salvata subito). **Escludere un modello da Auto:** disattiva il modello, scegli *Escludi da Auto* sul suo provider o rimuovi il prezzo confermato. **Perché questo modello?** **Prova una decisione di instradamento**, le intestazioni `x-geek-routing-*` o Analytics. **Nessun modello idoneo:** un 422 spiega il motivo. Il routing Auto dei *modelli* non ha nulla a che fare con la modalità Auto riservata della ricerca web.

Nel dashboard la pagina Routing espone l'intera politica Auto: **Fallback, escalation e continuità** (tentativi di fallback, modalità e soglie di escalation, pool di destinazione, modalità shadow, stickiness) e **Prova una decisione di instradamento**, un dry-run che mostra modello, tier, strategia e ogni fase di filtro che ha rimosso candidati. Nulla viene inviato al provider.

## Chat nativo: ricerca web e budget di contesto

La scheda **Chat** del dashboard riduce la cronologia della conversazione alla
finestra di contesto del modello scelto. Ogni risposta riporta i token stimati,
il budget e quanti messaggi precedenti sono stati omessi, così una risposta
accorciata non viene mai scambiata per un guasto del modello.

La ricerca web è facoltativa e disattivata per impostazione predefinita.
Configurala in **Impostazioni → Chat → Ricerca web** con SearXNG (auto-ospitato),
Brave o Tavily. SearXNG può essere avviato da `./install.sh` o con `docker
compose --profile search up -d`. Le chiavi di ricerca sono crittografate,
separate da quelle di inferenza, e le citazioni compaiono solo per le pagine
realmente restituite dal backend. La modalità `auto` è riservata e non ancora
implementata.

## Chat nativo: allegati

Il compositore accetta file in tre modi: la graffetta, il trascinamento sulla
conversazione e l'incolla. Un'immagine incollata diventa un allegato; il testo
semplice incollato resta nativo.

| Tipo | Formati | Cosa vede il modello |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Inviata come parti immagine a un modello con visione |
| `document` | PDF, DOCX, RTF | Testo estratto, delimitato |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Testo foglio per foglio, limitato |
| `text` / `code` | TXT, MD, JSON, YAML, sorgenti | Testo grezzo, delimitato |
| `archive` | ZIP, tar, gzip | Elenco delle voci e letture limitate; mai estratto su disco |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Video: metadati e fotogrammi equidistanti. Audio: solo metadati |

Gli allegati testuali degradano sempre in un blocco delimitato nel messaggio
utente, leggibile da qualsiasi modello. Le immagini diventano vere parti immagine
solo per il turno corrente; nella cronologia precedente si riducono a un
marcatore `[attached: name]` per non falsare la finestra di contesto. Se fissi un
modello senza visione, l'invio viene rifiutato con una diagnosi `no_vision`
invece di scartare il file in silenzio.

Limiti lato server (regolabili via env: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; vedi `.env.example`):

- Fino a 8 allegati per messaggio.
- 25 MB per file per impostazione predefinita, con un tetto massimo.
- I caricamenti non collegati vengono eliminati dopo 24 ore.

Gli errori di estrazione sono mostrati per singolo file e non bloccano mai il
testo digitato. `GET /api/chat/attachments/limits` comunica al browser cosa può
caricare, così l'interfaccia applica le stesse regole prima dell'invio.

I fotogrammi video richiedono `ffmpeg`/`ffprobe` nel `PATH`; senza di essi il
video si carica comunque e al modello viene detto che non è leggibile. L'audio
viene descritto al modello solo tramite metadati: la trascrizione automatica è
volutamente disattivata e al modello non viene mai detto di aver sentito qualcosa
che non ha sentito.

## Connessione IA locale

Porta i modelli che girano già sul tuo hardware nello stesso catalogo, nelle
stesse policy e nello stesso routing `model="auto"` dei provider cloud. Il
connettore è un agente solo in uscita: si collega alla tua istanza GeekCubo via
WebSocket, annuncia i modelli locali che vede e risponde alle richieste di chat.
Nessuna porta in ingresso, tunnel, VPN o account cloud nel mezzo.

**Dashboard → Connessione IA locale → Collega una macchina** guida otto passaggi:
generare un codice di registrazione monouso, avviare il connettore, approvare la
macchina, abilitare i modelli desiderati e verificare che siano disponibili per
Auto.

```bash
# Sulla macchina che esegue i modelli (Python 3.11+), da un checkout di questo repository
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

Il connettore rileva automaticamente i runtime locali più comuni:

| Adattatore | URL base predefinito | Protocollo |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Nativo `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | `/v1` compatibile OpenAI |
| `vllm` | `http://127.0.0.1:8000` | `/v1` compatibile OpenAI |
| `llamacpp` | `http://127.0.0.1:8080` | `/v1` compatibile OpenAI |
| `custom` | nessuno (con `--url`) | Qualsiasi server `/v1` compatibile OpenAI (`--api-key` per un token Bearer) |

Usa `--adapter` per limitare il rilevamento e `--url adapter=URL` per puntare un
adattatore a una porta non predefinita. `python -m geekcubo_connector ...`
equivale allo script `geekcubo-connector`. La dashboard offre file di servizio
pronti per systemd, launchd e Windows, così il connettore riparte con la macchina.

I codici di registrazione sono monouso, scadono dopo 30 minuti per impostazione
predefinita e non concedono nulla finché un amministratore non approva la
macchina. Una volta approvata, i modelli locali compaiono nel catalogo come
`local/<macchina>/<modello>` e possono essere fissati direttamente o inclusi in
`model="auto"`.

Il routing locale è governato dal blocco `local` della policy di routing:

- `enabled` — include i modelli locali approvati in Auto.
- `no_cloud_fallback` — se Auto sceglie un modello locale e la macchina è
  offline, la richiesta fallisce invece di riprovare in silenzio sul cloud.
- `machines` — limita Auto a specifici id macchina; vuoto significa tutte le
  macchine approvate e idonee.

Un modello locale ha un prezzo confermato pari a zero (gira sul tuo hardware), quindi supera sempre il filtro prezzi di Auto ed è primo con **Cheapest**. Usa l'interruttore Auto della macchina o il blocco `local` per escluderlo. Cosa supporta oggi il percorso: scoperta dei modelli, testo in streaming e riconnessione automatica (backoff fino a 30 s) per tutti gli adattatori; immagini per i modelli che Ollama dichiara con visione (gli altri adattatori le ricevono invariate). **Le chiamate agli strumenti non vengono restituite tramite il connettore**, quindi i modelli locali sono pubblicati senza Tools e Auto non invia loro richieste con strumenti.

Configurazione (tutto opzionale, vedi `.env.example`):

| Variabile | Predefinito | Scopo |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Interruttore principale; `false` chiude l'endpoint dell'agente e nasconde i modelli locali. |
| `LOCAL_CONNECT_PUBLIC_URL` | vuoto | URL pubblico scritto nel comando di installazione e nei file di servizio; vuoto = segnaposto `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Ogni quanto una macchina connessa si fa sentire (aggiorna l'ultimo contatto). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Durata di un codice di registrazione. |

Il socket dell'agente è un WebSocket su `/api/local-connect/agent`, quindi
qualsiasi reverse proxy davanti a GeekCubo deve inoltrare l'header `Upgrade`. La
configurazione Nginx generata da `./install.sh` include il `map` necessario e
Caddy gestisce i WebSocket automaticamente. L'hub delle connessioni in memoria
presuppone **un solo processo** server; un riavvio interrompe i connettori fino
alla loro riconnessione (backoff massimo 30 s). Le credenziali macchina sono
segreti bearer: salvate con hash sul server, scritte con permessi `0600`
sull'host dei modelli, revocabili o ruotabili dalla dashboard in qualsiasi
momento. Più worker o repliche non sono supportati; `REDIS_URL` non cambia questo.

## Streaming

Formato SSE compatibile OpenAI con il framing standard `data: ... \n\n` e un sentinel terminale `[DONE]` — drop-in per qualsiasi SDK che già fa streaming da OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Endpoint di protocollo nativi (Anthropic + Gemini)

GeekCubo parla tre protocolli in ingresso su un'unica pipeline di routing. I client che parlano solo i formati wire di Anthropic o Gemini si connettono direttamente — nessun SDK OpenAI richiesto:

```bash
# Claude Code, puntato su GeekCubo (nessun suffisso /v1 nell'URL base)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

Funziona anche `ANTHROPIC_AUTH_TOKEN` (inviato come `Authorization: Bearer`); GeekCubo accetta entrambe le intestazioni.

```python
# SDK google-genai, puntato su GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Le richieste vengono tradotte all'ingresso nella stessa pipeline interna, quindi `model="auto"`, la cache prompt cross-provider (condivisa tra i protocolli), le strategie di routing e la dashboard analytics funzionano tutti in modo identico. Guide: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Catalogo modelli

Il catalogo integrato (diverse centinaia di modelli di chat dei provider supportati) viene caricato all'avvio dalla copia del [database prezzi della community](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) inclusa in LiteLLM; nessun elenco di modelli da mantenere. Ogni voce espone:

- `id` (es. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mappato sulle tue chiavi configurate)
- Flag di capacità: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Costo per token input/output (alimenta il widget risparmi + `model="auto"`)

`GET /v1/models` restituisce `auto`, i profili di routing attivi e il catalogo completo in formato OpenAI (in formato Anthropic con l'intestazione `anthropic-version`).

Per i modelli dei provider personalizzati, Tools, Vision, modalità JSON, schema JSON, contesto e prezzi di riferimento vengono risolti automaticamente, campo per campo, da LiteLLM, Models.dev e Portkey con **Recupera → Seleziona → Aggiungi modelli selezionati**, mostrando la fonte di ogni campo. Un valore diventa supportato/non supportato solo con una corrispondenza affidabile ed esplicita; altrimenti resta Sconosciuto, e un prezzo sconosciuto non blocca le capacità. I modelli ambigui non ricevono valori presi in prestito finché non scegli la chiave di catalogo nel selettore con ricerca. Le sostituzioni dell'amministratore (incluso «Sconosciuto») restano dopo gli aggiornamenti; «Usa catalogo» le rimuove. Auto, Chat e i profili usano le stesse capacità salvate. La modalità JSON (json_object) e JSON Schema / output strutturati (json_schema) sono capacità indipendenti risolte separatamente; le evidenze di output strutturato del catalogo valgono solo per JSON Schema, mai per la modalità JSON.

## Deploy altrove

GeekCubo è un singolo container Docker. Senza Compose, costruisci l'immagine da un checkout e tieni i dati su un volume con nome:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Le release con tag sono predisposte per pubblicare un'immagine multi-architettura su `ghcr.io/geekcubo/geekcubo-ai-router` (`.github/workflows/release.yml`); usa quel nome quando una release è stata pubblicata. VPS e reverse proxy: [DEPLOYMENT.md](./DEPLOYMENT.md).

## Cosa c'è nella scatola

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + cache prompt cross-provider
- `POST /v1/messages` — **ingress dell'API Messages di Anthropic** (Claude Code / gli SDK Anthropic si connettono direttamente; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **ingress dell'API Gemini** (l'SDK google-genai si connette direttamente; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, profili di routing e catalogo modelli (integrato da `litellm.model_cost`, più modelli personalizzati e locali)
- `GET/PUT/DELETE /v1/providers/{provider}` — imposta / lista / revoca chiavi provider cifrate
- `GET/PUT /v1/routing` — strategia (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; legacy `fastest`) e politica; `/v1/routing-profiles` — profili Auto con nome
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — analytics locali, nessuna telemetria esce dalla scatola
- `GET/POST/DELETE /v1/keys/...` — lista / ruota / revoca chiavi API
- `/api/local-connect/*` — **Connessione IA locale**: codici di iscrizione, approvazione/revoca/rotazione delle macchine, interruttori dei modelli, generazione di file di servizio e il WebSocket dell'agente in uscita su `/api/local-connect/agent` (id di routing `local/<machine>/<model>`; inferenza locale solo testo)
- `POST /api/chat/attachments` — carica/estrai/elimina gli allegati della chat; `GET /api/chat/attachments/limits` riporta i limiti applicati dal server così la UI li rispetta
- Dashboard single-page su `/`
- Scheda **Chat** integrata nel dashboard — chatta con i tuoi modelli distribuiti dal browser; le richieste vengono instradate, memorizzate in cache e tracciate nei costi esattamente come il traffico SDK (la cronologia resta nel database locale, con conservazione configurabile; il taglio del contesto è riportato a ogni turno e la ricerca web facoltativa (SearXNG, Brave o Tavily) aggiunge citazioni)
- SQLite di default; Postgres opt-in via `DATABASE_URL`; Redis opzionale
- Funziona come **un unico processo server**. `REDIS_URL` sposta la cache dei prompt su Redis ma non condivide tra processi Local AI Connect, lo stato di conversazione di Auto né i dati di Adaptive; il multi-worker non è supportato.

### Widget risparmi

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` riporta quanto sarebbe costato il tuo traffico con il modello di riferimento rispetto al costo reale (prezzo di listino del riferimento). Le richieste con prezzo sconosciuto non contano come risparmio.

## ❤️ Sostieni GeekCubo

GeekCubo è gratuito, open source e sviluppato in modo indipendente. Puoi sostenerne lo sviluppo esplorando servizi che completano la tua configurazione IA.

- [**Provider di API IA**](https://geekcubo.com/providers/) — Scopri provider di modelli IA compatibili.
- [**VPS e hosting cloud**](https://geekcubo.com/hosting/) — Esplora opzioni di hosting per installazioni self-hosted.
- [**VPN e privacy**](https://geekcubo.com/vpn/) — Esplora strumenti opzionali per privacy e reti sicure.

**Informativa sull'affiliazione:** alcuni link possono farci guadagnare una commissione senza costi aggiuntivi per te. Usarli è facoltativo e non influisce sul routing dei modelli di GeekCubo né sulla compatibilità dei provider.

## Licenza

MIT. Vedi [LICENSE](./LICENSE).

GeekCubo deriva da OrcaRouter Lite. La licenza MIT originale e il suo avviso di copyright ("Copyright (c) 2026 OrcaRouter contributors") sono conservati in [LICENSE](./LICENSE) e devono essere mantenuti in tutte le copie o parti sostanziali del software.

Le risorse di terzi mantengono le proprie licenze: i contorni del carattere usati nel logo (Inter, SIL Open Font License 1.1) sono descritti in [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).

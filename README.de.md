# GeekCubo

**Ein Gateway. Jedes KI-Modell.**
**Open-Source-KI-Gateway und intelligenter LLM-Router.** OpenAI-kompatibel, BYOK, selbst gehostet. Streaming und `model="auto"`-Routing.
OpenAI-kompatibel. BYOK. Einzelner Workspace. Streaming. `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![ci](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](#lizenz)
[![website](https://img.shields.io/badge/website-geekcubo.com-2563eb)](https://geekcubo.com)

[English](./README.md) | [日本語](./README.ja.md) | [中文](./README.zh.md) | [한국어](./README.ko.md) | [Deutsch](./README.de.md) | [Français](./README.fr.md) | [Español](./README.es.md) | [Italiano](./README.it.md) | [Русский](./README.ru.md) | [Português](./README.pt.md) | [Tiếng Việt](./README.vi.md) | [हिन्दी](./README.hi.md)

> **Ausführliche Dokumentation** (auf Englisch): Sicherheit, Sitzungen und API-Schlüssel, Routing, Tool-Anbindung inklusive OpenCode, Bereitstellung — siehe [docs/](./docs/README.md). Bei Abweichungen gilt die [englische README](./README.md).

GeekCubo ist ein selbst gehostetes, OpenAI-kompatibles Gateway: Bringen Sie Ihre eigenen Provider-Schlüssel mit, und `model="auto"` wählt für jede Anfrage ein passendes Modell — mit Fallback und Kostenverfolgung.


## Warum es GeekCubo gibt

Automatisches Modell-Routing sollte Entwicklern Kontrolle geben, keine Ungewissheit.

GeekCubo entstand aus einem praktischen Problem: Wer eigene KI-Provider-Schlüssel nutzt, sieht nicht immer, welcher Provider eine Anfrage bearbeitet, ob ein Fallback einen separat abgerechneten Dienst nutzen könnte oder warum ein bestimmtes Modell gewählt wurde.

Wir wollten eine selbst gehostete Alternative, bei der Routing-Richtlinien, zulässige Provider, Modellfähigkeiten, Preisannahmen und Fallback-Verhalten sichtbar und konfigurierbar sind.

GeekCubo folgt diesem Prinzip: **Ihre Schlüssel, Ihre Infrastruktur, Ihre Routing-Entscheidungen.**

Es gibt keine verpflichtende gehostete Routing-Wallet. Sie legen fest, welche Provider und Modelle dem Router zur Verfügung stehen, und können nachvollziehen, wie das automatische Routing entscheidet.

### Open-Source-Ursprung

GeekCubo baut auf [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite) auf, einem unter der MIT-Lizenz veröffentlichten Open-Source-Projekt. Wir danken den ursprünglichen Entwicklern für das Fundament, auf dem sich GeekCubo entwickelt hat.

GeekCubo wird unabhängig entwickelt und gepflegt, mit eigenen Funktionen, eigener Architektur und eigener Produktausrichtung. Es ist weder mit den ursprünglichen OrcaRouter-Entwicklern verbunden noch von ihnen unterstützt.

Siehe [Lizenz](#lizenz) für Hinweise zu Urheberschaft und Lizenz.

## 60-Sekunden-Schnellstart

### Selbst gehostet (BYOK)

Führen Sie GeekCubo auf Ihrem eigenen Rechner aus; bringen Sie Ihre eigenen Provider-Schlüssel mit.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

Das Skript prüft Docker und Compose, validiert die Konfiguration, führt `docker compose up -d --build` aus, wartet auf den echten `/health`-Endpunkt und zeigt bei einer Neuinstallation das einmalige Einrichtungs-Token für den Administrator an. Erneutes Ausführen ist sicher: Datenvolume, `.env`, Administratorkonto, Provider-Zugangsdaten, Verschlüsselungsgeheimnisse und API-Schlüssel bleiben erhalten.

Manuell (dieselbe Compose-Konfiguration):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # nur solange kein Administrator existiert
```

Basis-URL: `http://127.0.0.1:8787/v1`. Verwenden Sie einen im Dashboard erzeugten `sk-geek-*`-Schlüssel. Das Einrichtungs-Token ist einmalig gültig, wird nach dem Anlegen des Administrators ungültig und sollte wie ein Passwort behandelt werden. Der Port ist nur an Loopback gebunden; für Fernzugriff nutzen Sie einen SSH-Tunnel oder einen TLS-Reverse-Proxy.

Auf einem VPS setzen Sie `PUBLIC_BASE_URL` in `.env` auf Ihre eigene Adresse — eine Hauptdomain wie `https://example.com` oder eine Subdomain wie `https://api.example.com`, beides ist gleichwertig. GeekCubo läuft vollständig auf Ihrer Infrastruktur und hängt von keinem von GeekCubo betriebenen Host ab; siehe [DEPLOYMENT.md](./DEPLOYMENT.md).

### Dann von einem beliebigen OpenAI-SDK aufrufen

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # oder "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
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

Die folgenden Beispiele verwenden die lokale Docker-Basis-URL `http://127.0.0.1:8787/v1`.

## `model="auto"` — das Hauptmerkmal

Senden Sie `model="auto"`, und GeekCubo filtert die für Auto zugelassenen Modelle auf diejenigen, die die Anfrage bedienen können, sortiert sie mit der unter **Routing** gewählten Strategie und ruft das beste auf — mit einer begrenzten Fallback-Kette dahinter. Keine manuellen Routing-Regeln und kein Kostenoptimierungs-Code in Ihrer Anwendung.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → nur Modelle, deren Vision-Fähigkeit „Unterstützt“ ist, kommen in Frage;
#   die aktive Strategie bestimmt die Reihenfolge
```

Das aufgelöste Modell wird dem Aufrufer über den Antwort-Header `x-geek-resolved-model` zurückgegeben, sodass Sie protokollieren/anzeigen können, was tatsächlich verwendet wurde.

### Welche Modelle Auto verwenden darf

Jede Auto-Anfrage filtert in dieser Reihenfolge; ein Modell, das einen Schritt nicht besteht, wird nie gewählt — auch nicht als Fallback:

1. **Zugelassen** — ein eingebauter Provider mit funktionierendem Schlüssel oder ein aktivierter benutzerdefinierter Provider mit *In Auto aufnehmen*; das Modell selbst ist aktiviert.
2. **Bestätigter Preis** — ein Listenpreis oder ein von Ihnen gesetzter Preis. Ein unbekannter Preis gilt nie als kostenlos; Referenzschätzungen zählen nur, wenn Sie sie erlauben.
3. **Fähig** — jede benötigte Fähigkeit (Tools, Vision, JSON-Modus, JSON-Schema) ist **Unterstützt**. „Unbekannt“ erfüllt nie eine Anforderung.
4. **Passt** — der geschätzte Prompt passt in ein bekanntes Kontextfenster. Ein unbekanntes Fenster schließt ein Modell nicht aus.
5. **Erlaubt** — Allowlist des API-Schlüssels und ggf. Einschränkungen eines Routing-Profils.

### Strategien

| Strategie | Reihenfolge der verbleibenden Kandidaten | Wenn Daten fehlen |
|---|---|---|
| **Balanced** (Standard) | Qualitätswert und Mischpreis gleich gewichtet; eine Qualitätsuntergrenze entfernt schwächere Modelle zuerst. Nur Modelle mit Qualitätswert nehmen teil. | Ohne Werte: Sortierung nach Preis, mit Hinweis in den Routing-Notizen. |
| **Cheapest** | Niedrigster Mischpreis (30 % Input, 70 % Output); Gleichstand nach Modell-ID. | Alle Preise unbekannt: kein Kandidat, Diagnose statt Raten. |
| **Quality First** | Höchster Qualitätswert; manuelle Werte überschreiben Artificial Analysis. | Ohne Werte: Preis als Ersatz (teuerstes zuerst), mit Hinweis. |
| **Adaptive** | Nach beobachteter Erfolgsquote, dann Latenz aus dem eigenen Request-Log (7 Tage). | Unter 20 Anfragen je Modell: verhält sich wie Balanced und meldet das. |
| **Adaptive-Gated** | Stuft die Anfrage als *Mundane* oder *Hard* ein (Tools, Bilder, lange Prompts, viele Nachrichten, großes `max_tokens`) und sortiert nur diesen Pool. | Pool ohne fähiges Modell: *Fallback*-Pool, dann *Mundane* für schwere Anfragen, falls erlaubt — nie der ganze Katalog. |
| **Fastest** (Legacy) | Benchmark-Durchsatz und Zeit bis zum ersten Token; Modelle ohne Messwerte werden ausgeschlossen. | Ohne Benchmarks: Sortierung nach Preis, mit Hinweis. |

**Auto nutzen:** `model="auto"` senden oder im Chat **Auto (Router wählt)** wählen. **Bestimmtes Modell:** seine volle ID senden oder im Chat wählen. **Strategie ändern:** Strategiekarte unter Routing anklicken (sofort gespeichert). **Modell aus Auto heraushalten:** Modell deaktivieren, beim Provider *Aus Auto ausschließen* wählen oder den bestätigten Preis entfernen. **Warum dieses Modell?** **Routing-Entscheidung testen**, die `x-geek-routing-*`-Header oder Analytics. **Kein zulässiges Modell:** 422 mit Begründung statt Raten. Das Auto-*Modell*-Routing hat nichts mit dem reservierten Auto-Modus der Websuche zu tun.

Im Dashboard zeigt die Routing-Seite die vollständige Auto-Politik: **Fallback, Escalation & Kontinuität** (Fallback-Versuche, Eskalationsmodus und -schwellen, Ziel-Pool, Shadow-Modus, Stickiness) sowie **Routing-Entscheidung testen**, einen Dry-Run, der Modell, Tier, Strategie und jede Filterstufe zeigt, die Kandidaten entfernt hat. Es wird nichts an einen Provider gesendet.

## Nativer Chat: Websuche und Kontextbudget

Der **Chat**-Tab im Dashboard kürzt den Gesprächsverlauf auf das Kontextfenster
des gewählten Modells. Jede Antwort meldet die geschätzten Token, das Budget und
wie viele ältere Nachrichten ausgelassen wurden — eine verkürzte Antwort wird so
nie mit einem Modellfehler verwechselt.

Die Websuche ist optional und standardmäßig aus. Konfigurieren Sie sie unter
**Einstellungen → Chat → Websuche** mit SearXNG (selbst gehostet), Brave oder
Tavily. SearXNG startet `./install.sh` oder `docker compose --profile search up
-d`. Suchschlüssel werden verschlüsselt und getrennt von Inferenzschlüsseln
gespeichert; Quellenangaben erscheinen nur für Seiten, die das Backend
tatsächlich zurückgegeben hat. Der Modus `auto` ist reserviert und noch nicht
implementiert.

## Nativer Chat: Anhänge

Der Composer nimmt Dateien auf drei Wegen an: über die Büroklammer, per
Drag-and-drop auf die Unterhaltung und per Einfügen. Eine eingefügte Grafik wird
zum Anhang; eingefügter reiner Text bleibt nativ.

| Art | Formate | Was das Modell sieht |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Als Bildteile an ein vision-fähiges Modell |
| `document` | PDF, DOCX, RTF | Extrahierter Text, abgegrenzt |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Text je Tabelle, begrenzt |
| `text` / `code` | TXT, MD, JSON, YAML, Quelldateien | Rohtext, abgegrenzt |
| `archive` | ZIP, tar, gzip | Eintragsliste plus begrenztes Lesen; nie auf die Platte entpackt |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Video: Metadaten plus gleichmäßig verteilte Frames. Audio: nur Metadaten |

Textanhänge werden immer zu einem abgegrenzten Block in der Benutzernachricht, den
jedes Modell lesen kann. Bilder werden nur für die aktuelle Runde zu echten
Bildteilen; in älterer Historie fallen sie auf einen `[attached: name]`-Marker
zusammen, damit das Kontextfenster ehrlich bleibt. Ist ein fest gewähltes Modell
nicht bildfähig, wird der Versand mit einer `no_vision`-Diagnose abgelehnt,
statt die Datei stillschweigend zu verwerfen.

Serverseitige Grenzen (per Env anpassbar: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; siehe `.env.example`):

- Höchstens 8 Anhänge pro Nachricht.
- Standardmäßig 25 MB pro Datei, begrenzt durch eine harte Obergrenze.
- Nicht gebundene Uploads werden nach 24 Stunden bereinigt.

Extraktionsfehler werden pro Datei gemeldet und blockieren den eingegebenen Text
nie. `GET /api/chat/attachments/limits` teilt dem Browser mit, was hochgeladen
werden darf, damit die UI vor dem Senden dieselben Regeln durchsetzt.

Video-Frames brauchen `ffmpeg`/`ffprobe` im `PATH`; ohne sie lässt sich ein Video
weiterhin hochladen, und dem Modell wird gesagt, dass es nicht gelesen werden
kann. Audio wird dem Modell nur als Metadaten beschrieben — automatische
Transkription ist bewusst nicht aktiviert, und dem Modell wird nie gesagt, es
hätte etwas gehört, das es nicht gehört hat.

## Lokale KI-Anbindung

Bringe Modelle, die bereits auf deiner eigenen Hardware laufen, in denselben
Katalog, dieselben Richtlinien und dasselbe `model="auto"`-Routing wie deine
Cloud-Anbieter. Der Connector ist ein reiner Ausgangs-Agent: Er wählt sich per
WebSocket bei deiner GeekCubo-Instanz ein, meldet die sichtbaren lokalen Modelle
und beantwortet Chat-Anfragen. Kein eingehender Port, kein Tunnel, kein VPN und
kein Cloud-Konto dazwischen.

**Dashboard → Lokale KI-Anbindung → Maschine verbinden** führt durch acht
Schritte: einmaligen Registrierungscode erzeugen, Connector starten, Maschine
freigeben, gewünschte Modelle aktivieren und prüfen, dass sie für Auto verfügbar
sind.

```bash
# Auf dem Modell-Host (Python 3.11+), aus einem Checkout dieses Repos
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

Der Connector erkennt gängige lokale Laufzeitumgebungen automatisch:

| Adapter | Standard-Basis-URL | Protokoll |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Nativ `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | OpenAI-kompatibles `/v1` |
| `vllm` | `http://127.0.0.1:8000` | OpenAI-kompatibles `/v1` |
| `llamacpp` | `http://127.0.0.1:8080` | OpenAI-kompatibles `/v1` |
| `custom` | keins (per `--url`) | Beliebiger OpenAI-kompatibler `/v1`-Server (`--api-key` für Bearer-Token) |

Mit `--adapter` schränkst du die Erkennung ein, mit `--url adapter=URL` zeigst du
einen Adapter auf einen anderen Port. `python -m geekcubo_connector ...` ist
gleichwertig zum Skript `geekcubo-connector`. Das Dashboard liefert fertige
systemd-, launchd- und Windows-Dienstdateien, damit der Connector mit der
Maschine startet.

Registrierungscodes sind einmalig, laufen standardmäßig nach 30 Minuten ab und
gewähren nichts, bis ein Administrator die Maschine freigibt. Danach erscheinen
lokale Modelle im Katalog als `local/<Maschine>/<Modell>` und lassen sich direkt
anheften oder in `model="auto"` aufnehmen.

Lokales Routing steuert der Block `local` der Routing-Richtlinie:

- `enabled` — freigegebene lokale Modelle in Auto aufnehmen.
- `no_cloud_fallback` — wählt Auto ein lokales Modell und die Maschine ist
  offline, schlägt die Anfrage fehl, statt still auf die Cloud auszuweichen.
- `machines` — Auto auf bestimmte Maschinen-IDs beschränken; leer bedeutet alle
  freigegebenen und auto-tauglichen Maschinen.

Ein lokales Modell hat einen bestätigten Preis von null (es läuft auf Ihrer Hardware) und besteht daher immer die Preisprüfung von Auto; unter **Cheapest** steht es vorn. Über den Auto-Schalter der Maschine oder den Block `local` halten Sie es aus Auto heraus. Was der Pfad heute leistet: Modellerkennung, Streaming-Text und automatische Wiederverbindung (Backoff bis 30 s) für alle Adapter; Bildeingaben für Modelle, die Ollama als vision-fähig meldet (andere Adapter erhalten sie unverändert). **Tool-Aufrufe werden über den Connector nicht zurückgegeben**, daher werden lokale Modelle ohne Tools angeboten und Auto schickt ihnen keine Tool-Anfragen.

Konfiguration (alles optional, siehe `.env.example`):

| Variable | Standard | Zweck |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Hauptschalter; `false` schließt den Agent-Endpunkt und blendet lokale Modelle aus. |
| `LOCAL_CONNECT_PUBLIC_URL` | leer | Öffentliche Basis-URL für Installationsbefehl und Dienstdateien; leer = Platzhalter `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Intervall, in dem sich eine verbundene Maschine meldet (aktualisiert „zuletzt gesehen“). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Gültigkeitsdauer eines Registrierungscodes. |

Der Agent-Socket ist ein WebSocket auf `/api/local-connect/agent`; jeder
Reverse-Proxy vor GeekCubo muss daher den HTTP-Header `Upgrade` weiterreichen.
Die von `./install.sh` erzeugte Nginx-Konfiguration enthält die nötige `map`,
und Caddy verarbeitet WebSockets automatisch. Der Verbindungs-Hub liegt im
Speicher und setzt **einen einzigen Serverprozess** voraus; ein Neustart trennt
Connectors, bis sie sich wieder verbinden (Backoff bis 30 s). Maschinen-
Anmeldedaten sind Bearer-Geheimnisse: serverseitig gehasht gespeichert, auf dem
Modell-Host mit `0600` geschrieben und jederzeit im Dashboard widerrufbar oder
rotierbar. Mehrere Worker oder Replikate werden nicht unterstützt; `REDIS_URL` ändert daran nichts.

## Streaming

OpenAI-kompatibles SSE-Format mit dem üblichen `data: ... \n\n`-Framing und einem abschließenden `[DONE]`-Sentinel — Drop-in für jedes SDK, das bereits von OpenAI streamt.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Native Protokoll-Endpunkte (Anthropic + Gemini)

GeekCubo spricht drei eingehende Protokolle über eine einzige Routing-Pipeline. Clients, die nur die Anthropic- oder Gemini-Wire-Formate sprechen, verbinden sich direkt — kein OpenAI-SDK erforderlich:

```bash
# Claude Code, auf GeekCubo gerichtet (kein /v1-Suffix in der Basis-URL)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN` (als `Authorization: Bearer` gesendet) funktioniert ebenso; GeekCubo akzeptiert beide Header.

```python
# google-genai-SDK, auf GeekCubo gerichtet
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Anfragen werden am Eingang in dieselbe interne Pipeline übersetzt, sodass `model="auto"`, der provider-übergreifende Prompt-Cache (über alle Protokolle geteilt), die Routing-Strategien und das Analytics-Dashboard identisch funktionieren. Anleitungen: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Modellkatalog

Beim Start wird der eingebaute Katalog (mehrere hundert Chat-Modelle der unterstützten Provider) aus der mit LiteLLM gebündelten Kopie der [Community-Preisdatenbank](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) geladen — keine manuell gepflegte Modellliste. Jeder Eintrag enthält:

- `id` (z. B. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (auf Ihre konfigurierten Schlüssel abgebildet)
- Capability-Flags: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Kosten pro Token für Input/Output (treibt das Einsparungs-Widget + `model="auto"` an)

`GET /v1/models` liefert `auto`, aktivierte Routing-Profile und den vollständigen Katalog im OpenAI-Format (mit `anthropic-version`-Header im Anthropic-Format).

Für Modelle benutzerdefinierter Anbieter werden Tools, Vision, JSON-Modus, JSON-Schema, Kontext und Referenzpreise beim **Abrufen → Auswählen → Ausgewählte Modelle hinzufügen** automatisch und feldweise aus LiteLLM, Models.dev und Portkey ermittelt, jeweils mit angezeigter Quelle. Ein Wert wird nur bei einem zuverlässigen Treffer mit expliziter Angabe als unterstützt/nicht unterstützt gesetzt, sonst bleibt er Unbekannt; ein unbekannter Preis blockiert keine Fähigkeiten. Mehrdeutige Modelle erhalten keine geliehenen Werte, bis Sie den Katalogschlüssel in der durchsuchbaren Auswahl wählen. Administrator-Überschreibungen (auch „Unbekannt“) bleiben bei Aktualisierungen erhalten; „Katalog verwenden“ entfernt sie. Auto, Chat und Profile nutzen dieselben gespeicherten Fähigkeiten. JSON-Modus (json_object) und JSON-Schema/Structured Outputs (json_schema) werden als getrennte Fähigkeiten unabhängig voneinander ermittelt; Belege für strukturierte Ausgaben aus dem Katalog gelten ausschließlich für das JSON-Schema, niemals für den JSON-Modus.

## Anderswo deployen

GeekCubo ist ein einzelner Docker-Container. Ohne Compose bauen Sie das Image aus einem Checkout und legen die Daten auf ein benanntes Volume:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Getaggte Releases sind darauf eingerichtet, ein Multi-Arch-Image nach `ghcr.io/geekcubo/geekcubo-ai-router` zu veröffentlichen (`.github/workflows/release.yml`); verwenden Sie diesen Namen, sobald ein Release erschienen ist. VPS und Reverse-Proxy: [DEPLOYMENT.md](./DEPLOYMENT.md).

## Was ist enthalten

- `POST /v1/chat/completions` — Proxy + Streaming + `model="auto"` + provider-übergreifender Prompt-Cache
- `POST /v1/messages` — **Anthropic-Messages-API-Ingress** (Claude Code / Anthropic-SDKs verbinden sich direkt; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **Gemini-API-Ingress** (google-genai-SDK verbindet sich direkt; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, Routing-Profile und Modellkatalog (eingebaut aus `litellm.model_cost`, dazu benutzerdefinierte und lokale Modelle)
- `GET/PUT/DELETE /v1/providers/{provider}` — verschlüsselte Provider-Schlüssel setzen / auflisten / widerrufen
- `GET/PUT /v1/routing` — Strategie (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; Legacy `fastest`) und Richtlinie; `/v1/routing-profiles` — benannte Auto-Profile
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — lokale Analytics, keine Telemetrie verlässt die Box
- `GET/POST/DELETE /v1/keys/...` — API-Schlüssel auflisten / rotieren / widerrufen
- `/api/local-connect/*` — **Lokale KI-Anbindung**: Registrierungscodes, Genehmigung/Widerruf/Rotation von Maschinen, Modell-Schalter, Generierung von Dienstdateien und der ausgehende Agent-WebSocket unter `/api/local-connect/agent` (`local/<machine>/<model>`-Routing-IDs; lokale Inferenz nur Text)
- `POST /api/chat/attachments` — Chat-Anhänge hochladen/extrahieren/löschen; `GET /api/chat/attachments/limits` meldet die serverseitigen Grenzen, damit die UI sie einhält
- Single-Page-Dashboard unter `/`
- Eingebauter **Chat**-Tab im Dashboard — im Browser mit den bereitgestellten Modellen sprechen; Anfragen werden wie SDK-Traffic geroutet, gecacht und kostenmäßig erfasst (Historie bleibt in der lokalen Datenbank, mit einstellbarer Aufbewahrung; die Kontextkürzung wird pro Runde gemeldet, und optionale Websuche (SearXNG, Brave oder Tavily) ergänzt Quellenangaben)
- Standardmäßig SQLite; Postgres optional via `DATABASE_URL`; Redis optional
- Läuft als **ein Serverprozess**. `REDIS_URL` verlagert den Prompt-Cache nach Redis, macht aber Local AI Connect, Auto-Gesprächszustand und Adaptive-Daten nicht prozessübergreifend; Multi-Worker-Betrieb wird nicht unterstützt.

### Einsparungs-Widget

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` zeigt, was Ihr Traffic mit dem Referenzmodell gekostet hätte gegenüber den tatsächlichen Kosten (Listenpreis des Referenzmodells). Anfragen mit unbekanntem Preis zählen nicht als Einsparung.

## ❤️ GeekCubo unterstützen

GeekCubo ist kostenlos, Open Source und wird unabhängig entwickelt. Sie können die Weiterentwicklung unterstützen, indem Sie Dienste ansehen, die Ihr KI-Setup ergänzen.

- [**KI-API-Provider**](https://geekcubo.com/providers/) — Kompatible KI-Modell-Provider entdecken.
- [**VPS & Cloud-Hosting**](https://geekcubo.com/hosting/) — Hosting-Optionen für selbst gehostete Installationen entdecken.
- [**VPN & Privatsphäre**](https://geekcubo.com/vpn/) — Optionale Werkzeuge für Privatsphäre und sichere Netzwerke entdecken.

**Hinweis zu Affiliate-Links:** Einige Links können uns ohne Mehrkosten für Sie eine Provision einbringen. Ihre Nutzung ist freiwillig und beeinflusst weder das Modell-Routing von GeekCubo noch die Provider-Kompatibilität.

## Lizenz

MIT. Siehe [LICENSE](./LICENSE).

GeekCubo ist von OrcaRouter Lite abgeleitet. Die ursprüngliche MIT-Lizenz und ihr Copyright-Hinweis („Copyright (c) 2026 OrcaRouter contributors") sind in [LICENSE](./LICENSE) erhalten und müssen in allen Kopien und wesentlichen Teilen der Software beibehalten werden.

Drittanbieter-Assets behalten ihre eigenen Lizenzen: Die im Logo verwendeten Schriftkonturen (Inter, SIL Open Font License 1.1) sind in [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt) beschrieben.

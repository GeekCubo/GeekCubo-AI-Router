# GeekCubo

**Un gateway. Todos los modelos de IA.**
**Puerta de enlace de IA de código abierto y enrutador LLM inteligente.** Compatible con OpenAI, BYOK, autoalojado. Streaming y enrutamiento `model="auto"`.
Compatible con OpenAI. BYOK. Workspace único. Streaming. `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![ci](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](#licencia)
[![website](https://img.shields.io/badge/website-geekcubo.com-2563eb)](https://geekcubo.com)

[English](./README.md) | [日本語](./README.ja.md) | [中文](./README.zh.md) | [한국어](./README.ko.md) | [Deutsch](./README.de.md) | [Français](./README.fr.md) | [Español](./README.es.md) | [Italiano](./README.it.md) | [Русский](./README.ru.md) | [Português](./README.pt.md) | [Tiếng Việt](./README.vi.md) | [हिन्दी](./README.hi.md)

> **Documentación detallada** (en inglés): seguridad, sesiones y claves de API, enrutamiento, conexión de herramientas incluido OpenCode y despliegue — consulta [docs/](./docs/README.md). Si hay diferencias, prevalece el [README en inglés](./README.md).

GeekCubo es una puerta de enlace autoalojada y compatible con OpenAI: trae tus propias claves de proveedor y `model="auto"` elige un modelo capaz para cada solicitud, con respaldo y seguimiento de costes.


## Por qué existe GeekCubo

El enrutamiento automático de modelos debería dar control a los desarrolladores, no incertidumbre.

GeekCubo nació de un problema práctico: al usar tus propias claves de proveedores de IA no siempre es evidente qué proveedor atenderá una solicitud, si un fallback podría usar un servicio facturado por separado ni por qué se eligió un modelo concreto.

Queríamos una alternativa autoalojada en la que las políticas de enrutamiento, los proveedores elegibles, las capacidades de los modelos, los supuestos de precio y el comportamiento de fallback fueran visibles y configurables.

GeekCubo se basa en ese principio: **tus claves, tu infraestructura, tus decisiones de enrutamiento.**

No hay ninguna cartera de enrutamiento alojada obligatoria. Tú configuras los proveedores y modelos disponibles para el router y puedes inspeccionar cómo decide el enrutamiento automático.

### Orígenes de código abierto

GeekCubo se basa en [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), un proyecto de código abierto publicado bajo la licencia MIT. Agradecemos a sus desarrolladores originales la base sobre la que GeekCubo ha evolucionado.

GeekCubo se desarrolla y mantiene de forma independiente, con sus propias funciones, arquitectura y dirección de producto. No está afiliado ni respaldado por los desarrolladores originales de OrcaRouter.

Consulta [Licencia](#licencia) para la atribución y los detalles de la licencia.

## Inicio rápido en 60 segundos

### Autoalojado (BYOK)

Ejecuta GeekCubo en tu propia máquina; trae tus propias claves de proveedor.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

El script comprueba Docker y Compose, valida la configuración, ejecuta `docker compose up -d --build`, espera al endpoint `/health` real y, en una instalación nueva, muestra el token de configuración de un solo uso para el administrador. Volver a ejecutarlo es seguro: conserva el volumen de datos, `.env`, la cuenta de administrador, las credenciales de proveedor, los secretos de cifrado y las claves API.

Instalación manual (la misma configuración de Compose):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # solo mientras no exista un administrador
```

URL base: `http://127.0.0.1:8787/v1`. Usa una clave `sk-geek-*` generada en el panel. El token de configuración es de un solo uso, deja de ser válido al crear el administrador y debe tratarse como una contraseña. El puerto solo escucha en loopback; para acceso remoto usa un túnel SSH o un proxy inverso con TLS.

En un VPS, define `PUBLIC_BASE_URL` en `.env` con tu propia dirección: un dominio raíz como `https://example.com` o un subdominio como `https://api.example.com`, ambos son válidos. GeekCubo se ejecuta por completo en tu infraestructura y no depende de ningún host operado por GeekCubo; consulta [DEPLOYMENT.md](./DEPLOYMENT.md).

### Luego invócalo desde cualquier SDK de OpenAI

Los ejemplos de abajo usan la URL base local de Docker `http://127.0.0.1:8787/v1`.

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

Los ejemplos de abajo usan la URL base local de Docker `http://127.0.0.1:8787/v1`.

## `model="auto"` — la característica estrella

Envía `model="auto"` y GeekCubo reduce los modelos elegibles para Auto a los que pueden atender la solicitud, los ordena con la estrategia elegida en **Routing** y llama al mejor, con una cadena de fallback limitada detrás. Sin reglas de enrutamiento manuales ni código de optimización de costes en tu aplicación.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → solo se consideran modelos cuya capacidad Vision es «Compatible»;
#   la estrategia activa los ordena
```

El modelo resuelto se expone de vuelta a quien llama a través de la cabecera de respuesta `x-geek-resolved-model`, para que puedas registrar/mostrar lo que realmente se usó.

### Qué modelos puede usar Auto

Cada solicitud Auto filtra en este orden; un modelo que falla un paso nunca se elige, ni siquiera como fallback:

1. **Elegible** — un proveedor integrado con clave válida, o un proveedor personalizado activado e *incluido en Auto*; el propio modelo está activado.
2. **Precio confirmado** — un precio de lista o un precio que hayas definido. Un precio desconocido nunca se trata como gratis; una estimación de referencia solo cuenta si la permites.
3. **Capaz** — cada capacidad requerida (Tools, Vision, modo JSON, JSON Schema) es **Compatible**. «Desconocido» nunca satisface un requisito.
4. **Cabe** — el prompt estimado cabe en una ventana de contexto conocida. Una ventana desconocida no excluye el modelo.
5. **Permitido** — la lista de permitidos de la clave API y, en su caso, las restricciones de un perfil de enrutamiento.

### Estrategias

| Estrategia | Cómo ordena los candidatos restantes | Si faltan datos |
|---|---|---|
| **Balanced** (por defecto) | Mismo peso para la puntuación de calidad y el precio combinado; un umbral de calidad elimina antes los modelos más débiles. Solo participan modelos con puntuación. | Sin puntuaciones: ordena por precio y lo indica en las notas de enrutamiento. |
| **Cheapest** | Precio combinado más bajo (30 % entrada, 70 % salida); empates por id de modelo. | Todos los precios desconocidos: ningún candidato, diagnóstico en lugar de adivinar. |
| **Quality First** | Mayor puntuación de calidad; las puntuaciones manuales sustituyen a Artificial Analysis. | Sin puntuaciones: usa el precio como aproximación (el más caro primero) y lo indica. |
| **Adaptive** | Tasa de éxito observada y luego latencia, según tu propio registro (7 días). | Menos de 20 solicitudes por modelo: se comporta como Balanced y lo indica. |
| **Adaptive-Gated** | Clasifica la solicitud como *Mundane* o *Hard* (herramientas, imágenes, prompts largos, muchos mensajes, `max_tokens` alto) y solo ordena ese pool. | Pool sin modelo capaz: pool *Fallback* y después *Mundane* para solicitudes difíciles si se permite; nunca todo el catálogo. |
| **Fastest** (heredado) | Rendimiento y latencia del primer token medidos; los modelos sin mediciones se excluyen. | Sin mediciones: ordena por precio y lo indica. |

**Usar Auto:** envía `model="auto"` o elige **Auto (elige el router)** en el Chat. **Un modelo concreto:** envía su id completo o elígelo en el Chat. **Cambiar la estrategia:** haz clic en una tarjeta en Routing (se guarda al instante). **Dejar un modelo fuera de Auto:** desactiva el modelo, elige *Excluir de Auto* en su proveedor o quita su precio confirmado. **¿Por qué este modelo?** **Probar una decisión de enrutado**, las cabeceras `x-geek-routing-*` o Analytics. **Ningún modelo elegible:** un 422 explica el motivo. El enrutamiento Auto de *modelos* no tiene relación con el modo Auto reservado de la búsqueda web.

En el panel, la página Routing expone toda la política de Auto: **Fallback, escalado y continuidad** (intentos de fallback, modo y umbrales de escalado, pool de destino, modo shadow, stickiness) y **Probar una decisión de enrutado**, un dry-run que muestra el modelo, el tier, la estrategia y cada etapa de filtrado que descartó candidatos. No se envía nada al proveedor.

## Chat nativo: búsqueda web y presupuesto de contexto

La pestaña **Chat** del panel recorta el historial de la conversación a la
ventana de contexto del modelo elegido. Cada respuesta informa los tokens
estimados, el presupuesto y cuántos mensajes anteriores se omitieron, de modo que
una respuesta acortada nunca se confunde con un fallo del modelo.

La búsqueda web es opcional y está desactivada por defecto. Configúrela en
**Ajustes → Chat → Búsqueda web** con SearXNG (autoalojado), Brave o Tavily.
SearXNG puede iniciarse con `./install.sh` o con `docker compose --profile
search up -d`. Las claves de búsqueda se guardan cifradas, separadas de las
claves de inferencia, y las citas solo se muestran para las páginas que el
backend devolvió realmente. El modo `auto` está reservado y aún no implementado.

## Chat nativo: adjuntos

El compositor acepta archivos de tres formas: el clip, arrastrar y soltar sobre
la conversación, y pegar. Una imagen pegada se convierte en adjunto; el texto
plano pegado sigue siendo nativo.

| Tipo | Formatos | Qué ve el modelo |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Se envía como partes de imagen a un modelo con visión |
| `document` | PDF, DOCX, RTF | Texto extraído, delimitado |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Texto hoja por hoja, acotado |
| `text` / `code` | TXT, MD, JSON, YAML, código fuente | Texto sin procesar, delimitado |
| `archive` | ZIP, tar, gzip | Lista de entradas y lecturas acotadas; nunca se descomprime en disco |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Vídeo: metadatos y fotogramas equiespaciados. Audio: solo metadatos |

Los adjuntos de texto siempre degradan a un bloque delimitado en el mensaje del
usuario, de modo que cualquier modelo puede leerlos. Las imágenes se convierten
en partes de imagen reales solo para el turno actual; en el historial anterior se
colapsan a un marcador `[attached: name]` para no falsear la ventana de contexto.
Si fijas un modelo que no acepta imágenes, el envío se rechaza con un diagnóstico
`no_vision` en lugar de descartar el archivo en silencio.

Límites del servidor (ajustables por entorno: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; ver `.env.example`):

- Hasta 8 adjuntos por mensaje.
- 25 MB por archivo por defecto, con un techo máximo.
- Las subidas sin vincular se purgan a las 24 horas.

Los fallos de extracción se muestran por archivo y nunca bloquean el texto que
escribiste. `GET /api/chat/attachments/limits` indica al navegador qué puede
subir, de modo que la interfaz aplica las mismas reglas antes de enviar.

Los fotogramas de vídeo necesitan `ffmpeg`/`ffprobe` en el `PATH`; sin ellos el
vídeo se sube igualmente y se avisa al modelo de que no puede leerse. El audio se
describe al modelo solo como metadatos: la transcripción automática está
deliberadamente desactivada y nunca se le dice al modelo que oyó algo que no oyó.

## Conexión de IA local

Lleva los modelos que ya se ejecutan en tu propio hardware al mismo catálogo, las
mismas políticas y el mismo enrutamiento `model="auto"` que tus proveedores en la
nube. El conector es un agente solo de salida: marca a tu instancia de GeekCubo
por WebSocket, anuncia los modelos locales que ve y responde solicitudes de chat.
Sin puerto entrante, túnel, VPN ni cuenta en la nube de por medio.

**Panel → Conexión de IA local → Conectar una máquina** guía ocho pasos: crear un
código de inscripción de un solo uso, ejecutar el conector, aprobar la máquina,
habilitar los modelos que quieras y confirmar que están disponibles para Auto.

```bash
# En la máquina que ejecuta los modelos (Python 3.11+), desde un checkout de este repositorio
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

El conector sondea automáticamente los entornos locales habituales:

| Adaptador | URL base por defecto | Protocolo |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Nativo `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | `/v1` compatible con OpenAI |
| `vllm` | `http://127.0.0.1:8000` | `/v1` compatible con OpenAI |
| `llamacpp` | `http://127.0.0.1:8080` | `/v1` compatible con OpenAI |
| `custom` | ninguna (con `--url`) | Cualquier servidor `/v1` compatible con OpenAI (`--api-key` para un token Bearer) |

Usa `--adapter` para limitar el sondeo y `--url adapter=URL` para apuntar un
adaptador a un puerto no predeterminado. `python -m geekcubo_connector ...` es
equivalente al script `geekcubo-connector`. El panel ofrece archivos de servicio
listos para systemd, launchd y Windows para que el conector se reinicie con la
máquina.

Los códigos de inscripción son de un solo uso, caducan a los 30 minutos de forma
predeterminada y no conceden nada hasta que un administrador aprueba la máquina.
Una vez aprobada, los modelos locales aparecen en el catálogo como
`local/<máquina>/<modelo>` y pueden fijarse directamente o incluirse en
`model="auto"`.

El enrutamiento local se rige por el bloque `local` de la política de enrutamiento:

- `enabled`: incluye los modelos locales aprobados en Auto.
- `no_cloud_fallback`: si Auto elige un modelo local y esa máquina está
  desconectada, la solicitud falla en lugar de reintentarse silenciosamente en la
  nube.
- `machines`: limita Auto a identificadores de máquina concretos; vacío significa
  todas las aprobadas y elegibles.

Un modelo local tiene un precio confirmado de cero (se ejecuta en tu hardware), así que siempre supera el filtro de precio de Auto y queda primero con **Cheapest**. Usa el interruptor Auto de la máquina o el bloque `local` para excluirlo. Lo que admite hoy la ruta: descubrimiento de modelos, texto en streaming y reconexión automática (backoff hasta 30 s) en todos los adaptadores; imágenes para modelos que Ollama declara con visión (los demás adaptadores las reciben sin cambios). **Las llamadas a herramientas no se devuelven a través del conector**, por eso los modelos locales se anuncian sin Tools y Auto no les envía solicitudes con herramientas.

Configuración (todo opcional, ver `.env.example`):

| Variable | Predeterminado | Propósito |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Interruptor maestro; `false` cierra el endpoint del agente y oculta los modelos locales. |
| `LOCAL_CONNECT_PUBLIC_URL` | vacío | URL pública escrita en el comando de instalación y los archivos de servicio; vacío = marcador `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Cada cuánto informa una máquina conectada (actualiza su última conexión). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Vida útil de un código de inscripción. |

El socket del agente es un WebSocket en `/api/local-connect/agent`, así que
cualquier proxy inverso delante de GeekCubo debe reenviar la cabecera `Upgrade`.
La configuración de Nginx generada por `./install.sh` incluye el `map` necesario
y Caddy gestiona los WebSocket automáticamente. El concentrador de conexiones en
memoria asume **un único proceso** de servidor; un reinicio corta los conectores
hasta que se reconectan (con retroceso de hasta 30 s). Las credenciales de máquina
son secretos portadores: se guardan con hash en el servidor, con permisos `0600`
en el host del modelo, y se pueden revocar o rotar desde el panel. No se admiten varios workers ni réplicas; `REDIS_URL` no cambia esto.

## Streaming

Formato SSE compatible con OpenAI con el framing estándar `data: ... \n\n` y un sentinel terminal `[DONE]` — drop-in para cualquier SDK que ya transmita desde OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Endpoints de protocolos nativos (Anthropic + Gemini)

GeekCubo habla tres protocolos de entrada sobre un único pipeline de enrutamiento. Los clientes que solo hablan los formatos wire de Anthropic o Gemini se conectan directamente — sin necesidad de un SDK de OpenAI:

```bash
# Claude Code, apuntando a GeekCubo (sin sufijo /v1 en la URL base)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN` (enviado como `Authorization: Bearer`) también funciona; GeekCubo acepta ambas cabeceras.

```python
# SDK google-genai, apuntando a GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Las solicitudes se traducen en la entrada hacia el mismo pipeline interno, así que `model="auto"`, la caché de prompts entre proveedores (compartida entre protocolos), las estrategias de enrutamiento y el panel de analítica funcionan todos de forma idéntica. Guías: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Catálogo de modelos

El catálogo integrado (varios cientos de modelos de chat de los proveedores soportados) se carga al inicio desde la copia de la [base de precios comunitaria](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) incluida con LiteLLM; no hay lista de modelos que mantener. Cada entrada expone:

- `id` (p. ej. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mapeado a tus claves configuradas)
- Flags de capacidad: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Coste por token de entrada/salida (alimenta el widget de ahorro + `model="auto"`)

`GET /v1/models` devuelve `auto`, los perfiles de enrutamiento activos y el catálogo completo en formato OpenAI (en formato Anthropic con la cabecera `anthropic-version`).

Para modelos de proveedores personalizados, Tools, Vision, modo JSON, esquema JSON, contexto y precios de referencia se resuelven automáticamente, campo por campo, desde LiteLLM, Models.dev y Portkey al hacer **Obtener → Seleccionar → Añadir modelos seleccionados**, mostrando la fuente de cada campo. Un valor solo pasa a compatible/no compatible con una coincidencia fiable y explícita; si no, queda Desconocido, y un precio desconocido no bloquea las capacidades. Los modelos ambiguos no reciben valores prestados hasta que elija la clave de catálogo en el selector con búsqueda. Las anulaciones del administrador (incluido «Desconocido») se conservan al actualizar; «Usar catálogo» las elimina. Auto, Chat y los perfiles usan las mismas capacidades guardadas. El modo JSON (json_object) y JSON Schema / salidas estructuradas (json_schema) son capacidades independientes que se resuelven por separado; la evidencia de salidas estructuradas del catálogo solo cuenta para JSON Schema, nunca para el modo JSON.

## Despliegue en otros sitios

GeekCubo es un único contenedor Docker. Sin Compose, construye la imagen desde un checkout y guarda los datos en un volumen con nombre:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Las versiones etiquetadas están preparadas para publicar una imagen multiarquitectura en `ghcr.io/geekcubo/geekcubo-ai-router` (`.github/workflows/release.yml`); usa ese nombre cuando se haya publicado una versión. VPS y proxy inverso: [DEPLOYMENT.md](./DEPLOYMENT.md).

## Qué incluye

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + caché de prompts entre proveedores
- `POST /v1/messages` — **ingress de la API Messages de Anthropic** (Claude Code / los SDK de Anthropic se conectan directamente; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **ingress de la API de Gemini** (el SDK google-genai se conecta directamente; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, perfiles de enrutamiento y catálogo de modelos (integrado desde `litellm.model_cost`, más modelos personalizados y locales)
- `GET/PUT/DELETE /v1/providers/{provider}` — crea / lista / revoca claves de proveedor cifradas
- `GET/PUT /v1/routing` — estrategia (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; heredada `fastest`) y política; `/v1/routing-profiles` — perfiles Auto con nombre
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — analítica local, sin telemetría que salga de la caja
- `GET/POST/DELETE /v1/keys/...` — lista / rota / revoca claves de API
- `/api/local-connect/*` — **Conexión de IA local**: códigos de inscripción, aprobación/revocación/rotación de máquinas, alternancia de modelos, generación de archivos de servicio y el WebSocket del agente saliente en `/api/local-connect/agent` (ids de enrutamiento `local/<machine>/<model>`; inferencia local solo de texto)
- `POST /api/chat/attachments` — sube/extrae/elimina adjuntos del chat; `GET /api/chat/attachments/limits` informa los límites del servidor para que la UI los respete
- Panel de una sola página en `/`
- Pestaña **Chat** integrada en el panel — conversa con tus modelos desplegados desde el navegador; las solicitudes se enrutan, cachean y miden en coste igual que el tráfico del SDK (el historial se guarda solo en tu base de datos local, con retención configurable; el recorte de contexto se informa en cada turno, y la búsqueda web opcional (SearXNG, Brave o Tavily) añade citas)
- SQLite por defecto; Postgres opt-in vía `DATABASE_URL`; Redis opcional
- Se ejecuta como **un único proceso de servidor**. `REDIS_URL` lleva la caché de prompts a Redis, pero no comparte Local AI Connect, el estado de conversación de Auto ni los datos de Adaptive entre procesos; el modo multiworker no está soportado.

### Widget de ahorros

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` informa de lo que tu tráfico habría costado con el modelo de referencia frente a su coste real (precio de lista de la referencia). Las solicitudes con precio desconocido no cuentan como ahorro.

## ❤️ Apoya GeekCubo

GeekCubo es gratuito, de código abierto y se desarrolla de forma independiente. Puedes apoyar su desarrollo explorando servicios que complementan tu configuración de IA.

- [**Proveedores de API de IA**](https://geekcubo.com/providers/) — Descubre proveedores de modelos de IA compatibles.
- [**VPS y alojamiento en la nube**](https://geekcubo.com/hosting/) — Explora opciones de alojamiento para despliegues autoalojados.
- [**VPN y privacidad**](https://geekcubo.com/vpn/) — Explora herramientas opcionales de privacidad y redes seguras.

**Aviso de afiliación:** algunos enlaces pueden generarnos una comisión sin coste adicional para ti. Usarlos es opcional y no influye en el enrutamiento de modelos de GeekCubo ni en la compatibilidad de proveedores.

## Licencia

MIT. Ver [LICENSE](./LICENSE).

GeekCubo deriva de OrcaRouter Lite. La licencia MIT original y su aviso de copyright («Copyright (c) 2026 OrcaRouter contributors») se conservan en [LICENSE](./LICENSE) y deben mantenerse en todas las copias o partes sustanciales del software.

Los recursos de terceros conservan sus licencias: los contornos tipográficos del logotipo (Inter, SIL Open Font License 1.1) se describen en [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).

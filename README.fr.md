# GeekCubo

**Une passerelle. Tous les modèles d'IA.**
**Passerelle IA open source et routeur LLM intelligent.** Compatible OpenAI, BYOK, auto-hébergé. Streaming et routage `model="auto"`.
Compatible OpenAI. BYOK. Workspace unique. Streaming. `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![tests](https://img.shields.io/badge/tests-passing-brightgreen)](./README.md#testing)
[![models](https://img.shields.io/badge/models-100%2B-blue)](#catalogue-de-modèles)
[![license](https://img.shields.io/badge/license-MIT-blue)](#licence)

## Langues

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

GeekCubo est une passerelle auto-hébergée compatible OpenAI : apportez vos propres clés de fournisseur et `model="auto"` choisit un modèle compétent pour chaque requête, avec repli et suivi des coûts.

> **Où il se place.** LiteLLM est une bibliothèque à intégrer ; OpenRouter est uniquement hébergé ; Ollama est uniquement local. GeekCubo est le serveur que vous exécutez vous-même — avec routage, repli et comptabilité intégrés.

## Pourquoi GeekCubo existe

Le routage automatique des modèles devrait donner du contrôle aux développeurs, pas de l'incertitude.

GeekCubo est né d'un problème concret : quand on utilise ses propres clés de fournisseurs d'IA, il n'est pas toujours évident de savoir quel fournisseur traitera une requête, si un repli peut passer par un service facturé séparément, ni pourquoi un modèle précis a été choisi.

Nous voulions une alternative auto-hébergée où les politiques de routage, les fournisseurs éligibles, les capacités des modèles, les hypothèses de prix et le comportement de repli sont visibles et configurables.

GeekCubo repose sur ce principe : **vos clés, votre infrastructure, vos décisions de routage.**

Il n'y a aucun portefeuille de routage hébergé obligatoire. Vous configurez les fournisseurs et les modèles disponibles pour le routeur, et vous pouvez examiner comment le routage automatique prend ses décisions.

### Origines open source

GeekCubo s'appuie sur [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), un projet open source publié sous licence MIT. Nous remercions ses développeurs d'origine d'avoir fourni la base sur laquelle GeekCubo a évolué.

GeekCubo est développé et maintenu de façon indépendante, avec ses propres fonctionnalités, son architecture et son orientation produit. Il n'est ni affilié aux développeurs d'origine d'OrcaRouter ni approuvé par eux.

Voir [Licence](#licence) pour l'attribution et les détails de licence.

## Démarrage rapide en 60 secondes

### Auto-hébergé (BYOK)

Exécutez GeekCubo sur votre propre machine ; apportez vos propres clés de fournisseur.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

Le script vérifie Docker et Compose, valide la configuration, exécute `docker compose up -d --build`, attend le véritable point de terminaison `/health` et, sur une installation neuve, affiche le jeton d'installation à usage unique de l'administrateur. Le relancer est sans risque : le volume de données, `.env`, le compte administrateur, les identifiants des fournisseurs, les secrets de chiffrement et les clés API sont conservés.

Installation manuelle (même configuration Compose) :

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # uniquement tant qu'aucun administrateur n'existe
```

URL de base : `http://127.0.0.1:8787/v1`. Utilisez une clé `sk-geek-*` générée dans le tableau de bord. Le jeton d'installation est à usage unique, devient invalide dès que l'administrateur est créé et doit être traité comme un mot de passe. Le port n'écoute que sur la boucle locale ; pour un accès distant, utilisez un tunnel SSH ou un reverse proxy TLS.

Sur un VPS, définissez `PUBLIC_BASE_URL` dans `.env` avec votre propre adresse — un domaine racine comme `https://example.com` ou un sous-domaine comme `https://api.example.com`, au choix. GeekCubo fonctionne entièrement sur votre infrastructure et ne dépend d'aucun hôte exploité par GeekCubo ; voir [DEPLOYMENT.md](./DEPLOYMENT.md).

### Puis appelez-le depuis n'importe quel SDK OpenAI

Les exemples ci-dessous utilisent l'URL de base Docker locale `http://127.0.0.1:8787/v1`.

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

Les exemples ci-dessous utilisent l'URL de base Docker locale `http://127.0.0.1:8787/v1`.

## Pourquoi ?

| | GeekCubo | Bibliothèque LiteLLM | OpenRouter | Ollama |
|---|---|---|---|---|
| Serveur auto-hébergé | ✓ | en tant que bibliothèque | ✗ | ✓ |
| Compatible OpenAI | ✓ | ✓ | ✓ | ✓ |
| Multi-fournisseur (OpenAI/Anthropic/Google/…) | ✓ | ✓ | ✓ | ✗ |
| Tableau de bord intégré | ✓ | ✗ | ✓ | ✗ |
| `model="auto"` (sélection selon la politique) | ✓ | ✗ | ✗ | n/a |
| Streaming | ✓ | ✓ | ✓ | ✓ |
| BYOK | ✓ | ✓ | ✗ | n/a |
| Pas de Postgres / pas de Redis requis | ✓ | n/a | n/a | ✓ |

## `model="auto"` — la fonctionnalité phare

Envoyez `model="auto"` : GeekCubo réduit les modèles éligibles à Auto à ceux qui peuvent servir la requête, les classe avec la stratégie choisie dans **Routage** et appelle le meilleur, avec une chaîne de repli bornée. Aucune règle de routage manuelle ni code d'optimisation des coûts dans votre application.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → seuls les modèles dont la capacité Vision est « Prise en charge » sont considérés ;
#   la stratégie active les classe
```

Le modèle résolu est exposé en retour aux appelants via l'en-tête de réponse `x-geek-resolved-model`, pour que vous puissiez logger/afficher ce qui a réellement été utilisé.

### Quels modèles Auto peut utiliser

Chaque requête Auto filtre dans cet ordre ; un modèle qui échoue à une étape n'est jamais choisi, pas même en repli :

1. **Éligible** — un fournisseur intégré avec une clé valide, ou un fournisseur personnalisé activé et *inclus dans Auto* ; le modèle lui-même est activé.
2. **Prix confirmé** — un prix catalogue ou un prix que vous avez défini. Un prix inconnu n'est jamais considéré comme gratuit ; une estimation de référence ne compte que si vous l'autorisez.
3. **Capable** — chaque capacité requise (Tools, Vision, mode JSON, JSON Schema) est **Prise en charge**. « Inconnu » ne satisfait jamais une exigence.
4. **Contexte** — le prompt estimé tient dans une fenêtre de contexte connue. Une fenêtre inconnue n'exclut pas le modèle.
5. **Autorisé** — la liste d'autorisation de la clé API et, le cas échéant, les restrictions d'un profil de routage.

### Stratégies

| Stratégie | Classement des candidats restants | Si les données manquent |
|---|---|---|
| **Balanced** (défaut) | Poids égal entre score de qualité et prix mixte ; un plancher de qualité retire d'abord les modèles plus faibles. Seuls les modèles notés participent. | Sans scores : classement par prix, signalé dans les notes de routage. |
| **Cheapest** | Prix mixte le plus bas (30 % entrée, 70 % sortie) ; égalité départagée par identifiant. | Tous les prix inconnus : aucun candidat, diagnostic au lieu d'un choix au hasard. |
| **Quality First** | Score de qualité le plus élevé ; les scores manuels remplacent Artificial Analysis. | Sans scores : le prix sert d'indicateur (le plus cher d'abord), signalé. |
| **Adaptive** | Taux de succès observé, puis latence, d'après votre propre journal (7 jours). | Moins de 20 requêtes par modèle : se comporte comme Balanced et l'indique. |
| **Adaptive-Gated** | Classe la requête *Mundane* ou *Hard* (outils, images, longs prompts, nombreux messages, `max_tokens` élevé) et ne classe que ce pool. | Pool sans modèle capable : pool *Fallback*, puis *Mundane* pour les requêtes difficiles si autorisé — jamais tout le catalogue. |
| **Fastest** (hérité) | Débit et délai du premier token mesurés ; les modèles sans mesures sont exclus. | Sans mesures : classement par prix, signalé. |

**Utiliser Auto :** envoyer `model="auto"` ou choisir **Auto (le routeur choisit)** dans le Chat. **Modèle précis :** envoyer son identifiant complet ou le choisir dans le Chat. **Changer de stratégie :** cliquer sur une carte dans Routage (enregistré immédiatement). **Exclure un modèle d'Auto :** désactiver le modèle, choisir *Exclure d'Auto* sur son fournisseur ou retirer son prix confirmé. **Pourquoi ce modèle ?** **Tester une décision de routage**, les en-têtes `x-geek-routing-*` ou Analytics. **Aucun modèle éligible :** une erreur 422 explique la cause. Le routage Auto des *modèles* n'a rien à voir avec le mode Auto réservé de la recherche web.

Dans le tableau de bord, la page Routage expose toute la politique Auto : **Fallback, escalade et continuité** (tentatives de fallback, mode et seuils d'escalade, pool de destination, mode shadow, stickiness) et **Tester une décision de routage**, un dry-run qui montre le modèle, le tier, la stratégie et chaque étape de filtrage ayant écarté des candidats. Rien n'est envoyé au fournisseur.

## Chat natif : recherche web et budget de contexte

L'onglet **Chat** du tableau de bord réduit l'historique de la conversation à la
fenêtre de contexte du modèle choisi. Chaque réponse indique les jetons estimés,
le budget et le nombre de messages plus anciens omis : une réponse raccourcie
n'est jamais confondue avec une panne du modèle.

La recherche web est facultative et désactivée par défaut. Configurez-la dans
**Paramètres → Chat → Recherche web** avec SearXNG (auto-hébergé), Brave ou
Tavily. SearXNG peut être lancé par `./install.sh` ou par `docker compose
--profile search up -d`. Les clés de recherche sont chiffrées, séparées des clés
d'inférence, et les citations ne s'affichent que pour les pages réellement
renvoyées par le backend. Le mode `auto` est réservé et pas encore implémenté.

## Chat natif : pièces jointes

Le compositeur accepte des fichiers de trois façons : le trombone, le glisser-
déposer sur la conversation, et le collage. Une image collée devient une pièce
jointe ; le texte brut collé reste natif.

| Type | Formats | Ce que voit le modèle |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Envoyée en parties d'image à un modèle doté de vision |
| `document` | PDF, DOCX, RTF | Texte extrait, délimité |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Texte feuille par feuille, borné |
| `text` / `code` | TXT, MD, JSON, YAML, sources | Texte brut, délimité |
| `archive` | ZIP, tar, gzip | Liste des entrées et lectures bornées ; jamais décompressé sur disque |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Vidéo : métadonnées et images espacées. Audio : métadonnées seules |

Les pièces jointes textuelles deviennent toujours un bloc délimité dans le
message de l'utilisateur, lisible par n'importe quel modèle. Les images ne
deviennent de vraies parties d'image que pour le tour en cours ; dans
l'historique plus ancien, elles se réduisent à un marqueur `[attached: name]`
pour ne pas fausser la fenêtre de contexte. Si vous épinglez un modèle sans
vision, l'envoi est refusé avec un diagnostic `no_vision` plutôt que de perdre
le fichier en silence.

Limites côté serveur (réglables par env : `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR` ; voir `.env.example`) :

- Jusqu'à 8 pièces jointes par message.
- 25 Mo par fichier par défaut, plafonnés à un maximum absolu.
- Les envois non rattachés sont purgés au bout de 24 heures.

Les échecs d'extraction sont signalés fichier par fichier et ne bloquent jamais
le texte saisi. `GET /api/chat/attachments/limits` indique au navigateur ce
qu'il peut envoyer, afin que l'interface applique les mêmes règles avant l'envoi.

Les images vidéo nécessitent `ffmpeg`/`ffprobe` dans le `PATH` ; sans eux la
vidéo s'envoie quand même et le modèle est averti qu'elle est illisible. L'audio
n'est décrit au modèle que par ses métadonnées : la transcription automatique
est volontairement désactivée, et on ne dit jamais au modèle qu'il a entendu
quelque chose qu'il n'a pas entendu.

## Connexion IA locale

Intégrez les modèles qui tournent déjà sur votre propre matériel au même
catalogue, aux mêmes politiques et au même routage `model="auto"` que vos
fournisseurs cloud. Le connecteur est un agent sortant uniquement : il se
connecte à votre instance GeekCubo en WebSocket, annonce les modèles locaux qu'il
voit et répond aux requêtes de chat. Aucun port entrant, tunnel, VPN ni compte
cloud entre les deux.

**Tableau de bord → Connexion IA locale → Connecter une machine** guide huit
étapes : générer un code d'enrôlement à usage unique, lancer le connecteur,
approuver la machine, activer les modèles voulus et vérifier qu'ils sont
disponibles pour Auto.

```bash
# Sur la machine qui exécute les modèles (Python 3.11+), depuis un clone de ce dépôt
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

Le connecteur sonde automatiquement les environnements locaux courants :

| Adaptateur | URL de base par défaut | Protocole |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Natif `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | `/v1` compatible OpenAI |
| `vllm` | `http://127.0.0.1:8000` | `/v1` compatible OpenAI |
| `llamacpp` | `http://127.0.0.1:8080` | `/v1` compatible OpenAI |
| `custom` | aucun (via `--url`) | Tout serveur `/v1` compatible OpenAI (`--api-key` pour un jeton Bearer) |

Utilisez `--adapter` pour limiter la détection et `--url adapter=URL` pour viser
un port non standard. `python -m geekcubo_connector ...` équivaut au script
`geekcubo-connector`. Le tableau de bord fournit des fichiers de service systemd,
launchd et Windows pour que le connecteur redémarre avec la machine.

Les codes d'enrôlement sont à usage unique, expirent après 30 minutes par défaut
et n'accordent rien tant qu'un administrateur n'a pas approuvé la machine. Une
fois approuvée, les modèles locaux apparaissent dans le catalogue sous
`local/<machine>/<modèle>` et peuvent être épinglés directement ou inclus dans
`model="auto"`.

Le routage local est régi par le bloc `local` de la politique de routage :

- `enabled` — inclure les modèles locaux approuvés dans Auto.
- `no_cloud_fallback` — si Auto choisit un modèle local et que la machine est
  hors ligne, la requête échoue au lieu d'être silencieusement retentée dans le
  cloud.
- `machines` — limiter Auto à des identifiants de machine précis ; vide signifie
  toutes les machines approuvées et éligibles.

Un modèle local a un prix confirmé de zéro (il tourne sur votre matériel) : il passe donc toujours le filtre de prix d'Auto et arrive en tête avec **Cheapest**. Utilisez l'interrupteur Auto de la machine ou le bloc `local` pour l'en exclure. Ce que le chemin prend en charge aujourd'hui : découverte des modèles, texte en streaming et reconnexion automatique (backoff plafonné à 30 s) pour tous les adaptateurs ; entrées image pour les modèles qu'Ollama déclare compatibles vision (les autres adaptateurs les reçoivent telles quelles). **Les appels d'outils ne sont pas renvoyés par le connecteur** : les modèles locaux sont donc proposés sans Tools et Auto ne leur envoie pas de requêtes avec outils.

Configuration (tout est optionnel, voir `.env.example`) :

| Variable | Défaut | Rôle |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Interrupteur principal ; `false` ferme l'endpoint de l'agent et masque les modèles locaux. |
| `LOCAL_CONNECT_PUBLIC_URL` | vide | URL publique écrite dans la commande d'installation et les fichiers de service ; vide = espace réservé `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Fréquence à laquelle une machine connectée se signale (met à jour « vu pour la dernière fois »). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Durée de vie d'un code d'enrôlement. |

Le socket de l'agent est un WebSocket sur `/api/local-connect/agent` ; tout
reverse proxy devant GeekCubo doit donc transmettre l'en-tête `Upgrade`. La
configuration Nginx générée par `./install.sh` inclut le `map` nécessaire et
Caddy gère les WebSockets automatiquement. Le hub de connexions en mémoire
suppose **un seul processus** serveur ; un redémarrage coupe les connecteurs
jusqu'à leur reconnexion (recul plafonné à 30 s). Les identifiants de machine
sont des secrets porteurs : hachés côté serveur, écrits en `0600` sur l'hôte du
modèle, et révocables ou renouvelables depuis le tableau de bord. Plusieurs workers ou réplicas ne sont pas pris en charge ; `REDIS_URL` n'y change rien.

## Streaming

Format SSE compatible OpenAI avec le framing standard `data: ... \n\n` et un sentinel terminal `[DONE]` — drop-in pour tout SDK qui stream déjà depuis OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Endpoints protocolaires natifs (Anthropic + Gemini)

GeekCubo parle trois protocoles entrants sur un seul pipeline de routage. Les clients qui ne parlent que les formats wire Anthropic ou Gemini se connectent directement — aucun SDK OpenAI requis :

```bash
# Claude Code, pointé sur GeekCubo (pas de suffixe /v1 dans l'URL de base)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN` (envoyé en `Authorization: Bearer`) fonctionne aussi ; GeekCubo accepte les deux en-têtes.

```python
# SDK google-genai, pointé sur GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Les requêtes sont traduites à l'entrée vers le même pipeline interne, donc `model="auto"`, le cache de prompts inter-fournisseurs (partagé entre les protocoles), les stratégies de routage et le tableau de bord d'analytics fonctionnent tous à l'identique. Guides : [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Catalogue de modèles

Le catalogue intégré (plusieurs centaines de modèles de chat des fournisseurs pris en charge) est chargé au démarrage depuis la copie de la [base de prix communautaire](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) livrée avec LiteLLM — aucune liste de modèles à maintenir. Chaque entrée expose :

- `id` (par ex. `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (mappé sur vos clés configurées)
- Drapeaux de capacité : `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Coût par token entrée/sortie (alimente le widget d'économies + `model="auto"`)

`GET /v1/models` renvoie `auto`, les profils de routage activés et le catalogue complet au format OpenAI (au format Anthropic avec l'en-tête `anthropic-version`).

Pour les modèles de fournisseurs personnalisés, Tools, Vision, mode JSON, schéma JSON, contexte et prix de référence sont résolus automatiquement, champ par champ, depuis LiteLLM, Models.dev et Portkey lors de **Récupérer → Sélectionner → Ajouter les modèles sélectionnés**, avec la source affichée pour chaque champ. Une valeur ne devient prise en charge/non prise en charge qu'avec une correspondance fiable et explicite ; sinon elle reste Inconnue, et un prix inconnu ne bloque pas les capacités. Les modèles ambigus ne reçoivent aucune valeur empruntée tant que vous n'avez pas choisi la clé de catalogue dans le sélecteur avec recherche. Les remplacements de l'administrateur (y compris « Inconnu ») sont conservés lors des actualisations ; « Utiliser le catalogue » les supprime. Auto, Chat et les profils utilisent les mêmes capacités enregistrées. Le mode JSON (json_object) et JSON Schema / sorties structurées (json_schema) sont des capacités distinctes, résolues indépendamment ; les preuves de sorties structurées du catalogue ne valent que pour JSON Schema, jamais pour le mode JSON.

## Déployer ailleurs

GeekCubo est un seul conteneur Docker. Sans Compose, construisez l'image depuis un checkout et gardez les données sur un volume nommé :

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Les versions taguées sont prévues pour publier une image multi-architecture sur `ghcr.io/geekcubo/geekcubo-ai-router` (`.github/workflows/release.yml`) ; utilisez ce nom une fois une version publiée. VPS et proxy inverse : [DEPLOYMENT.md](./DEPLOYMENT.md).

## Ce qu'il y a dans la boîte

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + cache de prompts inter-fournisseurs
- `POST /v1/messages` — **ingress de l'API Messages d'Anthropic** (Claude Code / les SDK Anthropic se connectent directement ; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **ingress de l'API Gemini** (le SDK google-genai se connecte directement ; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, profils de routage et catalogue de modèles (intégré depuis `litellm.model_cost`, plus les modèles personnalisés et locaux)
- `GET/PUT/DELETE /v1/providers/{provider}` — définir / lister / révoquer des clés de fournisseur chiffrées
- `GET/PUT /v1/routing` — stratégie (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated` ; hérité `fastest`) et politique ; `/v1/routing-profiles` — profils Auto nommés
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — analytics locales, aucune télémétrie ne sort de la boîte
- `GET/POST/DELETE /v1/keys/...` — lister / faire tourner / révoquer des clés API
- `/api/local-connect/*` — **Connexion IA locale** : codes d'inscription, approbation/révocation/rotation des machines, bascules de modèles, génération de fichiers de service et le WebSocket d'agent sortant sur `/api/local-connect/agent` (ids de routage `local/<machine>/<model>` ; inférence locale texte uniquement)
- `POST /api/chat/attachments` — téléverser/extraire/supprimer les pièces jointes du chat ; `GET /api/chat/attachments/limits` expose les limites imposées par le serveur pour que l'interface les respecte
- Tableau de bord en page unique sur `/`
- Onglet **Chat** intégré au tableau de bord — discutez avec vos modèles déployés depuis le navigateur ; les requêtes sont routées, mises en cache et facturées exactement comme le trafic SDK (l'historique reste dans votre base locale, avec une durée de conservation réglable ; le rognage du contexte est indiqué à chaque tour, et la recherche web facultative (SearXNG, Brave ou Tavily) ajoute des citations)
- SQLite par défaut ; Postgres opt-in via `DATABASE_URL` ; Redis optionnel
- Fonctionne comme **un seul processus serveur**. `REDIS_URL` déplace le cache de prompts vers Redis mais ne partage pas Local AI Connect, l'état de conversation d'Auto ni les données d'Adaptive entre processus ; le multi-worker n'est pas pris en charge.

### Widget d'économies

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` indique ce que votre trafic aurait coûté avec le modèle de référence face à son coût réel (prix catalogue de la référence). Les requêtes au prix inconnu ne comptent pas comme économies.

## ❤️ Soutenir GeekCubo

GeekCubo est gratuit, open source et développé de façon indépendante. Vous pouvez soutenir son développement en découvrant des services qui complètent votre configuration IA.

- [**Fournisseurs d'API IA**](https://geekcubo.com/providers/) — Découvrir des fournisseurs de modèles IA compatibles.
- [**VPS et hébergement cloud**](https://geekcubo.com/hosting/) — Explorer des options d'hébergement pour les déploiements auto-hébergés.
- [**VPN et confidentialité**](https://geekcubo.com/vpn/) — Explorer des outils optionnels de confidentialité et de réseau sécurisé.

**Divulgation d'affiliation :** certains liens peuvent nous rapporter une commission sans coût supplémentaire pour vous. Leur utilisation est facultative et n'influence ni le routage des modèles de GeekCubo ni la compatibilité des fournisseurs.

## Licence

MIT. Voir [LICENSE](./LICENSE).

GeekCubo est dérivé d'OrcaRouter Lite. La licence MIT d'origine et son avis de copyright (« Copyright (c) 2026 OrcaRouter contributors ») sont conservés dans [LICENSE](./LICENSE) et doivent figurer dans toute copie ou partie substantielle du logiciel.

Les ressources tierces conservent leur licence : les contours de police utilisés dans le logo (Inter, SIL Open Font License 1.1) sont couverts par [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).

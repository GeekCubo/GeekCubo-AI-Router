# GeekCubo

**Một cổng kết nối. Mọi mô hình AI.**
**Cổng AI mã nguồn mở và bộ định tuyến LLM thông minh.** Tương thích OpenAI, BYOK, tự lưu trữ. Streaming và định tuyến `model="auto"`.
Tương thích OpenAI. BYOK. Workspace đơn. Streaming. `model="auto"`.

![GeekCubo](design/brand/geekcubo-logo.png)

[![ci](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](#giấy-phép)
[![website](https://img.shields.io/badge/website-geekcubo.com-2563eb)](https://geekcubo.com)

[English](./README.md) | [日本語](./README.ja.md) | [中文](./README.zh.md) | [한국어](./README.ko.md) | [Deutsch](./README.de.md) | [Français](./README.fr.md) | [Español](./README.es.md) | [Italiano](./README.it.md) | [Русский](./README.ru.md) | [Português](./README.pt.md) | [Tiếng Việt](./README.vi.md) | [हिन्दी](./README.hi.md)

> **Tài liệu chi tiết** (tiếng Anh): bảo mật, phiên đăng nhập và khóa API, định tuyến, kết nối công cụ gồm OpenCode, triển khai — xem [docs/](./docs/README.md). Nếu có khác biệt, [README tiếng Anh](./README.md) là bản chuẩn.

GeekCubo là một cổng tự lưu trữ tương thích OpenAI: mang theo khoá provider của riêng bạn và `model="auto"` sẽ chọn một mô hình phù hợp cho mỗi yêu cầu, cùng dự phòng và theo dõi chi phí.


## Vì sao GeekCubo ra đời

Định tuyến mô hình tự động nên mang lại quyền kiểm soát cho nhà phát triển, chứ không phải sự mơ hồ.

GeekCubo bắt nguồn từ một vấn đề thực tế: khi dùng khoá của chính các nhà cung cấp AI, không phải lúc nào cũng rõ nhà cung cấp nào sẽ xử lý một yêu cầu, liệu fallback có thể dùng một dịch vụ tính phí riêng hay không, hoặc vì sao một mô hình cụ thể được chọn.

Chúng tôi muốn một giải pháp tự lưu trữ, nơi chính sách định tuyến, các nhà cung cấp hợp lệ, năng lực mô hình, giả định về giá và hành vi fallback đều hiển thị rõ ràng và có thể cấu hình.

GeekCubo được xây dựng trên nguyên tắc đó: **khoá của bạn, hạ tầng của bạn, quyết định định tuyến của bạn.**

Không có ví định tuyến lưu trữ bắt buộc nào. Bạn cấu hình các nhà cung cấp và mô hình mà bộ định tuyến được dùng, và có thể xem định tuyến tự động đã ra quyết định như thế nào.

### Nguồn gốc mã nguồn mở

GeekCubo được xây dựng dựa trên [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), một dự án mã nguồn mở phát hành theo giấy phép MIT. Chúng tôi cảm ơn các nhà phát triển ban đầu đã tạo nền tảng để GeekCubo phát triển.

GeekCubo được phát triển và duy trì độc lập, với tính năng, kiến trúc và định hướng sản phẩm riêng. GeekCubo không liên kết và không được các nhà phát triển ban đầu của OrcaRouter bảo trợ.

Xem [Giấy phép](#giấy-phép) để biết thông tin ghi công và giấy phép.

## Khởi động nhanh trong 60 giây

### Tự lưu trữ (BYOK)

Chạy GeekCubo trên máy của bạn; mang theo khoá provider của riêng bạn.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

Tập lệnh kiểm tra Docker và Compose, xác thực cấu hình, chạy `docker compose up -d --build`, chờ endpoint `/health` thật và trên bản cài mới sẽ hiển thị token thiết lập dùng một lần cho quản trị viên. Chạy lại an toàn: volume dữ liệu, `.env`, tài khoản quản trị viên, thông tin xác thực provider, bí mật mã hoá và khoá API được giữ nguyên.

Cài thủ công (cùng cấu hình Compose):

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec api python -m app.admin_cli setup-token   # chỉ khi chưa có quản trị viên
```

URL gốc: `http://127.0.0.1:8787/v1`. Dùng khoá `sk-geek-*` tạo trong bảng điều khiển. Token thiết lập chỉ dùng một lần, hết hiệu lực sau khi tạo quản trị viên và phải được đối xử như mật khẩu. Cổng chỉ gắn với loopback; để truy cập từ xa, hãy dùng SSH tunnel hoặc reverse proxy TLS.

Trên VPS, đặt `PUBLIC_BASE_URL` trong `.env` thành địa chỉ của riêng bạn — tên miền gốc như `https://example.com` hoặc tên miền con như `https://api.example.com`, cách nào cũng được. GeekCubo chạy hoàn toàn trên hạ tầng của bạn và không phụ thuộc vào máy chủ nào do GeekCubo vận hành; xem [DEPLOYMENT.md](./DEPLOYMENT.md).

### Sau đó gọi từ bất kỳ OpenAI SDK nào

Các ví dụ bên dưới dùng URL gốc Docker cục bộ `http://127.0.0.1:8787/v1`.

<details>
<summary><b>Python</b></summary>

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-abc123...",
)
r = client.chat.completions.create(
    model="auto",  # hoặc "gpt-4o-mini", "claude-3-5-sonnet-latest", ...
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

Các ví dụ bên dưới dùng URL gốc Docker cục bộ `http://127.0.0.1:8787/v1`.

## `model="auto"` — tính năng chủ lực

Gửi `model="auto"`, GeekCubo lọc các mô hình được phép tham gia Auto xuống còn những mô hình xử lý được yêu cầu, xếp hạng chúng bằng chiến lược bạn chọn trong **Routing** và gọi mô hình tốt nhất, với một chuỗi fallback có giới hạn phía sau. Không cần luật định tuyến thủ công hay code tối ưu chi phí trong ứng dụng của bạn.

```python
client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": "What's in this image?"},
        {"type": "image_url", "image_url": {"url": "data:..."}},
    ]}],
)
# → chỉ các mô hình có năng lực Vision là «Hỗ trợ» mới được xét;
#   chiến lược đang dùng quyết định thứ tự
```

Mô hình được chọn được trả về cho bên gọi qua header phản hồi `x-geek-resolved-model`, để bạn có thể log/hiển thị mô hình thực sự đã dùng.

### Auto được dùng những mô hình nào

Mỗi yêu cầu Auto lọc ứng viên theo thứ tự sau; mô hình không qua một bước sẽ không bao giờ được chọn, kể cả làm fallback:

1. **Hợp lệ** — nhà cung cấp tích hợp có khoá hoạt động, hoặc nhà cung cấp tùy chỉnh đã bật và *đưa vào Auto*; bản thân mô hình đã bật.
2. **Giá đã xác nhận** — giá niêm yết hoặc giá bạn đặt. Giá không rõ không bao giờ được coi là miễn phí; ước tính tham chiếu chỉ được tính nếu bạn cho phép.
3. **Có năng lực** — mọi năng lực cần thiết (Tools, Vision, chế độ JSON, JSON Schema) đều **Hỗ trợ**. «Không rõ» không bao giờ đáp ứng yêu cầu.
4. **Vừa ngữ cảnh** — prompt ước tính nằm gọn trong cửa sổ ngữ cảnh đã biết. Mô hình có cửa sổ không rõ không bị loại vì lý do này.
5. **Được phép** — danh sách cho phép của khoá API và, nếu có, giới hạn của hồ sơ định tuyến.

### Chiến lược

| Chiến lược | Cách xếp hạng ứng viên còn lại | Khi thiếu dữ liệu |
|---|---|---|
| **Balanced** (mặc định) | Trọng số ngang nhau giữa điểm chất lượng và giá pha trộn; ngưỡng chất lượng loại các mô hình yếu hơn trước. Chỉ mô hình có điểm mới tham gia. | Không có điểm: xếp theo giá và ghi chú trong routing notes. |
| **Cheapest** | Giá pha trộn thấp nhất (30 % đầu vào, 70 % đầu ra); hoà thì theo id mô hình. | Mọi giá đều không rõ: không có ứng viên, trả về chẩn đoán thay vì đoán. |
| **Quality First** | Điểm chất lượng cao nhất; điểm thủ công thay thế Artificial Analysis. | Không có điểm: dùng giá làm thay thế (đắt nhất trước) và ghi chú. |
| **Adaptive** | Xếp lại theo tỷ lệ thành công quan sát được, sau đó là độ trễ, từ nhật ký yêu cầu của bạn (7 ngày). | Dưới 20 yêu cầu mỗi mô hình: hoạt động như Balanced và báo số mẫu. |
| **Adaptive-Gated** | Phân loại yêu cầu là *Mundane* hoặc *Hard* (công cụ, hình ảnh, prompt dài, nhiều tin nhắn, `max_tokens` lớn) và chỉ xếp hạng trong pool đó. | Pool không có mô hình phù hợp: pool *Fallback*, rồi *Mundane* cho yêu cầu khó nếu được phép; không bao giờ mở rộng ra cả danh mục. |
| **Fastest** (cũ) | Thông lượng và độ trễ token đầu đo được; mô hình không có số đo bị loại. | Không có số đo: xếp theo giá và ghi chú. |

**Dùng Auto:** gửi `model="auto"` hoặc chọn **Auto (router picks)** trong Chat. **Một mô hình cụ thể:** gửi id đầy đủ hoặc chọn trong Chat. **Đổi chiến lược:** bấm thẻ chiến lược ở trang Routing (lưu ngay). **Loại mô hình khỏi Auto:** tắt mô hình, chọn *Loại khỏi Auto* ở nhà cung cấp hoặc xoá giá đã xác nhận. **Vì sao chọn mô hình này?** **Thử một quyết định định tuyến**, header `x-geek-routing-*` hoặc Analytics. **Không có mô hình hợp lệ:** trả về 422 kèm lý do thay vì đoán. Định tuyến *mô hình* Auto không liên quan đến chế độ Auto dành riêng của tìm kiếm web.

Trên bảng điều khiển, trang Routing trình bày toàn bộ chính sách Auto: **Fallback, leo thang và tính liên tục** (số lần fallback, chế độ và ngưỡng leo thang, pool đích, chế độ shadow, stickiness) và **Thử một quyết định định tuyến**, một dry-run hiển thị mô hình, tier, chiến lược và từng bước lọc đã loại bỏ ứng viên. Không có gì được gửi tới nhà cung cấp.

## Chat gốc: tìm kiếm web và ngân sách ngữ cảnh

Tab **Chat** trên bảng điều khiển cắt lịch sử hội thoại cho vừa cửa sổ ngữ cảnh
của mô hình đã chọn. Mỗi câu trả lời báo số token ước tính, ngân sách và số tin
nhắn cũ bị bỏ qua, nên một câu trả lời bị rút gọn không bao giờ bị nhầm là lỗi
mô hình.

Tìm kiếm web là tùy chọn và mặc định tắt. Cấu hình trong **Cài đặt → Chat → Tìm
kiếm web** với SearXNG (tự lưu trữ), Brave hoặc Tavily. SearXNG có thể khởi động
bằng `./install.sh` hoặc `docker compose --profile search up -d`. Khóa tìm kiếm
được lưu mã hóa, tách biệt với khóa suy luận, và trích dẫn chỉ hiển thị cho những
trang mà backend thực sự trả về. Chế độ `auto` được để dành và chưa được triển
khai.

## Chat gốc: tệp đính kèm

Khung soạn nhận tệp theo ba cách: nút kẹp giấy, kéo-thả vào cuộc hội thoại, và dán.
Ảnh được dán sẽ trở thành tệp đính kèm; văn bản thuần được dán vẫn như cũ.

| Loại | Định dạng | Mô hình thấy gì |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Gửi dưới dạng phần ảnh tới mô hình có thị giác |
| `document` | PDF, DOCX, RTF | Văn bản trích xuất, có dấu phân cách |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Văn bản theo từng trang tính, có giới hạn |
| `text` / `code` | TXT, MD, JSON, YAML, mã nguồn | Văn bản thô, có dấu phân cách |
| `archive` | ZIP, tar, gzip | Danh sách mục và đọc có giới hạn; không bao giờ giải nén ra đĩa |
| `video` / `audio` | MP4, WebM, MOV, MP3, WAV, … | Video: siêu dữ liệu và khung hình cách đều. Âm thanh: chỉ siêu dữ liệu |

Tệp đính kèm dạng văn bản luôn được chuyển thành khối có dấu phân cách trong tin
nhắn người dùng, mô hình nào cũng đọc được. Ảnh chỉ trở thành phần ảnh thật cho lượt
hiện tại; trong lịch sử cũ hơn chúng thu gọn thành dấu `[attached: name]` để không
làm sai lệch cửa sổ ngữ cảnh. Nếu bạn ghim một mô hình không nhận ảnh, lần gửi bị từ
chối với chẩn đoán `no_vision` thay vì âm thầm bỏ tệp.

Giới hạn phía máy chủ (điều chỉnh qua biến môi trường: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; xem `.env.example`):

- Tối đa 8 tệp đính kèm mỗi tin nhắn.
- Mặc định 25 MB mỗi tệp, bị chặn bởi mức trần cứng.
- Tệp tải lên chưa gắn vào tin nhắn bị xóa sau 24 giờ.

Lỗi trích xuất được hiển thị theo từng tệp và không bao giờ chặn văn bản bạn đã gõ.
`GET /api/chat/attachments/limits` cho trình duyệt biết được phép tải gì, để giao
diện áp dụng đúng quy tắc trước khi gửi.

Khung hình video cần `ffmpeg`/`ffprobe` trong `PATH`; nếu không có, video vẫn được
tải lên và mô hình được cho biết là không đọc được. Âm thanh chỉ được mô tả cho mô
hình bằng siêu dữ liệu — chép lời tự động được cố ý tắt, và không bao giờ nói với mô
hình rằng nó đã nghe điều nó không nghe.

## Kết nối AI cục bộ

Đưa các mô hình đang chạy trên phần cứng của bạn vào cùng danh mục, cùng chính
sách và cùng định tuyến `model="auto"` như các nhà cung cấp đám mây. Bộ kết nối là
một tác nhân chỉ gọi ra ngoài: nó kết nối tới GeekCubo qua WebSocket, thông báo các
mô hình cục bộ mà nó thấy và trả lời yêu cầu chat. Không cần cổng vào, đường hầm,
VPN hay tài khoản đám mây.

**Bảng điều khiển → Kết nối AI cục bộ → Kết nối một máy** hướng dẫn tám bước: tạo
mã đăng ký dùng một lần, chạy bộ kết nối, phê duyệt máy, bật các mô hình mong muốn
và xác nhận chúng có sẵn cho Auto.

```bash
# Trên máy chạy mô hình (Python 3.11+), từ bản sao của kho này
pip install .
geekcubo-connector enroll --server https://example.com --code lcenr-...   # your GeekCubo address
geekcubo-connector run
```

Bộ kết nối tự động dò các môi trường cục bộ phổ biến:

| Bộ chuyển đổi | URL gốc mặc định | Giao thức |
|---|---|---|
| `ollama` | `http://127.0.0.1:11434` | Gốc `/api/tags`, `/api/show`, `/api/chat` |
| `lmstudio` | `http://127.0.0.1:1234` | `/v1` tương thích OpenAI |
| `vllm` | `http://127.0.0.1:8000` | `/v1` tương thích OpenAI |
| `llamacpp` | `http://127.0.0.1:8080` | `/v1` tương thích OpenAI |
| `custom` | không có (đặt bằng `--url`) | Bất kỳ máy chủ `/v1` tương thích OpenAI (`--api-key` cho token Bearer) |

Dùng `--adapter` để giới hạn phạm vi dò và `--url adapter=URL` để trỏ tới cổng
khác mặc định. `python -m geekcubo_connector ...` tương đương với lệnh
`geekcubo-connector`. Bảng điều khiển cung cấp sẵn tệp dịch vụ systemd, launchd và
Windows để bộ kết nối khởi động cùng máy.

Mã đăng ký dùng một lần, mặc định hết hạn sau 30 phút và không cấp quyền gì cho đến
khi quản trị viên phê duyệt máy. Sau khi phê duyệt, mô hình cục bộ xuất hiện trong
danh mục dưới dạng `local/<máy>/<mô hình>` và có thể ghim trực tiếp hoặc đưa vào
`model="auto"`.

Định tuyến cục bộ do khối `local` trong chính sách định tuyến điều khiển:

- `enabled` — đưa các mô hình cục bộ đã phê duyệt vào Auto.
- `no_cloud_fallback` — nếu Auto chọn mô hình cục bộ mà máy ngoại tuyến, yêu cầu
  thất bại thay vì âm thầm thử lại trên đám mây.
- `machines` — giới hạn Auto cho các id máy cụ thể; để trống nghĩa là mọi máy đã
  phê duyệt và đủ điều kiện.

Mô hình cục bộ có giá đã xác nhận bằng 0 (chạy trên phần cứng của bạn), nên luôn qua bước kiểm tra giá của Auto và đứng đầu với **Cheapest**. Dùng công tắc Auto của máy hoặc khối `local` để loại nó khỏi Auto. Những gì đường truyền hỗ trợ hiện nay: khám phá mô hình, văn bản streaming và tự kết nối lại (backoff tối đa 30 giây) cho mọi bộ chuyển đổi; ảnh đầu vào cho các mô hình mà Ollama báo là hỗ trợ thị giác (các bộ chuyển đổi khác nhận nguyên vẹn). **Lệnh gọi công cụ không được trả về qua connector**, nên mô hình cục bộ được công bố không có Tools và Auto không gửi yêu cầu cần công cụ cho chúng.

Cấu hình (tất cả tùy chọn, xem `.env.example`):

| Biến | Mặc định | Mục đích |
|---|---|---|
| `LOCAL_CONNECT_ENABLED` | `true` | Công tắc chính; `false` đóng điểm cuối tác nhân và ẩn mô hình cục bộ. |
| `LOCAL_CONNECT_PUBLIC_URL` | trống | URL công khai ghi vào lệnh cài đặt và tệp dịch vụ; để trống thì hiện chỗ giữ `https://your-geekcubo-host`. |
| `LOCAL_CONNECT_HEARTBEAT_SECONDS` | `45` | Tần suất một máy đã kết nối báo cáo (cập nhật lần thấy cuối). |
| `LOCAL_CONNECT_ENROLLMENT_TTL_MINUTES` | `30` | Thời hạn của mã đăng ký. |

Socket của tác nhân là WebSocket tại `/api/local-connect/agent`, nên mọi proxy
ngược trước GeekCubo phải chuyển tiếp tiêu đề HTTP `Upgrade`. Cấu hình Nginx do
`./install.sh` tạo đã có `map` cần thiết và Caddy xử lý WebSocket tự động. Trung
tâm kết nối trong bộ nhớ giả định **một tiến trình máy chủ** duy nhất; khởi động
lại sẽ ngắt các bộ kết nối cho đến khi chúng kết nối lại (giãn cách tối đa 30
giây). Thông tin đăng nhập của máy là bí mật bearer: lưu dạng băm trên máy chủ,
ghi với quyền `0600` trên máy chủ mô hình, và có thể thu hồi hoặc xoay vòng từ bảng
điều khiển bất cứ lúc nào. Không hỗ trợ nhiều worker hoặc nhiều bản sao; `REDIS_URL` không thay đổi điều này.

## Streaming

Định dạng SSE tương thích OpenAI với framing chuẩn `data: ... \n\n` và sentinel kết thúc `[DONE]` — drop-in cho bất kỳ SDK nào đã stream từ OpenAI.

```python
for chunk in client.chat.completions.create(
    model="auto",
    messages=[{"role": "user", "content": "Tell me a story"}],
    stream=True,
):
    print(chunk.choices[0].delta.content or "", end="", flush=True)
```

## Các endpoint giao thức native (Anthropic + Gemini)

GeekCubo nói ba giao thức đầu vào trên cùng một pipeline định tuyến. Các client chỉ nói định dạng wire của Anthropic hoặc Gemini có thể kết nối trực tiếp — không cần OpenAI SDK:

```bash
# Claude Code trỏ vào GeekCubo (URL gốc không có hậu tố /v1)
export ANTHROPIC_BASE_URL=http://127.0.0.1:8787
export ANTHROPIC_API_KEY=sk-geek-...
claude
```

`ANTHROPIC_AUTH_TOKEN` (gửi dưới dạng `Authorization: Bearer`) cũng dùng được; GeekCubo chấp nhận cả hai header.

```python
# google-genai SDK trỏ vào GeekCubo
from google import genai
from google.genai.types import HttpOptions
client = genai.Client(api_key="sk-geek-...",
                      http_options=HttpOptions(base_url="http://127.0.0.1:8787"))
client.models.generate_content(model="auto", contents="Hello!")
```

Request được chuyển đổi ngay ở biên vào cùng một pipeline nội bộ, nên `model="auto"`, cache prompt liên-provider (dùng chung giữa các giao thức), các chiến lược định tuyến và dashboard analytics đều hoạt động y hệt nhau. Hướng dẫn: [integrations/claude-code.md](./integrations/claude-code.md), [integrations/gemini-sdk.md](./integrations/gemini-sdk.md).

## Danh mục mô hình

Danh mục tích hợp (vài trăm mô hình chat của các nhà cung cấp được hỗ trợ) được nạp khi khởi động từ bản sao [cơ sở dữ liệu giá do cộng đồng duy trì](https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json) đi kèm LiteLLM — không có danh sách mô hình cần duy trì thủ công. Mỗi mục gồm:

- `id` (ví dụ: `gpt-4o`, `claude-3-5-sonnet-latest`)
- `provider` (ánh xạ tới các khoá đã cấu hình của bạn)
- Cờ năng lực: `supports_tools`, `supports_vision`, `supports_json_mode`, `supports_json_schema`
- Chi phí mỗi token đầu vào/đầu ra (chạy widget tiết kiệm + `model="auto"`)

`GET /v1/models` trả về `auto`, các hồ sơ định tuyến đang bật và toàn bộ danh mục theo định dạng OpenAI (định dạng Anthropic khi có header `anthropic-version`).

Với mô hình của nhà cung cấp tùy chỉnh, Tools, Vision, JSON mode, JSON Schema, ngữ cảnh và giá tham chiếu được tự động xác định theo từng trường từ LiteLLM, Models.dev và Portkey khi **Fetch → Select → Add Selected Models**, kèm nguồn của từng trường. Một giá trị chỉ được đặt là hỗ trợ/không hỗ trợ khi khớp đáng tin cậy và có giá trị rõ ràng; nếu không sẽ giữ là Không rõ, và giá không rõ không chặn khả năng. Mô hình mơ hồ không mượn giá trị nào cho đến khi bạn chọn khóa danh mục trong danh sách có tìm kiếm. Ghi đè của quản trị viên (kể cả "Không rõ") được giữ khi làm mới; "Dùng danh mục" sẽ gỡ bỏ chúng. Auto, Chat và hồ sơ dùng cùng các khả năng đã lưu. JSON mode (json_object) và JSON Schema / đầu ra có cấu trúc (json_schema) là hai năng lực độc lập được xác định riêng; bằng chứng đầu ra có cấu trúc trong danh mục chỉ tính cho JSON Schema, không bao giờ tính cho JSON mode.

## Triển khai ở nơi khác

GeekCubo là một container Docker duy nhất. Khi không dùng Compose, hãy build image từ bản checkout và giữ dữ liệu trên một volume có tên:

```bash
docker build -t geekcubo .
docker run -d --name geekcubo -p 127.0.0.1:8787:8000 \
  -v geekcubo-data:/data \
  -e DATABASE_URL=sqlite+aiosqlite:////data/geekcubo.db \
  geekcubo
```

Các bản phát hành có tag được thiết lập để đăng image đa kiến trúc lên `ghcr.io/geekcubo/geekcubo-ai-router` (`.github/workflows/release.yml`); dùng tên đó sau khi có bản phát hành. VPS và reverse proxy: [DEPLOYMENT.md](./DEPLOYMENT.md).

## Có gì trong hộp

- `POST /v1/chat/completions` — proxy + streaming + `model="auto"` + cache prompt liên-provider
- `POST /v1/messages` — **ngõ vào Anthropic Messages API** (Claude Code / các Anthropic SDK kết nối trực tiếp; `+ /count_tokens`)
- `POST /v1beta/models/{model}:generateContent` — **ngõ vào Gemini API** (google-genai SDK kết nối trực tiếp; `+ :streamGenerateContent`, `GET /v1beta/models`)
- `GET  /v1/models` — `auto`, hồ sơ định tuyến và danh mục mô hình (tích hợp từ `litellm.model_cost`, cùng mô hình tùy chỉnh và cục bộ)
- `GET/PUT/DELETE /v1/providers/{provider}` — đặt / liệt kê / thu hồi khoá provider được mã hoá
- `GET/PUT /v1/routing` — chiến lược (`balanced` / `cheapest` / `quality` / `adaptive` / `adaptive_gated`; cũ `fastest`) và chính sách; `/v1/routing-profiles` — hồ sơ Auto có tên
- `GET  /v1/analytics/{recent,routing,spend,latency,savings,baseline-comparison}` — analytics local, không có telemetry rời khỏi hộp
- `GET/POST/DELETE /v1/keys/...` — liệt kê / xoay vòng / thu hồi khoá API
- `/api/local-connect/*` — **Kết nối AI cục bộ**: mã đăng ký, phê duyệt/thu hồi/xoay vòng máy, bật/tắt mô hình, tạo tệp dịch vụ và WebSocket của tác nhân gửi ra tại `/api/local-connect/agent` (id định tuyến `local/<machine>/<model>`; suy luận cục bộ chỉ văn bản)
- `POST /api/chat/attachments` — tải lên/trích xuất/xóa tệp đính kèm của chat; `GET /api/chat/attachments/limits` báo các giới hạn do máy chủ áp đặt để UI tuân theo
- Dashboard single-page tại `/`
- Tab **Chat** tích hợp trong bảng điều khiển — trò chuyện với các mô hình đã triển khai ngay trên trình duyệt; request được định tuyến, cache và tính chi phí đúng như traffic SDK (lịch sử chỉ lưu trong cơ sở dữ liệu cục bộ, thời gian lưu giữ tuỳ chỉnh được; việc cắt ngữ cảnh được báo mỗi lượt, và tìm kiếm web tùy chọn (SearXNG, Brave hoặc Tavily) thêm trích dẫn)
- SQLite mặc định; Postgres tuỳ chọn qua `DATABASE_URL`; Redis tuỳ chọn
- Chạy dưới dạng **một tiến trình máy chủ**. `REDIS_URL` chuyển cache prompt sang Redis nhưng không chia sẻ Local AI Connect, trạng thái hội thoại của Auto hay dữ liệu Adaptive giữa các tiến trình; không hỗ trợ nhiều worker.

### Widget tiết kiệm

`GET /v1/analytics/savings?baseline=gpt-4o&days=7` cho biết lưu lượng của bạn sẽ tốn bao nhiêu với mô hình tham chiếu so với chi phí thực tế (theo giá niêm yết của mô hình tham chiếu). Yêu cầu có giá không rõ không được tính là tiết kiệm.

## ❤️ Ủng hộ GeekCubo

GeekCubo miễn phí, mã nguồn mở và được phát triển độc lập. Bạn có thể ủng hộ việc phát triển bằng cách tham khảo các dịch vụ bổ trợ cho hệ thống AI của mình.

- [**Nhà cung cấp API AI**](https://geekcubo.com/providers/) — Khám phá các nhà cung cấp mô hình AI tương thích.
- [**VPS và lưu trữ đám mây**](https://geekcubo.com/hosting/) — Tìm hiểu các lựa chọn lưu trữ cho triển khai tự quản.
- [**VPN và quyền riêng tư**](https://geekcubo.com/vpn/) — Tìm hiểu các công cụ tùy chọn về quyền riêng tư và mạng an toàn.

**Công bố liên kết tiếp thị:** một số liên kết có thể mang lại hoa hồng cho chúng tôi mà bạn không mất thêm chi phí. Việc sử dụng là tùy chọn và không ảnh hưởng đến định tuyến mô hình hay khả năng tương thích nhà cung cấp của GeekCubo.

## Giấy phép

MIT. Xem [LICENSE](./LICENSE).

GeekCubo được phát triển từ OrcaRouter Lite. Giấy phép MIT gốc và thông báo bản quyền của nó ("Copyright (c) 2026 OrcaRouter contributors") được giữ nguyên trong [LICENSE](./LICENSE) và phải được giữ trong mọi bản sao hoặc phần đáng kể của phần mềm.

Tài nguyên của bên thứ ba giữ giấy phép riêng: đường nét phông chữ dùng trong logo (Inter, SIL Open Font License 1.1) được mô tả trong [design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).

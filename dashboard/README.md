# Dashboard (Next.js, yarn)

Giao diện demo của SME CI Agent. Chỉ đọc dữ liệu theo `docs/schema/events.json` (hợp đồng backend ↔ dashboard) và `docs/schema/payloads.md`. Yêu cầu: `docs/briefs/frontend.md` (FR-01..12, NFR-1..7), storyboard: `docs/demo-storyboard.md`.

Stack: Next.js 16 + React 19, Tailwind CSS v4 (token màu trong `app/globals.css`), lucide-react, radix-ui (Select, Tooltip theo mẫu shadcn trong `components/ui/`, dùng token của dashboard), Recharts (chỉ màn Tổng quan KPI), vitest + Testing Library, Playwright (chụp màn hình).

## Quyết định đã chốt (vai D, 2026-10-11)

Trả lời các câu hỏi mở ở mục 11 của `docs/briefs/frontend.md` và một thay đổi tiêu chí:

- **Ngôn ngữ hiển thị:** tiếng Việt. Mọi chuỗi ở `lib/strings.ts`, thêm tiếng Nhật/Anh bằng một object cùng hình dạng.
- **Thư viện UI:** Tailwind CSS v4 + `radix-ui` (component kiểu shadcn tự viết trên token của dashboard, không chạy `shadcn init`).
- **Biểu đồ:** Recharts.
- **FR-05, câu hỏi "chưa đủ dữ liệu sau thay đổi":** thay ô trả lời bắt buộc bằng một nút **Đo lại khi có thêm dữ liệu** (ghi chú tuỳ chọn); câu tiếng Anh của backend nằm trong "Chi tiết kỹ thuật". Lý do: backend không đọc nội dung câu trả lời này, chỉ đo lại (H-34). Ca kiểm thử của vai Q cho FR-05 cần theo tiêu chí mới này.

## Lưu ý khi demo

- **Bật chế độ Trình chiếu (phím F) trước khi lên sân khấu.** Chữ thường là 16px; NFR-1 (chữ thân ≥ 18px, tiêu đề ≥ 28px trên màn chiếu) chỉ đạt ở chế độ Trình chiếu (125%: chữ 20px, tiêu đề ~30px).
- Nhánh "chưa đủ dữ liệu sau thay đổi" (H-34) lặp mãi với dữ liệu sandbox: khi run dừng chờ người, chọn **Kết thúc run**.

## Lệnh

```bash
cd dashboard
yarn install      # Node >= 22.13; nếu yarn báo engine thì thêm --ignore-engines
yarn dev          # http://localhost:3000
yarn lint
yarn test         # vitest, chạy một lần
yarn build
```

## Các màn

| URL | Màn | Dữ liệu |
|---|---|---|
| `/` hoặc `/?source=fixture&file=<tên>` | Phiên chạy, **phát lại** một bản ghi (mặc định `run-happy`) | `fixtures/examples/*.json` (bản sao của `docs/schema/examples/`) |
| `/?source=live` | Phiên chạy, **trực tiếp** với backend; `&run=<id>` để mở lại run sau khi tải lại trang | API + SSE |
| `/?source=sse&run=<id>` | Chỉ theo dõi một run | SSE |
| `/runs` | Lịch sử run: run đang chờ mở live để làm tiếp, run đã xong mở chế độ theo dõi | `GET /runs` |
| `/overview` | Tổng quan KPI: biểu đồ, mức nền, giới hạn trên, vùng bất thường | `GET /metrics` (tên KPI chính) + `GET /kpi/series` |
| `/kaizen` | Phiếu kaizen + 3 chỉ số | `GET /metrics`; phiếu từ `GET /runs/{id}/export` của các run hoàn tất |
| `/audit` | Nhật ký và phiên bản SOP | `GET /audit`, `GET /sop/{id}/versions` (SOP lấy từ nhật ký) |

Bốn màn này cần backend (`bash scripts/demo.sh`); backend tắt thì hiện lỗi kèm nút Thử lại. Hàm gọi API ở `lib/readApi.ts`. Chỉ số `available: false` hiện "Chưa có số liệu", không bao giờ hiện số giả.

Phím **F** (hoặc nút "Trình chiếu"): ẩn sidebar, phóng chữ 125% cho máy chiếu, ẩn phần kỹ thuật (run id, nhật ký sự kiện, "Chi tiết kỹ thuật"). **Ctrl/⌘ B**: thu gọn sidebar. Nút mặt trăng: giao diện tối. Dưới 1536px (laptop, hoặc trình chiếu trên laptop) Phiên chạy dùng một cột, ba thẻ bên phải gom thành dải ngữ cảnh mở được.

## Phát lại (dự phòng sân khấu, FR-07)

Mỗi bản ghi có `steps` (từng lần gọi API kèm trạng thái run) và `events`. `lib/replay.ts` cắt luồng event theo từng bước, nên phát lại đi qua đúng các màn như khi chạy thật và dừng chờ ở mỗi câu hỏi / duyệt / lỗi. Thanh công cụ: chọn bản ghi, tạm dừng (phím **Space**), tốc độ 1×/2×, **Tự chạy** (tự qua các bước chờ, dùng khi quay video), phát lại từ đầu. Nút trên màn chỉ đẩy bản ghi đi tiếp; người duyệt được điền sẵn theo bản ghi; dải xanh phía trên cho biết bản ghi sẽ làm gì ở bước sau.

Sau khi chạy lại `uv run python scripts/export_fixtures.py`, chép `docs/schema/examples/*.json` sang `dashboard/fixtures/examples/` (test `bundled recordings` báo nếu hai nơi lệch nhau).

## Chạy với backend thật

```bash
bash scripts/demo.sh            # ở gốc repo: db + backend :8000 + dashboard :3000, LLM giả
# mở http://localhost:3000/?source=live, bấm "Bắt đầu phân tích"
```

`NEXT_PUBLIC_API_URL` mặc định `http://localhost:8000`. Mọi quyết định chỉ gửi khi người bấm; nút khoá cho tới khi chọn người duyệt trong danh sách `/config/approvers`. Lỗi 409 tự tải lại trạng thái run; lỗi khác hiện nguyên văn `detail` của backend.

## Cấu trúc

- `lib/strings.ts`: mọi chuỗi hiển thị (tiếng Việt). Thêm tiếng Nhật/Anh bằng một object cùng hình dạng.
- `lib/format.ts`: định dạng %, ngày giờ, nhãn; không bao giờ trả về `null`/`undefined`/`NaN`.
- `lib/runModel.ts`: suy ra màn đang hiện (phase), bước của vòng lặp, giả thuyết, tool… từ event + trạng thái run. Không có React, test bằng fixture thật.
- `lib/replay.ts`, `lib/recordings.ts`: phát lại bản ghi.
- `components/run/`: các màn của Phiên chạy (`RunScreen` ghép tất cả; `ProposalStage`, `Stages`, `DecisionPanel`, `SopDiff`, `MeasurementCard`, `KaizenCard`, `LoopStepper`, `SidePanels`).
- `components/LiveRun.tsx`, `components/ReplayRun.tsx`: bộ điều khiển trực tiếp / phát lại, dùng chung `RunScreen`.
- `components/shell/AppShell.tsx`: sidebar, topbar, trình chiếu, giao diện tối.
- `lib/api.ts`, `lib/sources.ts`, `lib/useRunEvents.ts`, `lib/validate.ts`: dùng chung với backend (đổi thì ghi trong PR).

## Chụp màn hình (DoD: ảnh 1920×1080 cho mỗi trạng thái)

```bash
yarn build && yarn start -p 3100
BASE=http://localhost:3100 yarn shots              # ghi vào dashboard/screenshots/ (không commit)
THEME=dark BASE=http://localhost:3100 yarn shots
```

Cần Chromium cho Playwright (`npx playwright install chromium` nếu máy chưa có).

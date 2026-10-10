# Dashboard (Next.js, yarn)

Giao diện demo của SME CI Agent. Chỉ đọc dữ liệu theo `docs/schema/events.json` (hợp đồng backend ↔ dashboard) và `docs/schema/payloads.md`. Yêu cầu: `docs/briefs/frontend.md` (FR-01..12, NFR-1..7), storyboard: `docs/demo-storyboard.md`.

Stack: Next.js 16 + React 19, Tailwind CSS v4 (token màu trong `app/globals.css`), lucide-react, Recharts (chỉ màn Tổng quan KPI), vitest + Testing Library, Playwright (chụp màn hình).

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
| `/runs` | Lịch sử run (bấm để phát lại) | bản ghi mẫu, chờ `GET /runs` |
| `/overview` | Tổng quan KPI: biểu đồ, mức nền, giới hạn trên, vùng bất thường | mẫu, chờ `GET /kpi/series` |
| `/kaizen` | Phiếu kaizen + 3 chỉ số | phiếu từ bản ghi; chỉ số mẫu, chờ `GET /metrics` (T-042) |
| `/audit` | Nhật ký và phiên bản SOP | từ bản ghi, chờ `GET /audit`, `GET /sop/{id}/versions` |

Các màn có dữ liệu mẫu đều hiện nhãn "Dữ liệu mẫu…". Khi backend có API (R10a), thay các hàm trong `lib/mockData.ts` bằng lời gọi API, giữ nguyên hình dạng.

Phím **F** (hoặc nút "Trình chiếu"): ẩn sidebar, phóng chữ cho máy chiếu. Nút mặt trăng: giao diện tối.

## Phát lại (dự phòng sân khấu, FR-07)

Mỗi bản ghi có `steps` (từng lần gọi API kèm trạng thái run) và `events`. `lib/replay.ts` cắt luồng event theo từng bước, nên phát lại đi qua đúng các màn như khi chạy thật và dừng chờ ở mỗi câu hỏi / duyệt / lỗi. Thanh công cụ: chọn bản ghi, tạm dừng, tốc độ 1×/2×, **Auto** (tự qua các bước chờ, dùng khi quay video), phát lại từ đầu. Nút trên màn chỉ đẩy bản ghi đi tiếp; dải xanh phía trên cho biết bản ghi sẽ làm gì ở bước sau.

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

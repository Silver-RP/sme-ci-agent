# Dashboard (Next.js, yarn)

Chỉ đọc dữ liệu theo `docs/schema/events.json` (hợp đồng backend ↔ dashboard). Theo ADR-005: bảng anomaly + timeline trace, ít biểu đồ.

## Lệnh

```bash
cd dashboard
yarn install      # .yarnrc đặt ignore-engines vì Node 22.12 bị một vài gói cảnh báo
yarn dev          # http://localhost:3000
yarn lint
yarn test         # vitest, chạy một lần
yarn build
```

## Chạy với fixture (không cần backend)

```bash
cd dashboard && yarn dev
# mở http://localhost:3000 (mặc định ?source=fixture): phát lại fixtures/scenario1.json
```

## Chạy với backend thật

```bash
# terminal 1 (gốc repo): Postgres rồi API (cần cấu hình model và khoá API theo hướng dẫn của repo)
docker compose up -d db
uv run uvicorn backend.api.app:create_app --factory --port 8000
# terminal 2
cd dashboard
NEXT_PUBLIC_API_URL=http://localhost:8000 yarn dev
# mở http://localhost:3000/?source=live
```

`NEXT_PUBLIC_API_URL` mặc định `http://localhost:8000`. Trang `?source=live`:

1. Nhập `change_time` (ISO) và bấm "Start run" (`POST /runs`).
2. Khi agent hỏi (Ask), ô trả lời hiện ra; gửi bằng `POST /runs/{id}/answer`.
3. Khi chờ duyệt đề xuất hoặc rollback, nút Approve/Reject hiện ra; chỉ gửi `POST /runs/{id}/approval` khi người bấm (kèm `decided_by`).
4. Lỗi 404/409/422 hiển thị nguyên văn `detail` của backend.

Xem một run có sẵn: `?source=sse&run=<run_id>`. Nguồn SSE và fixture dùng chung một giao diện (`lib/sources.ts`).

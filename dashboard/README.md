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

## Trạng thái (dev-01)

Trang chính hiển thị fixture `fixtures/scenario1.json` (một run scenario 1 từ `anomaly_detected` đến `run_finished`). Nguồn SSE và API thật sẽ thêm ở dev-02/dev-03; `NEXT_PUBLIC_API_URL` (mặc định `http://localhost:8000`) dùng từ đó.

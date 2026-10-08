# SME CI Agent

Agentic AI giúp SME cải tiến vận hành liên tục: phát hiện bất thường, điều tra nguyên nhân gốc, đề xuất cải tiến, cập nhật SOP sau khi được duyệt, đo KPI trước/sau và học để ngăn lỗi tái diễn.

Hackathon: Vietnam Japan AI Hackathon 2026. Pitch Day 24/10 (Tokyo), Demo Day 07/11.

## Chạy nhanh

```bash
cp .env.example .env          # điền ANTHROPIC_API_KEY, không commit
docker compose up -d db       # Postgres local
uv sync                       # cài thư viện Python
uv run pytest                 # chạy test
```

## Dữ liệu sandbox và báo cáo kiểm tra

```bash
uv run python scripts/gen_data.py --seed 42     # sinh CSV 6 tháng vào data/generated/
uv run python scripts/data_report.py --seed 42  # khoảng ngày, số dòng, anomaly Detect so với ground truth
```

## Chạy demo

Cần Docker (Postgres), `uv`, Node ≥ 22.13 và `yarn` (chạy `yarn install` một lần trong `dashboard/`).

**Với LLM giả (không cần key)**: dữ liệu synthetic seed 42, Detect chạy thật, LLM được kịch bản hoá.

```bash
scripts/demo.sh                 # bật db, migration, backend :8000, dashboard :3000; Ctrl+C để dừng
# mở http://localhost:3000/?source=live, bấm Start run (để trống change time), trả lời câu hỏi,
# chọn tên người duyệt trong danh sách rồi Approve
uv run python scripts/run_scenario.py   # hoặc chạy một vòng từ dòng lệnh, in tóm tắt event, thoát 0 nếu xong
```

Backend chọn LLM giả bằng biến môi trường `SME_LLM=scripted` (demo.sh đặt sẵn). Cổng đổi qua `API_PORT`, `DASH_PORT`, `DB_PORT`.

**Với LLM thật**: tự điền `ANTHROPIC_API_KEY` và `MODEL_REASONING` trong `.env` (agent/CI không đọc file này), rồi:

```bash
SME_LLM=real scripts/demo.sh                    # dashboard + backend dùng AnthropicLLM
uv run python scripts/run_scenario.py --llm real
```

Lưu ý: ở dữ liệu seed 42 anomaly kéo dài đến hết dữ liệu nên sau khi duyệt, KPI không phục hồi; agent đề xuất rollback và người duyệt quyết định (script chạy thử từ chối rollback để vòng kết thúc).

## Đọc theo thứ tự

- CLAUDE.md: mục tiêu, quy ước, giới hạn của agent
- docs/PLAN.md: mục tiêu và kế hoạch G3 → G5
- TASKS.md: danh sách việc, ai làm gì, hạn nào
- docs/decisions.md: các quyết định kiến trúc đã chốt
- docs/schema/events.json: hợp đồng giữa backend và dashboard

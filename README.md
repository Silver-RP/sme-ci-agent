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

## Đọc theo thứ tự

- CLAUDE.md: mục tiêu, quy ước, giới hạn của agent
- docs/PLAN.md: mục tiêu và kế hoạch G3 → G5
- TASKS.md: danh sách việc, ai làm gì, hạn nào
- docs/decisions.md: các quyết định kiến trúc đã chốt
- docs/schema/events.json: hợp đồng giữa backend và dashboard

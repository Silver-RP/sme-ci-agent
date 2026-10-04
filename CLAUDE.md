# SME CI Agent: hướng dẫn cho Claude và cả team

## Mục tiêu

MVP = scenario 1 chạy đủ vòng Detect → Learn từ dashboard, trên dữ liệu sandbox (synthetic). Ngôn ngữ: code và tên biến bằng tiếng Anh; tài liệu bằng tiếng Việt.

## Mốc cứng

Proposal nộp hạn 5/10 21:59 JST · tag v0.1-e2e 13/10 · freeze code 20/10 (v0.2-freeze) · Pitch Day 24/10 · Demo Day 07/11.

## Kiến trúc đã chốt (xem docs/decisions.md)

- MỘT agent trung tâm bằng LangGraph (StateGraph + interrupt + checkpointer Postgres). KHÔNG làm multi-agent, KHÔNG làm Agent Manager dùng LLM trong MVP.
- Vòng lặp: Observe → Detect → Investigate → Ask → Improve → Act → Measure → Learn.
- Detect là code thống kê, không gọi LLM. Investigate/Improve là node trong cùng graph. Act/Measure/Learn là tool.
- Điều phối bằng cạnh điều kiện (rule): chuyển bước, hỏi người (interrupt), rollback khi KPI không đạt ngưỡng. Quyết định rollback do ngưỡng KPI và người xác nhận, không do LLM.
- Hai lớp: Reasoning core (dùng chung mọi ngành) + Domain config (data/context_profile.yaml).
- LLM: Sonnet cho suy luận, Haiku cho việc rẻ. Tên model đặt trong .env, không hard-code.

## Giới hạn quyền của agent (bắt buộc giữ trong code)

- Chỉ có quyền ĐỌC log và dữ liệu nguồn; không sửa/xóa.
- Mọi thay đổi SOP/rule, mọi hành động ảnh hưởng sản xuất và mọi rollback đều cần người duyệt.
- Mọi thay đổi SOP có phiên bản (sop_versions); mọi hành động ghi vào audit_log.
- Thiếu bằng chứng thì HỎI người (interrupt), không tự kết luận.
- Chỉ dùng synthetic data. Không dùng dữ liệu thật hay dữ liệu cá nhân.

## Quy tắc code để sau này nâng cấp không đau

- agent/state.py dùng tên trung tính: anomaly, hypotheses, evidence, proposal, domain. Không đặt tên theo "defect".
- KPI, nhóm giả thuyết (Ishikawa), SOP nằm trong data/context_profile.yaml, không hard-code trong prompt hay node.
- Tool nhận tham số (loại KPI, khoảng thời gian), không ngầm hiểu defect.
- Mỗi event theo docs/schema/events.json có agent và domain.

## Hợp đồng

docs/schema/events.json là hợp đồng backend ↔ dashboard. Đổi file này phải qua PR riêng và báo trong sync.

## Quy ước làm việc

- Nhánh: feat/<mốc>-<tên> (ví dụ feat/m1-detect). Commit: init / chore / feat / fix.
- Mỗi PR có 1 người review, review trong 12 giờ.
- Không commit API key. Tag: v0.1-e2e (13/10), v0.2-freeze (20/10).
- Sync 15 phút mỗi ngày; review mốc mỗi thứ Bảy.

## Lệnh thường dùng

```bash
docker compose up -d db      # Postgres
uv sync                      # cài thư viện
uv run pytest                # test
uv run ruff check .          # lint
```

## Khi được giao một task

Đọc TASKS.md (mục task, DoD), docs/PLAN.md, rồi làm đúng phạm vi task. Không mở rộng sang multi-agent, scenario 2–3 hay biểu đồ phức tạp. Xong thì tick checkbox trong TASKS.md trong cùng PR.

# SME CI Agent: hướng dẫn cho Claude và cả team

## Mục tiêu

MVP = scenario 1 chạy đủ vòng Detect → Learn từ dashboard, trên dữ liệu sandbox (synthetic). Ngôn ngữ: code và tên biến bằng tiếng Anh; tài liệu bằng tiếng Việt.

## Mốc (tham khảo)

Proposal nộp hạn 5/10 21:59 JST · tag v0.1-e2e 13/10 · freeze code 20/10 (v0.2-freeze) · Pitch Day 24/10 · Demo Day 07/11.

Các ngày ở đây và hạn (Due) trong TASKS.md, docs/PLAN.md chỉ để tham khảo; leader tự điều chỉnh. Agent không tự hoãn, cắt việc hay từ chối task vì hạn.

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

## Công cụ (Claude Code)

- Bắt đầu mỗi nhiệm vụ: ghi một dòng ước tính thời gian (phút người phải chờ; thêm USD nếu chạy auto-dev, LLM thật hay tìm web), tách riêng phần chờ bên ngoài (check GitHub, pytest + Postgres, demo). Vượt quá 2 lần thì báo giữa chừng kèm ước tính mới.
- ADR trong docs/decisions.md và TASKS.md là cố định: không đề xuất lại multi-agent hay Agent Manager.
- Brainstorm/lập kế hoạch chỉ trong phạm vi một task; ghi kế hoạch vào PR, không tạo file kế hoạch mới ở gốc repo.
- Dùng TDD cho backend/detect, backend/sandbox, backend/tools.
- Chỉ dùng subagent cho T-020 và T-024; các task khác làm trực tiếp để tiết kiệm token. Ngoại lệ: developer/reviewer khi chạy /run-milestone (auto-dev).
- Không đọc hay in nội dung .env.

## Lệnh thường dùng

```bash
docker compose up -d db      # Postgres
uv sync                      # cài thư viện
uv run pytest                # test
uv run ruff check .          # lint
```

## Khi được giao một task

Đọc TASKS.md (mục task, DoD), docs/PLAN.md, rồi làm đúng phạm vi task. Không mở rộng sang multi-agent, scenario 2–3 hay biểu đồ phức tạp. Xong thì tick checkbox trong TASKS.md trong cùng PR.

## Auto-dev (thử nghiệm, chế độ A)

- Plan lớn (plugin): docs/autodev/ (thiết kế, ROADMAP, PROGRESS, HANDOFF). Plan nhỏ (dự án): plan/Mx.md (dev-xx kèm mã T-0xx), nhật ký plan/PROGRESS.md. TASKS.md vẫn là nguồn chung cho team. Ưu tiên auto-dev nhưng không làm sai mục tiêu dự án.
- Chạy một mốc: `/run-milestone M1`. Agent: .claude/agents/developer.md (code) và reviewer.md (chỉ đọc).
- Kiểm tra cứng: `uv run python .autodev/verify.py` (ruff → pytest, so với .autodev/baseline.json). Máy nào phải đổi cổng DB: đặt `DB_PORT` khi chạy docker compose và chép `.autodev/env.local.example.json` thành `.autodev/env.local.json` (không commit).
- developer không sửa tiêu chí chấp nhận hay phạm vi mốc; chỉ ghi vào "Đề xuất chờ duyệt" trong plan/PROGRESS.md. Worker không sửa file plugin (.claude/, .autodev/*.py, docs/autodev/).
- Supervisor (`/supervise Mx`) giao mốc cho worker headless, duyệt và merge (thiết kế mục 6.15).
- Không đọc hay in nội dung .env.

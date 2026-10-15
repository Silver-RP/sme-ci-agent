# SME CI Agent: hướng dẫn cho Claude và cả team

## Mục tiêu

MVP = scenario 1 chạy đủ vòng Detect → Learn từ dashboard, trên dữ liệu sandbox (synthetic). Ngôn ngữ: code và tên biến bằng tiếng Anh; tài liệu bằng tiếng Việt.

**Từ 2026-10-15 (ADR-012):** ưu tiên 100% phát triển auto-dev (leader chỉ đưa mục tiêu + kết quả mong muốn, auto-dev tự phân tích, hỏi, lập kế hoạch, điều phối các vai). Dự án này là dự án thử cho auto-dev; mốc R chỉ chạy khi kiểm chứng một khả năng của plugin.

## Mốc thời gian

Không có mốc ngày (leader gỡ 2026-10-14, ADR-011). Mọi ngày, hạn (Due), lịch pitch, freeze, Demo Day từng ghi trong TASKS.md, docs/PLAN.md, ROADMAP, brief, plan/Rx.md **đều vô hiệu**; leader sẽ đặt lại khi cần. Việc xếp theo thứ tự ở `docs/autodev/ROADMAP.md` mục "Kế hoạch lại 14/10". Agent không tự đặt hạn, không hoãn, cắt việc hay từ chối task vì thời gian. Tag `v0.1-e2e` đã gắn; `v0.2-freeze` gắn khi qua cổng v0.2 (`docs/eval/criteria.md` mục 3).

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
- Mỗi PR có 1 lượt review (reviewer/supervisor của auto-dev hoặc leader).
- Không commit API key. Tag: v0.1-e2e (đã gắn), v0.2-freeze (khi qua cổng v0.2).

## Công cụ (Claude Code)

- Bắt đầu mỗi nhiệm vụ: ghi một dòng ước tính thời gian (phút người phải chờ; thêm USD nếu chạy auto-dev, LLM thật hay tìm web), tách riêng phần chờ bên ngoài (check GitHub, pytest + Postgres, demo). Vượt quá 2 lần thì báo giữa chừng kèm ước tính mới.
- ADR trong docs/decisions.md và TASKS.md là cố định: không đề xuất lại multi-agent hay Agent Manager.
- Brainstorm/lập kế hoạch chỉ trong phạm vi một task; ghi kế hoạch vào PR, không tạo file kế hoạch mới ở gốc repo.
- Dùng TDD cho backend/detect, backend/sandbox, backend/tools.
- Chỉ dùng subagent cho T-020 và T-024; các task khác làm trực tiếp để tiết kiệm token. Ngoại lệ: developer/reviewer khi chạy /run-milestone (auto-dev); một reviewer cuối nhánh khi làm theo skill superpowers (`executing-plans`, `requesting-code-review`).
- Superpowers (plugin, bật trong `.claude/settings.json`): việc nào có skill phù hợp (brainstorm, lập kế hoạch, TDD, gỡ lỗi, review, kiểm trước khi báo xong) thì dùng skill đó và nói đang dùng skill nào. Ngoại lệ: phiên headless (`claude -p`: worker, supervisor, audit của runner) không brainstorm và không hỏi người; plan mốc đã là spec.
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

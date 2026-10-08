# Trạng thái dự án (đọc trước plan mốc)

Developer, reviewer, supervisor và auditor đọc file này trước `plan/Rx.md`. Bản máy đọc: `docs/autodev/state.json` (cùng nội dung). Cập nhật sau mỗi audit và mỗi mốc; giữ dưới 150 dòng (`.autodev/tests/test_project_state.py`).

Cập nhật: 2026-10-09 · Nguồn: bản đầu P5; audit 2026-10-09 cập nhật.

## Mốc

| Loại | Mốc | Trạng thái | Ghi chú |
|---|---|---|---|
| Dự án | M0–M2 | ✅ 19/19 task | |
| Dự án | M3 | 🔄 1/2 | T-030 chờ người dùng chạy LLM thật |
| Dự án | M4 | 🔄 1/6 | T-040 xong; T-041..T-045 mở; tag v0.1-e2e 13/10 |
| Chạy | R4–R8 | ✅ merge #19, #21, #27, #31, #37 | 2,29 / 3,01 / 1,81 / 2,58 / 6,40 USD |
| Plugin | P1–P3 | ✅ | |
| Plugin | P4 | 🔄 | chưa gặp hạn mức thật |
| Plugin | P5 | 🔄 | audit + trạng thái (file này) |
| Plugin | P6–P8 | ⏳ | kế hoạch dài hạn; Telegram + API trạng thái; đóng gói |

## Mục tiêu và 3 điều cần kiểm chứng

MVP: scenario 1 chạy đủ vòng Detect → Learn từ dashboard trên dữ liệu sandbox (docs/PLAN.md mục 1).

| # | Điều cần kiểm chứng | % đạt | Bằng chứng | Còn thiếu |
|---|---|---|---|---|
| 1 | Tìm đúng nguyên nhân gốc, biết hỏi người khi thiếu bằng chứng | 60 | test_investigate, test_ask, data_report (LLM giả) | T-030 LLM thật; correlate thiếu tín hiệu people, ambient_temperature |
| 2 | Duyệt → KPI cải thiện; không thì rollback, điều tra lại | 70 | test_measure_r8, test_act, test_return_edges_r8 | e2e uvicorn nhánh rollback; `fix_addresses_cause` khớp từ khoá |
| 3 | 3 chỉ số trước/sau trên 6 tháng mô phỏng | 15 | data_report (phát hiện, báo động giả) | T-042, T-043 |

## Kiến trúc hiện nay

- Một agent LangGraph (`backend/agent/graph.py`): Detect thống kê → Investigate → Ask (interrupt) → Improve → duyệt (interrupt) → Act → Measure → Learn; cạnh quay lại (T-040).
- Checkpointer **InMemorySaver**; run và event chỉ ở bộ nhớ của `backend/api/app.py` (bảng `runs`/`events` trống). Mất khi backend tắt.
- Postgres: `audit_log`, `sop_versions`, `learning_store` (alembic 0001).
- Sandbox: simulator + injector + post_change (dữ liệu sau thay đổi riêng cho từng run).
- API FastAPI + SSE; dashboard Next.js một trang. LLM giả mặc định; `SME_LLM=real` dùng Anthropic (model trong `.env`).

## Quy tắc → test bảo vệ

| Quy tắc (CLAUDE.md) | Test bảo vệ |
|---|---|
| Rollback/áp dụng SOP cần người duyệt; LLM không duyệt | test_api::test_approval_by_agent_or_llm_is_rejected, test_tools_actions::test_apply_without_valid_approval_refused |
| Rollback do ngưỡng KPI, không do LLM | test_act::test_measure_node_uses_threshold_from_config_and_no_llm, test_measure_r8::test_llm_direction_and_kpi_do_not_change_the_verdict |
| Mọi hành động vào audit_log (append-only) | test_db::test_audit_log_append_only_api_and_db, test_tools_readonly::test_one_audit_row_per_call |
| SOP có phiên bản | test_db::test_sop_versions_increment_without_overwrite |
| Thiếu bằng chứng thì hỏi người | test_ask::test_low_confidence_pauses_at_ask, test_measure_r8::test_too_few_samples_is_not_enough_evidence_not_a_failure |
| Tool chỉ đọc dữ liệu nguồn | test_tools_readonly::test_tools_do_not_modify_source_tables, test_measure_r8::test_source_tables_are_not_modified_by_a_run |
| Tên trung tính | test_state::test_no_defect_names, test_tools_readonly::test_no_defect_naming_in_tools |
| KPI/giả thuyết/SOP trong YAML | test_domain_config::test_no_hardcoded_names_in_code |
| Event có agent và domain | test_db::test_event_rejects_bad_type_and_agent_and_shape, test_detect::test_domain_comes_from_config |
| Tên model không hard-code | **chưa có** (R9 `tests/test_invariants.py`) |
| Số lần hỏi/rollback/retry có giới hạn | test_ask::test_ask_is_bounded_then_awaits_human, test_act::test_max_rollbacks_halts; retry **chưa có** |

## Lỗ hổng mở

Chưa có audit theo mã H-xx. Việc mở từ R8 (audit 2026-10-09 sẽ đánh mã):
- `fix_addresses_cause` khớp từ khoá: câu phủ định vẫn tính là sửa đúng.
- `POST /runs/{id}/retry` không giới hạn số lần.
- e2e uvicorn nhánh rollback chưa có (R8-c2); `docs/schema/payloads.md` chưa có (R8-c1).
- Run/event và checkpointer chỉ ở bộ nhớ.

## Quyết định gần đây

- 2026-10-09: thứ tự sau R8: P5 → audit đầu → gói bàn giao UI → T-030 → P6 → R9 → R10 (người dùng duyệt).
- 2026-10-09: UI sản phẩm do bạn frontend làm; từ R9 auto-dev không sửa phần trình bày trong `dashboard/`.
- 2026-10-08: R8-c2 (e2e uvicorn rollback) chuyển sang R9.
- 2026-10-08: supervisor Opus effort medium, worker Sonnet; smoke bắt buộc trước merge.

## Tầm nhìn 3–5 mốc tới

P6 điền (đường găng, thứ tự cắt, pre-mortem). Tạm thời theo HANDOFF: R9 (invariants, R8-c2, checkpointer Postgres, API danh sách run) → R10 (T-041, T-042, T-044) → audit 2 → tag v0.1-e2e.

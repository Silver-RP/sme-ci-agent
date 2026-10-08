# Trạng thái dự án (đọc trước plan mốc)

Developer, reviewer, supervisor và auditor đọc file này trước `plan/Rx.md`. Bản máy đọc: `docs/autodev/state.json` (cùng nội dung). Cập nhật sau mỗi audit và mỗi mốc; giữ dưới 150 dòng (`.autodev/tests/test_project_state.py`).

Cập nhật: 2026-10-09 · Nguồn: audit `docs/audits/2026-10-09.md`.

## Mốc

| Loại | Mốc | Trạng thái | Ghi chú |
|---|---|---|---|
| Dự án | M0–M2 | ✅ 19/19 task | |
| Dự án | M3 | 🔄 1/2 | T-030 chờ người dùng chạy LLM thật |
| Dự án | M4 | 🔄 1/6 | T-040 xong; T-041..T-045 mở; tag v0.1-e2e 13/10 |
| Chạy | R4–R9 | ✅ merge #19, #21, #27, #31, #37, #44 | 2,29 / 3,01 / 1,81 / 2,58 / 6,40 USD / R9 chưa đo |
| Plugin | P1–P3 | ✅ | |
| Plugin | P4 | 🔄 | chưa gặp hạn mức thật |
| Plugin | P5 | 🔄 | audit + trạng thái (file này) |
| Plugin | P6–P8 | ⏳ | kế hoạch dài hạn; Telegram + API trạng thái; đóng gói |

## Mục tiêu và 3 điều cần kiểm chứng

MVP: scenario 1 chạy đủ vòng Detect → Learn từ dashboard trên dữ liệu sandbox (docs/PLAN.md mục 1).

| # | Điều cần kiểm chứng | % đạt | Bằng chứng | Còn thiếu |
|---|---|---|---|---|
| 1 | Tìm đúng nguyên nhân gốc, biết hỏi người khi thiếu bằng chứng | 25 | Detect khớp ground truth (test_data_report); luật hỏi theo ngưỡng (test_ask). LLM giả viết sẵn đáp án nên chưa chứng minh | H-12 eval + T-030 LLM thật; H-10; anomaly quá rõ (~10σ) |
| 2 | Duyệt → KPI cải thiện; không thì rollback, điều tra lại | 40 | Cơ chế đúng ở mức graph (test_measure_r8, test_act, test_return_edges_r8); uvicorn chỉ nhánh thuận (test_e2e) | H-06 (kết quả dựng sẵn theo từ khoá); e2e chuỗi sai → rollback → đúng → Learn; H-07..H-09 |
| 3 | 3 chỉ số trước/sau trên 6 tháng mô phỏng | 10 | `measure()` 1 máy, 7 ngày; MTTD/MTTR chỉ test nạp tay | H-11; T-042, T-043 |

Audit 2026-10-09 hạ % (trước: 60/70/15) vì chạy theo kịch bản viết sẵn không phải bằng chứng.

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

Từ `docs/audits/2026-10-09.md` (chi tiết, bằng chứng, test cần có để đóng). Đóng khi có test chứng minh.

R9 (PR #44, 2026-10-09) đã có test tái hiện xanh cho H-06, H-07, H-08, H-09, H-10, H-12, H-17, H-21, H-23 (tên test trong `.autodev/reports/R9.md`); audit 2 xác nhận rồi mới đánh dấu đóng và chỉnh % đạt.

| Mã | Mức | Tóm tắt |
|---|---|---|
| H-06 | cao | Measure đạt theo từ khoá ground truth; câu phủ định tính là sửa đúng |
| H-07 | cao | Audit quyết định của người mất khi bước sau lỗi |
| H-08 | cao | ValueError sau resume → 422, run kẹt |
| H-09 | cao | `wait_evidence` không thành pending answer ở API |
| H-10 | cao | SOP trong YAML (ép phun) lệch scenario (reflow) |
| H-11 | cao | Chỉ số 3 chưa có đường code |
| H-12 | cao | Không có eval nguyên nhân so với ground truth |
| H-13 | vừa | Sau retry SSE không mở lại, `event_id` trùng |
| H-14 | vừa | Hai run song song ghi đè SOP |
| H-15 | vừa | Run/event/checkpointer chỉ ở bộ nhớ |
| H-16 | vừa | Demo LLM giả: reject/revise/halt-investigate lỗi |
| H-17 | vừa | revise, halt-investigate, retry không giới hạn |
| H-18 | vừa | `has_tool_evidence` tính tool của cả run |
| H-19 | vừa | Halt → điều tra lại quên SOP đang hiệu lực |
| H-20 | vừa | Trả lời không kèm id câu hỏi |
| H-21 | thấp | Parser JSON lấy object đầu |
| H-22 | thấp | Giá trị miền hard-code ngoài YAML |
| H-23 | thấp | Không đặt temperature; chưa record/replay |
| H-24 | thấp | UI không phân biệt kết quả run (team frontend) |
| H-25 | thấp | Payload event chưa có tài liệu |
| H-26 | thấp | `demo.sh --check` chỉ kiểm khởi động |

## Quyết định gần đây

- 2026-10-09: R9 merge (PR #44): Measure theo hành động có cấu trúc, eval nguyên nhân (LLM giả), e2e uvicorn chuỗi rollback, 8 fixture. Supervisor chưa đưa eval vào smoke.
- 2026-10-09: **người dùng chọn hướng R9 theo audit**. R9 làm điều 1–2 thật: H-10 trước tiên, rồi H-06, eval, e2e rollback, H-07/08/09/17/21, temperature. R10 làm điều 3 và luồng demo. Hoãn đến sau v0.1-e2e: checkpointer Postgres, invariants, API danh sách run, khoá SOP.
- 2026-10-09: audit đầu: 21 lỗ hổng (7 cao), % đạt hạ còn 25/40/10. Đề xuất R9 làm điều 1–2 thật, R10 làm điều 3 (chờ người dùng duyệt ở P6).
- 2026-10-09: thứ tự sau R8: P5 → audit đầu → gói bàn giao UI → T-030 → P6 → R9 → R10 (người dùng duyệt).
- 2026-10-09: UI sản phẩm do bạn frontend làm; từ R9 auto-dev không sửa phần trình bày trong `dashboard/`.
- 2026-10-08: R8-c2 (e2e uvicorn rollback) chuyển sang R9.
- 2026-10-08: supervisor Opus effort medium, worker Sonnet; smoke bắt buộc trước merge.

## Tầm nhìn 3–5 mốc tới

P6 điền chi tiết (đường găng, thứ tự cắt, pre-mortem). Hướng đã duyệt:

| Mốc | Mục tiêu | Lỗ hổng / task |
|---|---|---|
| R9 | Điều 1–2 thành thật | H-10, H-06, H-12, H-07, H-08, H-09, H-17, H-21, H-23 |
| T-030 | Người dùng chạy LLM thật (sau H-10) | ghi lỗi vào `docs/decisions.md` |
| R10 | Điều 3 thành thật + luồng demo | H-11, H-13, H-16, H-26; T-041, T-042, T-044 |
| Audit 2 | Rà sau R9 + R10 | rồi tag v0.1-e2e (người dùng duyệt) |

# Trạng thái dự án (đọc trước plan mốc)

Developer, reviewer, supervisor và auditor đọc file này trước `plan/Rx.md`. Bản máy đọc: `docs/autodev/state.json` (cùng nội dung). Cập nhật sau mỗi audit và mỗi mốc; giữ dưới 150 dòng (`.autodev/tests/test_project_state.py`).

Cập nhật: 2026-10-10 · Nguồn: audit `docs/audits/2026-10-09_2.md` + R9i merge #55 + R9ih merge #58 + quyết định team 10/10.

## Mốc

| Loại | Mốc | Trạng thái | Ghi chú |
|---|---|---|---|
| Dự án | M0–M2 | ✅ 19/19 task | |
| Dự án | M3 | ✅ 2/2 | T-030 xong 10/10: vòng LLM thật khép kín; dashboard lỗi H-44 |
| Dự án | M4 | 🔄 1/6 | T-040 xong; T-041..T-045 mở; tag v0.1-e2e 13/10 |
| Chạy | R4–R9, R9h, R9i, R9ih | ✅ merge #19, #21, #27, #31, #37, #44, #49, #55, #58 | 2,29 / 3,01 / 1,81 / 2,58 / 6,40 / 7,18 / ~1,15 / ~1,60 / ~0,64 (worker) USD |
| Plugin | P1–P3 | ✅ | |
| Plugin | P4 | 🔄 | chưa gặp hạn mức thật |
| Plugin | P5 | 🔄 | audit + trạng thái (file này) |
| Plugin | P6–P8 | ⏳ | kế hoạch dài hạn; Telegram + API trạng thái; đóng gói |

## Mục tiêu và 3 điều cần kiểm chứng

MVP: scenario 1 chạy đủ vòng Detect → Learn từ dashboard trên dữ liệu sandbox (docs/PLAN.md mục 1).

| # | Điều cần kiểm chứng | % đạt | Bằng chứng | Còn thiếu |
|---|---|---|---|---|
| 1 | Tìm đúng nguyên nhân gốc, biết hỏi người khi thiếu bằng chứng | 30 | SOP khớp scenario (H-10); Detect khớp ground truth; luật hỏi theo ngưỡng; eval chạy được nhưng tự đúng (H-28) | T-030 + `eval_rootcause.py --llm real` có kết quả; H-28, H-29 |
| 2 | Duyệt → KPI cải thiện; không thì rollback, điều tra lại | 65 | Measure theo `action` thật (test_measure_h06); e2e uvicorn sai → rollback → đúng → Learn (test_e2e_rollback_r9); đề xuất phải đủ `action` + `sop_proposal`, action hữu hạn, trong miền YAML, đúng máy (R9i) | H-31, H-32, H-36, H-19; LLM thật (T-030 lần 2) |
| 3 | 3 chỉ số trước/sau trên 6 tháng mô phỏng | 5 | `measure()` 1 máy, 7 ngày; MTTD/MTTR chỉ test nạp tay | H-11 (cả thiết kế MTTD); T-042, T-043 |

Audit 1 hạ % xuống 25/40/10; sau R9 supervisor nâng lên 45/70/10; audit 2 hạ còn 30/55/5 vì eval tự đúng và bỏ `action` là tắt được rollback; R9i đóng lỗ bỏ `action` → 30/65/5.

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
| Tên model không hard-code | **chưa có**; đang vi phạm ở `llm.py:33` (H-39) |
| Số lần hỏi/rollback/retry có giới hạn | test_ask::test_ask_is_bounded_then_awaits_human, test_act::test_max_rollbacks_halts; retry **chưa có** |

## Lỗ hổng mở

Từ `docs/audits/2026-10-09_2.md` (chi tiết, bằng chứng, test cần có để đóng). Đóng khi có test chứng minh. H-06..H-23 đóng ở R9 (ghi trong audit 1).

| Mã | Mức | Tóm tắt |
|---|---|---|
| H-11 | cao | Chỉ số 3 chưa có đường code; MTTD ≈ 0 theo cấu tạo (Detect nhìn lại) |
| H-28 | cao | Eval nguyên nhân tự đúng: script chứa nhãn, chấm theo chuỗi (phủ định = đúng) |
| H-29 | cao | Bài toán quá dễ: `correlate` trả nhãn r≈0,98, anomaly ~10σ, hỏi người chỉ do script |
| H-31 | vừa | Bản SOP rollback mất nếu lần gọi LLM kế tiếp lỗi |
| H-32 | vừa | Chẩn đoán sai + hành động đúng → Learn lưu nguyên nhân sai là success |
| H-33 | vừa | `revision_count` không đặt lại sau halt → investigate |
| H-34 | vừa | Câu hỏi "chưa đủ bằng chứng" của Measure không trả lời được |
| H-35 | vừa | UI chưa theo R9: Retry khi `retryable:false`, halt `options`, thẻ duyệt thiếu `action` (team frontend) |
| H-36 | vừa | Điều tra lại sau rollback không biết `action` đã thất bại |
| H-37 | vừa | Mỗi run một Engine DB mới, không dispose |
| H-13 | vừa | Sau retry SSE không mở lại, `event_id` trùng |
| H-14 | vừa | Hai run song song ghi đè SOP |
| H-15 | vừa | Run/event/checkpointer chỉ ở bộ nhớ |
| H-16 | vừa | Demo LLM giả: reject/revise/halt-investigate lỗi |
| H-18 | vừa | `has_tool_evidence` tính tool của cả run |
| H-19 | vừa | Halt → điều tra lại quên SOP đang hiệu lực |
| H-20 | vừa | Trả lời không kèm id câu hỏi |
| H-44 | vừa | Dashboard không hiện thẻ đề xuất khi chờ duyệt (team frontend) |
| H-22 | thấp | Giá trị miền hard-code ngoài YAML |
| H-24 | thấp | UI không phân biệt kết quả run (team frontend) |
| H-25 | thấp | Payload event chưa có tài liệu |
| H-26 | thấp | `demo.sh --check` chỉ kiểm khởi động |
| H-38 | thấp | Thiếu audit_log cho trả lời, halt, Measure không kết quả |
| H-39 | thấp | Tên model hard-code (`claude-haiku-4-5`); `MODEL_CHEAP` không dùng |
| H-40 | thấp | Ví dụ `docs/schema/examples` không qua test dashboard; `payloads.md` sai chỗ |

## Quyết định gần đây

- 2026-10-10: team 4 người theo vai: A dữ liệu (#63), D giao diện (#64), Q kiểm chứng (#65); backend do leader + auto-dev. Từ nay auto-dev không sửa phần trình bày `dashboard/`; dữ liệu mới chờ D1 (#66). `main` bắt buộc qua PR + check `plugin-guard` (chỉ leader sửa file plugin).
- 2026-10-10: leader duyệt hợp đồng dữ liệu v0.1 (`docs/schema/data_contract.md`): nhập số đếm `production_log`; `material_batches` thay `inventory` + `supplier`; `environment_log` + `training_level` sang R11.
- 2026-10-09: sau T-030, tạm dừng thêm tính năng để chuẩn hoá dữ liệu (hợp đồng + nhập CSV) và làm UI demo (`docs/demo-storyboard.md`) trước P6.
- 2026-10-09: R9ih merge #58: prompt Improve có danh mục SOP (id, version hiệu lực tính `sop_versions`, title, nội dung cắt theo config); `sop_id` lạ → thông báo sửa lại nêu id hợp lệ. Đóng H-43. % đạt giữ nguyên (cần T-030 lần 3 với LLM thật để chứng minh vòng khép). Supervisor tự kiểm 3 tiêu chí cấp mốc, 6 test mới đỏ trên main.
- 2026-10-09: R9i merge #55: đề xuất thiếu `action` hoặc `sop_proposal`, `new_content` rỗng, `action` NaN/inf/ngoài miền YAML/máy lạ → gửi lại LLM, hết lượt thì `error` retryable. Đóng H-27, H-30, H-41, H-42; điều 2: 55 → 65. Supervisor tự kiểm 5 tiêu chí cấp mốc, test mới đỏ trên main.

- 2026-10-09: audit 2 (sau R9 + R9h): 15 lỗ hổng mới H-27..H-41 (4 cao), 0 đóng, 27 mở. % đạt 45/70/10 → 30/55/5: eval tự đúng (H-28, H-29), bỏ `action` là tắt được rollback (H-27), MTTD ≈ 0 theo cấu tạo. Đề xuất R9i (H-27, H-30) trước T-030.

- 2026-10-09: R9h merge #49 (T-030 lần đầu chạy thật dừng vì SDK bỏ `temperature`; H-23 chỉ kiểm bằng client giả). Thêm test so khoá request với chữ ký SDK đã cài. Supervisor chấp nhận `backend/api/app.py` (2 dòng, ngoài danh sách file) như điều chỉnh (a).
- 2026-10-09: R9 merge #44. Đóng 9 lỗ hổng; % đạt 45/70/10. Lần đầu chạm hạn mức thật: runner chờ reset rồi chạy tiếp đúng (P4).

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
| R9 | ✅ merge #44 | đóng H-06, H-07, H-08, H-09, H-10, H-12, H-17, H-21, H-23 |
| R9h | ✅ merge #49 | bỏ `temperature` → `output_config.effort` (`LLM_EFFORT`); script `--llm real` tự nạp `.env`, thiếu key báo rõ |
| R9i | ✅ merge #55 | đóng H-27, H-30, H-41, H-42 |
| R9ih | ✅ merge #58 | đóng H-43 (danh mục SOP trong prompt Improve) |
| T-030 | ✅ 10/10 vòng LLM thật khép kín | lỗi trong `docs/decisions.md`; H-44 giao vai D |
| R10a | API cho storyboard + dự phòng sân khấu (không chờ D1) | 4 API (FR-09..12), T-041, H-13, H-16, H-26 |
| R10b | Dữ liệu theo hợp đồng + điều 3 (sau D1 #66) | `production_log`, import CSV + validator V01–V09, simulator số đếm; H-11, T-042, H-31, H-33, H-39 |
| R11 | Điều 1 thành thật (sau D4 + D5 của vai A) | H-28, H-29, H-32, H-36, H-18; kịch bản khó; eval chấm theo mã |
| Audit 3 | Rà sau R10 | rồi tag v0.1-e2e (người dùng duyệt) |

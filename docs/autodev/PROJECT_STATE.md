# Trạng thái dự án (đọc trước plan mốc)

Developer, reviewer, supervisor và auditor đọc file này trước `plan/Rx.md`. Bản máy đọc: `docs/autodev/state.json` (cùng nội dung). Cập nhật sau mỗi audit và mỗi mốc; giữ dưới 150 dòng (`.autodev/tests/test_project_state.py`).

Cập nhật: 2026-10-10 · Nguồn: audit `docs/audits/2026-10-10.md` (audit 3) + R9i merge #55 + R9ih merge #58 + R10a merge #82 + R10c merge #84 + R10ch merge #91 + quyết định team 10/10 + kế hoạch P6 (duyệt 10/10).

## Mốc

| Loại | Mốc | Trạng thái | Ghi chú |
|---|---|---|---|
| Dự án | M0–M2 | ✅ 19/19 task | |
| Dự án | M3 | ✅ 2/2 | T-030 xong 10/10: vòng LLM thật khép kín; dashboard lỗi H-44 |
| Dự án | M4 | 🔄 2/6 | T-040, T-041 xong; T-042..T-045 mở; tag v0.1-e2e 13/10 |
| Chạy | R4–R9, R9h, R9i, R9ih, R10a, R10c, R10ch | ✅ merge #19, #21, #27, #31, #37, #44, #49, #55, #58, #82, #84, #91 | 2,29 / 3,01 / 1,81 / 2,58 / 6,40 / 7,18 / ~1,15 / ~1,60 / ~0,64 / 4,00 / 5,81 / 3,51 (worker) USD |
| Plugin | P1–P3 | ✅ | |
| Plugin | P4 | 🔄 | chờ reset hạn mức phiên đã chạy thật (R9); còn kiểm hạn mức trước mốc, hạn mức tuần mới thử bằng test giả |
| Plugin | P5 | ✅ | audit + trạng thái (file này); trang trạng thái Artifact làm mới bằng `.autodev/export_status.py` khi leader yêu cầu (đóng 10/10) |
| Plugin | P6 | ✅ | kế hoạch hai luồng duyệt 10/10; P6a (ước tính + pre-mortem) dùng từ R10a; P6b `metrics.py` (3 lỗi sửa 10/10); báo cáo đối chiếu R10a–R10ch trong PROGRESS (B3 3/3 mốc đạt; luật ước tính + pre-mortem mới ở thiết kế 6.5) |
| Plugin | P7, P8, P9 | ⏳ | Telegram + API trạng thái; đóng gói; reviewer cho PR của team |

## Mục tiêu và 3 điều cần kiểm chứng

MVP: scenario 1 chạy đủ vòng Detect → Learn từ dashboard trên dữ liệu sandbox (docs/PLAN.md mục 1).

Từ 2026-10-10, **% đạt tính bằng công thức từ chỉ số đo được** (`docs/eval/criteria.md` mục 2), không ước lượng. Chỉ số chưa đo được tính 0, nên % hiện là 0. Cột "Ước lượng cũ" chỉ để tham khảo.

| # | Điều cần kiểm chứng | % đo được | Ước lượng cũ | Chỉ số (ngưỡng freeze) | Nền 10/10 | Mốc đo |
|---|---|---|---|---|---|---|
| 1 | Tìm đúng nguyên nhân gốc, biết hỏi người khi thiếu bằng chứng | 0 | 30 | A1 top-1 tập giữ lại ≥ 0,7; A2 precision ≥ 0,6, recall ≥ 0,8; A3 = 0 | eval LLM giả chỉ kiểm bộ chấm (right 100%, wrong 0%, unsure hỏi 100%); chấm theo chuỗi (H-28) | đo nền LLM thật sau R10a; R11a, R11b |
| 2 | Duyệt → KPI cải thiện; không thì rollback, điều tra lại | 50 | 65 | A4 ≥ 0,9; A5 (a) 1,0, (b) ≥ 0,8; A6 = 0 vi phạm | Luật chỉ số nhiều phần (`criteria.md`): A5 = trung bình (LLM giả, LLM thật). R10ch đóng H-54: LLM giả (a) 1,00, (b) 1,00 đọc `kpi_measured.passed`, đối chứng LLM luôn sai (b) = 0, không áp dụng gì không `passed` → 1,0; LLM thật chưa đo → A5 = 0,5. A6 = 0 vi phạm → 1. A4 chưa có lệnh → 0. (0 + 0,5 + 1)/3 = 50 | R10b2 (A4), A5 LLM thật |
| 3 | 3 chỉ số trước/sau trên 6 tháng mô phỏng | 0 | 5 | A7: 3 chỉ số tính được, tốt hơn đối chứng "không agent" | `measure()` 1 máy, 7 ngày; H-11 | R10b2 |

Cổng go/no-go 13/10 và 20/10: `docs/eval/criteria.md` mục 3. Chỉ số plugin B1–B5: `python3 .autodev/metrics.py` (nền: B1 = 1,67 ở audit 1, 1,75 ở audit 2; B2 = 2/44 task cần ≥ 2 vòng sau R10a).

## Kiến trúc hiện nay

- Một agent LangGraph (`backend/agent/graph.py`): Detect thống kê → Investigate → Ask (interrupt) → Improve → duyệt (interrupt) → Act → Measure → Learn; cạnh quay lại (T-040).
- Có `DATABASE_URL`: checkpointer **PostgresSaver**, run/event ghi bảng `runs`/`events`, khôi phục khi khởi động; một engine chung (pool 5 + 5) (R10c). Test vẫn tiêm InMemorySaver. Sau restart: số retry giữ (suy từ chuỗi event lỗi), run bị kill giữa bước thành `error` retryable, dựng LLM lỗi chỉ hỏng run đó (R10ch); `steps` của `/export` mất. `POST /runs/{id}/close` đóng run lỗi hết retry (người duyệt, không đụng SOP).
- Postgres: `audit_log`, `sop_versions`, `learning_store` (alembic 0001).
- Sandbox: simulator + injector + post_change (dữ liệu sau thay đổi riêng cho từng run).
- API FastAPI + SSE; dashboard Next.js một trang. LLM giả mặc định; `SME_LLM=real` dùng Anthropic (model trong `.env`).

## Quy tắc → test bảo vệ

| Quy tắc (CLAUDE.md) | Test bảo vệ |
|---|---|
| Rollback/áp dụng SOP cần người duyệt; LLM không duyệt | test_api::test_approval_by_agent_or_llm_is_rejected, test_tools_actions::test_apply_without_valid_approval_refused, test_invariants::test_random_sequences_keep_every_invariant (A6, cả audit, bảng nguồn, `sop_versions`) |
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
| H-32 | vừa | Chẩn đoán sai + hành động đúng → Learn lưu nguyên nhân sai là success |
| H-33 | vừa | `revision_count` không đặt lại sau halt → investigate |
| H-34 | vừa | Câu hỏi "chưa đủ bằng chứng" của Measure không trả lời được |
| H-35 | vừa | UI chưa theo R9: Retry khi `retryable:false`, halt `options`, thẻ duyệt thiếu `action` (team frontend) |
| H-36 | vừa | Điều tra lại sau rollback không biết `action` đã thất bại |
| H-18 | vừa | `has_tool_evidence` tính tool của cả run |
| H-44 | vừa | Dashboard không hiện thẻ đề xuất khi chờ duyệt (team frontend) |
| H-22 | thấp | Giá trị miền hard-code ngoài YAML |
| H-24 | thấp | UI không phân biệt kết quả run (team frontend) |
| H-25 | thấp | Payload event chưa có tài liệu |
| H-39 | thấp | Tên model hard-code (`claude-haiku-4-5`); `MODEL_CHEAP` không dùng |
| H-40 | thấp | Ví dụ `docs/schema/examples` không qua test dashboard; `payloads.md` sai chỗ |
| H-46 | cao | Dashboard đóng SSE ở `run_finished` lỗi đầu tiên; sau Retry timeline chết (team frontend) |
| H-49 | vừa | `question_id` của `/answer` tuỳ chọn, dashboard không gửi |
| H-52 | vừa | Rollback bị `SopConflict` vẫn chạy tiếp như đã rollback; `sop_conflict` thiếu audit và trường |
| H-53 | vừa | `applied` bị ghi đè khi đổi SOP khác sau halt |
| H-55 | vừa | `test_invariants` thiếu: run song song, lỗi DB/kill, audit `apply_sop`, nội dung SOP sau rollback |
| H-56 | vừa | Sau rollback/revise/halt, điều tra không gọi tool vẫn không hỏi người (bằng chứng mới của H-18) |
| H-57 | thấp | `/kpi/series` 500 với múi giờ; tham số rỗng không 422 |
| H-58 | thấp | `demo.sh`: cổng bận không phát hiện, `--check` ép scripted, không phủ SSE/rollback, không CI |
| H-59 | thấp | Gom: cache `Run` nhiều tiến trình, `/export` sau retry, `/audit` không giới hạn, NaN trong Measure |

## Quyết định gần đây

- 2026-10-10 (đóng phiên đêm): quy tắc ước tính thời gian khi bắt đầu nhiệm vụ (`CLAUDE.md`) + ghi % hạn mức 5 giờ và tuần trước/sau (`.autodev/usage.py`). Báo cáo so sánh bên ngoài (`docs/autodev/research/`): phiên sau làm đề xuất 1 (cổng "không nới test") + 3 (câu hỏi bắt buộc cho reviewer); 7 đề xuất chưa vào ROADMAP. Chỉ đề xuất đóng phiên khi có lý do (việc lớn mới, ngữ cảnh dài, trước auto-dev).
- 2026-10-10 (đêm): **tạm dừng việc dự án, chờ team** (D1 #66, FR #67/#89/#90, Daivon #65); điểm bắt đầu lại ở HANDOFF mục "Tạm dừng". Duyệt luật ước tính + pre-mortem mới (thiết kế 6.5). Chuyển sang nghiên cứu auto-dev. `demo.sh --fresh-db` duyệt và merge (#95). Trang trạng thái chỉ làm mới khi leader yêu cầu.
- 2026-10-10 (đóng phiên): thứ tự R10a → R10c → R10ch → R10b1 (**sau khi D1 #66 của vai A merge**; D1 là việc của vai A, backend không code hợp đồng trước) → R10b2. Thay quyết định "R10b không chờ D1". Audit 3 chạy sau R10c (đặt tay `.autodev/runs/audit.json`). Trang trạng thái Artifact (P5) đã tạo, làm mới tay. Đề xuất lệnh tiếp theo luôn đánh số.
- 2026-10-10: R10ch merge #91: đóng H-31, H-45, H-47, H-48, H-50, H-51, H-54 (21 test mới đỏ trên main, supervisor tự chạy). A5 đo lại không theo cấu tạo: LLM đúng (a) 1,00 (b) 1,00; LLM luôn sai (b) 0; không áp dụng gì không `passed` → điều 2 = 50%. Treo (đề xuất R11a): kill giữa commit `apply_sop` và checkpoint có thể tạo bản SOP trùng khi retry; số retry suy từ hậu tố `event_id`.
- 2026-10-10: luật chỉ số nhiều phần (`docs/eval/criteria.md`): mỗi phần trọng số bằng nhau, phần chưa đo = 0; phần đo "đạt theo cấu tạo" (audit phát hiện, ví dụ H-54) = 0 đến khi sửa. Điều 2 = 42%. Mốc sửa nhanh R10ch trước tag 13/10 (H-45, H-31, H-47, H-48, H-50, H-51, H-54).
- 2026-10-10: audit 3 (sau R9i, R9ih, R10a, R10c): 15 lỗ hổng mới H-45..H-59 (2 cao), 0 đóng, 31 mở. A5 và A6 tái hiện (A5 1,00/1,00; A6 60 chuỗi, 0 vi phạm). % đạt 0/50/0 giữ nguyên; điều 2: `criteria.md` cho A5 LLM giả = 1,0 (67%) còn bảng trên dùng 0,5, leader chốt. Đề xuất H-45, H-48, H-54 vào R10b2; H-47, H-49, H-50, H-51 trước tag; H-46 giao vai D.
- 2026-10-10: R10c merge #84: Postgres cho run/event/checkpoint (sống qua restart, kiểm bằng 2 tiến trình uvicorn), khoá SOP theo `base_version`, `question_id` (cũ → 409), audit cho trả lời/halt/Measure không kết quả, `tests/test_invariants.py`. Đóng H-14, H-15, H-19, H-20, H-37, H-38 (supervisor tự chạy test đỏ trên main). A6 = 0 → điều 2 = 50%. Bất biến "không có `claude-`" xfail strict tới R10b2 (H-39, gỡ xfail khi đóng).
- 2026-10-10: R10a merge #82: API storyboard (`/runs`, `/runs/{id}/export`, `/kpi/series`, `/audit`, `/sop/{id}/versions`, `/metrics` khung trung thực), record_run, `demo.sh --check --repeat`, LLM giả mọi nhánh + chế độ rollback. Đóng H-13, H-16, H-26. A5 v0.1 đạt (LLM giả), A8 10/10 p95 0,4 s. Supervisor tự quyết: A5 tính 0,5 vào % điều 2 (phần LLM thật của ngưỡng freeze chưa đo) → điều 2 = 17%.
- 2026-10-10: % đạt tính bằng công thức từ chỉ số đo được (`docs/eval/criteria.md`: A1–A8, cổng 13/10 và 20/10); ước lượng audit chỉ tham khảo. Ngưỡng A1 freeze trên tập giữ lại ≥ 0,7. Chỉ số plugin B1–B6 (ROADMAP bảng B, `.autodev/metrics.py`). Đo nền LLM thật sau R10a, ≤ 2 USD.
- 2026-10-10: leader duyệt kế hoạch P6 hai luồng đến Demo Day (ROADMAP). R10b không còn chờ D1 (hợp đồng v0.1 đã duyệt); R10c (H-15, H-14, H-19, H-20, H-37, H-38) làm trước v0.1; R11 tách R11a (cơ chế eval, không chờ team) và R11b (nhập D4/D5). Cổng UI 13/10: chưa có PR FR-01 thì hỏi leader. P9 (reviewer cho PR của team, chỉ comment) sau v0.1.
- 2026-10-10: mở/đóng phiên bằng lệnh của leader `/session-start`, `/session-end` (bàn giao qua HANDOFF + file này, PR, merge sau check).
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

Kế hoạch P6 (duyệt 10/10; đầy đủ, kèm luồng plugin, pre-mortem, thứ tự cắt: `docs/autodev/ROADMAP.md` mục "Kế hoạch hai luồng"). Ngày là đề xuất.

| Mốc | Ngày | Mục tiêu | Lỗ hổng / task | Chờ team? |
|---|---|---|---|---|
| R10a | ✅ 10/10 #82 | API storyboard + dự phòng sân khấu | T-041; H-13, H-16, H-26 | |
| R10c | ✅ 10/10 #84 | Bền cho demo | H-14, H-15, H-19, H-20, H-37, H-38; A6 = 0 | |
| Audit 3 | ✅ 10/10 #86 | Rà R9i, R9ih, R10a, R10c | B1 = 0,71 (ngưỡng ≤ 0,5); H-45..H-59 | |
| R10ch | ✅ 10/10 #91 | Sửa nhanh sau audit 3 | H-31, H-45, H-47, H-48, H-50, H-51, H-54; A5 LLM giả đo thật | |
| R10b1 | 12/10 | Dữ liệu theo hợp đồng **D1 đã chốt** | `production_log`, `material_batches`, simulator nhị thức, `import_data.py` + V01–V09 (dùng D2) | **chờ D1 #66 merge** (vai A) |
| R10b2 | 12–13/10 | Điều 3 | H-11, T-042, `/metrics` thật, `metrics_report.py` có đối chứng; H-33, H-39 | sau R10b1; giả định cần D3 |
| Cổng 13/10 | 13/10 | tag v0.1-e2e (leader duyệt) | `criteria.md` mục 3; UI FR-01..05 | UI: vai D |
| R11a | 13–14/10 | Điều 1: cơ chế eval trung thực | H-28, H-29, H-32, H-36, H-18; 1 kịch bản khó do backend soạn; `environment_log`, `training_level` | không |
| R11b | 15–17/10 | Điều 1: đề độc lập | nhập D4/D5; eval nhiều seed LLM thật; ghi run tốt để phát lại | vai A |
| R12 | 18–19/10 | Gom lỗi bug bash 2, audit 4, bộ dữ liệu demo (D6) | | vai Q, A |

Chỉ số mỗi mốc phải đo được khi xong: R10b2 → A4, A7; R11a → A1–A3 tập dev; R11b → A1 tập giữ lại (`TASKS.md`, `docs/eval/criteria.md`). D1 chưa merge sáng 12/10 thì leader quyết; R10b2 trễ thì A7 chuyển sang cổng 20/10.

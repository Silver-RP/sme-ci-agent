# Trạng thái dự án (đọc trước plan mốc)

Developer, reviewer, supervisor và auditor đọc file này trước `plan/Rx.md`. Bản máy đọc: `docs/autodev/state.json` (cùng nội dung). Cập nhật sau mỗi audit và mỗi mốc; giữ dưới 150 dòng (`.autodev/tests/test_project_state.py`).

Cập nhật: 2026-10-14 tối (kế hoạch lại, ADR-011: tiếp quản vai A, D, Q) · Nguồn: audit `docs/audits/2026-10-12.md` (audit 4) + audit `2026-10-10.md` (audit 3) + R9i merge #55 + R9ih merge #58 + R10a merge #82 + R10c merge #84 + R10ch merge #91 + quyết định team 10/10 + kế hoạch P6 (duyệt 10/10) + bộ thử reviewer (#105–#108) + R10d merge #120 + R10b1 merge #130 + R10b2 merge #132 + cổng 13/10 (#135, tag v0.1-e2e) + leader chốt điều 3 (12/10) + R10e merge #138 + đo nền LLM thật và ADR-010 (12/10).

## Mốc

| Loại | Mốc | Trạng thái | Ghi chú |
|---|---|---|---|
| Dự án | M0–M2 | ✅ 19/19 task | |
| Dự án | M3 | ✅ 2/2 | T-030 xong 10/10: vòng LLM thật khép kín; dashboard lỗi H-44 |
| Dự án | M4 | 🔄 4/6 | T-040..T-042, T-044 xong; T-043 → R11d, T-045 bug bash → leader (ADR-011); **cổng 13/10 go, tag `v0.1-e2e` trên c60fec5 (#135, 12/10)** |
| Chạy | R4–R9, R9h, R9i, R9ih, R10a, R10c, R10ch, R10d, R10b1, R10b2, R10e | ✅ merge #19, #21, #27, #31, #37, #44, #49, #55, #58, #82, #84, #91, #120, #130, #132, #138 | 2,29 / 3,01 / 1,81 / 2,58 / 6,40 / 7,18 / ~1,15 / ~1,60 / ~0,64 / 4,00 / 5,81 / 3,51 / ~3,63 / 9,10 / 8,76 / 7,05 (worker) USD |
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
| 1 | Tìm đúng nguyên nhân gốc, biết hỏi người khi thiếu bằng chứng | 0 | 30 | A1 top-1 tập giữ lại ≥ 0,7; A2 precision ≥ 0,6, recall ≥ 0,8; A3 = 0 | eval LLM giả chỉ kiểm bộ chấm (right 100%, wrong 0%, unsure hỏi 100%); chấm theo chuỗi (H-28). **Nền LLM thật 12/10** (`--llm real --seeds 3`, sau R10e): DB sạch 3/3 đúng `wrong_setpoint` (A1, M02), hỏi 0%, ~41k token; DB dùng chung 67% do chấm theo chữ + 185 bài học lộ đáp án. Bài dễ (~10σ, 3 seed chỉ đổi nhiễu) → chưa phải A1 tập giữ lại, % giữ 0 | R11a, R11b |
| 2 | Duyệt → KPI cải thiện; không thì rollback, điều tra lại | 67 | 65 | A4 ≥ 0,9; A5 (a) 1,0, (b) ≥ 0,8; A6 = 0 vi phạm | Luật chỉ số nhiều phần (`criteria.md`). A4: R10e `eval_rootcause.py --until learn --seeds 5` LLM giả, chấm theo nguyên nhân (`cause_status`): `right` confirmed 5/5 = 1,0, `wrong` 0/5 (H-32 đóng); LLM thật chưa đo → A4 = 0,5 (LLM thật chưa xuất `signal` nên luôn `unconfirmed`: R11a). A5: LLM giả 1,0 (R10ch), LLM thật chưa đo → 0,5. A6 = 0 vi phạm → 1. (0,5 + 0,5 + 1)/3 = 67 | A4, A5 LLM thật |
| 3 | 3 chỉ số trước/sau trên 6 tháng mô phỏng | 67 | 5 | A7: 3 chỉ số tính được, tốt hơn đối chứng "không agent" | R10b2 `metrics_report.py --months 6 --seed 42` (LLM giả, lặp lại cùng số): có agent / không agent: tỷ lệ lỗi `period_rate` 0,0204 / 0,0208; MTTD 8 / 72 giờ, MTTR 24 / 44 giờ; tái diễn 0,25 / 0,5 → cả 3 phần tốt hơn → 100 theo công thức. **Cảnh báo:** 4 giả định đều "chờ D3"; MTTD không agent = giả định, tái diễn theo cấu tạo; lợi thế tỷ lệ lỗi rất nhỏ. **Audit 4 (12/10):** đề nghị ≤ 67 (33 nếu chặt): tái diễn đạt theo cấu tạo, độ nhạy chung đảo chiều (H-64). **Leader chốt 12/10: 67** (tái diễn = 0 theo `criteria.md` mục 2; tỷ lệ lỗi, MTTD/MTTR tính 1; cờ H-64 chờ D3) | nguồn D3; R11a (tái diễn theo nguyên nhân) |

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
| Tên model không hard-code | `test_small_fixes_r10b2::test_h39_no_model_name_in_backend`, `test_invariants.py` (H-39 đóng R10b2; model không hỗ trợ effort khai qua `LLM_NO_EFFORT_MODELS`) |
| Số lần hỏi/rollback/retry có giới hạn | test_ask::test_ask_is_bounded_then_awaits_human, test_act::test_max_rollbacks_halts; retry **chưa có** |

## Lỗ hổng mở

Từ `docs/audits/2026-10-12.md` (mới) và `2026-10-10.md`, `2026-10-09_2.md` (chi tiết, bằng chứng, test cần có để đóng). Đóng khi có test chứng minh. H-06..H-23 đóng ở R9 (ghi trong audit 1).

| Mã | Mức | Tóm tắt |
|---|---|---|
| H-28 | cao | Eval nguyên nhân tự đúng: script chứa nhãn, chấm theo chuỗi (phủ định = đúng) |
| H-29 | cao | Bài toán quá dễ: `correlate` trả nhãn r≈0,98, anomaly ~10σ, hỏi người chỉ do script |
| H-36 | vừa | Điều tra lại sau rollback không biết `action` đã thất bại |
| H-18 | vừa | `has_tool_evidence` tính tool của cả run |
| H-22 | thấp | Giá trị miền hard-code ngoài YAML |
| H-24 | thấp | UI không phân biệt kết quả run (team frontend) |
| H-25 | thấp | Payload event chưa có tài liệu |
| H-40 | thấp | Ví dụ `docs/schema/examples` không qua test dashboard; `payloads.md` sai chỗ |
| H-52 | vừa | Rollback bị `SopConflict` vẫn chạy tiếp như đã rollback; `sop_conflict` thiếu audit và trường |
| H-53 | vừa | `applied` bị ghi đè khi đổi SOP khác sau halt |
| H-55 | vừa | `test_invariants` thiếu: run song song, lỗi DB/kill, audit `apply_sop`, nội dung SOP sau rollback |
| H-56 | vừa | Sau rollback/revise/halt, điều tra không gọi tool vẫn không hỏi người (bằng chứng mới của H-18) |
| H-58 | thấp | `demo.sh`: cổng bận không phát hiện, `--check` ép scripted, không phủ SSE/rollback, không CI |
| H-59 | thấp | Gom: cache `Run` nhiều tiến trình, `/export` sau retry, `GET /runs` nạp hết, `POST /runs` không body (audit 4 đã bỏ `/audit`, NaN) |
| H-64 | cao | Điều 3: đối chứng dựa 4 giả định chưa có nguồn D3; tái diễn đạt theo cấu tạo (agent luôn sai vẫn 0,0); độ nhạy chung đảo chiều |
| H-65 | vừa | `/metrics` phía UI còn: (b) bỏ `dataset`/`seed`/giả định, (f) `before = 0` → null, (g) thông điệp cũ; (a, c, d, e) đóng R10e; giao vai D #139 |
| H-60 | vừa | `POST /runs` kiểm `change_time` theo anomaly đầu, graph chọn anomaly chưa xử lý (H-48 tái phát) |
| H-61 | vừa | `SME_DATASET`: Measure vẫn dùng dữ liệu sau thay đổi mô phỏng từ scenario1.yaml |
| H-62 | vừa | V09 (PII) chỉ quét tên cột, không quét giá trị `note`/`step_text` |
| H-63 | vừa | Kết quả tool rỗng (`no_data`, `count:0`) vẫn tính là bằng chứng, không hỏi người |
| H-67, H-68, H-69 | vừa | UI (team frontend): thẻ Measure đơn vị sai; kẹt sau Close; kẹt khi tải lại run 404 |
| H-70 | vừa | Khoá lesson không có dataset/seed; `no_change` tính là đã xử lý |
| H-71, H-72, H-73, H-74 | thấp | Learn chưa commit; Learn chỉ khi pass; target NaN; gom nhỏ (xem audit 2026-10-12) |
## Quyết định gần đây
- **2026-10-14 tối, ADR-011:** leader + auto-dev **tiếp quản toàn bộ việc còn lại của vai A, D, Q**; bỏ mốc ngày cũ, xếp theo giá trị/chi phí (ROADMAP "Kế hoạch lại 14/10"). Tập giữ lại do **phiên cách ly** soạn (không đọc backend, prompt, tập dev), leader duyệt đáp án, lưu ngoài repo, SHA-256 niêm phong; pitch nêu rõ (`criteria.md` mục 1). Thứ tự: P4 tối thiểu → plan R11d → chuỗi 1 R11c → R11a → R11d (song song D3, D5, định dạng kịch bản) → tập giữ lại → R11b → audit 5 → đo LLM thật → R12 → cổng freeze. Ước 40–55 USD worker (~60–90% tuần); cổng `/usage` sau mỗi chuỗi. Sổ `docs/token-cost.md` (T-044).
- 2026-10-13: leader chốt **điều 1 = 0** (đúng luật công thức; ghi kèm "nền LLM thật 3/3 bài dễ"). P8a để sau freeze. Quy tắc tên phiên `leader-<MMDD>-<việc>`. **Duyệt kế hoạch tổng thể 13/10 → 07/11:** tuần 97% (reset 14/10 13:00, lần sau 21/10) nên mọi việc tới freeze nằm trong một tuần hạn mức; tách R11a (eval trung thực) / R11c (ADR-010 backend + vững); P4 tối thiểu trước chuỗi; đo A4/A5 LLM thật sau R11a; R11b không có D4 tới 16/10 tối thì leader chọn holdout do người ngoài backend soạn, hoặc điều 1 ≤ 60% khi pitch. Thứ tự cắt: R12 → H-52/53/55 → ghi run phát lại (ROADMAP). **2026-10-14:** plan R11c + R11a merge #144. Ranh giới vai A (brief: R11 làm sau D4 + D5): luật chấm (H-28), kịch bản + injector, tập dev khó (H-29), eval A1–A3 chuyển sang R11b sau D4/D5; mốc dự phòng D5 17/10 (chưa có thì chấm tối thiểu khớp mã, ghi tạm, điều 1 ≤ 60% khi pitch). R11c chạy trước (vai D chờ nhãn), R11a còn 3 task (`signal`, H-63/H-18/H-56, H-36). Dọn nhánh đã merge.

- 2026-10-12 (đóng phiên chiều): **đo nền LLM thật lần đầu** cho điều 1 (leader cho chạy): DB sạch 3/3, DB dùng chung 67% (lỗi chấm + bài học lộ đáp án); ~0,4 USD cả hai lần (ước từ token). **ADR-010** (leader chốt): mọi chữ trên UI tiếng Việt, mã giữ trong code/API, thuật ngữ ngành giữ nguyên có giải nghĩa, dữ liệu nguồn hiện dạng "trích nguyên văn"; vai D #141. R11a bắt buộc: trường `signal` (chấm theo mã), eval luôn trên DB sạch, ≥ 1 kịch bản khó (phân tích seed 42: zone3 chỉ đổi đúng 2 lần = 2 anomaly, `correlate` r ≈ 0,95, 7/9 giả thuyết `no_data`). Comment #63 làm rõ dạng bàn giao D4/D6 (đáp án theo mã, CSV ≥ 42 ngày qua `import_data.py`). % đạt giữ 0/67/67; leader có thể chốt lại điều 1.
- 2026-10-12: R10e merge #138 (câu chữ tiếng Việt từ config, `/config/domain`, Learn `cause_status`, Measure không hỏi lặp, `/metrics` trung thực, ví dụ sinh lại). Supervisor tự kiểm: 1028 passed, smoke 4/4, `demo.sh --fresh-db --check` xanh, A4 theo nguyên nhân `right` 5/5, `wrong` 0/5 (8 seed cũng 8/8, 0/8). Đóng H-32, H-34, H-66 (test đỏ trên main); H-65 còn phần UI. Đóng #111, #114. **(c) supervisor quyết:** tiêu chí 1 tính đạt phần backend dù 6 vitest dashboard đỏ (plan cấm sửa `dashboard/tests`, đã dự kiến) → vai D #139. % đạt giữ 0/67/67.
- 2026-10-12 (đóng phiên): cổng 13/10 **go**, tag `v0.1-e2e` trên c60fec5 (biên bản `docs/qa/gate-v0.1-e2e.md`, #135); A4 tính đạt theo chữ ngưỡng v0.1, **H-32 phải sửa trước freeze 20/10**. Điều 3 chốt **67** (tái diễn = 0 theo luật "đạt theo cấu tạo"; H-64 chờ D3). #126 (5 bộ D2 thêm) merge; R10b2 dev-07 thêm test 37 bộ D2 (#129). Guard giữ nguyên, không thêm duyệt xoá một lần. Phiên sau: câu chữ cho người dùng bằng tiếng Việt (đang hard-code tiếng Anh ở `ask.py`), #114, #111.
- 2026-10-12: audit 4 (sau R10d, R10b1, R10b2): 15 lỗ hổng mới H-60..H-74 (1 cao: H-64), đóng H-35, H-44, H-46 (auditor chạy vitest, 49 passed), còn 31 mở. Điều 3 đề nghị hạ 100 → ≤ 67 (33 nếu đọc chặt): tái diễn đạt theo cấu tạo, 4 giả định chưa có nguồn D3, độ nhạy một chiều không đảo chiều. % đạt công thức giữ 0/67/100 đến khi leader chốt.
- 2026-10-12: R10b2 merge #132 (điều 3: Measure trọng số sản lượng, Detect theo dòng thời gian, run chọn anomaly chưa xử lý + đọc bài học, `metrics_report.py` có đối chứng + độ nhạy, eval `--until learn`, `/metrics` thật). Supervisor tự kiểm: 4/4 tiêu chí cấp mốc đạt (936 passed, smoke 4/4). Đóng H-11, H-33, H-39 (H-33, H-39 đỏ trên main). % đạt 0/67/100; điều 3 dựa trên giả định chưa có nguồn D3. 6 đề xuất (c) của worker chờ leader (PR #132).
- 2026-10-11: R10b1 merge #130 (dữ liệu theo hợp đồng D1: `production_log` số đếm, `material_batches`, `sop`, simulator nhị thức, `kpi_log` dẫn xuất, `import_data.py` + V01–V09, `SME_DATASET`). Supervisor tự kiểm: 4/4 tiêu chí cấp mốc đạt; 31/31 bộ D2 đúng mã; nhập seed 7 thì app đọc đúng bảng nhập; A1 ≈ 9,6σ (chưa nhỏ đi, H-29 cần D4). Không đóng H-xx. 7 đề xuất (c) của worker chờ leader/vai A (PR #130). Fixture + 2 test dashboard đổi số mong đợi: báo vai D.
- 2026-10-11 (đóng phiên chiều): hết tạm dừng: UI của vai D (#116–#118) và D1, D2 của vai A (#122, #123) merge sau khi Claude kiểm phía backend; leader merge D1 **không chờ vai Q**. API của vai D: #110 có múi giờ → 422 (không quy đổi, giống `change_time`); #114 `/config/domain` để sau R10b1; #111 vào R11a. Plan R10b1 đối chiếu D1 (#124), chạy `R10b1 R10b2` với audit 4 sau R10b2 (20–26 USD). Không merge PR draft của thành viên. Guard chặn mọi lệnh xoá: leader tự chạy lệnh Claude đưa.
- 2026-10-11: R10d merge #120 (API cho dashboard: #110, #112, #113, #115). Đóng H-49 (`question_id` bắt buộc ở `/answer`, thiếu → 422) và H-57 (`/kpi/series` múi giờ hoặc tham số rỗng → 422, không 500). Lượt duyệt đầu chưa đạt tiêu chí 3 (tài liệu múi giờ) → dev-05 (b), lượt 2 đạt. Treo: `export_fixtures.py` làm mới `docs/schema/examples/`.
- 2026-10-11 (đóng phiên rạng sáng): làm đề xuất 1 + 3 (cổng `test_guard`, `risk_checks` của reviewer) và 4 (bộ thử reviewer, 6,60 USD). Bộ thử: reviewer chặn 2/9 lỗi đã lọt, thấy 5/9. Luật leader đặt trước khi đo: chỉ giữ thay đổi prompt nếu recall trên holdout tăng → bản sửa (a)(d) **không** vào `reviewer.md`. Giữ audit 4 sau R10b2. Đo lại luật xếp mức chỉ trên ca mới (audit 4), mỗi ca 3 lần. Không nhắc lại trong báo cáo: nhắc team, giờ kickoff, ROADMAP nghiên cứu.
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
- 2026-10-09: R9 merge #44 (Measure theo hành động có cấu trúc, eval nguyên nhân LLM giả, e2e uvicorn chuỗi rollback, 8 fixture). Đóng 9 lỗ hổng; % đạt 45/70/10. Lần đầu chạm hạn mức thật: runner chờ reset rồi chạy tiếp đúng (P4).
- 2026-10-09: **người dùng chọn hướng R9 theo audit**. R9 làm điều 1–2 thật: H-10 trước tiên, rồi H-06, eval, e2e rollback, H-07/08/09/17/21, temperature. R10 làm điều 3 và luồng demo. Hoãn đến sau v0.1-e2e: checkpointer Postgres, invariants, API danh sách run, khoá SOP.
- 2026-10-09: audit đầu: 21 lỗ hổng (7 cao), % đạt hạ còn 25/40/10. Đề xuất R9 làm điều 1–2 thật, R10 làm điều 3 (chờ người dùng duyệt ở P6).
- 2026-10-09: thứ tự sau R8: P5 → audit đầu → gói bàn giao UI → T-030 → P6 → R9 → R10 (người dùng duyệt).
- 2026-10-09: UI sản phẩm do bạn frontend làm; từ R9 auto-dev không sửa phần trình bày trong `dashboard/` (hết hiệu lực 14/10, ADR-011).
- 2026-10-08: R8-c2 (e2e uvicorn rollback) chuyển sang R9. Supervisor Opus effort medium, worker Sonnet; smoke bắt buộc trước merge.

## Tầm nhìn 3–5 mốc tới

Kế hoạch lại 14/10 (ADR-011; đầy đủ, kèm phân tích, pre-mortem, thứ tự cắt: `docs/autodev/ROADMAP.md` mục "Kế hoạch lại 14/10"). Không theo ngày cũ; leader đặt ngày.

| Mốc | Ngày | Mục tiêu | Lỗ hổng / task | Chờ team? |
|---|---|---|---|---|
| R10a, R10c, audit 3, R10ch | ✅ 10/10 #82, #84, #86, #91 | API storyboard, bền cho demo, sửa sau audit 3 | T-041; H-13..H-54 (xem PROGRESS); A6 = 0; A5 LLM giả đo thật | |
| R10d | ✅ 11/10 #120 | API cho dashboard | #110, #112, #113, #115; H-49, H-57 | |
| R10b1 | ✅ 11/10 #130 | Dữ liệu theo hợp đồng **D1 đã chốt** (#122) | `production_log`, `material_batches`, `sop`, simulator nhị thức, `import_data.py` + V01–V09 (dùng D2 #123); plan #124 | không (D1, D2 đã merge) |
| R10b2 | ✅ 12/10 #132 | Điều 3 | H-11, T-042, `/metrics` thật, `metrics_report.py` có đối chứng; H-33, H-39; audit 4 sau mốc này (`--audit-every 3`) | giả định cần D3 |
| Cổng 13/10 | ✅ 12/10 #135 | tag v0.1-e2e (leader duyệt) | A6 0, A8 10/10 p95 0,8 s, A5 1,0/1,0, A7 tính được, A4 1,0 (H-32 sửa trước freeze), FR-01..05 #116–#118 | |
| P4 tối thiểu | trước chuỗi 1 | Runner chạy chuỗi R11 được | phiên chat | không |
| R11c | chuỗi 1 | ADR-010 backend + vững | `labels` + thuật ngữ qua `/config/domain`, prompt dùng nhãn, `new_content`/SOP gốc tiếng Việt; H-52, H-53, H-55 | không |
| R11a | chuỗi 1 | `signal` + bằng chứng thật | `signal` (A4/A5 LLM thật đo được), H-63, H-18, H-56, H-36 | không |
| R11d | chuỗi 1 | Giao diện (việc vai D cũ) | #139, #141, H-65 b/f/g, H-67..H-69, FR còn thiếu, T-043; ảnh chụp 1920×1080 | không (ADR-011) |
| Nghiên cứu | song song chuỗi 1 | D3, D5, định dạng kịch bản (việc vai A cũ) | `docs/research/reflow_domain.md` có nguồn (H-64), `scoring.md`, `scenarios.md` | không |
| Tập giữ lại | sau nghiên cứu | ≥ 4 kịch bản, phiên cách ly soạn, leader duyệt | SHA-256 trong `docs/research/holdout-seal.md` | không |
| R11b | chuỗi 2 | Điều 1: chấm theo mã + đề | H-28, loader + injector, tập dev khó (H-29), eval A1–A3 DB sạch, chấm tập giữ lại, ghi run phát lại, A8 LLM thật; audit 5 sau mốc | không |
| R12 | sau audit 5 | Lỗ hổng audit 5, H-60..H-62, H-64, D6, Q5, Q7 → cổng freeze → tag | | không |

Chỉ số mỗi mốc phải đo được khi xong: R11a → A4/A5 LLM thật đo được; R11b → A1–A3 tập dev + A1 tập giữ lại (`TASKS.md`, `docs/eval/criteria.md`).

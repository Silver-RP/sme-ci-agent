# Tiến độ và số đo của plugin auto-dev (plan lớn)

Supervisor cập nhật sau mỗi mốc, lấy số liệu từ báo cáo mốc `.autodev/reports/Mx.md`. Nhật ký task của dự án ở `plan/PROGRESS.md`.

## Chỉ số theo task (mục 9.1 của thiết kế)

| Task | Vòng dev↔review | Verify bị chặn | Kết quả | % hạn mức | Thời gian | Lỗi người dùng phát hiện sau |
|---|---|---|---|---|---|---|
| M1/dev-01 (T-015) | 1 | 0 | PASS | (người dùng điền) | dev ~61s + review ~33s | |
| M1/dev-02 (T-017 p1) | 1 | 0 | PASS | (người dùng điền) | dev ~81s + review ~24s | |
| M1/dev-03 (T-017 p2) | 1 | 0 | PASS | (người dùng điền) | dev ~97s + review ~107s | 2 (domain rỗng; event_id không reset), sửa ở dev-04 |
| M1/dev-04 (T-017 bổ sung) | 1 | 0 | PASS | (người dùng điền) | dev ~80s + review ~35s | |
| M2/dev-01 (T-010) | 2 | 0 | FAIL → PASS | (người dùng điền) | dev ~150s + review ~134s; rework ~158s + review ~77s | |
| M2/dev-02 (T-011) | 1 | 0 | PASS | (người dùng điền) | dev ~199s + review ~306s | |
| M2/dev-03 (T-012) | 1 | 0 | PASS | (người dùng điền) | dev ~838s + review ~84s | |
| M3/dev-01 (M2-c1, M2-c2) | 1 | 0 | PASS | (theo mốc) | dev ~80s | |
| M3/dev-02 (T-013) | 1 | 2* | PASS | (theo mốc) | dev ~225s | |
| M3/dev-03 (T-014) | 1 | 0* | PASS | (theo mốc) | dev ~134s | |

\* M3: hook ghi `BLOCKED_BY_VERIFY` vì hook không có `DATABASE_URL` (Postgres trên máy chiếm cổng 5432), không phải lỗi code; báo cáo mốc ghi số vòng là 0, ở đây quy về 1 (một lần review).

## Theo mốc

| Mốc | Cách chạy | Thời gian | Chi phí ước tính (`total_cost_usd`) | % cửa sổ 5 giờ | Ghi chú |
|---|---|---|---|---|---|
| M1 (4 task) | phiên VS Code | ~10 phút | không đo | ~7% | |
| M2 (3 task) | phiên VS Code | ~36 phút | không đo | ~18% | 1 vòng REWORK |
| M3 (3 task) | **headless từ supervisor** | 12,3 phút, 41 lượt | 1,72 USD | ~16–22% (người dùng ước) | 1 lệnh bị từ chối đúng (xoá file) |
| R4 (4 task) | **chế độ B** (`autodev-run.sh`), worker + supervisor headless | 19 phút (worker 17, supervisor 2) | 2,29 USD (worker 2,00 + supervisor 0,28); thêm 0,31 cho lần no-op | chưa đo | 4 task PASS vòng 1, 162 test (trước 106); verify sạch; supervisor merge #19 |
| R5 (3 task) | **chế độ B**, nối tiếp R4 | 21 phút (worker 18, supervisor 3) | 3,01 USD (worker 2,68 + supervisor 0,33) | chưa đo | T-022, T-024, T-025; dev-02 REWORK 1 vòng (apply SOP rồi crash ở Measure khi thiếu `change_time`); 226 test tracked, verify sạch; supervisor merge #21 |

## Hạn mức (người dùng đo bằng `/usage`)

- 2026-10-07: mỗi lần chạy `/run-milestone` tốn khoảng **7–18% hạn mức của cửa sổ 5 giờ** (gói Pro). Mốc nhỏ (M1, 3–4 task đơn giản) ở mức thấp; M2 (3 task phụ thuộc nhau, 1 vòng REWORK, ~36 phút) ở mức cao. Chưa đo hạn mức tuần.
- 2026-10-08: M3 chạy headless (phiên điều phối Sonnet) tốn ~16–22%, ngang M2 dù nhanh hơn 3 lần (12 phút so với 36 phút). Chạy headless không làm rẻ hơn; chi phí chủ yếu nằm ở developer/reviewer. Đối chiếu: 1,72 USD ước tính ≈ 16–22%.
- 2026-10-08: chế độ B chạy R4 + R5 liền nhau trong 40 phút, tổng 5,29 USD ước tính (cả lần no-op: 5,60), **không chạm hạn mức**, nên chưa kiểm chứng được nhánh chờ reset của `run.py`. Supervisor headless chiếm ~10% chi phí mỗi mốc.
- Hệ quả: một cửa sổ 5 giờ chạy được khoảng 5–14 mốc cỡ này; cần đo thêm hạn mức tuần trước khi làm chế độ B (chạy qua đêm).

## Bài học (đã thành sửa đổi prompt, gate hoặc quy tắc)

- M1/dev-03: reviewer chỉ đọc test có sẵn, bỏ sót `domain` rỗng và bộ đếm `event_id` dùng chung → reviewer phải tự probe trường hợp biên; xác nhận có tác dụng ở dev-04.
- Hook `Stop` trong frontmatter của developer không chạy → chuyển sang `SubagentStop` trong `.claude/settings.json`; thêm `hook_runs` để kiểm chứng (M2: 0 → 4).
- Hook chạy bằng `python3` hệ thống (3.9) trong khi dự án dùng 3.12 → script hook chỉ dùng thư viện chuẩn, tương thích 3.9.
- Lệnh có heredoc, `$(...)`, chuyển hướng ra file luôn bị hỏi quyền (M2: 27/99 lệnh) → quy tắc commit bằng nhiều `-m`, probe bằng `python -c`.
- `state.json` không tách theo mốc → task cùng tên giữa các mốc bị coi là đã xong → lưu `history.<mốc>`.
- 2026-10-07: gộp PR kèm xoá nhánh đã gỡ luôn worktree đang dùng nhánh đó → không xoá khi chưa được duyệt; guard chặn các lệnh xoá.

- Nhận xét của người duyệt về dự án thử (2026-10-07): anomaly trong scenario1 lớn khoảng 10 lần độ nhiễu nên detect bắt ngay (độ trễ 0, 0 báo động giả trên 30 seed). Khi làm T-004 nên thêm một anomaly nhỏ (khoảng 3–4 lần độ nhiễu) để demo thuyết phục hơn.
- M3: worker headless (`claude -p`, Auto, `--permission-prompts none`) chạy trọn mốc, tự mở PR, 1 lệnh bị từ chối (có `rm` file) → developer chuyển sang cách khác, đúng ý "không xoá khi chưa duyệt".
- M3: Postgres cài trên máy chiếm `127.0.0.1:5432` trước container Docker → test DB không vào được container; developer tự dựng container tạm `sme-dev02-pg` (cổng 55432). Cổng verify cần biến môi trường riêng cho từng máy; developer không được tự tạo dịch vụ ngoài (container, DB) mà phải dừng và báo.
- M3: phiên điều phối ghi `round` = 0 cho task PASS ở lần review đầu → quy ước lại: vòng 1 = lần review đầu.
- M3 (dự án): `correlate` chỉ có tín hiệu cho `wrong_setpoint` và `material_batch`; nhóm people (thay ca đêm) và `ambient_temperature` là `no_data`. Cần cho Investigate (T-020) và T-004.

- R4: lần chạy đầu của worker là no-op (worktree chưa cập nhật từ origin/main nên thiếu plan/R4.md, exit 0 sau 40 giây). Runner cần tạo `milestone/<Rx>` từ origin/main trước khi giao và coi "exit 0 không PR/báo cáo" là lỗi. Lần sau worker chạy đủ.
- R4: developer dev-02 dùng script Python inline sửa code (trái quy ước), reviewer vẫn bắt được kết quả đúng; `apply_sop` chấp nhận `approved_by='llm'` (chuyển thành tiêu chí 5 của R5/dev-02).
- R5: reviewer bắt đúng lỗi thứ tự (apply trước khi kiểm tra `change_time`) ở dev-02 vòng 1. Supervisor probe: `parse_decision` chặn `llm/agent/system` nhưng chỉ là deny-list (`bot`, `claude` lọt); `apply_sop` gọi trực tiếp vẫn chỉ chặn `agent/system`, chưa chặn `llm`. Ghi vào việc mở.
- R5: worktree supervisor có file rác `* 2.py` (untracked, bản sao) làm `verify.py` báo 7 lỗi lint N999 và pytest chạy 282 thay vì 226; không thuộc PR. Cần người dùng duyệt xoá.
- R5: nguyên nhân file `* 2.py`: thư mục Desktop của máy này đồng bộ iCloud Drive, iCloud tạo bản sao "tên 2" khi xung đột. Nên chuyển repo và worktree ra ngoài Desktop/Documents (ví dụ `~/dev/`), hoặc tắt đồng bộ Desktop.
- P4 chạy thật: runner chạy `nohup` tách khỏi phiên chat nên phiên chat không được báo khi xong; người dùng phải tự hỏi. Thêm `.autodev/watch.sh` (chỉ đọc) để xem tiến độ; cần thêm thông báo khi runner dừng (macOS notification) và tuỳ chọn để phiên chat đang mở theo dõi runner (Monitor / chạy nền có báo).

- R6 (dashboard Next.js, T-016 + T-026): worker headless, 3 task PASS vòng 1, ~20 phút (03:21 → 03:41 JST), PR #27 merge. Supervisor chạy lại verify sạch: pytest 226, vitest 34, yarn lint/build đạt. Chưa đo % hạn mức (điền từ /usage). Điều chỉnh (a): `dashboard/.yarnrc` `ignore-engines true` (Node 22.12 < 22.13); `POST /runs` chạy đồng bộ tới interrupt đầu nên SSE mở sau khi có `run_id`. Chưa chạy thử uvicorn thật với dashboard. Gợi ý nhỏ: chặn nút Approve/Reject khi `decided_by` trống; test đối chiếu validator tay với `events.json`; `docs/schema/payloads.md` chưa có.
- R7 (M3 end-to-end, T-031 + chuẩn bị T-030): worker headless, 4 task PASS vòng 1, ~36 phút (13:21 → 13:57Z), PR #31 merge. Supervisor chạy lại: verify sạch, pytest 262, vitest 38. Kiểm độc lập: `scripts/data_report.py` khớp ground truth (A1, A2 phát hiện, FP1 không báo, 0 báo động giả); `run_scenario.py` trên DB chưa migrate lỗi thiếu bảng audit_log (docstring có ghi cần migration, README chưa; demo.sh tự migrate). Chưa đo % hạn mức. (c) R7-c1 (anomaly seed 42 kéo đến hết horizon nên demo không tới Learn): chưa quyết, để leader.
- R7 (sau merge, phiên supervisor tương tác): `uv run alembic upgrade head` (dòng đầu của `demo.sh`) lỗi `ModuleNotFoundError: backend` vì test chỉ gọi alembic qua Python API trong pytest; sửa ở #34. Rà soát chỉ đọc sau đó thấy tiêu chí cấp mốc 3 của R7 (khoá nút duyệt khi tên không hợp lệ) chưa đạt ở UI. → Thêm `smoke` vào `.autodev/config.json` + `verify.py --smoke` (chạy đúng lệnh người dùng gõ); supervisor bắt buộc chạy smoke và lập bảng "tiêu chí cấp mốc → lệnh/test → kết quả" tự kiểm; reviewer chạy smoke khi task đụng scripts/README.
- Hardening runner (2026-10-08): supervisor chạy model/effort riêng (`AUTODEV_SUPERVISOR_MODEL`=opus, `AUTODEV_SUPERVISOR_EFFORT`=medium; worker sonnet); chỉ tính PR mốc tạo trong lần chạy này (tránh khớp PR cũ cùng tên); runner tự merge PR hồ sơ chỉ sửa `docs/autodev/**` (supervisor bị chặn merge 2 lần: #22, #32); chỉ coi là hạn mức khi bước lỗi; baseline không bao giờ ghi khoá `exit:*`; guard chặn thêm: merge kèm cờ xoá nhánh dạng ngắn, xoá đệ quy có cờ tách rời, huỷ toàn bộ thay đổi bằng restore/checkout, find kèm xoá, tự ghi baseline.
- R8 ("mạch chặt": Measure đúng, run lỗi dừng gọn, bền LLM thật, duyệt ràng buộc, T-040): worker headless, 5 task PASS vòng 1, ~67 phút (14:43 → 15:50Z), PR #37 merge. Lần đầu supervisor chạy Opus (medium) với smoke bắt buộc. Supervisor chạy lại: verify sạch, `--smoke` sạch (gồm `demo.sh --check`), pytest 371, vitest 56. Kiểm độc lập: `build_post_change_tables` seed 7 (sửa đúng → 0,020 ≈ baseline; sửa sai → 0,063 giữ mức anomaly; bảng nguồn không đổi); `extract_json_object` đúng với ngoặc trong chuỗi, khối `{...}` thừa, `"false"`; `run_scenario.py` mặc định, `--seed 7`, `--on-proposal reject|revise` đều tới `learning_saved` → `run_finished`, exit 0. Điểm yếu: `fix_addresses_cause` khớp từ khoá nên câu phủ định ("Setpoint is NOT the cause…") vẫn tính là sửa đúng; LLM giả không còn kịch bản đi nhánh rollback. (c) supervisor tự quyết: tiêu chí cấp mốc 2(b) (e2e uvicorn nhánh rollback) và assert `learning_saved` qua uvicorn chuyển sang R9 (R8-c2); hành vi đã có test mức graph/TestClient. Quy trình: developer vẫn sửa file bằng `python3 - <<EOF`/`sed -i` (dev-03..05). Chưa đo % hạn mức.
- R9 ("làm thật" điều 1–2, theo audit 2026-10-09): worker headless (2 phiên: dev-01/02, rồi dev-03..06), 6 task PASS vòng 1, PR #44 merge. Mỗi H-xx có commit đỏ trước khi sửa. Supervisor Opus chạy lại (chế độ B, --review-only), bảng tiêu chí:
  | Tiêu chí cấp mốc R9 | Lệnh / test supervisor tự chạy | Kết quả |
  |---|---|---|
  | 1. verify + smoke sạch | `python3 .autodev/verify.py`; `python3 .autodev/verify.py --smoke`; `uv run pytest -q` | sạch; smoke 4/4 ok (alembic, run_scenario, data_report, demo.sh --check); 412 passed |
  | 2. Measure theo thay đổi thật | `tests/test_measure_h06.py` (11 test) + thử biên của supervisor | xanh; giả thuyết phủ định + đổi 180 → đạt (từ khoá không quyết định); 160 và 220 → không đạt; tham số/máy khác → không đạt |
  | 3. eval_rootcause | `uv run python scripts/eval_rootcause.py` | exit 0; right 100% / wrong 0% / unsure ask 100% |
  | 4. e2e uvicorn chuỗi rollback | `tests/test_e2e_rollback_r9.py::test_wrong_fix_then_rollback_then_right_fix_completes_over_uvicorn` | xanh (SSE: rollback_done → hypothesis_updated → … → learning_saved → run_finished completed) |
  | 5. H-xx có test xanh | 13 test tên trong báo cáo (`-k` chạy riêng) + `test_domain_config` (H-10, H-22) | 13 passed; test_domain_config xanh |
  | 6. Không sửa dashboard/app, components | `git diff origin/main --stat -- dashboard/app dashboard/components docs/schema/events.json dashboard/lib` | rỗng |
  Kiểm độc lập (thử biên): `value` NaN → `DataError` khi ghi JSON vào Postgres (worker đã ghi trong báo cáo; chuyển R10); `value` thiếu → yêu cầu LLM sửa lại rồi lỗi; `"180"` dạng chuỗi được chấp nhận. Đề xuất (c) của worker: chưa đưa eval vào smoke (eval chỉ chứng minh graph + bộ chấm, LLM giả); xoá `docs/schema/examples/run-reject-error.json` chờ người dùng duyệt; `parse_bool("maybe")`, `fix_addresses_cause` không dùng, `fake_metrics.py` còn "M02" → R10. Chưa đo chi phí và % hạn mức.
- R9h (sửa nhanh để T-030 chạy được: SDK `anthropic` 1.11 bỏ `temperature`; script `--llm real` không nạp `.env`): chế độ B, worker 2 task PASS vòng 1, ~20 phút (22:01 → 22:21 JST), 1,15 USD worker; PR #49 merge. Supervisor Opus chạy lại:
  | Tiêu chí cấp mốc R9h | Lệnh / test supervisor tự chạy | Kết quả |
  |---|---|---|
  | 1. verify + smoke sạch | `python3 .autodev/verify.py`; `--smoke`; `uv run pytest -q` | sạch; smoke 4/4 ok; 421 passed |
  | 2. Test chữ ký SDK thật, đỏ trên main | chép `backend/agent/llm.py` của main vào nhánh mốc, chạy `pytest tests/test_robust_r8.py -k signature`, rồi trả lại | đỏ: `keys not accepted by installed anthropic SDK: {'temperature'}`; với code mốc: xanh |
  | 3. Thiếu key báo rõ, không traceback | bỏ `ANTHROPIC_API_KEY`, `MODEL_REASONING` khỏi env, chạy `eval_rootcause.py --llm real --seeds 1` và `run_scenario.py --llm real`; `pytest tests/test_scripts_env_r9h.py` | một dòng "Missing ANTHROPIC_API_KEY, MODEL_REASONING…", exit 2 (cả hai script); 7 passed |
  Kiểm độc lập: chỉ có key, thiếu model → chỉ báo "Missing MODEL_REASONING", exit 2; `LLM_EFFORT=" HIGH "` → `high`, rỗng → `medium`; client `anthropic` thật trỏ tới cổng đóng: Sonnet (có `output_config`) và Haiku 4.5 (không có) đều tới `APIConnectionError`, tức SDK nhận đủ tham số, không còn `TypeError`; eval LLM giả không còn cảnh báo deserializing. Ngoài phạm vi ghi trong plan: `backend/api/app.py` đổi 2 dòng sang `memory_checkpointer()` (cùng mục đích dev-02, supervisor chấp nhận như (a)). Non-blocking → R10: `postgres_checkpointer` chưa dùng allowlist; tiền tố Haiku chỉ khớp `claude-haiku-4-5`.
- R9i (đề xuất của LLM phải đủ `action` + `sop_proposal` và hợp lệ; H-27, H-30, H-41, H-42): chế độ B, worker 2 task PASS vòng 1, ~25 phút, 1,60 USD worker; PR #55 merge. Supervisor Opus chạy lại (`--review-only`):
  | Tiêu chí cấp mốc R9i | Lệnh / test supervisor tự chạy | Kết quả |
  |---|---|---|
  | 1. verify + smoke sạch | `python3 .autodev/verify.py`; `--smoke`; `uv run pytest -q` | sạch; smoke 4/4 ok; 442 passed |
  | 2. Có action, thiếu sop_proposal → sửa lại → `measured`; hỏng quá giới hạn → error retryable, không `completed` | `tests/test_proposal_complete_r9i.py::test_action_without_sop_is_sent_back_then_measured`, `..._twice_is_a_retryable_error_not_completed`; thử biên qua API (dưới) | xanh trên nhánh, đỏ trên main; API trả `state=error`, `retryable=true` |
  | 3. Có sop_proposal, thiếu action (H-27) → tương tự, không có bản SOP mới chưa đo | `test_sop_without_action_is_sent_back_then_measured`, `test_sop_without_action_twice_makes_no_new_sop_version`, `test_act_refuses_a_proposal_without_action_and_writes_no_sop` | xanh trên nhánh, đỏ trên main; `sop_versions` rỗng |
  | 4. action NaN/inf/ngoài min–max YAML/máy lạ (H-30) → sửa lại; không NaN trong audit/SSE | `tests/test_improve_action_range_h30.py` (11 test, gồm `test_range_comes_from_config`, biên min/max); thử biên `NaN`/`Infinity` dạng literal JSON | xanh trên nhánh, 10/11 đỏ trên main; literal bị từ chối; `grep NaN docs/schema/examples/*` rỗng |
  | 5. `test_measure_h06.py` bỏ khoá hành vi cũ | đọc `tests/test_measure_h06.py:62–72` | `action=None` kèm SOP giờ phải ném `ProposalError`, không còn `completed` |
  Cách kiểm đỏ trên main: chép 2 file test mới vào checkout `origin/main`, chạy → 20 failed / 1 passed (test bỏ kiểm máy khi không có anomaly), rồi chuyển file ra thư mục tạm. Thử biên độc lập: literal `NaN`, `Infinity` trong JSON của LLM → `ProposalError`; API hai lần thiếu `sop_change` → `error`, `retryable: true`, thông điệp nêu rõ thiếu gì. Fixture `run-happy.json`: `proposal_created` → `kpi_measured` (measured) → `learning_saved`. Prompt Improve không hard-code tên tham số (ví dụ dùng placeholder). Không đổi `events.json`, `dashboard/`. Non-blocking (worker gợi ý): unit test `action_level` máy lạ ở tầng Measure; Act tự vệ ném `ValueError` → run `error` (retryable theo số lần retry chung).
- R9ih (sửa nhanh H-43: prompt Improve có danh mục SOP): chế độ B, worker 1 task PASS vòng 1, ~12 phút, 0,64 USD worker; PR #58 merge. Supervisor Opus chạy lại (`--review-only`):
  | Tiêu chí cấp mốc R9ih | Lệnh / test supervisor tự chạy | Kết quả |
  |---|---|---|
  | 1. verify + smoke sạch | `python3 .autodev/verify.py`; `--smoke`; `uv run pytest -q` | sạch; smoke 4/4 ok; 448 passed |
  | 2. Prompt Improve chứa id, version hiệu lực (tính `sop_versions`), nội dung SOP; lấy từ config/DB | `tests/test_improve_sop_catalog_h43.py::test_prompt_lists_every_sop_with_id_version_and_content_from_config`, `test_prompt_shows_the_new_version_after_a_sop_was_applied`, `test_prompt_cuts_long_sop_content_by_config_limit`; đọc diff `sop_catalog` (dùng `repo.get_sop_version` như `current_sop`) | xanh trên nhánh, đỏ khi thay `improve.py` bằng bản main |
  | 3. `sop_id` lạ → thông báo nêu id hợp lệ; sai rồi đúng → `measured` | `test_unknown_sop_id_is_sent_back_with_valid_ids_then_measured`, `test_unknown_sop_id_twice_error_lists_valid_ids` | xanh trên nhánh, đỏ trên main (6/6 test H-43 đỏ với `improve.py` của main) |
  Thử biên độc lập (test tạm ở scratchpad, không commit): DB có bản mới cho 1 SOP dài 5000 ký tự → danh mục cắt đúng giới hạn config, đuôi `...(truncated)`, SOP còn lại giữ bản config; gọi lặp lại cho kết quả giống nhau. Non-blocking: chưa có test riêng cho nhánh fallback config khi DB trống (đã gián tiếp qua test 1); khi DB và config cùng trống thì prompt nói "phải là một trong []" (không xảy ra với YAML hiện tại).

<!-- metrics:start (tự sinh bởi .autodev/metrics.py, đừng sửa tay) -->
## Số đo plugin B1–B5 (định nghĩa: ROADMAP bảng B)

### B1 Lỗi lọt qua review (lỗ hổng mới mức cao + vừa / task trong phạm vi audit; ngưỡng ≤ 0,5)

| Audit | Phạm vi | Lỗ hổng mới cao+vừa | Task | B1 |
|---|---|---|---|---|
| 2026-10-09.md | R7, R8 | 15 | 9 | 1,67 |
| 2026-10-09_2.md | R9, R9h | 14 | 8 | 1,75 |

### B2 Độ chặt review: 2/37 task cần ≥ 2 vòng (5%). Đọc cùng B1: B2 thấp mà B1 cao là reviewer lỏng.

### B3–B5 theo mốc (B3: thực tế / ước tính, 1,0 = trong khoảng, ngưỡng 0,5–2; B4: số lần runner dừng, ngưỡng 0; B5: chi phí trên task)

| Mốc | Task | Phút | USD | Phút/task | USD/task | Lượt | B3 phút | B3 USD | B4 dừng |
|---|---|---|---|---|---|---|---|---|---|
| M1 | 4 | 0 | 0,00 | 0,0 | 0,00 | 0 | – | – | 0 |
| M2 | 3 | 0 | 0,00 | 0,0 | 0,00 | 0 | – | – | 0 |
| M3 | 3 | 0 | 0,00 | 0,0 | 0,00 | 0 | – | – | 0 |
| R4 | 4 | 21 | 2,59 | 5,3 | 0,65 | 86 | – | – | 1 |
| R5 | 3 | 21 | 3,01 | 7,1 | 1,00 | 26 | – | – | 0 |
| R6 | 3 | 23 | 1,81 | 7,8 | 0,60 | 63 | – | – | 0 |
| R7 | 4 | 40 | 2,58 | 10,1 | 0,65 | 61 | – | – | 0 |
| R8 | 5 | 71 | 6,40 | 14,2 | 1,28 | 71 | – | – | 0 |
| R9 | 6 | 83 | 7,18 | 13,8 | 1,20 | 108 | – | – | 1 |
| R9h | 2 | 25 | 2,02 | 12,7 | 1,01 | 59 | – | – | 0 |
| R9i | 2 | 35 | 2,90 | 17,5 | 1,45 | 80 | – | – | 0 |
| R9ih | 1 | 18 | 1,45 | 17,9 | 1,45 | 43 | – | – | 0 |

Mốc trước R4 chạy chế độ A (không có `runs/*.json`) nên phút/USD = 0.
<!-- metrics:end -->

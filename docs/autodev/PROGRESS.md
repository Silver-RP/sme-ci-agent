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

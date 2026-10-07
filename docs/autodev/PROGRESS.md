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
| R4 (4 task) | worker headless (chạy lần 2 sau lần no-op) | ~18 phút | chưa có (log runs/ không có trên máy supervisor) | chưa đo | 4 task PASS vòng 1, 162 test (trước 106); verify sạch; supervisor merge #19 |
| R5 (3 task) | worker headless, supervisor headless | ~18 phút | chưa có | chưa đo | T-022, T-024, T-025; dev-02 REWORK 1 vòng (apply SOP rồi crash ở Measure khi thiếu `change_time`); 226 test tracked, verify sạch; supervisor merge #21 |

## Hạn mức (người dùng đo bằng `/usage`)

- 2026-10-07: mỗi lần chạy `/run-milestone` tốn khoảng **7–18% hạn mức của cửa sổ 5 giờ** (gói Pro). Mốc nhỏ (M1, 3–4 task đơn giản) ở mức thấp; M2 (3 task phụ thuộc nhau, 1 vòng REWORK, ~36 phút) ở mức cao. Chưa đo hạn mức tuần.
- 2026-10-08: M3 chạy headless (phiên điều phối Sonnet) tốn ~16–22%, ngang M2 dù nhanh hơn 3 lần (12 phút so với 36 phút). Chạy headless không làm rẻ hơn; chi phí chủ yếu nằm ở developer/reviewer. Đối chiếu: 1,72 USD ước tính ≈ 16–22%.
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

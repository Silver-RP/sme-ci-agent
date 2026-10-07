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

## Hạn mức (người dùng đo bằng `/usage`)

- 2026-10-07: mỗi lần chạy `/run-milestone` tốn khoảng **7–18% hạn mức của cửa sổ 5 giờ** (gói Pro). Mốc nhỏ (M1, 3–4 task đơn giản) ở mức thấp; M2 (3 task phụ thuộc nhau, 1 vòng REWORK, ~36 phút) ở mức cao. Chưa đo hạn mức tuần.
- Hệ quả: một cửa sổ 5 giờ chạy được khoảng 5–14 mốc cỡ này; cần đo thêm hạn mức tuần trước khi làm chế độ B (chạy qua đêm).

## Bài học (đã thành sửa đổi prompt, gate hoặc quy tắc)

- M1/dev-03: reviewer chỉ đọc test có sẵn, bỏ sót `domain` rỗng và bộ đếm `event_id` dùng chung → reviewer phải tự probe trường hợp biên; xác nhận có tác dụng ở dev-04.
- Hook `Stop` trong frontmatter của developer không chạy → chuyển sang `SubagentStop` trong `.claude/settings.json`; thêm `hook_runs` để kiểm chứng (M2: 0 → 4).
- Hook chạy bằng `python3` hệ thống (3.9) trong khi dự án dùng 3.12 → script hook chỉ dùng thư viện chuẩn, tương thích 3.9.
- Lệnh có heredoc, `$(...)`, chuyển hướng ra file luôn bị hỏi quyền (M2: 27/99 lệnh) → quy tắc commit bằng nhiều `-m`, probe bằng `python -c`.
- `state.json` không tách theo mốc → task cùng tên giữa các mốc bị coi là đã xong → lưu `history.<mốc>`.
- 2026-10-07: gộp PR kèm xoá nhánh đã gỡ luôn worktree đang dùng nhánh đó → không xoá khi chưa được duyệt; guard chặn các lệnh xoá.

- Nhận xét của người duyệt về dự án thử (2026-10-07): anomaly trong scenario1 lớn khoảng 10 lần độ nhiễu nên detect bắt ngay (độ trễ 0, 0 báo động giả trên 30 seed). Khi làm T-004 nên thêm một anomaly nhỏ (khoảng 3–4 lần độ nhiễu) để demo thuyết phục hơn.


# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Trạng thái hiện tại (2026-10-08)
- Mốc plugin: **P3 gần xong**. M3 (M2-c1/c2, T-013, T-014) chạy bằng worker headless trong 12,3 phút, cả 3 task PASS; supervisor đã chạy lại verify (106 test pass) và probe T-014 với seed 7 (chỉ đọc, 1 audit mỗi lần gọi, `correlate` đúng).
- PR #14 (M3): supervisor quyết định merge; nếu chưa merge được do lỗi GitHub thì merge lại (`gh pr merge 14 --merge`, không xoá nhánh).
- **Môi trường trên máy này:** Postgres cài trên máy (PID cũ 14691) chiếm `127.0.0.1:5432`, nên `localhost:5432` không vào container `sme-ci-agent-autodev-db-1`. Developer đã dựng container tạm `sme-dev02-pg` (cổng 55432). Chạy test DB cần `DATABASE_URL=postgresql+psycopg://sme:sme@localhost:55432/sme_ci`. Chờ người dùng chọn cách xử lý (dừng Postgres trên máy, hoặc đổi cổng qua biến môi trường riêng từng máy) và có xoá container tạm hay không.
- Worktree: `../sme-ci-agent-autodev` trên nhánh `milestone/M3` (đã đẩy lên GitHub), có `.claude/settings.local.json` (Auto, danh sách lệnh, tắt Superpowers).
- Lệnh chạy worker: trong worktree, `claude -p "/run-milestone Mx" --model sonnet --permission-mode auto --permission-prompts none --output-format json` (chạy nền). `claude` là wrapper ở `~/.local/bin/claude` trỏ tới bản đi kèm extension VS Code.

## Quyền và quy tắc đang áp dụng
- Bảng quyền supervisor: thiết kế mục 6.15. Supervisor tự merge PR mốc sau khi chạy lại verify.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến).
- Ưu tiên auto-dev nhưng không làm sai mục tiêu của SME CI Agent (ROADMAP, nguyên tắc ưu tiên).

## Việc mở / cần để ý
- Cổng verify cần biến môi trường riêng từng máy (xem trên); hook `SubagentStop` không có `DATABASE_URL` nên ghi `BLOCKED_BY_VERIFY` giả.
- P4: hướng xử lý hết hạn mức đã được duyệt (ROADMAP). Chưa gặp hết hạn mức ở headless lần nào.
- Chưa đo % hạn mức của M3 và hạn mức tuần.
- Guard so khớp theo chữ: commit message hay chuỗi thử chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.
- Dự án: `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature` (cần cho T-020, T-004).

## Mốc kế tiếp đề xuất
- Plugin: đóng P3 (biến môi trường cho verify), rồi P4.
- Dự án (TASKS.md M2): T-020 System prompt + Investigate, T-021 Ask + resume, T-023 propose/apply SOP + measure. Chọn mốc để thử được P4 (nhiều mốc liên tiếp, có thể chạm hạn mức).

## Lịch sử ngắn
- P1 (M1), P2 (M2) xong; P3 (M3) gần xong. Chi tiết trong `PROGRESS.md`.

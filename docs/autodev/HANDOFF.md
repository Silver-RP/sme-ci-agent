# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Trạng thái hiện tại (2026-10-08)
- Mốc plugin: **P3 xong**. M3 (M2-c1/c2, T-013, T-014) chạy bằng worker headless trong 12,3 phút, cả 3 task PASS; supervisor đã chạy lại verify (106 test pass) và probe T-014 với seed 7 (chỉ đọc, 1 audit mỗi lần gọi, `correlate` đúng).
- PR #14 (M3) đã merge (2026-10-08, sau một lúc GitHub trả HTTP 500 cho mọi thao tác ghi; thử lại sau là được). M3 tốn ~16–22% cửa sổ 5 giờ.
- **Môi trường trên máy này:** đã dừng dịch vụ Homebrew `postgresql@14` theo yêu cầu người dùng (bật lại: `brew services start postgresql@14`; dữ liệu giữ nguyên). Cổng 5432 giờ là container `sme-ci-agent-autodev-db-1`; test chạy với URL mặc định. Container tạm `sme-dev02-pg` (cổng 55432, developer tự dựng ở M3) vẫn còn, chờ người dùng quyết có xoá không.
- Worktree: `../sme-ci-agent-autodev` trên nhánh `milestone/M3` (đã đẩy lên GitHub), có `.claude/settings.local.json` (Auto, danh sách lệnh, tắt Superpowers).
- Lệnh chạy worker: trong worktree, `claude -p "/run-milestone Mx" --model sonnet --permission-mode auto --permission-prompts none --output-format json` (chạy nền). `claude` là wrapper ở `~/.local/bin/claude` trỏ tới bản đi kèm extension VS Code.

## Quyền và quy tắc đang áp dụng
- Bảng quyền supervisor: thiết kế mục 6.15. Supervisor tự merge PR mốc sau khi chạy lại verify.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến).
- Ưu tiên auto-dev nhưng không làm sai mục tiêu của SME CI Agent (ROADMAP, nguyên tắc ưu tiên).

## Việc mở / cần để ý
- Máy nào cần đổi cổng DB: `DB_PORT` cho docker compose và `.autodev/env.local.json` cho verify (mẫu `.autodev/env.local.example.json`).
- P4: hướng xử lý hết hạn mức đã được duyệt (ROADMAP). Chưa gặp hết hạn mức ở headless lần nào.
- Chưa đo hạn mức tuần.
- Guard so khớp theo chữ: commit message hay chuỗi thử chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.
- Dự án: `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature` (cần cho T-020, T-004).

## Mốc kế tiếp đề xuất
- Plugin: P4 (chế độ B, xử lý hết hạn mức).
- Dự án (TASKS.md M2): T-020 System prompt + Investigate, T-021 Ask + resume, T-023 propose/apply SOP + measure. Chọn mốc để thử được P4 (nhiều mốc liên tiếp, có thể chạm hạn mức).

## Lịch sử ngắn
- P1 (M1), P2 (M2), P3 (M3) xong. Chi tiết trong `PROGRESS.md`.

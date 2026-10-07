# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Trạng thái hiện tại (2026-10-07)
- Mốc plugin đang làm: **P3** (supervisor, worker headless, verify có Postgres, HANDOFF).
- Mốc dự án dùng để thử: **plan/M3.md** (M2-c1/c2, T-013, T-014). Chưa chạy.
- Worktree: `../sme-ci-agent-autodev` trên nhánh `milestone/M3`, có `.claude/settings.local.json` (Auto, danh sách lệnh, tắt Superpowers). Postgres: container `sme-ci-agent-autodev-db-1`, cổng 5432.
- Worker chạy headless từ supervisor: `claude -p "/run-milestone M3" --permission-mode auto --permission-prompts none --output-format json` trong worktree (xem `/supervise`).

## Quyền và quy tắc đang áp dụng
- Bảng quyền supervisor: thiết kế mục 6.15. Supervisor tự merge PR mốc sau khi chạy lại verify.
- Không xoá file, thư mục, nhánh, worktree nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến).
- Ưu tiên auto-dev nhưng không làm sai mục tiêu của SME CI Agent (ROADMAP, nguyên tắc ưu tiên).

## Việc mở / cần để ý
- Chưa biết `claude -p` xử lý thế nào khi hết hạn mức (đợi hay thoát): ghi lại khi gặp.
- Chưa đo hạn mức tuần.
- Guard so khớp theo chữ: commit message hay chuỗi thử có chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.

## Lịch sử ngắn
- P1 (M1) và P2 (M2) xong; chi tiết trong `PROGRESS.md`.

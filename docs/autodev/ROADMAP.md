# Lộ trình plugin auto-dev (plan lớn)

Mục tiêu chính: xây và hoàn thiện plugin auto-dev (thiết kế: `auto-dev-review-design.md`). SME CI Agent là dự án chạy thử.

## Nguyên tắc ưu tiên (người dùng chốt 2026-10-07)
1. **Ưu tiên auto-dev.** Chọn mốc dự án sao cho thử được tính năng plugin còn thiếu.
2. **Không làm sai mục tiêu của SME CI Agent.** Mỗi mốc dự án vẫn phải đúng TASKS.md, docs/PLAN.md, CLAUDE.md và DoD của task; chất lượng không được sơ sài vì là "mốc thử". SME CI Agent chạy tốt thì mới chứng minh được auto-dev hiệu quả.
3. Thử nghiệm không được đổi phạm vi hay mục tiêu của dự án; nếu một tính năng plugin cần điều kiện mà dự án không có, ghi thành câu hỏi cho người dùng thay vì bẻ dự án theo plugin.

## Tách hai luồng
| | Plan lớn (plugin) | Plan nhỏ (SME CI Agent) |
|---|---|---|
| File | `docs/autodev/` (ROADMAP, PROGRESS, HANDOFF, thiết kế) | `plan/Mx.md`, `plan/PROGRESS.md`, TASKS.md |
| Ai sửa | supervisor | worker (developer, reviewer, `/run-milestone`) |
| File code | `.claude/`, `.autodev/*.py`, `.autodev/config.json` | code dự án, `.autodev/state.json`, `reviews/`, `reports/` |
| Nhánh | `chore/autodev-*` | `milestone/*` |

Hai luồng không sửa chung file nên chạy song song không xung đột. Liên kết: mỗi mốc plugin dưới đây ghi mốc dự án dùng để thử; mỗi `plan/Mx.md` ghi dòng "Phục vụ plugin: Px".

## Quy ước tên mốc
- Mốc **plugin**: P1, P2… (file này).
- Mốc **auto-dev chạy trên dự án** (`plan/`): từ 2026-10-08 đặt tên **R4, R5…** (R = run) để không trùng với mốc M0–M4 trong TASKS.md của team. Các mốc đã chạy trước đó giữ tên cũ: `plan/M1.md`, `M2.md`, `M3.md`.
- Nhánh: `milestone/R4`… Mỗi `plan/Rx.md` ghi mã T-0xx của TASKS.md.

## Các mốc plugin

| Mốc | Tính năng cần chứng minh | Thử qua | Trạng thái |
|---|---|---|---|
| P1 | Chế độ A: developer ⇄ reviewer, verify + baseline, guard, plan Mx/dev-xx | plan/M1.md | ✅ Xong (2026-10-06); phát hiện reviewer bỏ sót trường hợp biên → sửa prompt |
| P2 | Vòng FAIL → REWORK, hook `SubagentStop` chạy thật, task phụ thuộc nhau | plan/M2.md | ✅ Xong (2026-10-07) |
| P3 | Supervisor (vai con người) tự giao mốc, duyệt, merge; worker headless (`claude -p`) mỗi mốc một phiên mới; verify khi test cần Postgres; HANDOFF giữa các phiên supervisor | plan/M3.md | ✅ Xong (2026-10-08): worker headless chạy trọn mốc, supervisor duyệt + merge PR #14; cổng verify có biến môi trường riêng từng máy (`.autodev/env.local.json`, `DB_PORT`) |
| P4 | Chế độ B: script `autodev-run.sh` chạy nhiều mốc liên tiếp (supervisor headless + worker headless). Xử lý hết hạn mức: (1) nhận biết từ kết quả JSON / sự kiện `api_retry` (`rate_limit`), lấy giờ reset; (2) chờ đến giờ reset + 5 phút; (3) chạy lại `/run-milestone` bằng phiên mới, tiếp tục từ `state.json` (giữa vòng review thì chỉ chạy lại reviewer); (4) hết hạn mức tuần thì dừng, ghi HANDOFF, báo người dùng. Tự ghi `total_cost_usd` mỗi mốc và quy đổi ra % hạn mức; kiểm tra ngân sách trước khi bắt đầu mốc; thông báo một chiều (Q1) | plan/R4.md + plan/R5.md (chạy nối tiếp) | 🔄 Đang làm: `.autodev/run.py` + `.autodev/autodev-run.sh` đã viết, 10 test với `claude` giả (hết hạn mức → chờ → chạy lại; hết hạn mức tuần → dừng; lỗi → thử lại 1 lần). Chạy thật lần đầu: R4 xong (merge #19, ~18 phút, 4 task PASS); lần đầu no-op do worktree chưa cập nhật (runner cần sửa). R5 xong (merge #21, 3 task PASS, 1 vòng REWORK). Hai mốc liền nhau 40 phút, 5,29 USD, không chạm hạn mức. Có `.autodev/watch.sh` để xem tiến độ; guard xét đúng thư mục đích của `cd`/`git -C`. Còn: sửa runner (worktree về `origin/main`, no-op → exit 4, thông báo khi dừng), kiểm chứng nhánh chờ reset khi gặp hạn mức thật. |
| P5 | Đóng gói plugin: tách sang repo riêng, `plugin.json`, cài bằng marketplace, onboarding dự án thứ hai | dự án thứ hai | ⏳ |

## Để sau (người dùng chốt 2026-10-08)
- Đo độ dài phiên: ghi `num_turns`, token, thời gian của mỗi phiên headless vào PROGRESS; ngưỡng cảnh báo mốc quá to.
- Đo chất lượng theo thời gian: số vòng review, số lần verify chặn, lỗi tìm ra sau merge.
- Hook trước khi Claude Code nén ngữ cảnh (cần kiểm chứng tên và cú pháp) để nhắc cập nhật HANDOFF và mở phiên mới.

## Tiêu chí "plugin đạt" cho từng mốc
- Không cần người dùng chuyển tin giữa các phiên trong suốt một mốc.
- Lỗi người dùng phát hiện sau khi mốc đã merge: 0, hoặc mỗi lỗi dẫn tới một sửa đổi prompt/gate.
- Hạn mức mỗi mốc được ghi lại trong `PROGRESS.md`.

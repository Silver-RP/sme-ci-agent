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

## Các mốc plugin

| Mốc | Tính năng cần chứng minh | Thử qua | Trạng thái |
|---|---|---|---|
| P1 | Chế độ A: developer ⇄ reviewer, verify + baseline, guard, plan Mx/dev-xx | plan/M1.md | ✅ Xong (2026-10-06); phát hiện reviewer bỏ sót trường hợp biên → sửa prompt |
| P2 | Vòng FAIL → REWORK, hook `SubagentStop` chạy thật, task phụ thuộc nhau | plan/M2.md | ✅ Xong (2026-10-07) |
| P3 | Supervisor (vai con người) tự giao mốc, duyệt, merge; worker headless (`claude -p`) mỗi mốc một phiên mới; verify khi test cần Postgres; HANDOFF giữa các phiên supervisor | plan/M3.md | 🔄 Đang làm |
| P4 | Chế độ B: script chạy nhiều mốc liên tiếp (supervisor headless + worker headless), xử lý hết hạn mức (chờ đến giờ reset rồi chạy tiếp), thông báo (Q1) | (chọn sau) | ⏳ |
| P5 | Đóng gói plugin: tách sang repo riêng, `plugin.json`, cài bằng marketplace, onboarding dự án thứ hai | dự án thứ hai | ⏳ |

## Tiêu chí "plugin đạt" cho từng mốc
- Không cần người dùng chuyển tin giữa các phiên trong suốt một mốc.
- Lỗi người dùng phát hiện sau khi mốc đã merge: 0, hoặc mỗi lỗi dẫn tới một sửa đổi prompt/gate.
- Hạn mức mỗi mốc được ghi lại trong `PROGRESS.md`.

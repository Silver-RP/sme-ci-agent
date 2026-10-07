# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- Hai plan lồng nhau: **plan lớn** = xây plugin auto-dev (`docs/autodev/`), **plan nhỏ** = dự án SME CI Agent dùng để thử (`plan/`, TASKS.md). Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD (ROADMAP, "Nguyên tắc ưu tiên").
- Phiên supervisor = **vai con người**: lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15.
- Người dùng giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa và được báo ngắn gọn.

## Bước tiếp theo (người dùng duyệt 2026-10-08)
1. **R6 = dashboard** (T-016, T-026), plan ở `plan/R6.md`: Next.js + yarn trong `dashboard/`, fixture → SSE → API thật. Cổng verify có bước `dashboard` (lint + test + build, chỉ chạy khi có `dashboard/package.json`). Trước khi chạy: kiểm tra `node`/`yarn` có trên máy (thiếu thì người dùng cài; worker không tự cài). Chạy bằng chế độ B: `nohup .autodev/autodev-run.sh R6 > .autodev/runs/nohup.out 2>&1 &`.
2. Còn của P4: kiểm chứng nhánh chờ reset khi gặp hạn mức thật (đối chiếu `LIMIT_RE`/`RESET_RE`), rồi đóng P4.
3. Để sau (ROADMAP "Để sau"): dashboard xem tiến trình `claude -p`, thông báo qua Telegram.

Đã xong 2026-10-08: xoá file `* 2.py`; sửa runner (PR #23: worktree worker về `origin/main`, no-op → exit 4, thông báo macOS mặc định tắt, bật bằng `AUTODEV_NOTIFY=1`); chuyển repo ra khỏi iCloud.

Cách khởi chạy chế độ B (đã chạy thật): từ repo chính `nohup .autodev/autodev-run.sh R6 R7 > .autodev/runs/nohup.out 2>&1 &`; theo dõi bằng `.autodev/watch.sh` trong một terminal. Phiên chat **không** tự được báo khi runner xong (tiến trình tách rời); nếu muốn phiên chat được gọi lại thì khởi chạy bằng Bash chạy nền của chính phiên đó hoặc dùng Monitor theo dõi `run.log`.

## Trạng thái hiện tại (2026-10-08)
- Plugin: P1–P3 xong. P4 đã chạy thật: R4 + R5 liền nhau, 40 phút, 5,29 USD ước tính, không chạm hạn mức (nhánh chờ reset chưa kiểm chứng). Runner đã sửa (PR #23).
- Dự án: R4 (PR #19: T-020, T-021, T-023) và R5 (PR #21: T-022, T-024, T-025) đã merge; 226 test, verify sạch. Còn T-016, T-026 (dashboard) → R6.
- **Vị trí repo (từ 2026-10-08):** `~/dev/sme-ci-agent/` chứa 3 worktree cạnh nhau: `sme-ci-agent` (chính), `sme-ci-agent-autodev` (worker), `sme-ci-agent-supervisor` (supervisor). Đã chuyển khỏi Desktop vì iCloud sinh file "tên 2". Tài liệu hackathon vẫn ở Desktop, cạnh alias "sme-ci-agent (code)". Docker DB `sme-ci-agent-autodev-db-1` cổng 5432 (volume có tên, không phụ thuộc đường dẫn).
- Máy này: đã dừng Homebrew `postgresql@14` (bật lại: `brew services start postgresql@14`).

## Quyền và quy tắc đang áp dụng
- Supervisor tự merge PR mốc sau khi chạy lại verify; worker không merge.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến; merge không kèm xoá nhánh).
- Không đọc hay in `.env`.

## Việc mở / cần để ý
- Chưa biết `claude -p` báo hết hạn mức dạng nào; `run.py` đoán theo chữ "limit" + "resets <giờ>". Lần chạy thật đầu tiên gặp hết hạn mức thì đối chiếu và sửa `LIMIT_RE` / `RESET_RE` nếu cần.
- Guard so khớp theo chữ: commit message hay chuỗi thử chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.
- Dự án: `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature` (cần cho T-020, T-004).
- Dự án (từ R5): (1) `apply_sop` gọi trực tiếp chưa chặn `approved_by='llm'`; `parse_decision` là deny-list (`bot`, `claude` lọt) → nên dùng một danh sách người duyệt hợp lệ (allow-list) dùng chung. (2) Detect thật chưa nối vào graph mặc định; registry run của API trong bộ nhớ; factory mặc định chưa test thật.
- Sau khi chuyển repo (người dùng duyệt 2026-10-08): xoá thư mục shim `~/Desktop/…/Vietnam Japan AI Hackathon 2026/sme-ci-agent/` (chỉ còn `.autodev/guard.py` tạm) và `__pycache__/* 2.pyc` trong worktree supervisor. Thư mục lịch sử Claude cũ `~/.claude/projects/-Users-ishopjapan-Desktop-…` (đã chép sang tên mới) giữ vài ngày rồi xoá.
- Để sau (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh (ROADMAP, "Để sau").

## Lịch sử ngắn
- P1 (plan/M1), P2 (plan/M2), P3 (plan/M3) xong. Từ R4, mốc auto-dev đặt tên R4, R5… để không trùng TASKS.md. Chi tiết trong `PROGRESS.md`.

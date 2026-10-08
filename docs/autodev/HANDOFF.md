# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- Hai plan lồng nhau: **plan lớn** = xây plugin auto-dev (`docs/autodev/`), **plan nhỏ** = dự án SME CI Agent dùng để thử (`plan/`, TASKS.md). Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD (ROADMAP, "Nguyên tắc ưu tiên").
- Phiên supervisor = **vai con người**: lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15.
- Người dùng giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa và được báo ngắn gọn.

## Bước tiếp theo (2026-10-08)
1. **R7 đã merge (PR #31).** Người dùng tự chạy T-030 với LLM thật: tự điền khoá API và tên model trong file môi trường (theo README "Chạy demo"), `uv run alembic upgrade head`, rồi `SME_LLM=real scripts/demo.sh` hoặc `uv run python scripts/run_scenario.py --llm real`. Sau đó tick T-030.
2. Leader quyết R7-c1: để demo ra nhánh Measure đạt → Learn, simulator cần anomaly có điểm kết thúc (seed 42 kéo đến hết dữ liệu nên chỉ tới rollback).
3. Thêm một dòng README: `run_scenario.py` cần `alembic upgrade head` trước (chỉ `demo.sh` tự migrate).
4. Còn của P4: kiểm chứng nhánh chờ reset khi gặp hạn mức thật, rồi đóng P4.
5. Để sau: dashboard xem tiến trình `claude -p`, thông báo Telegram.

## Trạng thái hiện tại (2026-10-08)
- Plugin: P1–P3 xong. P4 đã chạy thật: R4 + R5 liền nhau, 40 phút, 5,29 USD ước tính, không chạm hạn mức (nhánh chờ reset chưa kiểm chứng). Runner đã sửa (PR #23).
- Dự án: R6 (dashboard) và R7 (M3 end-to-end, PR #31, 262 pytest, 38 vitest) đã merge. R4 (PR #19: T-020, T-021, T-023) và R5 (PR #21: T-022, T-024, T-025) đã merge; 226 test, verify sạch. Còn T-016, T-026 (dashboard) → R6.
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

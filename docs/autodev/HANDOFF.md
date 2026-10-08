# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- Hai plan lồng nhau: **plan lớn** = xây plugin auto-dev (`docs/autodev/`), **plan nhỏ** = dự án SME CI Agent dùng để thử (`plan/`, TASKS.md). Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD (ROADMAP, "Nguyên tắc ưu tiên").
- Phiên supervisor = **vai con người**: lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15.
- Người dùng giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa và được báo ngắn gọn.

## Bước tiếp theo (2026-10-08, người dùng duyệt)
1. **R8 = "mạch chặt"** (`plan/R8.md`): sửa lỗ hổng vòng lặp do rà soát chỉ đọc tìm ra: Measure luôn trượt (cửa sổ sau rỗng, sandbox tĩnh) và chiều tốt do LLM khai; run lỗi kẹt "running" và mất audit; LLM thật làm tràn context (`query_logs` không giới hạn); duyệt không gắn với đề xuất cụ thể, UI không cho thấy nội dung đề xuất và không khoá tên ngoài danh sách; thiếu cạnh quay lại T-040. R7-c1 đã quyết: hướng (1), simulator sinh dữ liệu sau thay đổi.
   Chạy: `AUTODEV_SUPERVISOR_MODEL=opus AUTODEV_SUPERVISOR_EFFORT=medium PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH nohup .autodev/autodev-run.sh R8 > .autodev/runs/nohup.out 2>&1 &`.
2. Sau R8: người dùng chạy T-030 với LLM thật (Anthropic API trả theo lượng dùng; gói Pro/Max không kèm API). Cổng 5432 bị container auto-dev chiếm: chạy demo ở repo chính với `DB_PORT=5433` và `DATABASE_URL` cùng cổng.
3. R9: checkpointer Postgres + dùng bảng `runs`/`events` (đang trống), run id trên URL, trang danh sách run và trang Dữ liệu (audit_log, sop_versions, learning_store), Detect không chọn lại anomaly đã xử lý, đọc `learning_store`, khoá phiên bản SOP khi chạy song song.
4. Còn của P4: kiểm chứng nhánh chờ reset khi gặp hạn mức thật, rồi đóng P4.
5. Để sau: dashboard xem tiến trình `claude -p` (log stream-json), thông báo Telegram.

## Trạng thái hiện tại (2026-10-08)
- Plugin: P1–P3 xong. P4 đã chạy thật: R4 + R5 liền nhau, 40 phút, 5,29 USD ước tính, không chạm hạn mức (nhánh chờ reset chưa kiểm chứng). Runner đã sửa (PR #23).
- Dự án: R6 (dashboard) và R7 (M3 end-to-end, PR #31, 262 pytest, 38 vitest) đã merge. R4 (PR #19: T-020, T-021, T-023) và R5 (PR #21: T-022, T-024, T-025) đã merge; 226 test, verify sạch. 
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

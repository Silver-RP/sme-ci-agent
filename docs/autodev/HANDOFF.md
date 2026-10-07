# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- Hai plan lồng nhau: **plan lớn** = xây plugin auto-dev (`docs/autodev/`), **plan nhỏ** = dự án SME CI Agent dùng để thử (`plan/`, TASKS.md). Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD (ROADMAP, "Nguyên tắc ưu tiên").
- Phiên supervisor = **vai con người**: lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15.
- Người dùng giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa và được báo ngắn gọn.

## Bước tiếp theo (chờ người dùng chọn, 2026-10-08)
1. **Cần duyệt xoá:** 11 file `* 2.py` untracked trong worktree `../sme-ci-agent-supervisor` (bản sao do iCloud, xem "Việc mở"). Chưa xoá thì verify ở worktree đó báo lỗi lint và pytest đếm sai.
2. **Sửa runner (tổng kết P4):** (a) trước khi giao worker, đưa worktree worker về `milestone/<Rx>` tạo từ `origin/main`; (b) worker exit 0 mà không có PR/báo cáo → exit 4; (c) khi runner dừng (xong, lỗi, hạn mức) gửi thông báo macOS; (d) xoá `STOPPED.md` cũ khi bắt đầu lần chạy mới là thao tác xoá → thay bằng đổi tên kèm thời gian hoặc ghi đè nội dung.
3. **Đề xuất (người dùng hỏi, chưa duyệt):** dashboard cục bộ chỉ đọc để xem worker headless trực tiếp (dòng thời gian dev-xx/review, tool gần nhất, chi phí), đọc transcript `~/.claude/projects/<worktree>/*.jsonl`; có thể chuyển runner sang `--output-format stream-json`. Đây là việc plugin (P4/P5), không phải TASKS.md.
4. Sau đó chọn mốc dự án tiếp theo: dashboard T-016/T-026 (cần cho demo) và việc mở của R5.

Cách khởi chạy chế độ B (đã chạy thật): từ repo chính `nohup .autodev/autodev-run.sh R6 R7 > .autodev/runs/nohup.out 2>&1 &`; theo dõi bằng `.autodev/watch.sh` trong một terminal. Phiên chat **không** tự được báo khi runner xong (tiến trình tách rời); nếu muốn phiên chat được gọi lại thì khởi chạy bằng Bash chạy nền của chính phiên đó hoặc dùng Monitor theo dõi `run.log`.

## Trạng thái hiện tại (2026-10-08)
- Plugin: P1–P3 xong. P4 đã chạy thật: R4 + R5 liền nhau, 40 phút, 5,29 USD ước tính, không chạm hạn mức (nhánh chờ reset chưa kiểm chứng). Còn sửa runner (bước 2) rồi đóng P4.
- Dự án: R4 (PR #19: T-020, T-021, T-023) và R5 (PR #21: T-022, T-024, T-025) đã merge; 226 test, verify sạch. TASKS.md nhóm M1 còn T-016; dashboard T-026 chưa ai làm.
- Worktree: `../sme-ci-agent-autodev` (worker, ở `milestone/R5` đã merge), `../sme-ci-agent-supervisor` (supervisor). Docker DB `sme-ci-agent-autodev-db-1` cổng 5432.
- Máy này: đã dừng Homebrew `postgresql@14` (bật lại: `brew services start postgresql@14`). Desktop đồng bộ iCloud.

## Quyền và quy tắc đang áp dụng
- Supervisor tự merge PR mốc sau khi chạy lại verify; worker không merge.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến; merge không kèm xoá nhánh).
- Không đọc hay in `.env`.

## Việc mở / cần để ý
- Chưa biết `claude -p` báo hết hạn mức dạng nào; `run.py` đoán theo chữ "limit" + "resets <giờ>". Lần chạy thật đầu tiên gặp hết hạn mức thì đối chiếu và sửa `LIMIT_RE` / `RESET_RE` nếu cần.
- Guard so khớp theo chữ: commit message hay chuỗi thử chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.
- Dự án: `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature` (cần cho T-020, T-004). Dashboard (T-016, T-026) chưa có ai làm, cần cho demo.
- Dự án (từ R5): (1) `apply_sop` gọi trực tiếp chưa chặn `approved_by='llm'`; `parse_decision` là deny-list (`bot`, `claude` lọt) → nên dùng một danh sách người duyệt hợp lệ (allow-list) dùng chung. (2) Detect thật chưa nối vào graph mặc định; registry run của API trong bộ nhớ; factory mặc định chưa test thật.
- Repo nằm trong Desktop đồng bộ iCloud → iCloud sinh file "tên 2" khi xung đột. Nên chuyển repo và worktree ra ngoài (ví dụ `~/dev/`); việc này cần người dùng làm và duyệt.
- Để sau (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh (ROADMAP, "Để sau").

## Lịch sử ngắn
- P1 (plan/M1), P2 (plan/M2), P3 (plan/M3) xong. Từ R4, mốc auto-dev đặt tên R4, R5… để không trùng TASKS.md. Chi tiết trong `PROGRESS.md`.

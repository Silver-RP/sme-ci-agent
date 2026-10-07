# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc (và trước khi người dùng đóng phiên). Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- Hai plan lồng nhau: **plan lớn** = xây plugin auto-dev (`docs/autodev/`), **plan nhỏ** = dự án SME CI Agent dùng để thử (`plan/`, TASKS.md). Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD (ROADMAP, "Nguyên tắc ưu tiên").
- Phiên supervisor = **vai con người**: lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15.
- Người dùng giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa và được báo ngắn gọn.

## Bước tiếp theo (người dùng đã duyệt 2026-10-08)
1. Kiểm tra nhanh điều kiện chạy:
   - Docker DB: `docker compose ps` trong `../sme-ci-agent-autodev` thấy `sme-ci-agent-autodev-db-1` chạy ở cổng 5432 (nếu dừng: `docker compose up -d db` trong thư mục đó).
   - `gh auth status` đã đăng nhập; `claude --version` chạy được (wrapper `~/.local/bin/claude`).
   - Worktree: `../sme-ci-agent-autodev` (worker, đang ở `milestone/M3` đã merge; `/run-milestone` sẽ tự tạo `milestone/R4` từ `origin/main`) và `../sme-ci-agent-supervisor` (supervisor, detached). Cả hai có `.claude/settings.local.json` (Auto, tắt Superpowers).
2. Khởi chạy chế độ B cho **R4 rồi R5**, tách khỏi phiên để vẫn chạy khi đóng VS Code (chạy từ thư mục repo chính):
   `nohup .autodev/autodev-run.sh R4 R5 > .autodev/runs/nohup.out 2>&1 &`
3. Báo người dùng: đã khởi chạy, cách theo dõi (`.autodev/runs/run.log`), dự kiến 30–90 phút cộng thời gian chờ reset nếu chạm hạn mức (ước 35–50% cửa sổ 5 giờ cho 2 mốc).
4. Khi chạy xong hoặc dừng: đọc `run.log`, các file JSON trong `.autodev/runs/`, `STOPPED.md` nếu có (exit 2 lỗi, 3 hạn mức, 4 mốc chưa merge). Supervisor headless đã duyệt/merge từng mốc; phiên này tóm tắt cho người dùng, ghi số đo (thời gian, `total_cost_usd`, có chạm hạn mức không, script có tự chờ và chạy tiếp đúng không) vào `PROGRESS.md`, cập nhật ROADMAP (P4) và file này qua một PR `chore/autodev-*`.

## Trạng thái hiện tại (2026-10-08)
- Plugin: P1, P2, P3 xong. P4 đang làm: bộ chạy `.autodev/run.py` + `.autodev/autodev-run.sh` đã viết, 10 test với `claude` giả (`python3 -m unittest discover .autodev/tests`), **chưa chạy thật**.
- Dự án: TASKS.md nhóm M1 xong 7/8 (còn T-016 dashboard, chưa ai làm). R4 = T-020, T-021, T-023; R5 = T-022, T-024, T-025. Test không gọi LLM thật, không cần API key.
- Hạn mức: mỗi mốc 7–22% cửa sổ 5 giờ; M3 (headless) ~16–22%, ~1,72 USD ước tính. Chưa đo hạn mức tuần.
- Máy này: đã dừng dịch vụ Homebrew `postgresql@14` theo yêu cầu người dùng (bật lại: `brew services start postgresql@14`). Máy nào cần đổi cổng DB: `DB_PORT` + `.autodev/env.local.json`.

## Cập nhật 2026-10-08 (supervisor headless, R4 --review-only): R4 ĐÃ MERGE
- Worker R4 chạy xong (lần chạy sau lần no-op), PR #19 merge vào main: T-020, T-021, T-023 xong, 162 test, verify sạch. Tôi chạy lại verify + pytest, kiểm tra LLM thật báo `LLMConfigError` khi thiếu `MODEL_REASONING`.
- Còn R5 (T-022, T-024, T-025). Đã thêm tiêu chí 5 vào R5/dev-02: approval chỉ từ người, `apply_sop` từ chối `approved_by` như `llm`.
- Việc cho runner (P4): tạo `milestone/<Rx>` từ `origin/main` trước khi giao worker; coi worker "exit 0 mà không có PR/báo cáo" là lỗi (exit 4). Worker `../sme-ci-agent-autodev` cần `git fetch` và chuyển sang `milestone/R5` từ origin/main trước khi chạy R5.
- Chưa có số `total_cost_usd` và % hạn mức của R4.

## Quyền và quy tắc đang áp dụng
- Supervisor tự merge PR mốc sau khi chạy lại verify; worker không merge.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến; merge không kèm xoá nhánh).
- Không đọc hay in `.env`.

## Việc mở / cần để ý
- Chưa biết `claude -p` báo hết hạn mức dạng nào; `run.py` đoán theo chữ "limit" + "resets <giờ>". Lần chạy thật đầu tiên gặp hết hạn mức thì đối chiếu và sửa `LIMIT_RE` / `RESET_RE` nếu cần.
- Guard so khớp theo chữ: commit message hay chuỗi thử chứa lệnh bị cấm cũng bị chặn; viết lại câu chữ hoặc đưa chuỗi thử vào file.
- Dự án: `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature` (cần cho T-020, T-004). Dashboard (T-016, T-026) chưa có ai làm, cần cho demo.
- Để sau (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh (ROADMAP, "Để sau").

## Lịch sử ngắn
- P1 (plan/M1), P2 (plan/M2), P3 (plan/M3) xong. Từ R4, mốc auto-dev đặt tên R4, R5… để không trùng TASKS.md. Chi tiết trong `PROGRESS.md`.

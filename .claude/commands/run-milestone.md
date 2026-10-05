---
description: Chạy một mốc auto-dev (chế độ A). Ví dụ /run-milestone M1
argument-hint: <mốc, ví dụ M1>
---

Chạy mốc $ARGUMENTS theo chế độ A của auto-dev (thiết kế: docs/autodev/auto-dev-review-design.md, mục 6.8). Bạn là session điều phối: KHÔNG tự code, chỉ giao việc cho subagent `developer` và `reviewer`, rồi ghi trạng thái.

## Chuẩn bị
0. Nếu `$ARGUMENTS` rỗng: lấy `milestone` trong `.autodev/state.json`; nếu vẫn rỗng và `plan/` chỉ có một file `M*.md` thì dùng mốc đó; nếu không thì hỏi người dùng. Dưới đây `$ARGUMENTS` nghĩa là mốc đã chọn.
1. Đọc `.autodev/config.json`, `.autodev/state.json`, `plan/$ARGUMENTS.md`. Không đọc thêm file khác nếu không cần.
2. Nhánh: chạy `git fetch origin`, rồi quyết định:
   - Đang ở `milestone/$ARGUMENTS` hoặc `milestone/$ARGUMENTS-rN` và nhánh này **chưa merge** thì dùng tiếp. Chưa merge nghĩa là: chưa có commit nào ngoài `origin/main` (`git log origin/main..HEAD` rỗng VÀ `HEAD` = `origin/main`, tức nhánh mới tạo), hoặc còn commit chưa có trong `origin/main` (`git log origin/main..HEAD` không rỗng).
   - Ngược lại (đang ở `main`, HEAD tách rời, hoặc nhánh đã merge: không còn commit riêng nhưng `HEAD` khác `origin/main`) thì tạo nhánh mới từ `origin/main`: `git switch -c milestone/$ARGUMENTS-rN origin/main`, N là số nhỏ nhất ≥ 2 chưa có (dùng `milestone/$ARGUMENTS` nếu tên này chưa có).
   - Không bao giờ commit lên `main`.
3. Nếu `state.json` có task đang dở (`current_task`), tiếp tục từ task đó.

## Vòng lặp mỗi task (theo thứ tự phụ thuộc, bỏ qua task DONE)
1. Ghi `base = git rev-parse HEAD`; đặt task `IN_PROGRESS` trong state.json.
2. Gọi `developer` với: task_id, đường dẫn plan, và (nếu là vòng sau) nguyên văn `blocking_issues` của reviewer.
3. Sau khi developer trả về: đọc `state.json` → `verify.last_status`.
   - `VERIFY_FAILED` → task `BLOCKED` (lý do: verify không sạch sau nhiều lần), sang task kế.
   - Không có commit mới (`git log base..HEAD` rỗng) → coi như một vòng FAIL.
4. Gọi `reviewer` với: task_id, `base..HEAD`, đường dẫn plan. Lưu JSON nguyên văn vào `.autodev/reviews/<task>-r<vòng>.json` (tên file thay `/` bằng `-`).
5. `FAIL` → số vòng += 1, trạng thái `REWORK`, quay lại bước 2 với blocking issues.
   - Số vòng > `max_rounds` → `BLOCKED`.
   - Cùng một blocking issue (cùng file + cùng nội dung chính) lặp lại 2 vòng liên tiếp → `BLOCKED`.
6. `PASS` → `DONE`. Cập nhật trong `plan/$ARGUMENTS.md` (trạng thái, số vòng) và `plan/PROGRESS.md` (bảng chỉ số + nhật ký). Điều chỉnh plan (a)/(b) thì làm luôn và ghi lý do; (c) CHỈ ghi vào "Đề xuất chờ duyệt". Nếu mã T-0xx tương ứng đã xong hẳn thì tick trong TASKS.md.
7. Commit trạng thái: `chore($ARGUMENTS/<task>): cập nhật plan và trạng thái`.

Task BLOCKED: chạy tiếp các task không phụ thuộc vào nó (`blocked_policy`); task phụ thuộc cũng đánh dấu BLOCKED.

## Kết thúc mốc
1. Chạy `python3 .autodev/verify.py` toàn mốc.
2. Push nhánh `milestone/$ARGUMENTS` (không bao giờ push main).
3. Viết báo cáo vào `.autodev/reports/$ARGUMENTS.md` theo mục 6.10: tóm tắt so với tiêu chí cấp mốc; bảng task (trạng thái, số vòng, commit); BLOCKED + việc cần người quyết; điều chỉnh (a)/(b); đề xuất (c); kết quả verify so với baseline; cách chạy thử (`app` trong config); thời gian chạy. Nội dung này dùng làm mô tả PR.
4. Nhắc người dùng xem `/usage` (bảng theo subagent) và điền cột "% hạn mức" trong PROGRESS.md.
5. DỪNG. Không tự sang mốc tiếp theo.

Trả lời người dùng ngắn gọn bằng tiếng Việt; chi tiết để trong file.

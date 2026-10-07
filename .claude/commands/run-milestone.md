---
description: Chạy một mốc auto-dev (chế độ A). Ví dụ /run-milestone M1
argument-hint: <mốc, ví dụ M1>
---

Chạy mốc $ARGUMENTS theo chế độ A của auto-dev (thiết kế: docs/autodev/auto-dev-review-design.md, mục 6.8). Bạn là session điều phối: KHÔNG tự code, chỉ giao việc cho subagent `developer` và `reviewer`, rồi ghi trạng thái.

## Phạm vi file
Worker chỉ sửa code dự án, `plan/`, TASKS.md, `.autodev/state.json`, `.autodev/reviews/`, `.autodev/reports/`. KHÔNG sửa file của plugin: `.claude/`, `.autodev/*.py`, `.autodev/config.json`, `.autodev/baseline.json`, `docs/autodev/`. Thấy plugin có lỗi thì ghi vào báo cáo mốc.

## Ai giao việc
Nếu yêu cầu đến dưới dạng `<cross-session-message from="X">` thì X là SUPERVISOR (mục 6.15 của thiết kế). Mọi câu hỏi cần quyết định (BLOCKED, đề xuất (c)) và báo cáo cuối mốc gửi cho X bằng `SendMessage` (to = X), không hỏi người dùng. Nếu người dùng gõ lệnh trực tiếp thì báo cho người dùng như bình thường.

## Chuẩn bị
0. Nếu `$ARGUMENTS` rỗng: lấy `milestone` trong `.autodev/state.json`; nếu vẫn rỗng và `plan/` chỉ có một file `M*.md` thì dùng mốc đó; nếu không thì hỏi người dùng. Dưới đây `$ARGUMENTS` nghĩa là mốc đã chọn.
1. Đọc `.autodev/config.json`, `.autodev/state.json`, `plan/$ARGUMENTS.md`. Không đọc thêm file khác nếu không cần.
2. Nhánh: chạy `git fetch origin`, rồi quyết định:
   - Đang ở `milestone/$ARGUMENTS` hoặc `milestone/$ARGUMENTS-rN` và nhánh này **chưa merge** thì dùng tiếp. Chưa merge nghĩa là: chưa có commit nào ngoài `origin/main` (`git log origin/main..HEAD` rỗng VÀ `HEAD` = `origin/main`, tức nhánh mới tạo), hoặc còn commit chưa có trong `origin/main` (`git log origin/main..HEAD` không rỗng).
   - Ngược lại (đang ở `main`, HEAD tách rời, hoặc nhánh đã merge: không còn commit riêng nhưng `HEAD` khác `origin/main`) thì tạo nhánh mới từ `origin/main`: `git switch -c milestone/$ARGUMENTS-rN origin/main`, N là số nhỏ nhất ≥ 2 chưa có (dùng `milestone/$ARGUMENTS` nếu tên này chưa có).
   - Không bao giờ commit lên `main`.
3. Nếu `state.json` → `milestone` khác `$ARGUMENTS`: chuyển `tasks` cũ vào `history.<mốc cũ>.tasks`, đặt `milestone = $ARGUMENTS`, `current_task = null`, tạo `tasks` mới từ danh sách dev-xx trong plan (TODO, round 0), đặt `verify.last_status = null` và `consecutive_blocks = 0` (giữ `hook_runs`). Tên task (dev-01…) chỉ có nghĩa trong mốc hiện tại.
4. Nếu `state.json` có task đang dở (`current_task`), tiếp tục từ task đó.

## Vòng lặp mỗi task (theo thứ tự phụ thuộc, bỏ qua task DONE)
1. Ghi `base = git rev-parse HEAD` và `hook_runs` hiện tại (`verify.hook_runs` trong state.json, mặc định 0); đặt task `IN_PROGRESS`.
2. Gọi `developer` với: task_id, đường dẫn plan, và (nếu là vòng sau) nguyên văn `blocking_issues` của reviewer.
3. Sau khi developer trả về: đọc `state.json` → `verify`. Nếu `hook_runs` không tăng thì hook SubagentStop KHÔNG chạy: tự chạy `python3 .autodev/verify.py`, ghi "hook không chạy" vào báo cáo mốc cho task này. Sau đó xét `verify.last_status`.
   - `VERIFY_FAILED` → task `BLOCKED` (lý do: verify không sạch sau nhiều lần), sang task kế.
   - Không có commit mới (`git log base..HEAD` rỗng) → coi như một vòng FAIL.
4. Gọi `reviewer` với: task_id, `base..HEAD`, đường dẫn plan. Lưu JSON nguyên văn vào `.autodev/reviews/<task>-r<vòng>.json` (tên file thay `/` bằng `-`).
5. `FAIL` → số vòng += 1, trạng thái `REWORK`, quay lại bước 2 với blocking issues.
   - Số vòng > `max_rounds` → `BLOCKED`.
   - Cùng một blocking issue (cùng file + cùng nội dung chính) lặp lại 2 vòng liên tiếp → `BLOCKED`.
6. `PASS` → `DONE`. Cập nhật trong `plan/$ARGUMENTS.md` (trạng thái, số vòng) và `plan/PROGRESS.md` (chỉ nhật ký task của dự án). Số đo (số vòng, verify bị chặn, thời gian) ghi vào báo cáo mốc; supervisor chuyển sang `docs/autodev/PROGRESS.md`. Điều chỉnh plan (a)/(b) thì làm luôn và ghi lý do; (c) CHỈ ghi vào "Đề xuất chờ duyệt". Nếu mã T-0xx tương ứng đã xong hẳn thì tick trong TASKS.md.
7. Commit trạng thái: `chore($ARGUMENTS/<task>): cập nhật plan và trạng thái`.

Task BLOCKED: chạy tiếp các task không phụ thuộc vào nó (`blocked_policy`); task phụ thuộc cũng đánh dấu BLOCKED.

## Kết thúc mốc
1. Chạy `python3 .autodev/verify.py` toàn mốc.
2. Push nhánh `milestone/$ARGUMENTS` (không bao giờ push main) và mở PR vào `main` bằng `gh pr create --base main --head milestone/$ARGUMENTS --body-file .autodev/reports/$ARGUMENTS.md` (tạo báo cáo ở bước 3 trước). Không merge.
3. Viết báo cáo vào `.autodev/reports/$ARGUMENTS.md` theo mục 6.10: tóm tắt so với tiêu chí cấp mốc; bảng task (trạng thái, số vòng, commit); BLOCKED + việc cần người quyết; điều chỉnh (a)/(b); đề xuất (c); kết quả verify so với baseline; cách chạy thử (`app` trong config); thời gian chạy. Nội dung này dùng làm mô tả PR.
4. Báo kết quả (link PR, bảng task, BLOCKED, đề xuất (c)) cho supervisor nếu có, nếu không thì cho người dùng. Nhắc xem `/usage` để điền cột "% hạn mức".
5. DỪNG. Không tự sang mốc tiếp theo, không merge.

## Lệnh shell (để không phải hỏi quyền)
- Tạo/sửa file bằng công cụ Write/Edit, KHÔNG dùng `cat > file`, `echo >`, heredoc ghi file hay `python3 - <<EOF` để sửa file.
- Commit bằng nhiều cờ `-m` trên một dòng, ví dụ `git commit -m "feat(M1/dev-01): ..." -m "Co-Authored-By: ..."`; không dùng `$(cat <<EOF ...)`.
- Mỗi lệnh một việc; tránh `$(...)`, `$((...))`, và không ghi file ra ngoài repo (kể cả /tmp). Đo thời gian bằng cách ghi giờ bắt đầu/kết thúc (`date`) rồi tự trừ.

Trả lời người dùng ngắn gọn bằng tiếng Việt; chi tiết để trong file.

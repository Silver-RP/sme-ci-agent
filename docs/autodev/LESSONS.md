# Bài học của auto-dev

Nguyên tắc rút ra khi xây plugin và chạy thử trên SME CI Agent. Mỗi mục: nguyên tắc, sự việc dẫn tới nó, và nó đã thành quy tắc, test hay công cụ nào. Bốn mục đầu được người dùng đánh giá cao nhất. Supervisor thêm mục mới khi một sự cố dẫn tới sửa đổi prompt, gate hay công cụ; `.autodev/tests/test_project_state.py` giữ định dạng.

### 1. Đừng tin báo cáo, kể cả của chính mình
- **Nguyên tắc:** kết luận "đạt" chỉ dựa trên lệnh mình tự chạy và kết quả thấy được, không dựa trên báo cáo của người làm hay trí nhớ của phiên trước.
- **Ngộ ra từ:** M1/dev-03 reviewer chỉ đọc test có sẵn, bỏ sót `domain` rỗng; R7 báo đạt nhưng tiêu chí cấp mốc 3 (khoá nút duyệt) chưa có ở UI.
- **Đã thành:** reviewer phải tự probe trường hợp biên; supervisor lập bảng "tiêu chí cấp mốc → lệnh/test → kết quả" (`supervise.md` bước 8); `/audit` tự tái hiện mỗi phát hiện của agent con.

### 2. Người kiểm tra phải khác người làm và nhìn từ góc khác
- **Nguyên tắc:** người làm, người review task, người duyệt mốc và người rà soát toàn dự án là bốn vai khác nhau, mỗi vai nhìn một tầng.
- **Ngộ ra từ:** R8: reviewer từng task đều PASS, nhưng rà soát chỉ đọc 2026-10-08 nhìn cả vòng lặp mới thấy H1–H5 (Measure đo sai dữ liệu, duyệt hai lần…).
- **Đã thành:** reviewer chỉ đọc; supervisor chạy model khác (Opus) với worker (Sonnet); `/audit` ba góc (logic, hợp đồng API, mục tiêu) chạy định kỳ (`run.py --audit-every`).

### 3. Tự động hoá phải có điểm dừng rõ ràng và quyền hạn có giới hạn
- **Nguyên tắc:** mỗi vòng tự động có giới hạn số lần, điều kiện dừng và danh sách việc không bao giờ tự làm (xoá, merge tay ngoài quy trình, đổi mục tiêu).
- **Ngộ ra từ:** 2026-10-07 merge kèm xoá nhánh gỡ luôn worktree đang dùng; R4 worker no-op exit 0 mà runner vẫn coi là xong.
- **Đã thành:** `.autodev/guard.py` chặn lệnh xoá/force/main; `max_rounds`, `max_verify_blocks`; runner dừng (exit 2/3/4) và ghi `STOPPED.md`; tầng tầm nhìn (thứ tự mốc, cắt việc) luôn do người dùng duyệt.

### 4. Ngữ cảnh dài làm mất tầm nhìn tổng thể
- **Nguyên tắc:** trạng thái dự án phải nằm trong file ngắn đọc được từ đầu, không nằm trong trí nhớ của một phiên chat dài.
- **Ngộ ra từ:** phiên supervisor kéo dài qua R4–R8 bắt đầu bỏ sót việc mở và lệch giữa mục tiêu dự án với việc đang làm.
- **Đã thành:** `HANDOFF.md` mỗi cuối mốc; `PROJECT_STATE.md` + `state.json` (dưới 150 dòng) mà developer, reviewer, supervisor đọc trước plan mốc; mỗi mốc một phiên headless mới.

### 5. Quy tắc trong tài liệu sẽ bị quên; quy tắc thành test thì không
- **Nguyên tắc:** quy tắc quan trọng phải có test hoặc guard bảo vệ; bảng "quy tắc → test" cho thấy quy tắc nào còn trần.
- **Ngộ ra từ:** developer vẫn sửa file bằng `python3 - <<EOF` và `sed -i` ở R8 dù prompt cấm từ M2.
- **Đã thành:** guard chặn hai dạng đó (P5); `PROJECT_STATE.md` mục "Quy tắc → test bảo vệ"; R9 có `tests/test_invariants.py`.

### 6. Test xanh khác với dùng được
- **Nguyên tắc:** chạy đúng lệnh người dùng sẽ gõ (smoke), không chỉ pytest.
- **Ngộ ra từ:** R7 test xanh nhưng `uv run alembic upgrade head` (dòng đầu `demo.sh`) lỗi `ModuleNotFoundError`.
- **Đã thành:** `smoke` trong `.autodev/config.json`, `verify.py --smoke`; supervisor không merge khi smoke lỗi.

### 7. Im lặng không có nghĩa là chạy tốt
- **Nguyên tắc:** đo "còn sống" ở đúng tầng làm việc (sub-agent), không chỉ ở tiến trình cha.
- **Ngộ ra từ:** hook `Stop` trong frontmatter developer không bao giờ chạy mà không ai biết; runner chạy `nohup` nhìn bên ngoài không phân biệt được đang làm hay treo.
- **Đã thành:** bộ đếm `hook_runs`; `.autodev/watch.sh` hiện transcript sub-agent cập nhật bao lâu trước.

### 8. Chạy tách rời phải có kênh báo về
- **Nguyên tắc:** tiến trình chạy nền phải tự báo khi dừng hoặc xong, người dùng không phải hỏi.
- **Ngộ ra từ:** P4 lần đầu: runner xong mà phiên chat không biết.
- **Đã thành:** phiên chat chờ `run.log` bằng lệnh nền; thông báo macOS (`AUTODEV_NOTIFY=1`); Telegram ở P7.

### 9. Môi trường cũng là code
- **Nguyên tắc:** cổng, PATH, phiên bản Node, thư mục đồng bộ là một phần của hệ thống; ghi lại và kiểm tra như code.
- **Ngộ ra từ:**
  - iCloud sinh file "tên 2" làm verify báo lỗi;
  - Postgres Homebrew chiếm cổng 5432;
  - Node 22.12 không đủ cho Next;
  - R9: bản Claude Code mới cho sub-agent chạy nền mặc định, nên worker headless kết thúc khi dev-02 còn đang làm.
- **Đã thành:**
  - repo chuyển sang `~/dev/`;
  - `.autodev/env.local.json` và `DB_PORT`;
  - HANDOFF mục "Môi trường";
  - `demo.sh` dùng lại DB đang chạy;
  - `run_in_background: false` bắt buộc trong `run-milestone.md`/`audit.md` (`.autodev/tests/test_prompts.py`);
  - runner tự chạy tiếp một lần khi còn task dở (`unfinished_tasks`).

### 10. Guard so khớp theo chữ chặn nhầm cả lời nói
- **Nguyên tắc:** guard theo regex chặn cả câu chữ nhắc tới lệnh cấm (commit message, tài liệu); viết lại câu hoặc dùng Edit/Write thay vì lách guard.
- **Ngộ ra từ:** commit message và tài liệu nhắc tên file cấm hoặc lệnh xoá bị chặn nhiều lần (2026-10-08, 2026-10-09).
- **Đã thành:** HANDOFF mục "Quyền và quy tắc"; tách lệnh theo `&&`/`;`/`|` trước khi so khớp.

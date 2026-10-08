---
description: Rà soát chỉ đọc (plugin P5) - 3 góc song song, ghi docs/audits/<ngày>.md và cập nhật PROJECT_STATE. Ví dụ /audit R7 R8
argument-hint: <các mốc R vừa merge, ví dụ R7 R8; để trống = từ lần audit trước>
---

Bạn là AUDITOR của auto-dev (plugin P5: chống mất tầm nhìn). Bạn rà soát CHỈ ĐỌC dự án sau các mốc $ARGUMENTS, tìm lỗ hổng mà người làm và reviewer từng task dễ bỏ sót vì chỉ nhìn một task. Bạn không sửa code dự án, không sửa plan mốc.

## Đọc trước
`docs/autodev/PROJECT_STATE.md` (nếu có) → `docs/PLAN.md` mục 1 (mục tiêu, 3 điều cần kiểm chứng) → `CLAUDE.md` → `plan/<mốc>.md` của các mốc $ARGUMENTS (mục "Tiêu chí chấp nhận cấp mốc", "Ghi chú điều chỉnh", "Đề xuất chờ duyệt") → audit gần nhất trong `docs/audits/` (để biết H-xx nào còn mở). Mốc trống thì lấy các mốc merge sau audit gần nhất (`git log --merges`).

## Rà soát: 3 agent `Explore` song song (một lượt gọi, chế độ "very thorough")
Mỗi agent nhận đề bài tự đủ nghĩa dưới đây (thay `<...>`), yêu cầu trả lời bằng danh sách phát hiện, mỗi phát hiện có: mô tả, bằng chứng `file:dòng`, cách tái hiện (lệnh hoặc đầu vào cụ thể), mức (cao / vừa / thấp), và "test nào sẽ đỏ nếu lỗi này còn". Không trả lời kiểu "có vẻ ổn"; không tìm thấy gì thì nói rõ đã xem những file nào.

**(a) Logic vòng lặp và quy tắc CLAUDE.md**
> Rà chỉ đọc repo SME CI Agent (LangGraph, `backend/agent/`, `backend/tools/`, `backend/sandbox/`, `data/context_profile.yaml`). Tìm chỗ vòng Observe → Detect → Investigate → Ask → Improve → Act → Measure → Learn chạy sai hoặc vi phạm quy tắc CLAUDE.md: LLM tự quyết rollback hay áp dụng SOP không qua người duyệt; hành động không ghi audit_log; SOP đổi không có phiên bản; thiếu bằng chứng mà không hỏi người; tool ghi vào dữ liệu nguồn; KPI/giả thuyết/SOP hard-code ngoài YAML; tên model hard-code; event thiếu `agent`/`domain`. Tìm thêm: cạnh điều kiện dẫn tới ngõ cụt hoặc vòng lặp không giới hạn; trạng thái dùng chung giữa các run; đầu ra bất thường của LLM (JSON hỏng, câu phủ định, giá trị ngoài miền) làm sai kết quả; chỗ test chỉ kiểm đường thuận. Ưu tiên phần đổi trong các mốc <mốc> (`git log` / `git diff <commit đầu>..HEAD --stat`).

**(b) API ↔ dashboard và hợp đồng events.json**
> Rà chỉ đọc `backend/api/`, `dashboard/` và `docs/schema/events.json` của repo SME CI Agent. So từng event backend phát ra (tìm nơi tạo event) với schema: tên, trường bắt buộc, kiểu, enum; trường mới chưa có trong schema hoặc chưa được dashboard xử lý (ví dụ status mới, `passed` = null, kind mới của câu hỏi). So từng endpoint dashboard gọi với API thật: đường dẫn, mã lỗi (409/422), dạng body. Tìm: trạng thái run mà UI không hiển thị được hoặc kẹt; thao tác người duyệt bị gửi hai lần; dữ liệu chỉ ở bộ nhớ sẽ mất khi backend tắt; luồng demo (`scripts/demo.sh`) mà người dùng gõ có bước nào chưa có test hay smoke.

**(c) Độ khớp với mục tiêu**
> Đọc `docs/PLAN.md` (mục 1: 3 điều cần kiểm chứng; mốc và thứ tự cắt), `TASKS.md`, `plan/R*.md` và code hiện tại của repo SME CI Agent. Với từng điều cần kiểm chứng: (1) tìm đúng nguyên nhân gốc so với ground truth và biết hỏi người; (2) đề xuất được duyệt làm KPI cải thiện, nếu không thì rollback và điều tra lại; (3) đo 3 chỉ số trước/sau trên 6 tháng dữ liệu mô phỏng: ước lượng % đạt hiện nay, kèm bằng chứng (test/script chứng minh được điều đó, hay chỉ có code). Nêu chỗ đang lệch hướng: việc làm nhiều mà không đẩy điều nào; điều nào chưa có ai làm; task TASKS.md trước v0.1-e2e còn mở; rủi ro "đạt trên giấy mà demo hỏng" (LLM giả quá dễ, dữ liệu seed quá rõ, chỉ test bằng TestClient).

## Tự kiểm trước khi ghi (đừng tin báo cáo, kể cả của agent con)
- Với mỗi phát hiện mức cao/vừa: tự mở `file:dòng` hoặc chạy lệnh tái hiện chỉ đọc (`uv run python -c "..."`, `uv run pytest -q -k ...`). Không tái hiện được thì hạ mức hoặc ghi "chưa xác nhận".
- Gộp phát hiện trùng giữa 3 góc. Bỏ ý kiến về style.

## Ghi kết quả
1. `docs/audits/<YYYY-MM-DD>.md` (trùng ngày thì thêm `-2`), gồm:
   - Phạm vi: mốc, commit đầu/cuối, 3 góc.
   - Bảng lỗ hổng: `H-xx` (đánh số tiếp từ audit trước, không dùng lại số), mức, mô tả, bằng chứng, cách tái hiện, test cần có để đóng, trạng thái (`mở` / `đóng: <tên test>`).
   - Lỗ hổng cũ: cập nhật trạng thái; chỉ đóng khi có test chứng minh đã sửa (ghi tên test và đã tự chạy).
   - Độ khớp mục tiêu: bảng 3 điều cần kiểm chứng → % đạt → bằng chứng → việc còn thiếu.
   - Đề xuất cho mốc kế tiếp: H-xx nào thành task nào (gợi ý, supervisor quyết khi lập plan).
2. Cập nhật `docs/autodev/PROJECT_STATE.md` và `docs/autodev/state.json` (mục "Lỗ hổng mở", "% đạt", "Quyết định gần đây"); giữ PROJECT_STATE dưới 150 dòng; `python3 -m unittest .autodev/tests/test_project_state.py` phải xanh.
3. Nhánh `chore/autodev-audit-<ngày>` từ `origin/main`, chỉ commit `docs/audits/**` và `docs/autodev/**`, mở PR. Chạy headless (từ `.autodev/run.py`) thì runner tự merge PR này; chạy tương tác thì supervisor merge.

## Không được
- Sửa code dự án, test, `plan/`, TASKS.md, hay file plugin ngoài `docs/autodev/`. Lỗ hổng chỉ được ghi, không tự sửa.
- Xoá file/nhánh; đọc `.env`; gọi LLM thật hay mạng ngoài localhost.

Báo cuối bằng tiếng Việt, ngắn: số H-xx mới / đóng / còn mở, % đạt 3 điều, link PR.

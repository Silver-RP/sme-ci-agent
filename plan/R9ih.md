# R9ih (sửa nhanh sau R9i): Improve biết SOP nào đang có

**Phục vụ plugin: P5.** Mốc sửa nhanh: tên kết thúc bằng `h`, không tính vào `--audit-every`.

**Mục tiêu dự án:** T-030 lần 2 (`docs/decisions.md`) vẫn không khép vòng vì lỗi H-43.
- LLM thật chẩn đoán đúng, nhưng đặt `sop_id` là `PLACEHOLDER_NEEDS_VALID_SOP_ID`.
- Nguyên nhân: prompt của Improve không có danh sách SOP, và thông báo khi yêu cầu sửa lại không nêu id hợp lệ.

Hướng (b) của R9i giữ nguyên: đề xuất phải có cả `action` và `sop_proposal`.

## Phạm vi
- **Trong:** `backend/agent/nodes/improve.py`, `backend/agent/prompts/`, test tương ứng.
- **Ngoài:** mọi thứ khác.

## Quy ước chung
- Test không gọi LLM thật. Test cho H-43 phải đỏ trước khi sửa.

## Tiêu chí chấp nhận cấp mốc
1. `python3 .autodev/verify.py` và `python3 .autodev/verify.py --smoke` sạch.
2. Prompt (system hoặc user) gửi cho LLM ở Improve chứa danh mục SOP: id, phiên bản đang hiệu lực (có tính bản mới trong `sop_versions`) và nội dung hiện tại. Danh mục lấy từ config/DB, không hard-code.
3. `sop_id` lạ → thông báo yêu cầu sửa lại liệt kê các id hợp lệ. Với LLM giả trả id sai ở lần đầu và id đúng ở lần sửa, run đi tới `kpi_measured.status == "measured"`.

## Task

### dev-01: Danh mục SOP trong prompt Improve + thông báo sửa lại có id hợp lệ (H-43)
- **Mô tả:**
  - Khi dựng prompt Improve, thêm khối "SOP hiện có": mỗi SOP gồm id, version đang hiệu lực, title, nội dung (bước).
    - Nội dung lấy bằng cùng cơ chế với `read_sop` / `current_sop`, để bản đã áp dụng trong DB được tính.
    - Giới hạn độ dài mỗi SOP bằng giá trị trong config (dùng lại giới hạn ký tự đang có nếu phù hợp).
  - Hướng dẫn trong prompt: `sop_change.sop_id` phải là một trong các id đó; `new_content` là toàn bộ nội dung SOP mới, sửa trên nội dung hiện tại.
  - `ProposalError` cho `sop_id` lạ phải nêu danh sách id hợp lệ.
- **Tiêu chí chấp nhận:**
  1. Test bắt prompt gửi cho LLM giả ở Improve: có đủ id và nội dung SOP từ config; sau khi áp dụng một bản mới, prompt của run kế tiếp có version mới. Đỏ trên main.
  2. Test: LLM giả trả `sop_id` = `PLACEHOLDER_NEEDS_VALID_SOP_ID` rồi sửa thành id đúng → `kpi_measured.status == "measured"`. Thông báo sửa lại có chứa id hợp lệ. Đỏ trên main.
- **Phụ thuộc:** không
- **Trạng thái:** TODO · **Số vòng:** 0

## Ghi chú điều chỉnh (Claude ghi khi làm (a)/(b))

## Đề xuất chờ duyệt

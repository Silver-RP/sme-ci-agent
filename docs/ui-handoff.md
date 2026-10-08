# Bàn giao UI cho team frontend

Gửi: bạn frontend phụ trách giao diện sản phẩm (tên ghi ở `docs/PLAN.md` mục 4). Ngày: 2026-10-09.

## Ranh giới
- **Bạn làm:** toàn bộ phần trình bày trong `dashboard/` (component, layout, style, chữ hiển thị) và test giao diện (vitest, có thể thêm Playwright).
- **Auto-dev và backend làm:** API, dữ liệu, logic agent. Từ mốc R9, auto-dev **không sửa phần trình bày** trong `dashboard/`; nó chỉ có thể sửa `dashboard/lib/api.ts` và `dashboard/lib/validate.ts` khi API đổi, và sẽ báo trước trong PR.
- **Hợp đồng:**
  - `docs/schema/events.json` cho vỏ event;
  - `docs/schema/payloads.md` cho payload từng event và API;
  - ví dụ thật trong `docs/schema/examples/`.

  Cần trường mới thì mở issue hoặc nói trong sync, không tự đổi `events.json`.

## Chạy thử
```bash
bash scripts/demo.sh          # backend :8000 + dashboard :3000, LLM giả, không cần API key
# mở http://localhost:3000/?source=live
```
Không có backend thì mở trang không kèm tham số (mặc định `?source=fixture`): trang phát lại `dashboard/fixtures/scenario1.json`.

## Màn hình cho demo (Demo Day 07/11, bản đầu ở v0.1-e2e 13/10)

| # | Màn | Dữ liệu | Trạng thái phải hiển thị |
|---|---|---|---|
| 1 | Danh sách run | API danh sách run (backend làm ở R9; hiện chưa có) | đang chạy · chờ người · xong (đã Learn / đóng / không có anomaly) · lỗi |
| 2 | Chi tiết run: timeline | SSE `/runs/{id}/events` | Mỗi loại event có cách hiển thị riêng (mục 2 của payloads.md), không in JSON thô. Không hiển thị `sop_applied.sim` |
| 3 | Câu hỏi của agent | `pending.type == "answer"` | Câu hỏi, số lần hỏi `attempt/max_questions`, ô trả lời |
| 4 | Duyệt đề xuất | `pending.kind == "proposal"` | Giả thuyết + độ tin cậy; thay đổi; lý giải; KPI kỳ vọng; **SOP cũ → mới** (`current_sop.content` so với `sop_proposal.new_content`, kể cả trường hợp không đổi); ba nút Duyệt / Từ chối / Bác bỏ-bổ sung (`revise`, bắt buộc có lý do); chọn tên người duyệt từ `/config/approvers`, khoá nút khi chưa chọn |
| 5 | Duyệt rollback | `pending.kind == "rollback"` | Tiêu đề riêng ("KPI không đạt, đề xuất quay lại bản SOP trước"); số đo trước/sau, ngưỡng; SOP đang hiệu lực → bản sẽ khôi phục |
| 6 | Run dừng chờ người | `pending.kind == "halt"` | Lý do theo `reason` (5 giá trị, cần câu chữ dễ hiểu); nếu `sop_still_in_force` thì ghi rõ SOP nào đang hiệu lực; hai nút Điều tra lại / Kết thúc |
| 7 | Kết quả đo | event `kpi_measured` | `measured`: đạt hoặc không, trước → sau, ngưỡng. `insufficient_evidence`: "chưa đủ bằng chứng", có n_after / min_samples. `not_applied`: lý do. `passed: null` không được hiện thành rỗng |
| 8 | Lỗi | `state == "error"` hoặc `run_finished.status == "error"` | Thông điệp ngắn (đừng in nguyên traceback); nút Retry; sau Retry tiếp tục nhận event (hiện đang lỗi: H-13) |
| 9 | Đã Learn | event `learning_saved` | Bài học: nguyên nhân, thay đổi, KPI trước/sau, `outcome` |
| 10 | Số liệu 3 chỉ số | API số liệu (backend làm ở R10, T-042) | defect % trước/sau, MTTD/MTTR, tỷ lệ tái diễn; 6 tháng mô phỏng; biểu đồ đơn giản (không làm biểu đồ phức tạp) |
| 11 | Dữ liệu | API audit_log, sop_versions, learning_store (R9) | Bảng chỉ đọc: ai duyệt gì, lúc nào; lịch sử phiên bản SOP |

Thứ tự gợi ý đến 13/10: 4, 5, 6, 7, 8, 3, 2, rồi 9. Màn 1, 10, 11 làm khi API có.

## Nhánh cần có fixture
Đã có ví dụ thật:
- `docs/schema/examples/run-happy.json`: đi hết tới Learn;
- `docs/schema/examples/run-reject-error.json`: Từ chối dẫn tới lỗi.

Backend sẽ bổ sung ở R9 (script xuất fixture, chạy qua HTTP):
- rollback (đề xuất sai → KPI không đạt → duyệt rollback);
- từ chối rollback dẫn tới halt `rollback_declined`;
- chưa đủ bằng chứng;
- `revise`;
- halt `max_questions_reached`;
- retry sau lỗi;
- không có anomaly.

## Lỗ hổng liên quan UI (từ `docs/audits/2026-10-09.md`)
- H-09: câu hỏi "chưa đủ bằng chứng" chưa ra `pending` (backend sửa).
- H-13: Retry làm timeline đứng (SSE đóng ở `run_finished` lỗi; trùng `event_id`). Backend sửa phần `event_id`; frontend giữ luồng mở khi `status == "error"`.
- H-16: demo LLM giả, Reject / Bác bỏ / Điều tra lại hiện kết thúc bằng lỗi (backend sửa).
- H-24: kết quả run và `passed: null` hiển thị chưa rõ (frontend).

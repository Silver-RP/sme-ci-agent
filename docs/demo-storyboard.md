# Storyboard demo 4 phút và đặc tả màn hình (bản đề xuất v0.1)

Gửi bạn frontend và leader. Tài liệu này nối 3 thứ: kịch bản nói (`docs/demoscript.md`), màn hình phải có, và dữ liệu backend đã có cho màn đó (`docs/schema/payloads.md`, ví dụ thật trong `docs/schema/examples/`). Ranh giới: bạn frontend làm phần trình bày trong `dashboard/`; backend/auto-dev giữ API, dữ liệu và fixture (`docs/ui-handoff.md`).

**Câu chuyện:** một xưởng hàn reflow (SME) có 3 máy, 3 ca, 6 tháng dữ liệu. Tỷ lệ lỗi máy M02 ca đêm tăng từ khoảng 2% lên khoảng 6%. Agent phát hiện, tự điều tra, chỉ ra setpoint zone 3 bị đổi từ 180 lên 195 °C mà không ai duyệt, đề xuất khôi phục và sửa SOP. Quản đốc duyệt. KPI về lại khoảng 2%. Bài học được lưu.

Thời gian chạy thật: một vòng LLM thật mất khoảng 15–20 giây (T-030). Màn hình phải cho thấy agent **đang làm gì** trong lúc chờ, không để màn trắng.

## 1. Dòng thời gian demo

| Thời điểm | Người nói (ý chính) | Màn hình | Thao tác | Dữ liệu |
|---|---|---|---|---|
| 0:00–0:30 | SME thấy lỗi tăng nhưng không có người điều tra và học lại | S0 Bìa / vấn đề | (slide) | |
| 0:30–1:00 | Vòng khép kín Detect → Learn; người luôn là người quyết | S1 Vòng lặp (hình 8 bước, bước đang chạy sáng lên) | | `tool_called`, `hypothesis_updated`… để đổi bước sáng |
| 1:00–1:20 | "Đây là 6 tháng dữ liệu; hệ thống thấy M02 ca đêm vượt giới hạn" | S2 Tổng quan KPI | Bấm **Phân tích** | `anomaly_detected` (kpi, machine, shift, start, value, baseline, upper_limit) + chuỗi KPI (API mới, mục 3) |
| 1:20–1:50 | "Agent tự đọc log máy, lịch ca, tìm tương quan" | S3 Điều tra trực tiếp | (chờ, xem) | `tool_called` (tool, arguments), `hypothesis_updated` (nhóm, mô tả, confidence) |
| 1:50–2:00 | (nếu agent hỏi) "Thiếu bằng chứng thì nó hỏi người, không đoán" | S4 Câu hỏi | Gõ trả lời | `pending.type == "answer"` |
| 2:00–2:30 | "Đề xuất: khôi phục 180 °C và thêm bước vào SOP; tôi duyệt" | S5 Duyệt đề xuất | Chọn người duyệt, **Duyệt** | `pending.kind == "proposal"`: `proposal.hypothesis`, `change`, `rationale`, `action`, `expected_kpi`, `sop_proposal.new_content`, `current_sop.content` |
| 2:30–3:00 | "Sau thay đổi, tỷ lệ lỗi về 1,9%, đạt mục tiêu 2%" | S6 Kết quả đo | | `kpi_measured` (status, passed, before, after, target, n_before, n_after) |
| 3:00–3:15 | (phương án B) "Nếu không đạt, agent đề xuất rollback, người xác nhận" | S7 Duyệt rollback | | `pending.kind == "rollback"`, fixture `run-rollback.json` |
| 3:15–3:45 | "Agent chỉ đọc dữ liệu; mọi thay đổi có người duyệt, có phiên bản, có nhật ký" | S8 Nhật ký và phiên bản SOP | | audit_log, sop_versions (API mới, mục 3) |
| 3:45–4:00 | Bài học được lưu; nhiều ngành bằng config | S9 Bài học + 3 chỉ số | | `learning_saved`; chỉ số 3 (R10, T-042) |

Phương án dự phòng: phát lại một run đã ghi (record/replay, T-041) bằng `?source=fixture&file=<run>.json`, cùng màn hình, không cần LLM. Có thêm video quay sẵn.

## 2. Đặc tả màn hình (thứ tự ưu tiên)

### S5 Duyệt đề xuất: ưu tiên 1 (hiện đang lỗi, H-44)
- **Tiêu đề:** "Agent đề xuất thay đổi, cần bạn duyệt".
- **Khối "Vì sao":** giả thuyết (`hypothesis.group`, `description`), thanh độ tin cậy (`confidence` 0–1), bằng chứng (`evidence_refs`, liên kết tới bước điều tra ở S3).
- **Khối "Làm gì":**
  - hành động `action` dạng câu: "Máy **M02**: `zone3_setpoint_c` **195 → 180**". Giá trị cũ lấy từ machine_log, có thể để trống ở v0.1;
  - `change` (mô tả).
- **Khối "SOP cũ → mới":** so khác biệt từng dòng giữa `current_sop.content` (bản v*N*) và `sop_proposal.new_content`. Dòng thêm tô xanh, dòng bỏ tô đỏ. Nếu không có khác biệt thì ghi rõ "không đổi nội dung".
- **Khối "Kỳ vọng":** `expected_kpi` (KPI, chiều, mục tiêu).
- **Người duyệt:** chọn từ `/config/approvers` (dropdown, không gõ tự do). Có ô lý do.
- **Nút:**
  - **Duyệt**;
  - **Từ chối**;
  - **Bác bỏ giả thuyết / bổ sung thông tin**: bắt buộc nhập lý do.

  Khi đang gửi, khoá nút. Gặp lỗi 409 thì tải lại trạng thái.
- **Kiểm thử:** vitest dùng đúng `pending` trong `docs/schema/examples/run-happy.json` (payload R9i có `action`). Thẻ phải hiện đủ các khối trên.

### S3 Điều tra trực tiếp: ưu tiên 2
- Mỗi lần gọi tool là một thẻ. Thẻ có tên tool dễ hiểu: `query_logs` → "Đọc log máy", `correlate` → "Tìm tương quan", `get_shift_schedule` → "Xem lịch ca". Kèm tham số chính (máy, khoảng thời gian) và trạng thái (đang chạy / xong).
- Bảng giả thuyết cập nhật dần: nhóm Ishikawa, mô tả rút gọn, thanh confidence. Giả thuyết dẫn đầu được làm nổi.
- Trong lúc chờ LLM: hiển thị "Agent đang …" theo bước hiện tại. Không để màn trắng.

### S6 Kết quả đo: ưu tiên 3
- Hai số lớn "Trước" và "Sau" (định dạng %), mũi tên theo `direction`, đường mục tiêu, nhãn **Đạt** hoặc **Chưa đạt** (từ `passed`). Hiển thị số mẫu `n_before`/`n_after`.
- `status` khác `measured`:
  - `insufficient_evidence`: "Chưa đủ dữ liệu sau thay đổi", kèm ô trả lời;
  - `not_applied`: lý do.
- Không bao giờ hiện chuỗi `passed=` hay `null`.

### S2 Tổng quan KPI: ưu tiên 4
- Biểu đồ đường KPI theo thời gian (một máy/ca, hoặc chọn), đường baseline và upper_limit, vùng anomaly tô màu (`start`–`end`). Biểu đồ đơn giản, không cần tương tác phức tạp.
- Cần API chuỗi KPI (mục 3).

### S4 Câu hỏi, S7 Rollback, S1 Vòng lặp, S8 Nhật ký, S9 Bài học + chỉ số: ưu tiên 5
- **S4:** câu hỏi của agent, lần hỏi `attempt/max_questions`, ô trả lời.
- **S7:** tiêu đề riêng "KPI không đạt, đề xuất quay về SOP trước", số đo trước/sau, SOP đang hiệu lực → bản sẽ khôi phục.
- **Dừng chờ người (`kind == "halt"`):** lý do dễ hiểu theo `reason` (5 giá trị), hai nút Điều tra lại / Kết thúc.
- **S1:** hình vòng 8 bước; bước sáng theo event mới nhất.
- **S8:** bảng chỉ đọc ai duyệt gì lúc nào; lịch sử phiên bản SOP.
- **S9:** bài học (nguyên nhân, thay đổi, KPI trước/sau, `outcome`); 3 chỉ số (defect %, MTTD/MTTR, tỷ lệ tái diễn).

### Trạng thái chung (mọi màn)
- Lỗi run (`state == "error"`): thông điệp ngắn, nút **Thử lại**. Ẩn nút khi `retryable == false`. Sau khi thử lại, luồng event phải tiếp tục (H-13).
- Kết thúc run: phân biệt **Hoàn tất (đã học)**, **Đã đóng bởi người**, **Không có bất thường**, **Lỗi**. Không gộp hết thành "finished" (H-24).

## 3. API backend cần bổ sung cho storyboard (R10, auto-dev làm)
| API | Cho màn | Ghi chú |
|---|---|---|
| `GET /runs` | danh sách run, demo chọn lại run | id, trạng thái, thời điểm, kết quả |
| `GET /kpi/series?kpi=&machine=&shift=` | S2 | Từ `production_log` (hợp đồng dữ liệu) |
| `GET /audit?run_id=` và `GET /sop/{id}/versions` | S8 | Chỉ đọc |
| `GET /metrics` | S9 | 3 chỉ số (T-042) |
| `?source=fixture&file=` | dự phòng | Phát lại run đã ghi |

## 4. Phong cách
- Ngôn ngữ hiển thị: tiếng Việt cho demo tại Việt Nam, giữ được tiếng Nhật/Anh sau (chuỗi tách ra một file).
- Màu: đạt = xanh, chưa đạt hoặc anomaly = đỏ cam, chờ người = vàng. Mỗi khối có tiêu đề ngắn bằng động từ ("Vì sao", "Làm gì", "Kết quả").
- Màn chiếu 1920×1080, chữ đủ lớn để đọc từ cuối phòng (thân chữ ≥ 18px).

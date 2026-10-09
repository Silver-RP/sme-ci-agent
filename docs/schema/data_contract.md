# Hợp đồng dữ liệu đầu vào (bản đề xuất v0.1, chờ leader duyệt)

Tài liệu này mô tả dữ liệu mà một SME cần đưa vào để SME CI Agent phát hiện, điều tra và đo cải tiến. Simulator (sandbox) phải sinh dữ liệu **đúng hợp đồng này**; kịch bản mới (khó hơn, nhiều nguyên nhân) cũng được dựng trên hợp đồng này. MVP chỉ dùng dữ liệu synthetic; không nhận dữ liệu thật hay dữ liệu cá nhân (CLAUDE.md).

Người dùng (leader) chốt ngày 2026-10-09: mức chuẩn hoá là **hợp đồng + nhập CSV**. Chưa làm ánh xạ cột tuỳ biến và đa ngành (để sau Demo Day).

## 1. Nguyên tắc
- **Tên cột trung tính.** KPI là *giá trị* của một cột, không phải tên cột; agent không ngầm hiểu "defect". Tên KPI, đơn vị, chiều tốt và ngưỡng lấy từ `data/context_profile.yaml`.
- **Số đếm gốc tốt hơn tỷ lệ.** SME có thể xuất từ Excel số sản phẩm làm ra và số lỗi. Hệ thống tự tính tỷ lệ, nên đo trước/sau có trọng số và không mất thông tin.
- **Chỉ đọc.** Agent và tool không bao giờ sửa dữ liệu nguồn. Dữ liệu sau thay đổi được sinh riêng cho từng run (sandbox).
- **Một nguồn sự thật cho tên.** Mã máy, ca, người vận hành phải khớp giữa các bảng. Bộ kiểm hợp lệ báo lỗi nếu không khớp.
- **Múi giờ.** Mọi thời điểm là giờ địa phương của nhà máy, không kèm múi giờ, định dạng ISO `YYYY-MM-DDTHH:MM:SS`. Múi giờ nhà máy khai một lần trong config.

## 2. Các bảng

Ký hiệu: **B** = bắt buộc, **T** = tuỳ chọn. Kiểu: `str`, `int`, `float`, `bool`, `datetime`, `date`.

### 2.1 `production_log` (B): sản lượng và lỗi theo ca, theo máy
Bảng mới, thay vai trò nhập liệu của `kpi_log` hiện nay. `kpi_log` trở thành bảng **dẫn xuất** mà hệ thống tự tính từ bảng này.

| Cột | Kiểu | B/T | Mô tả, ràng buộc |
|---|---|---|---|
| `shift_start` | datetime | B | Giờ bắt đầu ca |
| `shift` | str | B | Có trong `plant.shifts` của config |
| `machine_id` | str | B | Có trong `plant.machines` |
| `units_produced` | int | B | ≥ 0 |
| `units_defective` | int | B | 0 ≤ giá trị ≤ `units_produced` |
| `units_reworked` | int | T | 0 ≤ giá trị ≤ `units_produced` |
| `product_id` | str | T | Mã sản phẩm/lot (để sau: phân tích theo sản phẩm) |
| `batch_id` | str | T | Lô nguyên liệu dùng trong ca; nối với `material_batches` |

Khoá: (`shift_start`, `machine_id`) không trùng. Mỗi KPI trong config khai công thức, ví dụ `defect_rate = units_defective / units_produced`; ca có `units_produced = 0` thì bỏ qua và ghi cảnh báo.

### 2.2 `machine_log` (B): sự kiện máy
| Cột | Kiểu | B/T | Mô tả, ràng buộc |
|---|---|---|---|
| `timestamp` | datetime | B | |
| `machine_id` | str | B | Có trong `plant.machines` |
| `event_type` | str | B | Một trong `setpoint_change`, `maintenance`, `calibration`, `breakdown`, `note` (danh sách khai trong config) |
| `parameter` | str | B nếu `setpoint_change` | Có trong `actions` của config (ví dụ `zone3_setpoint_c`) |
| `old_value`, `new_value` | float | B nếu `setpoint_change` | Hữu hạn; nằm trong khoảng `min`/`max` của tham số |
| `operator_id` | str | T | Ai thao tác; nối với `shift_schedule` |
| `note` | str | T | Ghi chú tự do |

### 2.3 `shift_schedule` (B): ai đứng máy
| Cột | Kiểu | B/T | Mô tả |
|---|---|---|---|
| `date` | date | B | |
| `shift` | str | B | |
| `machine_id` | str | B | |
| `operator_id` | str | B | Mã ẩn danh (ví dụ `OP-017`), **không** dùng tên thật |
| `is_substitute` | bool | B | Người thay ca |
| `training_level` | int | T | 1–3; dùng cho giả thuyết nhóm people (H-29) |

### 2.4 `material_batches` (T): lô nguyên liệu
Thay cho cặp `inventory` + `supplier` hiện nay, vốn chưa nối được với sản xuất.

| Cột | Kiểu | B/T | Mô tả |
|---|---|---|---|
| `batch_id` | str | B | Duy nhất |
| `material_id` | str | B | |
| `supplier_id` | str | B | |
| `received_date` | date | B | |
| `qc_result` | str | T | `pass` / `fail` / `conditional` |

### 2.5 `environment_log` (T): điều kiện xưởng
| Cột | Kiểu | B/T | Mô tả |
|---|---|---|---|
| `timestamp` | datetime | B | |
| `area` | str | B | Khu vực; config ánh xạ máy → khu vực |
| `ambient_temp_c` | float | T | |
| `humidity_pct` | float | T | 0–100 |

Bảng này làm cho giả thuyết `ambient_temperature` (đang `no_data`) có tín hiệu.

### 2.6 SOP (B): giữ nguyên cách hiện nay
Bản gốc nằm trong `data/context_profile.yaml` (`sop:`: id, version, title, steps). Các bản do agent đề xuất được lưu trong bảng `sop_versions` (Postgres), có phiên bản, không ghi đè. SME nhập SOP bằng YAML hoặc CSV (`sop_id, version, title, step_no, step_text`).

## 3. Nhập CSV
- Thư mục nhập: mỗi bảng một file `<tên bảng>.csv`, UTF-8, dấu phẩy, có dòng tiêu đề đúng tên cột ở mục 2. Cột thừa bị bỏ qua và có cảnh báo; thiếu cột bắt buộc thì báo lỗi.
- Lệnh (dự kiến ở R10): `uv run python scripts/import_data.py <thư mục> [--check-only]`.
  1. Kiểm hợp lệ theo mục 4, in báo cáo (số dòng, lỗi, cảnh báo).
  2. Nếu không lỗi thì nạp vào dataset được đặt tên để agent dùng: `SME_DATASET=<tên>`, mặc định là dữ liệu simulator.
  3. Không sửa file nguồn.
- Mẫu: `data/templates/*.csv`, mỗi file có 3–5 dòng ví dụ. Simulator xuất được dữ liệu ra đúng định dạng này (`scripts/gen_data.py --out-dir <thư mục>`), để thử vòng nhập → kiểm → chạy agent.

## 4. Kiểm hợp lệ (validator)
Gồm lỗi (chặn) và cảnh báo (cho qua, ghi báo cáo).

| Mã | Loại | Kiểm |
|---|---|---|
| V01 | lỗi | Thiếu bảng bắt buộc hoặc thiếu cột bắt buộc |
| V02 | lỗi | Sai kiểu (không parse được ngày giờ, số), giá trị NaN/inf |
| V03 | lỗi | Vi phạm ràng buộc: `units_defective > units_produced`, giá trị âm, ngoài `min`/`max` |
| V04 | lỗi | Khoá trùng (`shift_start`, `machine_id`) |
| V05 | lỗi | Mã máy, ca, tham số không có trong config |
| V06 | cảnh báo | Thiếu ca (lỗ hổng thời gian) lớn hơn N ca liên tiếp (N trong config) |
| V07 | cảnh báo | `operator_id` trong `machine_log` không có trong `shift_schedule` |
| V08 | cảnh báo | Lịch sử dưới `detect.reference_days` + khoảng tối thiểu: Detect kém tin cậy |
| V09 | lỗi | Có dấu hiệu dữ liệu cá nhân (cột tên giống `name`, `email`, `phone`) |

Mỗi lỗi trong báo cáo ghi: mã, bảng, dòng, cột, giá trị, cách sửa.

## 5. Ảnh hưởng lên code hiện tại (để lập R10/R11)
- `backend/sandbox/schema.py`: thêm `production_log`, `material_batches`, `environment_log`; `kpi_log` thành bảng dẫn xuất; `inventory`/`supplier` giữ tạm cho tương thích rồi bỏ.
- Simulator sinh số đếm (phân phối nhị thức theo `units_produced`), không sinh tỷ lệ trực tiếp. Nhờ đó nhiễu thật hơn, giúp làm anomaly nhỏ hơn (H-29).
- Tool chỉ đọc (`query_logs`, `correlate`, `get_shift_schedule`) đọc theo hợp đồng mới. `correlate` dùng `batch_id`, `environment_log`, `training_level` để có tín hiệu cho các nhóm hiện đang `no_data`.
- Measure và chỉ số 3 (H-11, T-042) tính từ `production_log` (có trọng số theo sản lượng).
- `docs/schema/events.json` **không đổi**.

## 6. Câu hỏi chờ leader duyệt
1. Đổi nhập liệu từ `kpi_log` (tỷ lệ) sang `production_log` (số đếm): đồng ý?
2. Bỏ `inventory` + `supplier`, thay bằng `material_batches`: đồng ý?
3. `environment_log` và `training_level` (tuỳ chọn) đưa vào R11 cùng kịch bản khó: đồng ý?

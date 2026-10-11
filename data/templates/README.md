# File mẫu CSV và bộ dữ liệu sai cố ý (D2)

Dữ liệu **synthetic**, theo `docs/schema/data_contract.md` (bản chốt v0.1). Dùng cho:
- SME: xem định dạng cần chuẩn bị (`valid/`);
- vai Q: ca kiểm thử V01–V09;
- auto-dev R10b1 (dev-04): dữ liệu test của validator. Bảng ở mục 4 là **đáp án**.

Mã người vận hành là mã ẩn danh (`OP-…`). Tên `Nguyen Van A` trong `V09b_operator_value` là giá trị giả, cố ý dùng để kiểm luật chặn dữ liệu cá nhân.

## 1. Cấu trúc

```
data/templates/
  valid/                    bộ hợp lệ: 5 bảng, mỗi bảng 5–10 dòng
  invalid/<mã>_<mô tả>/      mỗi thư mục là một bộ dữ liệu đầy đủ, chép từ valid/ rồi sửa một chỗ
```

Mỗi bộ `invalid/` chỉ vi phạm **một** luật V (mã N01–N04 đi kèm được phép). Hai ngoại lệ có nhiều dòng thay đổi vì luật cần nhiều dòng mới thấy được: `V06_gap` (thêm 8 dòng) và `V08_short_history` (sinh lại `production_log` và `shift_schedule`, 369 dòng mỗi bảng).

## 2. Config giả định
Config mặc định ở mục 1.2 và ví dụ mục 4 của hợp đồng:
- máy `M01`, `M02`, `M03`; ca `morning` 6 h, `afternoon` 14 h, `night` 22 h;
- `actions.parameters` = `zone3_setpoint_c`, `zone2_setpoint_c`, `other_parameter_c`; `zone3_setpoint_c` trong 150–220;
- KPI `defect_rate` → `units_nonconforming`, `rework_rate` → `units_reworked`;
- `detect.reference_days = 28`, `validate.min_monitor_days = 14` (ngưỡng V08 = 42 ngày), `validate.max_missing_shifts = 3`.

## 3. Bộ hợp lệ `valid/`

| File | Số dòng dữ liệu | Nội dung |
|---|---|---|
| `production_log.csv` | 9 | M01–M03 × 3 ca ngày 2026-03-10, đủ 8 cột; `batch_id` là `PST-2603-01` / `PST-2603-02` |
| `shift_schedule.csv` | 9 | Cùng 9 ca; ca đêm M02 là người thay ca `OP-SUB01` |
| `machine_log.csv` | 6 | Một dòng mỗi loại: `calibration`, `maintenance`, `setpoint_change` (M02 180 → 195, `OP-SUB01`), `note`, `program_change`, `alarm` |
| `sop.csv` | 5 | `SOP-RFL-001` bản 1 (3 bước), `SOP-CAL-002` bản 1 (2 bước) |
| `material_batches.csv` | 5 | Có `PST-2603-01`, `PST-2603-02`; hai lô không có `expiry_date` |

Tham chiếu chéo khớp: mọi `operator_id` trong `machine_log` có trong `shift_schedule`; mọi `batch_id` trong `production_log` có trong `material_batches`.

**Kết quả mong đợi của `valid/`:** 0 lỗi, 0 ghi chú, đúng **một cảnh báo V08** (`warning`, `production_log`, dòng trống, cột `shift_start`, `value` = `1`), vì dữ liệu chỉ có 1 ngày, nhỏ hơn 42. Không có V06 vì cả 3 máy đủ 3 ca trong dải xét. Đây là **cảnh báo nền**: mọi bộ `invalid/` đều có nó, trừ khi bảng 4 ghi khác.

Bộ hợp lệ nào không có cảnh báo V08 thì cần ≥ 42 ngày dữ liệu, tức hàng trăm dòng; xem `invalid/V08_short_history/` (41 ngày) để biết cách dựng.

## 4. Đáp án cho từng bộ

Quy ước:
- Cột kết quả liệt kê **đủ mọi mục** validator phải báo (so như tập hợp, không theo thứ tự). Không có mục nào khác.
- "Nền" = cảnh báo V08 `value` = `1` như mục 3.
- `row` = số dòng trong file CSV, dòng tiêu đề là 1. `—` = để trống.
- `value`: `*` nghĩa là hợp đồng không quy định, test **không** so; `""` nghĩa là chuỗi rỗng. Test không so `fix`.

| Bộ | Luật | Chỗ sửa so với `valid/` | Kết quả mong đợi (code, severity, table, row, column, value) |
|---|---|---|---|
| `V01a_missing_file` | V01 (a) | Xoá `sop.csv` | `V01, error, sop, —, —, sop.csv` · nền |
| `V01b_empty_file` | V01 (b) | `sop.csv` rỗng (0 byte) | `V01, error, sop, —, —, *` · nền |
| `V01c_header_only` | V01 (c) | `sop.csv` chỉ còn dòng tiêu đề | `V01, error, sop, —, —, *` · nền |
| `V01d_missing_column` | V01 (d) | `production_log.csv`: bỏ cột `units_nonconforming` | `V01, error, production_log, —, units_nonconforming, *` · `N04, note, production_log, —, units_nonconforming, defect_rate` · nền |
| `V01d_wrong_case` | V01 (d) | `production_log.csv` dòng 1: `shift_start` → `Shift_Start` | `V01, error, production_log, —, shift_start, *` · `N02, warning, production_log, —, Shift_Start, *` · **không có nền** (V08 cần cột `shift_start`) |
| `V01e_duplicate_column` | V01 (e) | `production_log.csv`: thêm cột `product_id` thứ hai, giá trị giống cột đầu | `V01, error, production_log, —, product_id, *` · nền. Không có N02 (mục 4.0) |
| `V02_int_decimal` | V02 | `production_log.csv` dòng 9, `units_produced`: `820` → `820.0` | `V02, error, production_log, 9, units_produced, 820.0` · nền |
| `V02_conditional_empty` | V02 | `machine_log.csv` dòng 4 (`setpoint_change`), `parameter`: `zone3_setpoint_c` → trống | `V02, error, machine_log, 4, parameter, ""` · nền |
| `V02_row_cell_count` | V02 | `production_log.csv` dòng 9: bỏ ô cuối (`batch_id`), còn 7 ô | `V02, error, production_log, 9, —, *` · nền |
| `V02_bool` | V02 | `shift_schedule.csv` dòng 9, `is_substitute`: `true` → `TRUE` | `V02, error, shift_schedule, 9, is_substitute, TRUE` · nền |
| `V02_date` | V02 | `shift_schedule.csv` dòng 2, `date`: `2026-03-10` → `2026-02-30` | `V02, error, shift_schedule, 2, date, 2026-02-30` · nền. Dòng này không tham gia V04 (ô khoá bị V02) |
| `V03_nonconforming_gt_produced` | V03 | `production_log.csv` dòng 9, `units_nonconforming`: `17` → `830` | `V03, error, production_log, 9, units_nonconforming, 830` · nền |
| `V03_reworked_gt_produced` | V03 | `production_log.csv` dòng 9, `units_reworked`: `5` → `900` | `V03, error, production_log, 9, units_reworked, 900` · nền |
| `V03_negative_count` | V03 | `production_log.csv` dòng 9, `units_reworked`: `5` → `-1` | `V03, error, production_log, 9, units_reworked, -1` · nền |
| `V03_shift_start_hour` | V03 | `production_log.csv` dòng 9, `shift_start`: `…T22:00:00` → `2026-03-10T21:00:00` | `V03, error, production_log, 9, shift_start, 2026-03-10T21:00:00` · nền |
| `V03_setpoint_out_of_limits` | V03 | `machine_log.csv` dòng 4, `new_value`: `195` → `250` | `V03, error, machine_log, 4, new_value, 250` · nền |
| `V03_expiry_before_received` | V03 | `material_batches.csv` dòng 2, `expiry_date`: `2026-09-02` → `2026-02-02` | `V03, error, material_batches, 2, expiry_date, 2026-02-02` · nền |
| `V03_qc_result_invalid` | V03 | `material_batches.csv` dòng 2, `qc_result`: `pass` → `ok` | `V03, error, material_batches, 2, qc_result, ok` · nền |
| `V03_sop_version_lt_1` | V03 | `sop.csv` dòng 6, `version`: `1` → `0` | `V03, error, sop, 6, version, 0` · `V03, error, sop, 6, step_no, 1` (nhóm `SOP-CAL-002` bản 0 chỉ có bước 2, thiếu bước 1) · nền |
| `V03_sop_step_no_lt_1` | V03 | `sop.csv` dòng 3, `step_no`: `2` → `0` | `V03, error, sop, 3, step_no, 0` · `V03, error, sop, 2, step_no, 2` (nhóm `SOP-RFL-001` bản 1 thiếu bước 2, báo ở dòng đầu nhóm) · nền |
| `V03_sop_step_gap` | V03 | `sop.csv` dòng 4, `step_no`: `3` → `4` | `V03, error, sop, 2, step_no, 3` · nền |
| `V03_sop_title_mismatch` | V03 | `sop.csv` dòng 3, `title` → `Reflow setpoint check rev B` | `V03, error, sop, 3, title, Reflow setpoint check rev B` · nền |
| `V04_duplicate_key` | V04 | `shift_schedule.csv`: thêm dòng 11 `2026-03-10,night,M02,OP-021,false` (trùng khoá với dòng 9) | `V04, error, shift_schedule, 11, date, 9` · nền |
| `V05_event_type` | V05 | `machine_log.csv` dòng 6, `event_type`: `program_change` → `recipe_swap` | `V05, error, machine_log, 6, event_type, recipe_swap` · nền |
| `V05_parameter` | V05 | `machine_log.csv` dòng 7 (`alarm`), `parameter`: `zone3_setpoint_c` → `zone9_temp_c` | `V05, error, machine_log, 7, parameter, zone9_temp_c` · nền |
| `V05_machine_case` | V05 | `production_log.csv` dòng 9, `machine_id`: `M02` → `m02` | `V05, error, production_log, 9, machine_id, m02` · nền. Không có V06: `m02` thiếu 2 ô, `M02` thiếu 1 ô, đều ≤ 3 |
| `V06_gap` | V06 | `production_log.csv`: thêm dòng 11–18 cho M01 và M03 ở cả 3 ca ngày 2026-03-11 và ca sáng 2026-03-12; M02 không có thêm dòng | `V06, warning, production_log, —, machine_id, M02 2026-03-11T06:00:00/2026-03-12T06:00:00 (4)` · `V08, warning, production_log, —, shift_start, 3` (thay cho nền) |
| `V07a_operator` | V07 (a) | `machine_log.csv` dòng 4, `operator_id`: `OP-SUB01` → `OP-099` | `V07, warning, machine_log, 4, operator_id, OP-099` · nền |
| `V07b_batch` | V07 (b) | `production_log.csv` dòng 9, `batch_id`: `PST-2603-01` → `PST-9999-99` | `V07, warning, production_log, 9, batch_id, PST-9999-99` · nền |
| `V08_short_history` | V08 | `production_log.csv` và `shift_schedule.csv` sinh lại: M01–M03 × 3 ca, mỗi ngày từ 2026-01-01 tới 2026-02-10 (369 dòng mỗi bảng), `batch_id` để trống; các file khác giữ nguyên | `V08, warning, production_log, —, shift_start, 41` · **không có nền, không có V06** |
| `V09a_header` | V09 (a) | `shift_schedule.csv`: thêm cột `operator_name` (ô trống) | `V09, error, shift_schedule, —, operator_name, *` · `N02, warning, shift_schedule, —, operator_name, *` · nền |
| `V09b_operator_value` | V09 (b) | `shift_schedule.csv` dòng 3, `operator_id`: `OP-005` → `Nguyen Van A` (người này không xuất hiện trong `machine_log`, nên không sinh V07) | `V09, error, shift_schedule, 3, operator_id, Nguyen Van A` · nền |

Ghi chú về `V08_short_history`:
- `shift_schedule` vẫn chứa mọi `operator_id` mà `machine_log` dùng, nên không có V07.
- `machine_log` giữ nguyên các sự kiện tháng 3, nằm ngoài khoảng sản xuất; không luật nào kiểm điều này.

## 5. Chưa có trong D2
- V02 file không phải UTF-8: R10b1 tự thêm ở `tests/fixtures/contract/` nếu cần.
- N01 (file thừa) và N03 (ca `units_produced = 0`) chưa có bộ riêng; chúng không phải luật V.

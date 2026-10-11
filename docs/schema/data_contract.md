# Hợp đồng dữ liệu đầu vào v0.1 (bản chốt D1)

> **Trạng thái:** bản chốt chi tiết của D1 (#66), chờ review vai Q và leader. Giữ nguyên **3 hướng leader đã duyệt** ở mục 6 (2026-10-10). Backend (R10b1) code theo bản này sau khi PR D1 merge. Các thay đổi so với bản đề xuất v0.1 mà R10b1 phải theo nằm ở mục 8. Số mục 1–6 giữ như bản đề xuất v0.1 để các tài liệu khác (`plan/R10b1.md`, brief vai A) vẫn trỏ đúng.

Tài liệu này mô tả dữ liệu mà một SME cần đưa vào để SME CI Agent phát hiện, điều tra và đo cải tiến. Simulator (sandbox) phải sinh dữ liệu **đúng hợp đồng này**; kịch bản mới (khó hơn, nhiều nguyên nhân) cũng được dựng trên hợp đồng này. MVP chỉ dùng dữ liệu synthetic; không nhận dữ liệu thật hay dữ liệu cá nhân (CLAUDE.md).

Người dùng (leader) chốt ngày 2026-10-09: mức chuẩn hoá là **hợp đồng + nhập CSV**. Chưa làm ánh xạ cột tuỳ biến và đa ngành (để sau Demo Day).

Các con số "thực tế ngành" nhắc tới ở đây là giả định để mô phỏng, sẽ được kiểm chứng kèm nguồn ở D3 (`docs/research/reflow_domain.md`). Chúng **không** phải ràng buộc của validator.

## 1. Nguyên tắc
- **Tên cột trung tính.** KPI là *giá trị* của một cột, không phải tên cột; agent không ngầm hiểu "defect". Tên KPI, đơn vị, chiều tốt và ngưỡng lấy từ `data/context_profile.yaml`. Cột đếm sản phẩm không đạt tên là `units_nonconforming` (thuật ngữ ISO 9001), dùng được cho mọi ngành.
- **Số đếm gốc tốt hơn tỷ lệ.** SME có thể xuất từ Excel số sản phẩm làm ra và số sản phẩm không đạt. Hệ thống tự tính tỷ lệ, nên đo trước/sau có trọng số và không mất thông tin.
- **Chỉ đọc.** Agent và tool không bao giờ sửa dữ liệu nguồn. Dữ liệu sau thay đổi được sinh riêng cho từng run (sandbox).
- **Một nguồn sự thật cho tên.** Mã máy, ca, tham số, loại sự kiện lấy từ config (mục 1.2). Bộ kiểm hợp lệ báo lỗi nếu không khớp.
- **Múi giờ.** Mọi thời điểm là giờ địa phương của nhà máy, không kèm múi giờ. Múi giờ nhà máy khai một lần trong config (`plant.timezone`).
- **Không dữ liệu cá nhân.** Xem mục 7.

### 1.1 Quy ước định dạng chung (áp dụng cho mọi bảng)

| Kiểu | Định dạng chấp nhận | Ví dụ đạt | Ví dụ bị V02 |
|---|---|---|---|
| `str` | Chuỗi bất kỳ | `M02` | (không có) |
| `int` | Số nguyên thập phân, có thể có dấu `-`, khớp `^-?\d+$` | `820` | `820.0`, `8.2e2`, `abc` |
| `float` | Số thực, dấu thập phân là `.`, khớp `^-?\d+(\.\d+)?$` | `195`, `180.5`, `-3` | `180,5`, `1e2`, `.5`, `NaN`, `inf` |
| `bool` | Chỉ `true` hoặc `false` (chữ thường) | `true` | `TRUE`, `1`, `yes` |
| `date` | `YYYY-MM-DD`, ngày có thật | `2026-03-10` | `10/03/2026`, `2026-3-10`, `2026-02-30` |
| `datetime` | `YYYY-MM-DDTHH:MM:SS`, **không** kèm múi giờ, ngày giờ có thật | `2026-03-10T22:00:00` | `2026-03-10 22:00`, `2026-03-10T22:00:00+07:00`, `2026-03-10T24:00:00` |

- **Khoảng trắng** đầu/cuối của mọi ô (mọi kiểu) và mọi tên cột bị cắt trước khi kiểm: `" 820 "` đọc là `820`.
- **Ô trống** (rỗng sau khi cắt) nghĩa là "không có giá trị". Chỉ được trống ở cột tuỳ chọn (T), hoặc ở cột "B nếu …" khi điều kiện không thỏa. Ô trống ở cột bắt buộc là lỗi V02.
- **Tên cột** viết thường, đúng tên ở mục 2, phân biệt hoa thường; thứ tự cột tuỳ ý. Tên file và mọi mã (máy, ca, loại sự kiện, tham số) cũng phân biệt hoa thường.
- **Đơn vị** ghi ở cột "Đơn vị" của từng bảng; `—` nghĩa là không có đơn vị (mã, nhãn). Tham số máy lấy đơn vị theo hậu tố tên (`_c` = °C).
- **Ca đêm** thuộc về **ngày bắt đầu ca**: ca `night` bắt đầu `2026-03-10T22:00:00` có `date = 2026-03-10` trong `shift_schedule`.

### 1.2 Khoá config mà hợp đồng dựa vào

D1 chỉ đặt tên và định nghĩa; **backend thêm vào `data/context_profile.yaml` ở R10b1**. Hiện `plant.*` chỉ có trong `data/scenarios/scenario1.yaml`; R10b1 đưa sang domain config để validator đọc được cả khi dữ liệu nhập không đến từ simulator.

| Khoá | Kiểu | Mặc định | Ý nghĩa |
|---|---|---|---|
| `plant.machines` | list[str] | (bắt buộc, không mặc định) | Mã máy hợp lệ, ví dụ `[M01, M02, M03]`. Dùng cho V05 |
| `plant.shifts` | list[str] | (bắt buộc) | Tên ca hợp lệ theo thứ tự trong ngày, ví dụ `[morning, afternoon, night]`. Dùng cho V05, V06 |
| `plant.shift_start_hours` | dict[str, int] | (bắt buộc) | Giờ bắt đầu từng ca, 0–23, ví dụ `{morning: 6, afternoon: 14, night: 22}`. Mỗi ca trong `plant.shifts` có đúng một giá trị. Dùng cho V03, V06 |
| `plant.timezone` | str (tên IANA) | `Asia/Ho_Chi_Minh` | Múi giờ nhà máy, chỉ để hiển thị và ghi tài liệu; dữ liệu không kèm múi giờ |
| `machine_log.event_types` | list[str] | `[setpoint_change, program_change, maintenance, calibration, breakdown, alarm, note]` | Loại sự kiện hợp lệ (V05). Phải chứa giá trị của `signals.setpoint_event` |
| `kpis[].numerator` | str | (bắt buộc với mỗi KPI) | Tên cột trong `production_log` làm tử số. Ví dụ `defect_rate` → `units_nonconforming`, `rework_rate` → `units_reworked` |
| `kpis[].denominator` | str | `units_produced` | Tên cột làm mẫu số |
| `validate.max_missing_shifts` | int ≥ 1 | `3` | N của V06: số ca trống liên tiếp tối đa trên một máy trước khi cảnh báo. Mặc định 3 để một ngày nghỉ (3 ca) không bị cảnh báo |
| `validate.min_monitor_days` | int ≥ 0 | `14` | Số ngày theo dõi tối thiểu sau kỳ tham chiếu. V08 cảnh báo khi lịch sử < `detect.reference_days` + giá trị này (mặc định 28 + 14 = 42 ngày) |
| `validate.operator_id_pattern` | str (regex) | `^OP-[A-Z0-9]+$` | Mẫu mã người vận hành ẩn danh. Dùng cho V09 |
| `validate.pii_tokens` | list[str] | `[name, fullname, email, phone, tel, mobile, address, birth, birthday, dob, cccd, cmnd]` | Từ khoá gợi ý dữ liệu cá nhân trong tên cột. Dùng cho V09 |

Các khoá đã có và được dùng lại: `actions.parameters`, `actions.limits` (V03, V05), `detect.reference_days` (V08), `signals.setpoint_event`.

## 2. Các bảng

Ký hiệu: **B** = bắt buộc, **T** = tuỳ chọn. Bảng **B** phải có file; bảng **T** có thể vắng mặt. Cột **B** phải có trong tiêu đề và mọi dòng phải có giá trị.

### 2.1 `production_log` (B): sản lượng và sản phẩm không đạt theo ca, theo máy
Thay vai trò nhập liệu của `kpi_log` cũ. `kpi_log` giờ là bảng **dẫn xuất** (mục 2.8).

| Cột | Kiểu | Đơn vị | B/T | Ràng buộc |
|---|---|---|---|---|
| `shift_start` | datetime | — | B | Giờ:phút:giây = `plant.shift_start_hours[shift]`:00:00 (V03) |
| `shift` | str | — | B | Có trong `plant.shifts` (V05) |
| `machine_id` | str | — | B | Có trong `plant.machines` (V05) |
| `units_produced` | int | board | B | ≥ 0 (V03) |
| `units_nonconforming` | int | board | B | 0 ≤ giá trị ≤ `units_produced` (V03) |
| `units_reworked` | int | board | T | 0 ≤ giá trị ≤ `units_produced` (V03) |
| `product_id` | str | — | T | Mã sản phẩm (để sau: phân tích theo sản phẩm) |
| `batch_id` | str | — | T | Lô nguyên liệu chính dùng trong ca; nên có trong `material_batches` (V07) |

- **Khoá:** (`shift_start`, `machine_id`) không trùng (V04).
- **Ca nghỉ:** không có dòng. Ca có dòng nhưng `units_produced = 0` là hợp lệ; ca đó bị bỏ qua khi tính KPI và có ghi chú N03 trong báo cáo (mục 4.0), không phải vi phạm.
- **Thực tế ở SME:** có ở gần như mọi xưởng. Nguồn là phiếu ca / phiếu theo lô (traveler) trên giấy được nhập lại vào Excel, hoặc báo cáo ca xuất từ MES đơn giản. Số board làm ra và số board lỗi là hai con số trưởng ca phải báo hằng ca. `units_reworked` có ở xưởng có trạm sửa (rework) ghi sổ riêng. `batch_id` có khi xưởng ghi lô kem hàn trên phiếu ca.

### 2.2 `machine_log` (B): sự kiện máy

| Cột | Kiểu | Đơn vị | B/T | Ràng buộc |
|---|---|---|---|---|
| `timestamp` | datetime | — | B | |
| `machine_id` | str | — | B | Có trong `plant.machines` (V05) |
| `event_type` | str | — | B | Có trong `machine_log.event_types` (V05) |
| `parameter` | str | — | B nếu `setpoint_change`; T nếu `alarm`; bỏ qua với loại khác | Với `setpoint_change` và `alarm` có giá trị: thuộc `actions.parameters` (V05) |
| `old_value` | float | theo `parameter` | B nếu `setpoint_change`; bỏ qua với loại khác | Trong `actions.limits[parameter]` (gồm biên) (V03) |
| `new_value` | float | theo `parameter` | B nếu `setpoint_change`; T nếu `alarm`; bỏ qua với loại khác | Như `old_value`. Với `alarm`: giá trị đo được lúc cảnh báo, chỉ kiểm định dạng (V02), không kiểm `limits` |
| `operator_id` | str | — | T | Khớp `validate.operator_id_pattern` (V09); nên có trong `shift_schedule` (V07) |
| `note` | str | — | T | Ghi chú tự do; không ghi tên người (mục 7) |

Ý nghĩa `event_type` (mặc định):

| Giá trị | Nghĩa | Cột kèm theo |
|---|---|---|
| `setpoint_change` | Đổi giá trị đặt của một tham số | `parameter`, `old_value`, `new_value` bắt buộc |
| `program_change` | Đổi chương trình lò (thường khi đổi sản phẩm) | Mã chương trình ghi ở `note` (ví dụ `PRG-B12`) |
| `maintenance` | Bảo trì **có kế hoạch** | |
| `calibration` | Hiệu chuẩn cảm biến / đo profile | |
| `breakdown` | Hỏng đột xuất | |
| `alarm` | Cảnh báo từ bộ điều khiển (ví dụ nhiệt lệch tạm thời) | `parameter`, `new_value` tuỳ chọn |
| `note` | Ghi chú khác của người vận hành | |

- "Bỏ qua" nghĩa là ô có thể trống hoặc có giá trị; validator không kiểm ô đó (kể cả V02) và hệ thống không dùng nó.
- **Khoá:** không có; hai sự kiện cùng thời điểm là hợp lệ.
- **Thực tế ở SME:** bộ điều khiển lò reflow thường tự lưu lịch sử đổi chương trình, đổi setpoint và cảnh báo; xưởng xuất ra CSV khi cần nhưng ít ai đọc. Bảo trì và hiệu chuẩn ghi trong sổ bảo trì (giấy hoặc Excel). Đổi setpoint "ngoài sổ" là nguồn gốc của kịch bản 1. Trong 6 tháng một lò thật có hàng trăm dòng (chỉnh nhỏ theo sản phẩm, đổi chương trình, cảnh báo); simulator phải sinh "nhiễu" này (`docs/research/data_realism.md` mục 3.3).

### 2.3 `shift_schedule` (B): ai đứng máy

| Cột | Kiểu | Đơn vị | B/T | Ràng buộc |
|---|---|---|---|---|
| `date` | date | — | B | Ngày bắt đầu ca (mục 1.1) |
| `shift` | str | — | B | Có trong `plant.shifts` (V05) |
| `machine_id` | str | — | B | Có trong `plant.machines` (V05) |
| `operator_id` | str | — | B | Mã ẩn danh khớp `validate.operator_id_pattern`, ví dụ `OP-017`; **không** dùng tên thật (V09) |
| `is_substitute` | bool | — | B | `true` nếu là người thay ca |

- **Khoá:** (`date`, `shift`, `machine_id`) không trùng (V04).
- `training_level` chuyển sang R11 (mục 2.5).
- **Thực tế ở SME:** lịch ca / bảng phân công hằng tuần trong Excel, đôi khi là bảng giấy dán ở xưởng. Người thay ca thường được ghi tay bên cạnh; khi nhập lại thì đánh `is_substitute = true`. Xưởng đổi tên người thành mã trước khi đưa vào hệ thống.

### 2.4 `material_batches` (T): lô nguyên liệu
Thay cho cặp `inventory` + `supplier` cũ, vốn không nối được với sản xuất.

| Cột | Kiểu | Đơn vị | B/T | Ràng buộc |
|---|---|---|---|---|
| `batch_id` | str | — | B | Không trùng (V04) |
| `material_id` | str | — | B | Mã vật tư, ví dụ `PASTE-SAC305` |
| `supplier_id` | str | — | B | Mã nhà cung cấp (không ghi tên công ty) |
| `received_date` | date | — | B | |
| `expiry_date` | date | — | T | Không trước `received_date` (V03) |
| `qc_result` | str | — | T | Một trong `pass`, `fail`, `conditional` (V03) |

- Dùng lô đã hết hạn trong sản xuất **không** phải lỗi dữ liệu; đó là tín hiệu để agent điều tra (nhóm `material`).
- **Thực tế ở SME:** sổ nhận hàng / kiểm tra đầu vào (IQC) trong Excel. Kem hàn gần như luôn có số lô và hạn dùng in trên lọ, vì phải bảo quản lạnh và rã đông có thời hạn; nhiều xưởng ghi lại hai thông tin này. Lô PCB và linh kiện ít khi được truy vết ở SME nhỏ.

### 2.5 Để sang R11: `environment_log` và `training_level`
Theo quyết định của leader (mục 6 ý 3). Phần này chỉ là bản phác; R10b1 **không** hiện thực và **không** kiểm hợp lệ. Nếu thư mục nhập có `environment_log.csv` hoặc cột `training_level` thì bị bỏ qua và có cảnh báo N01 / N02 như file/cột thừa (mục 4.0). Chi tiết chốt cùng kịch bản khó ở R11.

- **`environment_log`** (T): `timestamp` (datetime), `area` (str; config ánh xạ máy → khu vực), `ambient_temp_c` (float, °C), `humidity_pct` (float, %, 0–100). Làm cho giả thuyết `ambient_temperature` (đang `no_data`) có tín hiệu.
- **`shift_schedule.training_level`** (T): int 1–3, dùng cho giả thuyết nhóm `people` (H-29).

### 2.6 SOP (B)
Giữ cách hiện nay. Bản gốc có thể nằm trong `data/context_profile.yaml` (`sop:`: id, version, title, steps); khi nhập CSV, `sop.csv` là **bắt buộc** (V01) và SOP trong file này thay cho `sop:` của config đối với dataset được nhập. Các bản do agent đề xuất được lưu trong bảng `sop_versions` (Postgres), có phiên bản, không ghi đè.

| Cột | Kiểu | Đơn vị | B/T | Ràng buộc |
|---|---|---|---|---|
| `sop_id` | str | — | B | Ví dụ `SOP-RFL-001` |
| `version` | int | — | B | ≥ 1 (V03) |
| `title` | str | — | B | Giống nhau ở mọi dòng cùng (`sop_id`, `version`) (V03) |
| `step_no` | int | — | B | ≥ 1; trong mỗi (`sop_id`, `version`) là dãy 1, 2, 3… liên tục (V03) |
| `step_text` | str | — | B | Nội dung bước |

- **Khoá:** (`sop_id`, `version`, `step_no`) không trùng (V04).
- **Thực tế ở SME:** hướng dẫn công việc (Work Instruction) trong Word hoặc giấy dán tại máy; thường có số phiên bản nhưng hay lỗi thời. Nhập vào bằng cách chép mỗi bước thành một dòng.

### 2.7 Dữ liệu vắng mặt
- Bảng T vắng mặt: các giả thuyết dựa vào bảng đó nhận tín hiệu `no_data`; agent nên hỏi người thay vì đoán.
- Cột T vắng mặt trong `production_log`: KPI có `numerator` là cột đó không được tính và có ghi chú N04 trong báo cáo (ví dụ thiếu `units_reworked` thì không có `rework_rate`).

### 2.8 `kpi_log` (dẫn xuất, không nhập)
Hệ thống tính từ `production_log`, giữ nguyên cột như hiện nay để Detect, tool và Measure đọc như cũ: `timestamp` (= `shift_start`), `date`, `shift`, `machine_id`, `kpi`, `value`. Mỗi KPI trong config sinh một dòng cho mỗi dòng `production_log`, với `value = numerator / denominator`; dòng có mẫu số 0 không sinh dòng `kpi_log`. Không ai ghi trực tiếp `kpi_log`; nếu thư mục nhập có `kpi_log.csv` thì file bị bỏ qua và có cảnh báo N01 (mục 4.0).

## 3. Nhập CSV
- Thư mục nhập: mỗi bảng một file `<tên bảng>.csv`: `production_log.csv`, `machine_log.csv`, `shift_schedule.csv`, `sop.csv`, và tuỳ chọn `material_batches.csv`. UTF-8 (chấp nhận BOM mà Excel thêm vào), dấu phẩy, có dòng tiêu đề đúng tên cột ở mục 2.
- File không thuộc danh sách trên (kể cả `kpi_log.csv`, `environment_log.csv`) không được đọc và có cảnh báo N01. Cột thừa bị bỏ qua và có cảnh báo N02 (nhưng tên cột thừa vẫn qua V09). Thiếu file hoặc cột bắt buộc là V01.
- Lệnh (R10b1): `uv run python scripts/import_data.py <thư mục> [--check-only] [--name <tên>]`.
  1. Kiểm hợp lệ theo mục 4, in báo cáo (số dòng mỗi bảng, lỗi, cảnh báo, ghi chú).
  2. Có ít nhất một **lỗi** thì không nạp gì và thoát với mã khác 0. Chỉ có cảnh báo thì vẫn nạp.
  3. Không lỗi thì nạp vào dataset được đặt tên để agent dùng: `SME_DATASET=<tên>`, mặc định là dữ liệu simulator.
  4. Không sửa file nguồn.
- Mẫu: `data/templates/*.csv` (D2), mỗi bảng 5–10 dòng ví dụ hợp lệ, cộng một bộ file sai cố ý cho mỗi luật V01–V09, mỗi bộ chỉ vi phạm **một** luật V (N01–N04 đi kèm không tính). Luật có nhiều nhánh (V01 a–e, V03, V07 a–b, V09 a–b) nên có một bộ cho mỗi nhánh. Simulator xuất được dữ liệu ra đúng định dạng này (`scripts/gen_data.py --out-dir <thư mục>`), để thử vòng nhập → kiểm → chạy agent.

## 4. Kiểm hợp lệ (validator)
Gồm **lỗi** (chặn nhập), **cảnh báo** (cho qua, ghi báo cáo) và **ghi chú** (thông tin, không phải vấn đề của dữ liệu).

### 4.0 Quy tắc chung (áp dụng cho mọi luật)
- **Phạm vi file:** validator đọc đúng 5 file ở mục 3 (tên file phân biệt hoa thường). File khác trong thư mục không được đọc, chỉ sinh N01.
- **Đọc CSV:** theo RFC 4180: dấu phẩy, ô có dấu phẩy hoặc xuống dòng phải đặt trong dấu `"`. File không giải mã được bằng UTF-8 là V02 ở mức bảng. Dòng có số ô khác số cột của tiêu đề là V02 ở dòng đó (cột để trống). Dòng hoàn toàn trống bị bỏ qua nhưng vẫn được đếm khi đánh số dòng.
- **Cắt khoảng trắng:** mọi ô và mọi tên cột được cắt khoảng trắng đầu/cuối **trước** khi kiểm. Sau khi cắt mà rỗng thì là ô trống.
- **So khớp tên và mã:** phân biệt hoa thường. `Shift_Start` không phải `shift_start`; `m02` không phải `M02`.
- **Chạy hết, không dừng sớm:** validator luôn chạy mọi luật trên mọi bảng có mặt và báo **mọi** vi phạm; không dừng ở lỗi đầu tiên. Ngoại lệ, để không báo trùng:
  - bảng bị V01 ở mức bảng (thiếu file, không có tiêu đề, không có dòng dữ liệu) thì không kiểm luật nào khác trên bảng đó;
  - cột bị thiếu (V01) thì bỏ qua mọi luật cần cột đó;
  - cột trùng tên (V01e): một mục V01 cho mỗi tên trùng, không sinh N02, và bỏ qua mọi luật cần cột đó (như cột thiếu);
  - ô đã bị V02 hoặc V09 thì không kiểm V03–V07 trên ô đó, và dòng có ô khoá bị V02 thì không tham gia V04;
  - dòng có `shift_start` bị V02 thì không tham gia V06, V08;
  - dòng có `shift` không có trong `plant.shifts` (V05) thì không kiểm giờ ca (V03) và không tham gia V06; dòng có `parameter` không có trong `actions.parameters` thì không kiểm `limits` (V03).
- **Một vi phạm, một mục:** mỗi (luật, dòng, cột) sinh một mục. Một dòng vi phạm hai ràng buộc V03 khác nhau sinh hai mục.
- **Mục báo cáo** gồm: `code`, `severity` (`error` / `warning` / `note`), `table`, `row`, `column`, `value`, `fix`.
  - `row`: số dòng vật lý trong file CSV nơi bản ghi bắt đầu, tính dòng tiêu đề là 1 (dòng dữ liệu đầu tiên là 2). Trống với mục ở mức bảng.
  - `column`: tên cột như trong hợp đồng (hoặc như trong file với V01 cột trùng, V09, N02). Trống khi không gắn cột.
  - `value`: giá trị ô sau khi cắt khoảng trắng. Luật ở mức bảng ghi giá trị như mô tả ở từng luật.
  - `fix`: câu hướng dẫn tự do. **Test không so khớp `fix`**; test kiểm `code`, `severity`, `table`, `row`, `column` và (khi luật ghi rõ) `value`.
- **Mã ngoài V01–V09** (không phải luật kiểm hợp lệ, nhưng có mã để test được):

| Mã | Mức | Khi nào |
|---|---|---|
| N01 | cảnh báo | File trong thư mục không thuộc 5 bảng ở mục 3 (ví dụ `kpi_log.csv`, `environment_log.csv`). `table` = tên file |
| N02 | cảnh báo | Cột thừa trong một bảng (kể cả `training_level`). `column` = tên cột như trong file |
| N03 | ghi chú | Dòng `production_log` có `units_produced = 0`: hợp lệ, không sinh dòng `kpi_log` |
| N04 | ghi chú | KPI không tính được vì cột `numerator` vắng mặt. `column` = tên cột, `value` = tên KPI |

**Thứ tự chạy:** V01 → V02 → V09 → V03 → V04 → V05 → V06 → V07 → V08 → N01–N04. Thứ tự các mục trong báo cáo không phải điều kiện test.

Ví dụ dưới đây giả định config mặc định: máy `M01–M03`; ca `morning` 6 h, `afternoon` 14 h, `night` 22 h; `zone3_setpoint_c` trong 150–220; `detect.reference_days = 28`. Dòng ví dụ ghi theo thứ tự cột ở mục 2. Luật cần nhiều dòng mới thấy được (V04, V06, V07, V08) thì ví dụ là một cặp dòng hoặc một bộ dữ liệu nhỏ.

### V01 (lỗi): thiếu bảng, thiếu cột bắt buộc, cấu trúc file hỏng
- **Kiểm:**
  - (a) Thiếu một trong `production_log.csv`, `machine_log.csv`, `shift_schedule.csv`, `sop.csv`. Mức bảng; `value` = tên file. `sop.csv` bắt buộc khi nhập CSV, kể cả khi config có sẵn `sop:`.
  - (b) File có mặt (kể cả bảng T) nhưng rỗng hoặc không có dòng tiêu đề. Mức bảng.
  - (c) Bảng **B** có tiêu đề nhưng không có dòng dữ liệu nào. Mức bảng. Bảng T (`material_batches`) chỉ có tiêu đề là hợp lệ.
  - (d) Tiêu đề của một bảng có mặt thiếu cột B. Mỗi cột thiếu một mục; `column` = tên cột thiếu. Cột "B nếu …" cũng phải có trong tiêu đề (`parameter`, `old_value`, `new_value` của `machine_log`).
  - (e) Tiêu đề có hai cột trùng tên. `column` = tên cột trùng.
- **Đạt** (tiêu đề `production_log.csv`): `shift_start,shift,machine_id,units_produced,units_nonconforming`
- **Vi phạm (d):** `shift_start,shift,machine_id,units_produced` → thiếu `units_nonconforming`.
- **Vi phạm (d), sai hoa thường:** `Shift_Start,shift,machine_id,units_produced,units_nonconforming` → V01 thiếu `shift_start`, kèm N02 cột thừa `Shift_Start`.

### V02 (lỗi): sai kiểu, ô bắt buộc trống, NaN/inf
- **Kiểm:**
  - Giá trị không khớp định dạng của kiểu ở mục 1.1. Cụ thể: `int` khớp `^-?\d+$`; `float` khớp `^-?\d+(\.\d+)?$` (không nhận số mũ, `NaN`, `inf`, dấu phẩy thập phân); `bool` là `true`/`false`; `date` và `datetime` phải là ngày có thật (`2026-02-30` sai) và giờ trong 00:00:00–23:59:59.
  - Ô trống ở cột B, hoặc ở cột "B nếu …" khi điều kiện thỏa (ví dụ `parameter` trống ở dòng `setpoint_change`).
  - Dòng có số ô khác tiêu đề; file không phải UTF-8 (xem 4.0).
- **Đạt** (`production_log`): `2026-03-10T22:00:00,night,M02,820,17,5,PCB-A,PST-2603-01`
- **Vi phạm:** `2026-03-10T22:00:00,night,M02,820.0,17,5,PCB-A,PST-2603-01` → `units_produced` không phải số nguyên.
- **Đạt** (`machine_log`): `2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,195,OP-SUB01,`
- **Vi phạm (B có điều kiện):** `2026-03-10T22:05:00,M02,setpoint_change,,180,195,OP-SUB01,` → `parameter` trống ở dòng `setpoint_change`.

### V03 (lỗi): vi phạm ràng buộc giá trị
- **Kiểm:** mọi ràng buộc ghi "(V03)" ở mục 2:
  - `production_log`: `units_produced`, `units_nonconforming`, `units_reworked` âm; `units_nonconforming` hoặc `units_reworked` lớn hơn `units_produced`; giờ của `shift_start` khác `plant.shift_start_hours[shift]` hoặc phút/giây khác 0 (`column` = `shift_start`). Ràng buộc so sánh báo ở cột vế trái (`units_nonconforming`, `units_reworked`).
  - `machine_log`, chỉ dòng `setpoint_change`: `old_value` hoặc `new_value` ngoài `actions.limits[parameter]` (gồm biên). Tham số không có trong `actions.limits` thì bỏ qua. `old_value = new_value` **không** vi phạm.
  - `material_batches`: `expiry_date` trước `received_date` (bằng nhau là đạt; `column` = `expiry_date`); `qc_result` ngoài `pass`/`fail`/`conditional`.
  - `sop`: `version` < 1; `step_no` < 1; `title` khác `title` của dòng đầu tiên trong cùng (`sop_id`, `version`) (báo ở từng dòng khác). **Tính liên tục của `step_no`:** tập giá trị (không tính trùng, không phụ thuộc thứ tự dòng) của mỗi (`sop_id`, `version`) phải đúng bằng {1, …, max}; nếu không, một mục cho cả nhóm: `row` = dòng đầu tiên của nhóm, `column` = `step_no`, `value` = các số còn thiếu, ví dụ `3`.
- **Đạt** (`production_log`): `2026-03-10T22:00:00,night,M02,820,17,5,PCB-A,PST-2603-01`
- **Vi phạm:** `2026-03-10T22:00:00,night,M02,820,830,5,PCB-A,PST-2603-01` → `units_nonconforming` (830) lớn hơn `units_produced` (820).
- **Vi phạm (giờ ca):** `2026-03-10T21:00:00,night,M02,820,17,5,PCB-A,PST-2603-01` → ca `night` phải bắt đầu 22:00:00.
- **Đạt** (`machine_log`): `2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,195,OP-SUB01,`
- **Vi phạm:** `2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,250,OP-SUB01,` → 250 ngoài 150–220.
- **Đạt** (`material_batches`): `PST-2603-01,PASTE-SAC305,SUP-03,2026-03-02,2026-09-02,pass`
- **Vi phạm:** `PST-2603-01,PASTE-SAC305,SUP-03,2026-03-02,2026-02-02,pass` → `expiry_date` trước `received_date`.
- **Đạt** (`sop`, ba dòng): `SOP-RFL-001,1,Reflow setpoint check,1,Verify zone3_setpoint_c at shift start`, `SOP-RFL-001,1,Reflow setpoint check,2,Record zone3_setpoint_c on the shift sheet`, `SOP-RFL-001,1,Reflow setpoint check,3,Run a first-article inspection`
- **Vi phạm:** cùng ba dòng nhưng dòng cuối có `step_no` = `4` → một mục ở dòng đầu của nhóm, `value` = `3`.

### V04 (lỗi): khoá trùng
- **Kiểm:** trùng khoá trong bảng, so trên giá trị đã cắt khoảng trắng và đã parse (phân biệt hoa thường):
  - `production_log` (`shift_start`, `machine_id`);
  - `shift_schedule` (`date`, `shift`, `machine_id`);
  - `material_batches` (`batch_id`);
  - `sop` (`sop_id`, `version`, `step_no`).

  Dòng xuất hiện đầu tiên không bị báo; **mỗi dòng xuất hiện sau** sinh một mục (ba dòng trùng → hai mục). `column` = cột đầu tiên của khoá; `value` = số dòng xuất hiện đầu tiên. `machine_log` không có khoá. Một người đứng hai máy cùng ca (cùng `operator_id`, khác `machine_id`) là hợp lệ.
- **Đạt** (`shift_schedule`, hai dòng): `2026-03-10,night,M02,OP-SUB01,true` và `2026-03-10,night,M01,OP-017,false`
- **Vi phạm:** `2026-03-10,night,M02,OP-SUB01,true` (dòng 5) và `2026-03-10,night,M02,OP-021,false` (dòng 9) → một mục ở dòng 9, `value` = `5`.

### V05 (lỗi): mã không có trong config
- **Kiểm** (phân biệt hoa thường):
  - `machine_id` ngoài `plant.machines` (ở `production_log`, `machine_log`, `shift_schedule`);
  - `shift` ngoài `plant.shifts` (ở `production_log`, `shift_schedule`);
  - `event_type` ngoài `machine_log.event_types`;
  - `parameter` ngoài `actions.parameters`, **chỉ** ở dòng `setpoint_change` và dòng `alarm` có `parameter`. Ở các loại sự kiện khác, `parameter`, `old_value`, `new_value` bị bỏ qua, không kiểm.
- **Đạt** (`machine_log`, `program_change`): `2026-03-12T07:30:00,M02,program_change,,,,OP-017,PRG-B12`
- **Vi phạm:** `2026-03-12T07:30:00,M02,recipe_swap,,,,OP-017,PRG-B12` → `event_type` không có trong config.
- **Đạt** (`machine_log`, `alarm`): `2026-03-12T09:14:00,M01,alarm,zone3_setpoint_c,,188.4,,nhiệt vùng 3 lệch tạm thời`
- **Vi phạm:** `2026-03-12T09:14:00,M01,alarm,zone9_temp_c,,188.4,,nhiệt lệch` → `parameter` không có trong `actions.parameters`.
- **Vi phạm:** `2026-03-10T22:00:00,night,m02,820,17,5,PCB-A,PST-2603-01` (`production_log`) → `m02` không phải `M02`.

### V06 (cảnh báo): lỗ hổng thời gian
- **Kiểm:**
  - **Ô ca** là cặp (ngày, ca). Một dòng `production_log` chiếm ô (ngày của `shift_start`, `shift`). Các ô xếp theo ngày, rồi theo thứ tự ca trong `plant.shifts`.
  - **Dải xét** là mọi ô từ ô sớm nhất tới ô muộn nhất của **toàn bảng** (mọi máy gộp lại).
  - Với **mỗi máy có ít nhất một dòng** trong `production_log` (máy có trong config mà không có dòng nào thì không xét), mỗi chuỗi ô liên tiếp trong dải xét mà máy đó không có dòng, dài **lớn hơn** `validate.max_missing_shifts`, sinh một mục. Dòng có `units_produced = 0` vẫn tính là có dòng.
  - Mục báo cáo: mức bảng (`row` trống), `column` = `machine_id`, `value` = `<máy> <shift_start ô đầu>/<shift_start ô cuối> (<số ô>)`, ví dụ `M02 2026-03-15T06:00:00/2026-03-16T14:00:00 (5)`.
- **Đạt** (N = 3): M02 không có dòng nào ngày chủ nhật 2026-03-15 (3 ô: morning, afternoon, night), các ngày khác đủ. Chuỗi dài 3, không lớn hơn 3.
- **Vi phạm:** M02 thiếu từ ô `2026-03-15 morning` tới ô `2026-03-16 afternoon` (5 ô liên tiếp) → `M02 2026-03-15T06:00:00/2026-03-16T14:00:00 (5)`.

### V07 (cảnh báo): tham chiếu chéo không khớp
- **Kiểm:**
  - (a) `machine_log.operator_id` (khi có giá trị) không xuất hiện ở **bất kỳ** dòng nào của `shift_schedule` (không yêu cầu cùng ngày, cùng máy);
  - (b) `production_log.batch_id` (khi có giá trị) không có trong `material_batches.batch_id`, kể cả khi thiếu hẳn file `material_batches.csv`.

  Mỗi **giá trị lạ khác nhau** báo một lần, ở dòng đầu tiên gặp giá trị đó.
- **Đạt (a)** (khi `OP-SUB01` có trong `shift_schedule`): `2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,195,OP-SUB01,`
- **Vi phạm (a):** `2026-03-10T22:05:00,M02,setpoint_change,zone3_setpoint_c,180,195,OP-099,` → `OP-099` không có trong lịch ca.
- **Đạt (b)** (khi `PST-2603-01` có trong `material_batches`): `2026-03-10T22:00:00,night,M02,820,17,5,PCB-A,PST-2603-01`
- **Vi phạm (b):** `2026-03-10T22:00:00,night,M02,820,17,5,PCB-A,PST-9999-99` → lô không có trong `material_batches`.

### V08 (cảnh báo): lịch sử quá ngắn
- **Kiểm:** độ dài lịch sử = số **ngày lịch** từ ngày của `shift_start` sớm nhất tới ngày của `shift_start` muộn nhất trong `production_log`, **tính cả hai đầu**: `(ngày cuối − ngày đầu) + 1`. Tính trên toàn bảng, không theo máy. Cảnh báo khi độ dài **nhỏ hơn** `detect.reference_days` + `validate.min_monitor_days`. Một mục mức bảng, `column` = `shift_start`, `value` = độ dài (số ngày).
- **Đạt** (mặc định 28 + 14 = 42): dữ liệu từ ngày `2026-01-01` tới `2026-02-11` (42 ngày, đúng bằng ngưỡng).
- **Vi phạm:** dữ liệu từ ngày `2026-01-01` tới `2026-02-10` (41 ngày) → `value` = `41`.

### V09 (lỗi): dấu hiệu dữ liệu cá nhân
- **Kiểm:**
  - (a) **Tên cột** trong 5 file ở mục 3, **kể cả cột thừa** (cột thừa có tên giống dữ liệu cá nhân vẫn chặn, không chỉ cảnh báo N02). Cách tách từ: chèn ranh giới giữa chữ thường và chữ hoa liền sau (`OperatorName` → `Operator Name`), đổi sang chữ thường, tách theo mọi ký tự không phải chữ/số. Vi phạm khi có **từ trọn vẹn** nằm trong `validate.pii_tokens`. Ví dụ bị chặn: `operator_name`, `OperatorName`, `Full Name`, `email_addr`, `phone`, `product_name` (chủ ý chặn chặt; dùng `product_id`). Ví dụ không bị chặn: `username`, `filename` (không phải từ trọn vẹn); đây là giới hạn đã biết. Một mục mỗi cột; `row` trống; `column` = tên cột như trong file.
  - (b) **Giá trị** `operator_id` ở `shift_schedule` và `machine_log` (khi có giá trị) không khớp **toàn bộ** `validate.operator_id_pattern` (phân biệt hoa thường: `op-017` vi phạm).
- **Đạt** (tiêu đề `shift_schedule.csv`): `date,shift,machine_id,operator_id,is_substitute`
- **Vi phạm (a):** `date,shift,machine_id,operator_id,operator_name,is_substitute` → cột `operator_name`.
- **Đạt (b):** `2026-03-10,night,M02,OP-SUB01,true`
- **Vi phạm (b):** `2026-03-10,night,M02,Nguyen Van A,true` → `operator_id` không phải mã ẩn danh.

## 5. Ảnh hưởng lên code hiện tại (để lập R10/R11)
- `backend/sandbox/schema.py`: thêm `production_log` (với `units_nonconforming`), `material_batches`, `sop` theo mục 2; `kpi_log` thành bảng dẫn xuất (mục 2.8); `inventory`/`supplier` giữ tạm cho tương thích rồi bỏ.
- `data/context_profile.yaml`: thêm các khoá ở mục 1.2.
- Simulator sinh số đếm (phân phối nhị thức theo `units_produced`), không sinh tỷ lệ trực tiếp. Nhờ đó nhiễu thật hơn, giúp làm anomaly nhỏ hơn (H-29). Simulator nên sinh thêm các dòng `machine_log` bình thường (`program_change`, `alarm`, chỉnh setpoint nhỏ) để đáp án không lộ.
- Tool chỉ đọc (`query_logs`, `correlate`, `get_shift_schedule`) đọc theo hợp đồng mới. `correlate` dùng `batch_id` để có tín hiệu cho nhóm `material`; `environment_log`, `training_level` để R11.
- Measure và chỉ số 3 (H-11, T-042) tính từ `production_log` (có trọng số theo sản lượng).
- `docs/schema/events.json` **không đổi**.

## 6. Quyết định của leader (2026-10-10: đồng ý cả 3)
1. Đổi nhập liệu từ `kpi_log` (tỷ lệ) sang `production_log` (số đếm): **đồng ý**.
2. Bỏ `inventory` + `supplier`, thay bằng `material_batches`: **đồng ý**.
3. `environment_log` và `training_level` (tuỳ chọn) đưa vào R11 cùng kịch bản khó: **đồng ý**.

## 7. Dữ liệu cá nhân
- Không cột nào chứa tên, email, số điện thoại, địa chỉ, ngày sinh hay số giấy tờ của người. Tên cột chứa từ khoá trong `validate.pii_tokens` bị chặn (V09).
- `operator_id` (ở `shift_schedule` và `machine_log`) là mã ẩn danh khớp `validate.operator_id_pattern`; giá trị không khớp bị chặn (V09). Bảng đối chiếu mã ↔ người (nếu có) ở lại nhà máy, không đưa vào hệ thống.
- Nhà cung cấp chỉ ghi bằng mã (`supplier_id`).
- Cột `note` là văn bản tự do; quy định là không ghi tên người. Validator không kiểm được nội dung này một cách tin cậy, nên đây là quy định cho người nhập, không phải luật tự động.

## 8. Thay đổi so với bản đề xuất v0.1 (R10b1 phải theo)
**R10b1 dùng tên và định nghĩa ở bản này**, kể cả chỗ `plan/R10b1.md` còn ghi theo bản đề xuất v0.1 (ví dụ `units_defective` ở dev-01). Bước đối chiếu plan với D1 ở đầu plan R10b1 cần sửa các chỗ đó.

| # | Chỗ | Bản đề xuất | Bản chốt |
|---|---|---|---|
| 1 | `production_log` | `units_defective` | **Đổi tên thành `units_nonconforming`** (tên trung tính, brief vai A mục 6). KPI `defect_rate` khai `numerator: units_nonconforming` |
| 2 | Mọi bảng | Không có đơn vị, quy ước kiểu chưa rõ | Thêm cột "Đơn vị"; quy ước định dạng chung (mục 1.1): `int` không có phần thập phân, `bool` chỉ `true`/`false`, ô trống chỉ ở cột T, ca đêm thuộc ngày bắt đầu ca |
| 3 | Config | Nhắc `plant.*`, danh sách `event_type`, N của V06 nhưng chưa định nghĩa | Mục 1.2 định nghĩa 11 khoá (kiểu, mặc định, ý nghĩa); backend thêm vào `context_profile.yaml` ở R10b1 |
| 4 | `production_log` | | `shift_start` phải khớp giờ bắt đầu ca (V03); quy định ca `units_produced = 0` và cột T vắng mặt (mục 2.7) |
| 5 | `machine_log` | 5 loại `event_type` | Thêm `program_change` và `alarm` (tuỳ chọn dùng); bảng ý nghĩa từng loại; `parameter`/`new_value` tuỳ chọn với `alarm` |
| 6 | `shift_schedule` | Có `training_level` | Chuyển `training_level` sang R11 (mục 2.5); thêm khoá (`date`, `shift`, `machine_id`) |
| 7 | `material_batches` | | Thêm cột tuỳ chọn `expiry_date` (V03: không trước `received_date`); `supplier_id` là mã, không tên |
| 8 | SOP | Chỉ nêu tên cột CSV | Bảng cột cho `sop.csv`, khoá (`sop_id`, `version`, `step_no`), `step_no` liên tục |
| 9 | `environment_log` | Bảng T trong hợp đồng | Chuyển sang mục 2.5 "Để sang R11"; R10b1 không hiện thực, file bị bỏ qua có cảnh báo |
| 10 | `kpi_log` | "Bảng dẫn xuất" | Ghi rõ cột, công thức `numerator/denominator`; `kpi_log.csv` nhập vào bị bỏ qua |
| 11 | Nhập CSV | Mẫu 3–5 dòng | Mẫu 5–10 dòng (khớp D2); có lỗi thì không nạp, mã thoát khác 0; chấp nhận BOM; thêm `--name` |
| 12 | V01–V09 | Mô tả một dòng | Định nghĩa đủ để viết test, mỗi luật có ví dụ đạt và vi phạm; thứ tự kiểm; định nghĩa "dòng" trong báo cáo. Mở rộng: V03 thêm luật SOP, `expiry_date`, giờ ca; V04 thêm khoá của `shift_schedule`, `material_batches`, `sop`; V07 thêm `batch_id` → `material_batches`; V09 thêm kiểm giá trị `operator_id` và danh sách từ khoá trong config |
| 13 | Dữ liệu cá nhân | Rải rác | Thêm mục 7 riêng |
| 14 | Quy tắc chung của validator | Không có | Mục 4.0 (sau review theo góc nhìn vai Q): cắt khoảng trắng, phân biệt hoa thường, đọc CSV theo RFC 4180, chạy hết mọi luật, khi nào bỏ qua để không báo trùng, định dạng mục báo cáo (test không so `fix`), mã N01–N04 cho file/cột thừa và ghi chú. Chốt biên: V04 báo mọi dòng trùng sau dòng đầu; V06 chỉ xét máy có dữ liệu, `value` có định dạng cố định; V08 đếm ngày lịch tính cả hai đầu, bằng ngưỡng là đạt; V09 tách camelCase và chặn cả cột thừa; `sop.csv` bắt buộc khi nhập CSV; cột trùng tên (V01e) chỉ sinh một mục V01 mỗi tên, không N02, các luật cần cột đó bị bỏ qua |

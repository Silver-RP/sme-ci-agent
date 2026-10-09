# Phân tích: làm dữ liệu đầu vào "như thật", SOP chuẩn và chỗ của kaizen

Viết ngày 2026-10-10 làm điểm xuất phát cho vai A (`docs/briefs/data-research.md`).

Các con số về ngành SMT/reflow dưới đây là **giả định hợp lý để mô phỏng**, chưa phải số đã kiểm chứng; dòng nào có **[kiểm chứng]** thì người nghiên cứu cần tìm nguồn để xác nhận hoặc sửa. Mọi dữ liệu vẫn là synthetic.

## 1. Hiện trạng: dữ liệu đang quá sơ sài

Đo trên dữ liệu sinh với `uv run python scripts/gen_data.py --seed 42` (6 tháng, 3 máy, 3 ca):

| Bảng | Số dòng | Vấn đề |
|---|---|---|
| `kpi_log` | 1 629 | Chỉ có **tỷ lệ** lỗi (một số thập phân mỗi ca). Không có sản lượng, không có loại lỗi, không có KPI thứ hai thật sự |
| `machine_log` | **4** | 6 tháng chỉ có 2 lần đổi setpoint (**đúng 2 anomaly**) và 2 dòng bảo trì. Ai đọc log cũng thấy ngay đáp án |
| `shift_schedule` | 1 629 | Người vận hành cố định theo ca (`OP-M01`, `OP-A01`…); chỉ đổi người đúng lúc anomaly. Không có trình độ, không có luân chuyển |
| `inventory` | 362 | Tồn kho theo ngày, **không nối** được với ca hay máy nào → giả thuyết "lô nguyên liệu" không kiểm chứng được |
| `supplier` | 2 | Gần như vô dụng |
| `sop` | 5 dòng (2 SOP) | Mỗi SOP 3 câu, không có thông số, dung sai, cách xử lý khi lệch, lịch sử sửa đổi |

Hệ quả (audit 2, H-29):
- anomaly lệch khoảng 10σ;
- dấu vết duy nhất trong log trỏ thẳng vào nguyên nhân;
- các nhóm nguyên nhân khác (người, nguyên liệu, môi trường) không có dữ liệu để agent loại trừ một cách có căn cứ.

Vì vậy agent không cần "điều tra" và không bao giờ phải hỏi người. SOP 3 câu cũng làm phần "SOP cũ → mới" ở màn duyệt kém thuyết phục.

## 2. Một xưởng SMT/reflow nhỏ thật có những dữ liệu gì

Dòng chảy điển hình: in kem hàn → SPI (kiểm tra kem) → gắp đặt linh kiện → **lò reflow** → AOI (kiểm quang học) → kiểm cuối / sửa. **[kiểm chứng]**

Nguồn dữ liệu ở SME thường là Excel, phiếu giấy được nhập lại, log xuất từ máy, đôi khi có MES đơn giản.

| Nhóm dữ liệu | Nội dung | Ở SME thường có không | Agent dùng để |
|---|---|---|---|
| **Sản lượng và lỗi theo ca** (traveler / phiếu ca) | số board làm, số board lỗi, theo máy/line, sản phẩm | Có (Excel/phiếu) | KPI, Detect, Measure |
| **Kết quả AOI theo mã lỗi** | bridge, thiếu thiếc, tombstone, void, bi thiếc (solder ball), lệch linh kiện… | Có ở xưởng có AOI (xuất CSV) | **Pareto lỗi**: loại lỗi gợi ý nhóm nguyên nhân |
| **Log lò reflow** | setpoint và nhiệt thực từng vùng, tốc độ băng tải, cảnh báo; thay đổi chương trình | Máy có lưu; thường không ai đọc | Bằng chứng nhóm máy |
| **Đo profile định kỳ** (profiler) | nhiệt đỉnh, thời gian trên liquidus (TAL), tốc độ tăng nhiệt; mỗi ngày/tuần/khi đổi sản phẩm | Có ở xưởng làm bài bản | Phân biệt "setpoint đúng nhưng lò lệch" (calibration) với "setpoint sai" |
| **Đổi sản phẩm (changeover)** | thời điểm, sản phẩm, chương trình lò dùng | Có | Lỗi tăng đầu ca/sau đổi mã là bình thường, không phải anomaly |
| **Bảo trì (PM/CM)** | bảo trì định kỳ, hỏng đột xuất, thay quạt/thanh nhiệt | Có (sổ bảo trì) | Báo động giả (FP1), nhóm máy |
| **Truy vết vật tư** | lô kem hàn, hạn dùng / thời gian rã đông, lô PCB, nhà cung cấp | Thường có lô kem hàn | Nhóm nguyên liệu |
| **Môi trường xưởng** | nhiệt độ, độ ẩm (kem hàn nhạy độ ẩm) | Đôi khi có (nhiệt kế ghi tự động) | Nhóm môi trường |
| **Nhân sự** | lịch ca, người thay ca, **ma trận kỹ năng** (đã đào tạo SOP nào) | Có lịch ca; ma trận kỹ năng ít khi có | Nhóm con người |
| **SOP / hướng dẫn công việc** | có phiên bản, người duyệt, ngày hiệu lực | Có nhưng hay lỗi thời | Improve, Learn |
| **Sổ sự cố / NCR / kaizen** | sự cố trước đây, biện pháp đã làm | Rời rạc | **Học từ quá khứ**, đo tái diễn |

Đề xuất chia tầng cho hợp đồng dữ liệu (D1):

| Tầng | Bảng |
|---|---|
| **Bắt buộc** | `production_log` (số đếm), `defect_log` (số lỗi theo mã lỗi theo ca/máy, mới), `machine_log`, `shift_schedule`, SOP |
| **Nên có** | `reflow_profile_check`, `changeover_log`, `maintenance_log` (tách khỏi machine_log, hoặc dùng event_type), `material_lots` |
| **Tuỳ chọn** | `environment_log`, `skill_matrix`, `kaizen_history` |

## 3. Làm dữ liệu trông như thật (quy tắc cho simulator)

### 3.1 Quy mô và nhịp sản xuất **[kiểm chứng]**
- **Sản lượng:** 300–1 500 board/ca/line, tuỳ sản phẩm. Ca đêm có thể thấp hơn.
- **Sản phẩm:** 3–6 mã. Đổi mã 0–2 lần/ca. Mỗi mã có tỷ lệ lỗi nền riêng, vì board dày đặc linh kiện thì lỗi nhiều hơn.
- **Lịch:** có chủ nhật nghỉ, ngày lễ, tuần cao điểm cuối tháng.

### 3.2 Lỗi
- Sinh **số lỗi** theo phân phối nhị thức trên số board (hoặc Poisson trên số mối hàn). Nhiễu tự co giãn theo sản lượng: ca ít hàng thì tỷ lệ dao động mạnh hơn. Như vậy thật hơn "tỷ lệ cộng nhiễu chuẩn".
- **Pareto mã lỗi nền** (ví dụ): bridge 30%, thiếu thiếc 20%, lệch linh kiện 15%, tombstone 10%, bi thiếc 10%, void 10%, khác 5%. **[kiểm chứng]**
- **Mỗi nguyên nhân để lại "chữ ký" trên Pareto.** Đây là bằng chứng gián tiếp mà agent phải suy luận ra, thay vì đọc thẳng từ log. Ví dụ **[kiểm chứng]**:
  - nhiệt soak quá cao → bi thiếc / void tăng;
  - kem hàn quá hạn hoặc ẩm → bi thiếc, thiếu thiếc;
  - người mới đặt sai chương trình lò → nhiều loại lỗi cùng tăng ngay sau changeover;
  - lò lệch nhiệt thực (calibration) → setpoint vẫn đúng nhưng profile đo được lệch.
- Lỗi tăng nhẹ 1–2 giờ đầu ca và sau changeover là **bình thường**. Detect không được báo động vì điều này.

### 3.3 Log máy phải có "nhiễu" bình thường
- Trong 6 tháng nên có hàng trăm sự kiện:
  - chỉnh setpoint nhỏ ±2–5 °C theo sản phẩm (đúng SOP, có lý do);
  - đổi chương trình lò khi changeover;
  - cảnh báo nhiệt tạm thời;
  - bảo trì định kỳ;
  - thay linh kiện máy.
- Lần đổi setpoint gây lỗi chỉ là **một trong nhiều** dòng. Nó khác các dòng khác ở chỗ: lệch khỏi cửa sổ cho phép trong SOP, không có ghi chú phê duyệt, không được trả lại.
- Có cả **dữ liệu thiếu** (vài ca mất log), **ghi chú tự do lộn xộn**, có thể có lỗi chính tả. Validator phải bắt được hoặc cảnh báo.

### 3.4 Con người
- 8–15 người vận hành luân phiên ca theo tuần; có người nghỉ phép, người thay.
- Ma trận kỹ năng: ai đã được đào tạo SOP-RFL-001 bản nào. Một người mới chưa được đào tạo bản mới nhất là nguyên nhân tiềm năng có thật, kiểm chứng được.

### 3.5 Độ khó của anomaly
- Kịch bản demo chính khoảng **3–5σ**: rõ khi nhìn biểu đồ, nhưng không hiển nhiên.
- **Có ít nhất một giả thuyết gây nhiễu có tương quan thật nhưng yếu hơn.** Ví dụ trong cùng tuần vừa có lô kem hàn mới vừa có người thay ca; agent phải dùng Pareto mã lỗi và thời điểm để loại trừ.
- **Có ít nhất một kịch bản bằng chứng không đủ**, buộc agent phải hỏi người. Ví dụ log lò của 3 ngày bị mất; người trả lời "hôm đó có đổi chương trình lò do khách đổi mã".

## 4. SOP chuẩn ban đầu (baseline) nên trông thế nào

SOP thật ở xưởng (hoặc Work Instruction, ở Nhật gọi 作業標準書 / 作業手順書) thường có các phần sau. Có thể theo mẫu TWI Job Instruction: bước chính, điểm then chốt, lý do. **[kiểm chứng mẫu cụ thể]**

1. **Đầu trang:** mã, phiên bản, ngày hiệu lực, người soạn, người duyệt, phạm vi áp dụng (máy/line/sản phẩm).
2. **Mục đích và phạm vi.**
3. **Trách nhiệm:** người vận hành, trưởng ca, kỹ sư quy trình.
4. **An toàn / PPE.**
5. **Thiết bị và vật tư.**
6. **Bảng thông số kiểm soát** (phần cốt lõi, giống control plan): thông số, giá trị chuẩn, dung sai, tần suất kiểm, ai kiểm, ghi vào đâu.
7. **Các bước thao tác:** mỗi bước có *điểm then chốt* và *lý do*.
8. **Kế hoạch phản ứng** (reaction plan): làm gì khi thông số ra ngoài dung sai (dừng, báo ai, cách ly hàng).
9. **Hồ sơ** (biểu mẫu ghi chép).
10. **Lịch sử sửa đổi:** phiên bản, ngày, thay đổi gì, vì sao, ai duyệt. Phần này nối trực tiếp với kaizen.

Ví dụ phác thảo SOP-RFL-001 bản 1 (synthetic, số là giả định **[kiểm chứng]**):

```yaml
- id: SOP-RFL-001
  version: 1
  title: Vận hành lò reflow và kiểm soát profile nhiệt
  scope: Lò R1–R3 (M01–M03), mọi sản phẩm dùng kem hàn SAC305
  owner: process_engineer
  approved_by: qa_lead
  effective: "2026-01-01"
  parameters:            # bảng thông số kiểm soát
    - {name: zone3_setpoint_c, nominal: 180, tolerance: 5, check: "đầu ca, sau changeover", record: "phiếu ca"}
    - {name: conveyor_speed_cm_min, nominal: 80, tolerance: 5, check: "đầu ca", record: "phiếu ca"}
    - {name: peak_temp_c, nominal: 245, tolerance: 5, check: "profiler hằng tuần + khi đổi sản phẩm", record: "phiếu profile"}
  steps:
    - {step: "Chọn đúng chương trình lò theo mã sản phẩm", key_point: "đối chiếu bảng chương trình", reason: "sai chương trình làm lỗi hàng loạt"}
    - {step: "Kiểm setpoint từng vùng so với bảng thông số", key_point: "vùng 3 = 180 ±5 °C", reason: "soak quá nóng làm cạn flux → bi thiếc, void"}
    - {step: "Chạy board đầu tiên, kiểm AOI trước khi chạy lô", key_point: "0 lỗi nghiêm trọng", reason: "phát hiện sai sớm"}
    - {step: "Ghi thông số vào phiếu ca", key_point: "ghi giá trị đo, không ghi 'OK'", reason: "truy vết"}
  reaction_plan:
    - "Thông số ngoài dung sai: dừng nạp board, báo trưởng ca, chỉ chỉnh khi có kỹ sư quy trình duyệt và ghi vào machine_log"
    - "AOI board đầu có lỗi nghiêm trọng: cách ly, không chạy lô"
  revision_history:
    - {version: 1, date: "2026-01-01", change: "Ban hành", reason: "-", approved_by: qa_lead}
```

Khi đó đề xuất của agent thành một **thay đổi có ý nghĩa và nhìn thấy được trên màn "SOP cũ → mới"**:
- thêm vào bảng thông số yêu cầu "khoá setpoint, chỉ kỹ sư đổi";
- thêm vào kế hoạch phản ứng;
- thêm dòng lịch sử sửa đổi ghi run, lý do, người duyệt.

Cấu trúc này cần mở rộng schema SOP trong `context_profile.yaml` (hiện chỉ có `steps`). Đưa vào hợp đồng dữ liệu D1.

**Bộ SOP ban đầu đề xuất** (mỗi SOP ứng với một nhóm nguyên nhân, để agent có chỗ đề xuất đúng):

| SOP | Liên quan nhóm |
|---|---|
| SOP-RFL-001 Vận hành lò reflow | máy, phương pháp |
| SOP-RFL-002 Đo và xác nhận profile nhiệt | máy (calibration) |
| SOP-PST-001 Bảo quản và sử dụng kem hàn | nguyên liệu, môi trường |
| SOP-CHG-001 Đổi sản phẩm / chương trình | phương pháp, con người |
| SOP-QC-001 Kiểm board đầu và AOI | đo lường |
| SOP-TRN-001 Đào tạo và chứng nhận người vận hành | con người |

## 5. Kaizen nằm ở đâu

Vòng lặp của agent **chính là một vòng kaizen (PDCA)**; hiện chỉ thiếu tên gọi và sản phẩm đầu ra rõ ràng.

| Bước agent | Kaizen / PDCA | Hiện có | Nên thêm |
|---|---|---|---|
| Detect | Phát hiện bất thường (Check) | Có | Biểu đồ kiểm soát trên màn S2 |
| Investigate + Ask | Phân tích nguyên nhân (Plan): Ishikawa, 5 Why, hỏi gemba | Có (giả thuyết theo nhóm) | Chuỗi 5 Why ngắn trong kết luận; Pareto mã lỗi làm bằng chứng |
| Improve | Biện pháp đối phó (countermeasure) | Có (action + SOP mới) | Phân biệt **biện pháp tức thời** (khôi phục 180 °C) và **biện pháp phòng tái phát** (khoá setpoint, đào tạo) |
| Act (người duyệt) | Do | Có | |
| Measure | Check | Có | Đo cả Pareto mã lỗi trước/sau |
| Learn | **Tiêu chuẩn hoá** (sửa SOP) + **yokoten** (nhân rộng sang chỗ tương tự) | Lưu bài học dạng JSON | **Phiếu kaizen / A3** cho mỗi run; **yokoten**: đề xuất kiểm cùng lỗi ở M01, M03 |

**Yokoten là điểm "ăn tiền" cho demo và cho chỉ số tái diễn.** Kịch bản hiện có A2 (cùng lỗi setpoint lặp lại ở M01 vào tháng 6):
- nếu Learn đã đề xuất nhân rộng biện pháp sang M01 và người duyệt, A2 bị chặn trước, tỷ lệ tái diễn giảm;
- nếu không, agent phải phát hiện nhanh hơn nhờ bài học cũ, MTTD giảm.

Hai trường hợp này cho ra con số "trước/sau" của điều 3 một cách tự nhiên.

**Dữ liệu kaizen cần có:**
- **Lịch sử kaizen trước khi có agent** (`kaizen_history`, 3–6 phiếu cũ): sự cố, nguyên nhân, biện pháp, có tái phát không. Đây là đường cơ sở "trước" để so với "sau khi có agent"; agent cũng có thể đọc để tham khảo.
- **Phiếu kaizen do agent sinh:** vấn đề, hiện trạng (số liệu), nguyên nhân gốc, biện pháp tức thời, biện pháp phòng tái phát, kết quả đo, tiêu chuẩn hoá (SOP bản mới), yokoten, người duyệt. Lưu trong `learning_store`, hiển thị ở màn S9.

## 6. Việc tiếp theo (cho vai A, cập nhật vào D1–D6)
1. **D1:** thêm `defect_log` (mã lỗi), SOP có cấu trúc (mục 4), `kaizen_history`, và tầng bắt buộc / nên có / tuỳ chọn (mục 2).
2. **D3:** kiểm chứng các số **[kiểm chứng]** ở mục 2–4: profile SAC305, Pareto lỗi SMT, quan hệ nguyên nhân → mã lỗi, mẫu SOP/Work Instruction.
3. **D4:** viết lại scenario 1 theo mục 3. Thêm kịch bản "bằng chứng không đủ, phải hỏi" và kịch bản yokoten / tái diễn.
4. **D5:** chấm theo mã nguyên nhân; chấm thêm việc agent có đề xuất yokoten không.
5. Đề xuất cho storyboard: màn S9 hiển thị **phiếu kaizen / A3**, câu chốt demo là "mỗi sự cố thành một bài học được tiêu chuẩn hoá và nhân rộng".

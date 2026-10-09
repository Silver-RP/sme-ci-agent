# R9i (auto-dev run 9i): đề xuất của LLM phải đủ và hợp lệ để vòng Act → Measure khép kín

**Phục vụ plugin: P5.** Mốc thường, được tính vào `--audit-every`. Audit lần sau chạy bằng Sonnet.

**Mục tiêu dự án:** điều 2 (duyệt → KPI cải thiện; nếu không thì rollback) phải chạy đúng với LLM thật.

T-030 lần 1 (`docs/decisions.md`, 2026-10-09) cho thấy:
- LLM thật chẩn đoán đúng nguyên nhân và đề xuất `action` đúng (`zone3_setpoint_c = 180`);
- nhưng đề xuất không có `sop_proposal`, nên Act không áp dụng, Measure trả `not_applied`, Learn lưu `no_change`, run vẫn `completed`.

Audit 2 (`docs/audits/2026-10-09_2.md`) tìm thấy mặt ngược (H-27) và lỗ hổng kiểm miền giá trị (H-30).

**Người dùng đã chốt hướng (b) ngày 2026-10-09:** một đề xuất phải có **cả** `action` lẫn `sop_proposal` (SOP có phiên bản là một phần của vòng Learn). Thiếu một trong hai, hoặc giá trị không hợp lệ, thì yêu cầu LLM sửa lại (số lần có giới hạn), rồi mới báo lỗi retryable. Không được `completed` khi SOP đã đổi mà chưa đo.

Quy tắc CLAUDE.md giữ nguyên. `docs/schema/events.json` không đổi; trường mới ghi vào `docs/schema/payloads.md`.

## Phạm vi
- **Trong:** `backend/agent/nodes/improve.py`, `backend/agent/nodes/act.py`, `backend/agent/prompts/`, `backend/tools/actions.py`, `data/context_profile.yaml` (khoảng giá trị của action), `backend/agent/demo_llm.py`, `scripts/export_fixtures.py`, `docs/schema/examples/`, `docs/schema/payloads.md`, test tương ứng.
- **Ngoài:** `dashboard/` (phần trình bày), R10 (chỉ số 3, MTTD/MTTR), H-28/H-29 (eval, độ khó bài toán: để R11).

## Quy ước chung
- Test không gọi LLM thật, không API key. Mỗi H-xx có test đỏ trước khi sửa.
- Task đụng `scripts/` phải qua `python3 .autodev/verify.py --smoke`.

## Tiêu chí chấp nhận cấp mốc
1. `python3 .autodev/verify.py` và `python3 .autodev/verify.py --smoke` sạch.
2. Câu trả lời LLM giả có `action` mà không có `sop_proposal` (đúng dạng T-030 lần 1) → yêu cầu sửa lại; lần sửa có đủ thì đi tiếp tới Measure `measured`. Sửa hỏng quá giới hạn → run `error`, retryable. Không bao giờ ra `completed` với `not_applied`.
3. Câu trả lời có `sop_proposal` mà không có `action` (H-27) → xử lý tương tự; `sop_versions` không có bản mới khi chưa đo được.
4. `action` có `NaN`/`inf`, nằm ngoài khoảng min/max trong YAML, hoặc nhắm máy khác máy của anomaly (H-30) → yêu cầu sửa lại; không có `NaN` trong audit_log hay SSE.
5. `test_measure_h06.py` không còn khoá hành vi cũ (dòng 62–67: `action=None` kèm `sop_change` → `completed`).

## Task

### dev-01: Đề xuất phải đủ `action` + `sop_proposal` (H-42, H-27, H-41)
- **Mô tả:**
  - `parse_proposal` / Improve: thiếu `action` hoặc thiếu `sop_proposal`, hoặc `new_content` rỗng / chỉ khoảng trắng (H-41) → `ProposalError` có thông điệp nói rõ thiếu gì, để vòng sửa lại hiện có gửi cho LLM.
  - Prompt của Improve nói rõ hai trường đều bắt buộc, kèm ví dụ ngắn. Không hard-code tên tham số: lấy từ YAML.
  - Act: tự vệ thêm một lớp. Nếu vì lý do nào đó vẫn tới Act mà thiếu `action`, thì không ghi SOP mới và route về chờ người hoặc lỗi; không đi Learn `completed`.
  - LLM giả của demo (`demo_llm.py`) và `scripts/export_fixtures.py` sinh đề xuất đủ hai trường. Sinh lại `docs/schema/examples/` và cập nhật `payloads.md`.
- **Tiêu chí chấp nhận:**
  1. Test: đúng dạng T-030 lần 1 (có action, không sop_proposal) → yêu cầu sửa → lần sau đủ → `kpi_measured.status == "measured"`. Đỏ trên main.
  2. Test: H-27 (có sop_proposal, không action) → không có bản SOP mới chưa đo; không `completed`. Đỏ trên main.
  3. Test: H-41 (`new_content` = "   ") → yêu cầu sửa, không 422.
  4. Sửa `tests/test_measure_h06.py` dòng 62–67 theo hành vi mới (ghi trong báo cáo vì sao đổi).
- **Phụ thuộc:** không
- **Trạng thái:** DONE · **Số vòng:** 1 (commit 509a11a)

### dev-02: Kiểm miền giá trị của `action` (H-30)
- **Mô tả:**
  - YAML `actions:` có thêm `min`/`max` cho từng tham số (ví dụ `zone3_setpoint_c`: 150–220).
  - `parse_proposal` từ chối NaN/inf, giá trị ngoài khoảng, và `machine_id` khác máy của anomaly (`ProposalError`, để LLM sửa).
  - Không còn đường nào ghi `NaN` vào audit_log/SSE.
- **Tiêu chí chấp nhận:**
  1. `test_improve_rejects_out_of_range_action`: NaN, inf, 1e9, -1000, `M99` đều bị từ chối; giá trị biên min/max được nhận. Đỏ trên main.
  2. Khoảng giá trị lấy từ YAML: test đổi YAML tạm thì kết quả đổi theo.
- **Phụ thuộc:** dev-01
- **Trạng thái:** TODO · **Số vòng:** 0

## Ghi chú điều chỉnh (Claude ghi khi làm (a)/(b))

## Đề xuất chờ duyệt

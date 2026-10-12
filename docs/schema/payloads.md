# Payload của event và API (cho team frontend)

`docs/schema/events.json` là hợp đồng **vỏ** event (`event_id`, `run_id`, `ts`, `type`, `agent`, `domain`, `payload`). File này mô tả **payload** từng loại event và dạng trả về của API, theo code tại nhánh mốc R10e ngày 2026-10-12 (sau R10d, kèm các thay đổi R10e). Tài liệu này không đổi hợp đồng: đổi `events.json` vẫn phải qua PR riêng.

Ví dụ thật (sinh bằng `uv run python scripts/export_fixtures.py`, qua API, LLM giả, dữ liệu synthetic; lệnh chạy trên DB tạm `<tên>_fixtures_demo`, chuẩn hoá id, số phiên bản SOP và giờ của event nên kết quả không phụ thuộc DB dev, và chép sang `dashboard/fixtures/examples/` giống từng byte). Câu chữ hiển thị trong ví dụ là tiếng Việt (lấy từ `messages` của config). Mỗi file có `steps` (request, body, http, response, `last_event`) và `events` (luồng SSE cuối):

| File | Nhánh | Kết thúc |
|---|---|---|
| `run-happy.json` | hỏi, duyệt, KPI đạt, Learn | `run_finished` completed |
| `run-rollback.json` | sửa sai, Measure không đạt, người xác nhận rollback, điều tra lại, sửa đúng | `run_finished` completed |
| `run-rollback-declined.json` | người từ chối rollback | pending `halt` `rollback_declined` |
| `run-insufficient-evidence.json` | Measure chưa đủ mẫu, nguồn có thể có thêm dữ liệu (`more_data_possible: true`) | pending `answer` |
| `run-insufficient-evidence-final.json` | Measure chưa đủ mẫu, nguồn không thêm điểm (sandbox): halt một lần, người chọn `finish` | `run_finished` closed (`closed_by_human`) |
| `run-revise.json` | người gửi đề xuất lại (`revise`) | `run_finished` completed |
| `run-halt-max-questions.json` | hỏi quá số lần cho phép | pending `halt` `max_questions_reached` |
| `run-error-retry.json` | LLM lỗi, Retry | `run_finished` completed (bước đầu là `error` retryable) |
| `run-no-anomaly.json` | Detect không thấy bất thường | `run_finished` no_anomaly |

Ký hiệu: `?` = có thể vắng; `|` = một trong các giá trị.

## 1. Vỏ event

```json
{"event_id": "evt_run_ff5de085_0011", "run_id": "run_ff5de085", "ts": "2026-10-08T16:20:36Z",
 "type": "kpi_measured", "agent": "quality", "domain": "manufacturing", "payload": {...}}
```

- `agent`: `quality | investigation | improvement | system`.
- `event_id` = `evt_<run_id>_<số thứ tự 4 chữ số>`. Dedupe theo trường này. Event lỗi (`run_finished` status `error`) có dạng `evt_<run_id>_errNN`. Sau retry không có `event_id` trùng (H-13).

## 2. Payload từng loại

### tool_called (quality | investigation)
- Detect: `{tool: "detect", kpis: [str], anomalies_found: int}`
- Tool do LLM gọi: `{tool: str, arguments: {...}, ok: bool}`

### anomaly_detected (quality)
`{kpi, machine, shift, start, end, value, peak, baseline, sigma, upper_limit, n_points, planned: bool}`

```json
{"kpi": "defect_rate", "machine": "M02", "shift": "night", "start": "2026-03-10T22:00:00", "end": "2026-06-30T22:00:00",
 "value": 0.06214, "peak": 0.086749, "baseline": 0.019594, "sigma": 0.00462, "upper_limit": 0.033454, "n_points": 337, "planned": false}
```

### hypothesis_updated (investigation)
`{hypotheses: [{group, description, confidence: 0..1}], insufficient_evidence: bool}`. `group` là nhóm Ishikawa trong `data/context_profile.yaml`.

### question_asked
Có hai dạng; phân biệt bằng `kind`.
- **Câu hỏi thường** (investigation hoặc quality), không có `kind`: `{question, attempt, max_questions}`. Người trả lời qua `POST /runs/{id}/answer`.
- **Dừng chờ người** (system), `kind: "halt"`:
  - `{kind: "halt", reason, status: "awaiting_human", question, options: ["investigate", "finish"], questions?, sop_still_in_force?, sop_id?, sop_version?}`
  - `reason` là một trong:
    - `max_questions_reached`: hỏi quá `ask.max_questions`;
    - `insufficient_evidence`: Measure vẫn thiếu mẫu sau số lần chờ cho phép;
    - `rollback_declined`: người từ chối rollback (SOP đã áp dụng vẫn hiệu lực, có `sop_still_in_force`);
    - `max_rollbacks_reached`: quá `loop.max_rollbacks` giữa hai lần dừng (chọn `investigate` thì đếm lại);
    - `max_total_rollbacks_reached` (R9): tổng rollback của cả run chạm `loop.max_total_rollbacks`. Bộ đếm này (`rollback_total` trong state graph, không có trong event) không bao giờ đặt lại;
    - `max_rejections_reached`: quá `loop.max_rejections` lần từ chối;
    - `max_revisions_reached` (R9): quá `loop.max_revisions` lần `revise`.
  - `options` (R9): thường `["investigate", "finish"]`. Khi `max_total_rollbacks_reached` chỉ còn `["finish"]`; gửi `investigate` thì API trả 422.
  - Người trả lời bằng `POST /runs/{id}/approval` với `kind: "halt"`.

### answer_received (investigation | quality)
`{answer: str}`.

### proposal_created (improvement)
**Đề xuất thường:**

```json
{"proposal": {"proposal_id": "25d388b4bac2",
  "hypothesis": {"group": "machine", "description": "wrong_setpoint", "confidence": 0.8},
  "change": "Restore the setpoint and add a setpoint check step to the SOP",
  "rationale": "Evidence 0 shows the defect rate follows the setpoint change",
  "evidence_refs": [0],
  "expected_kpi": {"kpi": "defect_rate", "direction": "decrease", "target": 0.02},
  "status": "pending_approval",
  "action": {"parameter": "zone3_setpoint_c", "machine_id": "M02", "value": 180},
  "sop_proposal": {"proposal_id": "48af347b1856", "sop_id": "SOP-RFL-001", "base_version": 17,
    "new_content": "Verify the setpoint.\nCheck the setpoint again after the shift change.",
    "rationale": "...", "kpi": "defect_rate", "status": "pending_approval"}}}
```

**Bắt buộc đủ hai trường (R9i):** đề xuất thường luôn có cả `action` (không `null`) lẫn `sop_proposal` (không `null`, `new_content` không rỗng). Thiếu một trong hai thì Improve yêu cầu LLM sửa lại (tối đa `improve.max_format_retries` lần), rồi mới báo lỗi `retryable`; đề xuất thiếu không bao giờ tới màn duyệt.

**Đề xuất rollback:** `{proposal: {kind: "rollback", proposal_id, change, rationale, expected_kpi, status, sop_proposal}}`.

`proposal_hash` không nằm trong event này; nó có trong `pending` (mục 3) và trong `approval_decided`.

### approval_decided (system)
- **Đề xuất / rollback:** `{kind: "proposal" | "rollback", proposal_id, proposal_hash, decision, decided_by, reason, change}`.
  - `decision` là một trong: `approved | rejected | revise`. `revise` chỉ có với `kind: "proposal"` (bác bỏ giả thuyết hoặc bổ sung thông tin; quay lại Investigate).
  - `sop_conflict` (R10c, H-14, giá trị `decision` mới): lúc áp dụng, phiên bản SOP hiện hành đã khác phiên bản người duyệt đã xem (run khác đã đổi SOP). Không ghi SOP. Payload có thêm `message` và thông tin phiên bản (`sop_id`, `current_version`...); người phải duyệt lại đề xuất mới.
  - Từ chối rollback có thêm `{sop_still_in_force: true, sop_id, sop_version}`, nghĩa là SOP đã áp dụng vẫn đang hiệu lực.
- **Dừng chờ người:** `{kind: "halt", proposal_id: "halt_<n>", halt_reason, decision: "investigate" | "finish", decided_by, reason, sop_still_in_force?, sop_id?, sop_version?}`. Không có `proposal_hash`.

### sop_applied (improvement)
- Đã áp dụng: `{applied: true, sop_id, version, previous_version, approved_by, change_time, action}`. Từ R9i không còn `applied: false`: đề xuất thiếu `action` hoặc `sop_proposal` không tới Act (Act báo lỗi, không ghi SOP).
  - `action` là hành động có cấu trúc người đã duyệt: `{parameter, machine_id, value}`, luôn có. Tên `parameter` hợp lệ lấy từ YAML (`actions.parameters`).
  - Không còn trường `sim` (nội bộ simulator, từng lộ `fixed`, H-06, H-25).

### kpi_measured (quality)
`{kpi, direction, target, tolerance, status, passed, before, after, machine_id, change_time, window_days, delta, sufficient, n_before, n_after, n_unit, mttd_hours, mttr_hours}`, thêm `more_data_possible?`, `min_units_after?`, `min_samples_after?`, `reason?` tuỳ `status` (xem dưới)

`before`/`after` là tỷ lệ gộp trên `production_log` (tổng tử số / tổng mẫu số của KPI trong cửa sổ, không trung bình tỷ lệ từng ca). `n_before`/`n_after` đếm theo `n_unit`: `"units"` là số đơn vị (tổng mẫu số) khi tính từ `production_log`; `"points"` là số điểm `kpi_log` khi quay về đường cũ. Ngưỡng "chưa đủ bằng chứng" tương ứng: `min_units_after` (đơn vị, config `measure.min_units_after`) hoặc `min_samples_after` (điểm, đường `kpi_log`).

`status` có ba giá trị:
- `measured`: `passed` là `true` hoặc `false`.
- `insufficient_evidence`: có thêm `more_data_possible` (bool, R10e). `false` trên sandbox (config `measure.source_may_grow: false`, dữ liệu sau thay đổi là hàm của `run_id` nên chờ cũng không có điểm mới): Measure không hỏi chờ, chỉ báo một lần bằng event `question_asked` dạng halt (`reason: "insufficient_evidence"`, `options: ["finish"]`, `question` từ `messages.evidence_final_question`); chọn `finish` thì `run_finished` `status: "closed"`, `reason: "closed_by_human"`; gửi `investigate` bị từ chối. Không rollback, không tính là KPI thất bại. Phần mô tả tiếp theo (hỏi `answer`, đo lại) chỉ áp dụng khi `more_data_possible` là `true` (nguồn có thể có thêm điểm). `passed: null`, `before`/`after`/`delta` là `null`, `sufficient: false`, có thêm `n_unit` cùng ngưỡng: `min_units_after` (khi `n_unit` là `"units"`, so với `n_after`) và/hoặc `min_samples_after` (số điểm tối thiểu của config; có mặt cả khi `n_unit` là `"units"`, nhưng khi đó ngưỡng quyết định là `min_units_after`). Run hỏi người: `pending` là `{type: "answer", question, run_id}` (R9, H-09). Trả lời bằng `POST /runs/{id}/answer` (ví dụ "chờ thêm dữ liệu") thì Measure chạy lại; hết số lần cho phép thì dừng với `reason: "insufficient_evidence"`. Xem `run-insufficient-evidence.json`.
- `not_applied`: `passed: null`, có thêm `reason`.

`mttd_hours` và `mttr_hours` hiện luôn là `null` trong vòng lặp (H-11).

### rollback_done (improvement)
`{rolled_back: bool, approved_by, sop_id?, version?, restored_from_version?, failed_version?, conflict?, current_version?}`

`conflict` (chuỗi, R10c, H-14) chỉ có khi rollback không thực hiện được vì SOP đã bị run khác đổi (`rolled_back: false`, kèm `current_version`).

### learning_saved (improvement)
`{learning_id, domain, content: {anomaly, root_cause, change, action, rationale, sop_id, sop_version, kpi, kpi_before, kpi_after, outcome, cause_status}}`

`action` là hành động có cấu trúc đã áp dụng `{parameter, machine_id, value}` (giống `sop_applied.action`).

`outcome` là `success` hoặc `no_change`: hành động có làm KPI đạt hay không.

`cause_status` (R10e, H-32) là `confirmed` hoặc `unconfirmed`: nguyên nhân (`root_cause`) có được xác nhận hay không, tách khỏi `outcome`. `confirmed` khi đủ cả ba: KPI đạt; có kết quả tool cho chính tín hiệu của giả thuyết đứng đầu, `|r|` >= `learn.min_cause_evidence`; tham số của `action` nằm trong `learn.cause_parameters` của giả thuyết đó. Thiếu một điều kiện (kể cả `outcome: no_change`) thì `unconfirmed`. Bài học cũ không có trường này: coi như chưa biết. Bài học `unconfirmed` vào prompt Investigate kèm nhãn `learn.unconfirmed_label`.

### run_finished (system)
`status` là một trong:
- `completed`;
- `no_anomaly` (+ `reason`);
- `closed` (+ `reason: "closed_by_human"`). Hai nguồn: người chọn `finish` ở halt (kèm `halt_reason`), hoặc người đóng run lỗi không retry được qua `POST /runs/{id}/close` (kèm `closed_by`, `close_reason`, `error`; R10ch, H-48);
- `error` (+ `error: "<Loại>: <thông điệp>"`, `retryable: bool`). Lỗi xảy ra cả sau khi người đã quyết định (duyệt, từ chối, revise, trả lời): quyết định đó đã ghi `audit_log` và không ghi lại khi Retry (R9, H-07, H-08).
  - `retryable: true`: đừng đóng hẳn luồng theo dõi, người có thể bấm Retry (H-13).
  - `retryable: false` (R9): đã Retry liên tiếp `loop.max_retries` lần mà vẫn lỗi. `POST /runs/{id}/retry` trả 409. Dashboard ẩn nút Retry và chỉ báo lỗi.
  - Danh sách event của run chỉ nối thêm (H-13): sau Retry, event `error` cũ vẫn nằm ở vị trí cũ, chỉ số SSE (`id`) tiếp tục tăng, nối lại bằng `Last-Event-ID` nhận event thật kế tiếp. Luồng cuối có thể có `run_finished` lỗi rồi `run_finished` completed (xem `run-error-retry.json`).

## 3. API

| Phương thức | Đường dẫn | Body | Trả về / lỗi |
|---|---|---|---|
| POST | `/runs` | `{change_time?}` | 201 + trạng thái run. 422 ngay (trước khi gọi LLM) nếu `change_time` sai định dạng, có múi giờ (`Z`, `+09:00`), ở tương lai của dữ liệu, hoặc trước lúc anomaly bắt đầu (H-48) |
| GET | `/runs/{id}` | | trạng thái run; 404 nếu backend đã khởi động lại (H-15) |
| GET | `/runs/{id}/events?follow=true&after=N` | | SSE. `id` = số thứ tự (bắt đầu từ 1), `event` = type, `data` = event JSON. Hỗ trợ `Last-Event-ID` |
| POST | `/runs/{id}/answer` | `{answer, question_id}` (cả hai bắt buộc, không rỗng; thiếu `question_id` → 422) | 409 nếu run không chờ câu trả lời, hoặc `question_id` không khớp câu đang chờ (câu cũ, H-20): gọi lại `GET /runs/{id}`, câu hiện tại không bị trả lời. Lấy `question_id` từ `pending` của `GET /runs/{id}` (R10d, H-49) |
| POST | `/runs/{id}/approval` | `{proposal_id, kind, decision, decided_by, reason?}` | 409 nếu sai `kind` hoặc `proposal_id` (đề xuất đã cũ, hoặc bấm hai lần): gọi lại `GET /runs/{id}`. 422 nếu tên không có trong danh sách người duyệt, hoặc `revise` mà thiếu `reason` |
| POST | `/runs/{id}/retry` | | 409 nếu không có bước lỗi, hoặc đã Retry liên tiếp quá `loop.max_retries` lần (khi đó `retryable: false`) |
| POST | `/runs/{id}/close` | `{reason, closed_by}` (cả hai không rỗng; `closed_by` thuộc danh sách người duyệt) | 200 + trạng thái `finished`/`closed`. 409 nếu run không ở trạng thái `error` đã hết lượt retry (đang chờ duyệt, chờ rollback, còn retry được, đã đóng). 422 nếu thiếu lý do hoặc người đóng không hợp lệ. Ghi một dòng audit `run_closed`, phát `run_finished` `closed`; không tạo hay khôi phục bản SOP (H-48) |
| GET | `/config/approvers` | | `{approvers: [str]}` |
| GET | `/config/domain` | | `{domain, kpis: [{name, unit, direction}], machines: [str], shifts: [str], sops: [{sop_id, version}], llm}` (R10e, #114). `machines`, `shifts` từ `plant.*`; `sops[].version` là bản đang hiệu lực (mới nhất trong `sop_versions`, chưa có thì bản trong config); `llm` là `scripted` hoặc `real` theo `SME_LLM`, không trả tên model. Chỉ đọc, không ghi bảng nào |
| GET | `/runs` | | `{runs: [RunSummary]}`, mới nhất trước (R10a) |
| GET | `/audit?run_id=&limit=` | | `{rows: [AuditRow]}`, mới nhất trước. `limit` 1..500 (mặc định 100), ngoài khoảng thì 422 |
| GET | `/learnings?limit=` | | `{learnings: [{learning_id, run_id, created_at, content}]}` từ `learning_store` của domain đang chạy, mới nhất trước; `content` cùng hình dạng `learning_saved.content`. `limit` 1..500 (mặc định 50), ngoài khoảng thì 422. Chỉ đọc; không có `DATABASE_URL` thì `{learnings: []}`. Còn sau khi app khởi động lại (R10d) |
| GET | `/sop/{sop_id}/versions` | | `{sop_id, versions: [SopVersion]}`, cũ nhất trước; 404 nếu `sop_id` không có trong config. Từ R10b1: khi chạy với `SME_DATASET=<tên>` thì SOP gốc là SOP trong `sop.csv` của dataset (SOP chỉ có trong config thì 404) |
| GET | `/metrics` | | `{dataset, seed, generated_at, assumptions, llm, limits, metrics: [Metric]}`; `metrics` luôn đúng 3 phần tử theo thứ tự: KPI chính (tên, đơn vị lấy từ config), `mttd_mttr`, `recurrence_rate`. Mỗi `Metric` là `{name, unit, before, after, available, reason, run_id}`. Xem ví dụ và quy tắc `available` bên dưới (R10a, R10b2, R10e) |
| GET | `/kpi/series?kpi=&machine=&shift=&start=&end=` | `kpi` bắt buộc | chuỗi KPI từ bảng `kpi_log` của dữ liệu sandbox của app (bảng này suy ra từ `production_log`, hợp đồng dữ liệu 2.8; nhiều máy cùng thời điểm được lấy trung bình). `kpi`, `machine`, `shift` lạ hoặc `start`/`end` sai định dạng thì 422. `start`/`end` là giờ không múi giờ (giờ sandbox), ví dụ `2026-01-01T00:00:00`; có múi giờ (`Z`, `+09:00`) thì 422 với `detail` nêu tên tham số, không quy đổi. `start <= ts < end`; khoảng rỗng thì `points: []` |

Ví dụ phản hồi `GET /kpi/series`:

```json
{"kpi": "defect_rate", "machine": "M02", "shift": null,
 "points": [{"ts": "2026-01-01T06:00:00", "value": 0.019283}],
 "baseline": 0.019544, "upper_limit": 0.030544,
 "anomalies": [{"start": "2026-03-10T22:00:00", "end": "2026-06-30T22:00:00", "machine": "M02", "shift": "night"}]}
```

`baseline` và `upper_limit` là số của Detect cho (máy, KPI), bằng giá trị trong event `anomaly_detected`; là `null` khi không chọn `machine` (khi đó nhiều máy cùng thời điểm được lấy trung bình). Quá 1000 điểm thì gộp theo ngày (`ts` là 00:00 của ngày). `anomalies` lọc theo `machine`/`shift`/khoảng thời gian.

Ví dụ phản hồi `GET /metrics` (chưa có báo cáo cho dataset + seed hiện tại; mọi chỉ số `available: false`, không có số):

```json
{"dataset": "sandbox", "seed": 42, "generated_at": null, "assumptions": [], "llm": null, "limits": [],
 "metrics": [
  {"name": "defect_rate", "unit": "ratio", "before": null, "after": null, "available": false,
   "reason": "no metrics report for dataset 'sandbox', seed 42: run `uv run python scripts/metrics_report.py --months 6 --seed 42` for dataset 'sandbox'", "run_id": null},
  {"name": "mttd_mttr", "unit": "hours", "before": null, "after": null, "available": false,
   "reason": "no metrics report for dataset 'sandbox', seed 42: run `uv run python scripts/metrics_report.py --months 6 --seed 42` for dataset 'sandbox'", "run_id": null},
  {"name": "recurrence_rate", "unit": "ratio", "before": null, "after": null, "available": false,
   "reason": "no metrics report for dataset 'sandbox', seed 42: run `uv run python scripts/metrics_report.py --months 6 --seed 42` for dataset 'sandbox'", "run_id": null}]}
```

Từ R10b2 (dev-06) số lấy từ báo cáo `data/reports/metrics_<dataset>_seed<seed>.json` do `scripts/metrics_report.py` ghi (thư mục đổi bằng env `SME_REPORTS_DIR`); `dataset` là `SME_DATASET` hoặc `sandbox`, `seed` là 42 (seed dữ liệu giả lập của app). API chỉ đọc file, không tính lại (phát lại mất vài phút). Có báo cáo khớp dataset + seed (kể cả bên trong file) thì cả ba phần tử `available: true`, `reason: null`; `generated_at` và `assumptions` (tên, giá trị, `source`) lấy từ báo cáo. Báo cáo của dataset/seed khác, thiếu, hỏng, hoặc thiếu số của một chỉ số thì chỉ số đó `available: false` kèm `reason` (cách chạy lại), `before`/`after` là `null`. `before` = nhánh không agent (đối chứng), `after` = có agent, cùng kỳ:
- KPI chính: `period_rate` (tỷ lệ gộp theo sản lượng cả kỳ);
- `mttd_mttr` (giờ): MTTD + MTTR trung bình, tức từ lúc sự cố bắt đầu tới lúc xử lý xong;
- `recurrence_rate`: tỷ lệ tái diễn.
Từ R10e (dev-06): phản hồi có thêm `llm` (`scripted` hoặc `real`, lấy từ báo cáo) và `limits` (danh sách câu giới hạn của báo cáo, tiếng Anh như trong báo cáo); không có báo cáo thì `llm: null`, `limits: []`. Báo cáo có `months` khác 6 (hoặc thiếu) không được phục vụ: cả ba chỉ số `available: false` kèm `reason` nêu `months`. Số NaN/inf trong báo cáo thì chỉ số đó `available: false` (không trả 500), giá trị NaN/inf trong `assumptions` thành `null`.
`run_id` luôn `null`. Hình dạng phần tử không đổi so với R10a. Tuyệt đối không có số giả khi `available: false`.

Ba API đọc trên (R10a) chỉ đọc, không ghi DB. `GET /runs` đọc từ bộ nhớ của app nên mất khi backend khởi động lại (H-15, sửa ở R10c).

```json
RunSummary: {"run_id": "run_ff5de085", "state": "waiting | running | finished | error", "started_at": "2026-10-10T09:00:00+00:00",
  "finished_at": null | "2026-10-10T09:00:05+00:00", "outcome": null | "completed | closed | no_anomaly | error",
  "pending": null | {"type": "answer | approval", "kind?": "proposal | rollback | halt", "proposal_id?": "..."}}
AuditRow: {"id": 12, "ts": "2026-10-10T09:00:03+00:00", "run_id": "run_ff5de085" | null, "actor": "alice", "action": "approval_decided", "params": {...}}
```

`params` là object JSON (khoá nào cũng giữ cấu trúc: `save_learning.content`, `apply_sop.approval` là object, không phải chuỗi `repr`). Từ R10d. Dòng ghi trước R10d có thể còn `params` là chuỗi; audit append-only nên không sửa, dashboard đọc nguyên văn.

```json
SopVersion: {"version": 2, "created_by": "config | import | <người duyệt>", "run_id": "run_ff5de085" | null, "created_at": "..." | null, "content": "..."}
```
`created_by` là `"config"` cho bản gốc lấy từ `sop:` của config, `"import"` cho bản gốc lấy từ `sop.csv` của dataset (R10b1, `SME_DATASET`); cả hai có `run_id` và `created_at` là `null`.

`outcome` là `status` của event `run_finished` cuối (null khi chưa có). Bản gốc từ config có `created_by: "config"`, `run_id` và `created_at` là null; khi run đầu tiên sửa SOP, bản 1 trong DB là bản sao của bản gốc nên chỉ hiện một lần.

Trạng thái run:

```json
{"run_id": "run_ff5de085", "state": "waiting | running | finished | error", "status": "", "pending": null | {...}, "error?": "...", "retryable?": true}
```

`error` và `retryable` chỉ có khi `state: "error"` (`retryable` giống trường trong event `run_finished` lỗi). Trạng thái `error` có `status: "error"` và `pending: null`.

Hai dạng `pending`:
- **Trả lời:** `{type: "answer", question, question_id, attempt, run_id}`. `question_id` (chuỗi, là `event_id` của event `question_asked` tương ứng) và `attempt` (số lần hỏi, từ 1) là trường mới của R10c (H-20); dashboard phải gửi lại `question_id` trong `POST /answer` (bắt buộc từ R10d). Có hai nguồn: Investigate chưa chắc, hoặc Measure thiếu mẫu (R9). Cùng dạng, cùng `POST /answer`.
- **Duyệt:** `{type: "approval", kind, proposal_id, proposal_hash?, run_id, ...}`.
  - `kind: "proposal"` hoặc `"rollback"`: có thêm `proposal` (như event `proposal_created`) và `current_sop: {sop_id, version, content}`. Màn "SOP cũ → mới" so `current_sop.content` với `proposal.sop_proposal.new_content`.
  - `kind: "halt"`: `{reason, question, options, sop_still_in_force, sop_id, sop_version}`.

Lưu ý khi hiển thị:
- `status` là trường `status` của graph, có thể trống khi run đang chạy hoặc đang chờ.
- `completed`, `closed`, `no_anomaly` đều có `state: "finished"`. Muốn biết kết quả, đọc event `run_finished` (H-24).
- Với LLM giả, `new_content` có thể trùng `current_sop.content`. Màn so sánh vẫn phải hiển thị được trường hợp "không đổi".

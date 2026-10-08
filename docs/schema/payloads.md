# Payload của event và API (cho team frontend)

`docs/schema/events.json` là hợp đồng **vỏ** event (`event_id`, `run_id`, `ts`, `type`, `agent`, `domain`, `payload`). File này mô tả **payload** từng loại event và dạng trả về của API, theo code tại `main` ngày 2026-10-09 (sau R8). Tài liệu này không đổi hợp đồng: đổi `events.json` vẫn phải qua PR riêng.

Ví dụ thật (ghi từ API demo, LLM giả): `docs/schema/examples/run-happy.json` (đi hết tới Learn), `docs/schema/examples/run-reject-error.json` (Reject → lỗi, xem H-16).

Ký hiệu: `?` = có thể vắng; `|` = một trong các giá trị.

## 1. Vỏ event

```json
{"event_id": "evt_run_ff5de085_0011", "run_id": "run_ff5de085", "ts": "2026-10-08T16:20:36Z",
 "type": "kpi_measured", "agent": "quality", "domain": "manufacturing", "payload": {...}}
```

- `agent`: `quality | investigation | improvement | system`.
- `event_id` = `evt_<run_id>_<số thứ tự 4 chữ số>`. Dedupe theo trường này. Lưu ý: sau retry có thể trùng (H-13).

## 2. Payload từng loại

### tool_called (quality | investigation)
- Detect: `{tool: "detect", kpis: [str], anomalies_found: int}`
- Tool do LLM gọi: `{tool: str, arguments: {...}, ok: bool}`

### anomaly_detected (quality)
`{kpi, machine, shift, start, end, value, peak, baseline, sigma, upper_limit, n_points, planned: bool}`

```json
{"kpi": "defect_rate", "machine": "M02", "shift": "night", "start": "2026-03-10T22:00:00", "end": "2026-06-30T22:00:00",
 "value": 0.061942, "peak": 0.071583, "baseline": 0.019544, "sigma": 0.003667, "upper_limit": 0.030544, "n_points": 337, "planned": false}
```

### hypothesis_updated (investigation)
`{hypotheses: [{group, description, confidence: 0..1}], insufficient_evidence: bool}`. `group` là nhóm Ishikawa trong `data/context_profile.yaml`.

### question_asked
Có hai dạng; phân biệt bằng `kind`.
- **Câu hỏi thường** (investigation hoặc quality), không có `kind`: `{question, attempt, max_questions}`. Người trả lời qua `POST /runs/{id}/answer`.
- **Dừng chờ người** (system), `kind: "halt"`:
  - `{kind: "halt", reason, status: "awaiting_human", question, options: ["investigate", "finish"], questions?, sop_still_in_force?, sop_id?, sop_version?}`
  - `reason` là một trong: `max_questions_reached | insufficient_evidence | rollback_declined | max_rollbacks_reached | max_rejections_reached`.
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

**Đề xuất rollback:** `{proposal: {kind: "rollback", proposal_id, change, rationale, expected_kpi, status, sop_proposal}}`.

`proposal_hash` không nằm trong event này; nó có trong `pending` (mục 3) và trong `approval_decided`.

### approval_decided (system)
- **Đề xuất / rollback:** `{kind: "proposal" | "rollback", proposal_id, proposal_hash, decision, decided_by, reason, change}`.
  - `decision` là một trong: `approved | rejected | revise`. `revise` chỉ có với `kind: "proposal"` (bác bỏ giả thuyết hoặc bổ sung thông tin; quay lại Investigate).
  - Từ chối rollback có thêm `{sop_still_in_force: true, sop_id, sop_version}`, nghĩa là SOP đã áp dụng vẫn đang hiệu lực.
- **Dừng chờ người:** `{kind: "halt", proposal_id: "halt_<n>", halt_reason, decision: "investigate" | "finish", decided_by, reason, sop_still_in_force?, sop_id?, sop_version?}`. Không có `proposal_hash`.

### sop_applied (improvement)
- Không áp dụng: `{applied: false, reason}`.
- Đã áp dụng: `{applied: true, sop_id, version, previous_version, approved_by, change_time, action}`.
  - `action` là hành động có cấu trúc người đã duyệt: `{parameter, machine_id, value}` hoặc `null` (đề xuất không có hành động; Measure trả `not_applied`). Tên `parameter` hợp lệ lấy từ YAML (`actions.parameters`).
  - Không còn trường `sim` (nội bộ simulator, từng lộ `fixed`, H-06, H-25).

### kpi_measured (quality)
`{kpi, direction, target, tolerance, status, passed, before, after, machine_id, change_time, window_days, delta, sufficient, n_before, n_after, mttd_hours, mttr_hours}`

`status` có ba giá trị:
- `measured`: `passed` là `true` hoặc `false`.
- `insufficient_evidence`: `passed: null`, có thêm `min_samples_after`. Run sẽ hỏi người. Hiện API chưa đưa câu hỏi này ra `pending` (H-09).
- `not_applied`: `passed: null`, có thêm `reason`.

`mttd_hours` và `mttr_hours` hiện luôn là `null` trong vòng lặp (H-11).

### rollback_done (improvement)
`{rolled_back: bool, approved_by, sop_id?, version?, restored_from_version?, failed_version?}`

### learning_saved (improvement)
`{learning_id, domain, content: {anomaly, root_cause, change, rationale, sop_id, sop_version, kpi, kpi_before, kpi_after, outcome}}`

`outcome` là `success` hoặc `no_change`.

### run_finished (system)
`status` là một trong:
- `completed`;
- `no_anomaly` (+ `reason`);
- `closed` (+ `reason: "closed_by_human"`, `halt_reason`);
- `error` (+ `error: "<Loại>: <thông điệp>"`, `retryable: true`). Khi nhận `error`, đừng đóng hẳn luồng theo dõi, vì người có thể bấm Retry (H-13).

## 3. API

| Phương thức | Đường dẫn | Body | Trả về / lỗi |
|---|---|---|---|
| POST | `/runs` | `{change_time?}` | 201 + trạng thái run |
| GET | `/runs/{id}` | | trạng thái run; 404 nếu backend đã khởi động lại (H-15) |
| GET | `/runs/{id}/events?follow=true&after=N` | | SSE. `id` = số thứ tự (bắt đầu từ 1), `event` = type, `data` = event JSON. Hỗ trợ `Last-Event-ID` |
| POST | `/runs/{id}/answer` | `{answer}` (không rỗng) | 409 nếu run không chờ câu trả lời |
| POST | `/runs/{id}/approval` | `{proposal_id, kind, decision, decided_by, reason?}` | 409 nếu sai `kind` hoặc `proposal_id` (đề xuất đã cũ, hoặc bấm hai lần): gọi lại `GET /runs/{id}`. 422 nếu tên không có trong danh sách người duyệt, hoặc `revise` mà thiếu `reason` |
| POST | `/runs/{id}/retry` | | 409 nếu không có bước lỗi |
| GET | `/config/approvers` | | `{approvers: [str]}` |

Trạng thái run:

```json
{"run_id": "run_ff5de085", "state": "waiting | running | finished | error", "status": "", "pending": null | {...}, "error?": "..."}
```

Hai dạng `pending`:
- **Trả lời:** `{type: "answer", question, run_id}`.
- **Duyệt:** `{type: "approval", kind, proposal_id, proposal_hash?, run_id, ...}`.
  - `kind: "proposal"` hoặc `"rollback"`: có thêm `proposal` (như event `proposal_created`) và `current_sop: {sop_id, version, content}`. Màn "SOP cũ → mới" so `current_sop.content` với `proposal.sop_proposal.new_content`.
  - `kind: "halt"`: `{reason, question, options, sop_still_in_force, sop_id, sop_version}`.

Lưu ý khi hiển thị:
- `status` là trường `status` của graph, có thể trống khi run đang chạy hoặc đang chờ.
- `completed`, `closed`, `no_anomaly` đều có `state: "finished"`. Muốn biết kết quả, đọc event `run_finished` (H-24).
- Với LLM giả, `new_content` có thể trùng `current_sop.content`. Màn so sánh vẫn phải hiển thị được trường hợp "không đổi".

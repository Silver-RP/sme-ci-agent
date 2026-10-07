# Nhật ký auto-dev

Mỗi task một mục: thời gian, số vòng, commit, kết quả review, % hạn mức (đo bằng `/usage` trước và sau task), ghi chú.

## Chỉ số chạy thử (mục 9.1 của thiết kế)

| Task | Vòng dev↔review | Verify bị chặn | Kết quả | % hạn mức | Thời gian | Lỗi người dùng phát hiện sau |
|---|---|---|---|---|---|---|
| M1/dev-01 (T-015) | 1 | 0 | PASS | (người dùng điền) | dev ~61s + review ~33s | |
| M1/dev-02 (T-017 p1) | 1 | 0 | PASS | (người dùng điền) | dev ~81s + review ~24s | |
| M1/dev-03 (T-017 p2) | 1 | 0 | PASS | (người dùng điền) | dev ~97s + review ~107s | 2 (domain rỗng; event_id không reset), sửa ở dev-04 |
| M1/dev-04 (T-017 bổ sung) | 1 | 0 | PASS | (người dùng điền) | dev ~80s + review ~35s | |
| M2/dev-01 (T-010) | 2 | 0 | FAIL → PASS | (người dùng điền) | dev ~150s + review ~134s; rework ~158s + review ~77s | |
| M2/dev-02 (T-011) | 1 | 0 | PASS | (người dùng điền) | dev ~199s + review ~306s | |
| M2/dev-03 (T-012) | 1 | 0 | PASS | (người dùng điền) | dev ~838s + review ~84s | |

## Hạn mức (người dùng đo bằng `/usage`)

- 2026-10-07: mỗi lần chạy `/run-milestone` tốn khoảng **7–18% hạn mức của cửa sổ 5 giờ** (gói Pro). Mốc nhỏ (M1, 3–4 task đơn giản) ở mức thấp; M2 (3 task phụ thuộc nhau, 1 vòng REWORK, ~36 phút) ở mức cao. Chưa đo hạn mức tuần.
- Hệ quả: một cửa sổ 5 giờ chạy được khoảng 5–14 mốc cỡ này; cần đo thêm hạn mức tuần trước khi làm chế độ B (chạy qua đêm).

## Nhật ký

### M1/dev-01 (T-015): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: 3cc91ce. Review: .autodev/reviews/M1-dev-01-r1.json (PASS).
- Loader: `backend/domain_config.py` (`load_domain_config`). YAML có thêm KPI `rework_rate`, SOP synthetic SOP-INJ-001 và SOP-CAL-002.
- Non-blocking: test quét hard-code mới chỉ quét `backend/domain_config.py`.
- Ghi chú: hook Stop của developer không ghi `verify.last_status` vào state.json (vẫn là null). Session điều phối tự chạy verify và kết quả sạch.

### M1/dev-02 (T-017 phần 1): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: bc5d995. Review: .autodev/reviews/M1-dev-02-r1.json (PASS).
- `AgentState` (TypedDict, `events` có reducer cộng dồn), `Hypothesis` (Pydantic), `validate_hypothesis_groups(hypotheses, config)`.
- Non-blocking: việc khớp group với YAML nằm ở hàm riêng; dev-03 cần gọi hàm này.
- Hook Stop vẫn không ghi `verify.last_status`.

### M1/dev-03 (T-017 phần 2): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: 0ff8abc. Review: .autodev/reviews/M1-dev-03-r1.json (PASS).
- `backend/agent/graph.py` (Observe → Detect → Investigate → END, `build_graph(config, checkpointer=None)`, mặc định InMemorySaver); `backend/tools/fake_metrics.py` (`fetch_kpi_breakdown(kpi, start, end)`).
- Event được validate bằng code tự viết theo events.json, vì chưa có `jsonschema`.
- Non-blocking: bộ đếm event_id nằm trong closure (nên đưa vào state); DEFAULT_PERIOD và `kpis[0]` là giá trị tạm; Investigate mock luôn chọn nhóm đầu tiên.
- T-017 xong (dev-02 và dev-03), đã tick trong TASKS.md.

### M1/dev-04 (T-017 bổ sung): DONE
- Ngày: 2026-10-06. Nhánh: milestone/M1-r3. Vòng: 1. Commit: 10f757d. Review: .autodev/reviews/M1-dev-04-r1.json (PASS).
- Chạy với prompt mới (reviewer phải probe trường hợp biên, developer viết test biên).
- `make_event` lấy domain từ `config.domain` khi state thiếu hoặc rỗng. Bỏ `itertools.count` trong closure; số thứ tự event tính từ `len(state["events"])` của lần chạy hiện tại.
- Test mới: `test_domain_falls_back_to_config_when_state_has_none`, `test_event_ids_restart_per_run_on_same_graph`. Tổng 27 test pass, verify sạch so với baseline.
- Non-blocking: event_id có thể trùng nếu state đầu vào đã có events cùng run_id từ nguồn khác; có một dòng `make_event` ở node detect dài hơn 100 ký tự.
- Bài học: ở dev-03, reviewer cũ đã ghi bộ đếm closure là non-blocking nhưng không probe chạy graph hai lần, nên bỏ sót lỗi. Lần này reviewer mới có probe (chạy 3 run trên cùng graph, thử domain rỗng hoặc None).
- T-017 vẫn ở trạng thái đã tick trong TASKS.md, không đổi.

### M2/dev-01 (T-010): DONE
- Ngày: 2026-10-06. Nhánh: milestone/M2. Vòng: 2. Commit: a8f908a (code), 8019445 (fix). Review: .autodev/reviews/M2-dev-01-r1.json (FAIL), M2-dev-01-r2.json (PASS).
- Hook SubagentStop chạy cả 2 vòng (`hook_runs` 0 → 1 → 2, `last_status` PASS). Đây là lần đầu xác nhận hook hoạt động.
- `backend/sandbox/schema.py` (6 bảng, schema cố định), `backend/sandbox/simulator.py` (`SimParams`, `SetpointChange`, `params_from_config`, `simulate`, `expected_kpi_value`). Hàm lỗi: `baseline + sensitivity * |setpoint − sop_setpoint|`, rồi clip vào [0, 1].
- Vòng 1 FAIL (B1): hàm công khai tên `defect_mean`, trái tiêu chí 5. Vòng 2 đổi thành `expected_kpi_value` và thêm test `test_sandbox_public_names_are_domain_neutral`.
- Điều chỉnh (a): thêm `setpoint_sensitivity_per_c` và `shift_start_hours` vào `scenario1.yaml` (xem plan/M2.md).
- Non-blocking: `params_from_config` báo KeyError khó đọc khi thiếu khóa YAML; mặc định `materials` ('MAT-A', 'MAT-B') và `start_date` vẫn nằm trong code; bảng `sop` rỗng nếu không đi qua `params_from_config`.
- Developer vòng 1 tự báo đã sửa YAML bằng heredoc, trái quy tắc shell. Vòng 2 đã dùng Edit.
- 42 test pass. Đã tick T-010 trong TASKS.md.

### M2/dev-02 (T-011): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: d150ff1. Review: .autodev/reviews/M2-dev-02-r1.json (PASS).
- Hook SubagentStop chạy (`hook_runs` 2 → 3, PASS).
- `backend/sandbox/injector.py`: `generate_dataset(seed, scenario_path, profile_path) -> Dataset(tables, ground_truth)`, `inject`, `GroundTruth` (frozen dataclass). `scripts/gen_data.py` ghi CSV và `ground_truth.json` riêng vào `data/generated/` (đã thêm vào .gitignore).
- Cửa sổ hiệu lực `[start, end)`; A1/A2 không có `end` nên kéo dài đến hết horizon. FP1 ghi 2 dòng `maintenance` (start/end) trong `machine_log`. Ca đêm M02 quanh A1 có `OP-SUB01` thay thế (3 đêm).
- Điều chỉnh (a): thêm các khóa `trace.*` vào `scenario1.yaml` (xem plan/M2.md).
- Reviewer probe: quét seed 1..59, không seed nào lệch quá 1 noise_sd trong cả 3 cửa sổ; quét giá trị và tên cột không lộ ground truth. 62 test chạy trong 2.32s.
- Non-blocking: `setpoint_sensitivity_per_c` và `effect` là hai nguồn độc lập cho mức KPI; FP1 chỉ có 6 điểm nên biên an toàn của tiêu chí 3 hẹp.
- Đã tick T-011 trong TASKS.md.

### M2/dev-03 (T-012): DONE
- Ngày: 2026-10-06. Vòng: 1. Commit: 009e77b. Review: .autodev/reviews/M2-dev-03-r1.json (PASS).
- Hook SubagentStop chạy (`hook_runs` 3 → 4, PASS).
- `backend/detect/statistical.py`: tham chiếu 28 ngày đầu theo (máy, KPI); giới hạn trên = baseline + `alert_threshold_sd` × sigma (hệ số đọc từ YAML); luật 2 trên 3 điểm; gộp các điểm xác nhận cách nhau ≤ 3 ca; loại điểm trong cửa sổ bảo trì (`machine_log` event_type="maintenance") trước khi áp luật. Event dùng lại `make_event` của graph, `agent="quality"`.
- Seed 1..5: 0 báo động giả, mỗi seed đúng 2 event (M02 từ 2026-03-10 22:00, M01 từ 2026-06-02 22:00). Toàn repo 79 test, 3.3s.
- Developer mất ~14 phút (lâu nhất mốc), chủ yếu để dò tham số cho các test ngưỡng.
- Non-blocking: `DetectParams` (28 ngày, 2/3, gộp 3 ca) nằm trong code; bảo trì chồng lên anomaly làm báo trễ; bảo trì thiếu dòng end che đến hết horizon; dữ liệu < 28 ngày thì không bao giờ báo; chưa có sàn sigma khi sigma = 0; chưa phát event `planned: true`.
- Đã tick T-012 trong TASKS.md.

## Đề xuất chờ duyệt (c)

- ✅ **Đã duyệt 2026-10-07.** **M2-c1 (từ review dev-03):** đưa `DetectParams` (số ngày tham chiếu, luật k trên n, khoảng gộp) vào `data/context_profile.yaml` để leader chỉnh không cần sửa code, và thêm sàn sigma. Hiện không vi phạm quy ước mốc (quy ước chỉ liệt kê baseline, noise, setpoint, ngưỡng SD) nhưng trái tinh thần "domain config tách khỏi code".
- ✅ **Đã duyệt 2026-10-07, chọn: `effect` trong YAML là nguồn chính cho anomaly được tiêm; hàm setpoint chỉ dùng cho phép thử phản thực tế (khôi phục setpoint → về baseline). Ghi quy ước vào `scenario1.yaml`; các khóa mới vẫn chờ team chốt ở T-004.** **M2-c2 (từ dev-01, dev-02):** leader duyệt các khóa đã thêm vào `scenario1.yaml` khi làm T-004: `baseline.setpoint_sensitivity_per_c`, `plant.shift_start_hours`, `plant.start_date`, FP1 (`start`, `end`, `effect`, `planned`), `injected_anomalies[].trace.*`. Cần quyết định thêm: `effect` của A2 (0.055) không khớp với hàm setpoint (195 °C cho 0.062); giữ hai nguồn độc lập hay buộc khớp.
- Nhận xét của người duyệt (2026-10-07): anomaly trong scenario1 lớn khoảng 10 lần độ nhiễu nên detect bắt ngay (độ trễ 0, 0 báo động giả trên 30 seed). Khi làm T-004 nên thêm một anomaly nhỏ (khoảng 3–4 lần độ nhiễu) để demo thuyết phục hơn.

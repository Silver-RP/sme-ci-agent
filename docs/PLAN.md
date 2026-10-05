# Mục tiêu và kế hoạch G3 → G5

Cập nhật 5/10/2026. Lịch đã dời lại so với bản gốc vì repo mới được dựng ngày 5/10 (xem mục 3).

> Các ngày, hạn và điểm go/no-go trong file này chỉ để tham khảo; leader điều chỉnh khi cần (xem CLAUDE.md, mục Mốc).

## 1. Mục tiêu

Sản phẩm: MVP chạy scenario 1 (defect tăng bất thường) đủ vòng Detect → Learn từ dashboard, trên dữ liệu sandbox.

Ba điều cần kiểm chứng

1. Agent tìm đúng nguyên nhân gốc (so với ground truth ẩn) và biết hỏi người khi chưa đủ bằng chứng.
2. Đề xuất sau khi được duyệt làm KPI cải thiện; nếu không thì rollback và điều tra lại.
3. Đo được 3 chỉ số trước/sau trên 6 tháng dữ liệu mô phỏng: defect (%), MTTD/MTTR, tỷ lệ lỗi tái diễn.

Mốc cuộc thi: v0.1-e2e 13/10 · freeze 20/10 · Pitch Day 24/10 · Demo Day 07/11.

Ngoài phạm vi đến 13/10: multi-agent hoặc Agent Manager dùng LLM, scenario 2–3, biểu đồ phức tạp, dữ liệu thật.

## 2. Mốc (milestone)

| Mốc | Ngày | Tiêu chí hoàn thành |
|---|---|---|
| M0 Contract | 5/10 | Repo dựng xong, events.json v0.1 + interface 4 tool chốt, scenario1.yaml được duyệt, proposal đã nộp |
| M1 (≈ G3) | 8/10 | Sandbox + Detect xuất anomaly event đúng schema; Tools v1 chạy trên DB; dashboard skeleton (mock) đã freeze |
| M2 (≈ G4) | 10/10 | Agent chạy từ anomaly tới Improve và Act/Measure/Learn; API start/answer/approve + SSE chạy được |
| M3 | 11/10 | Một vòng end-to-end trên dashboard thật, dù còn thô |
| M4 (≈ G5) | 13/10 | 3 cạnh quay lại, số liệu 3 chỉ số, demo nội bộ #1, tag v0.1-e2e |

## 3. Vì sao dời lịch

Bản gốc: G3 3/10, G4 8/10, G5 13/10. Thực tế G3 chưa làm khi bắt đầu, và 4–5/10 dành cho proposal. Giữ nguyên 13/10 và 20/10; dời M1 sang 8/10 và M2 sang 10/10. Core và Dashboard chạy song song bằng fake tool và mock event để không chờ Data. Nếu cả team đồng ý lịch này thì ghi vào docs/decisions.md (ADR-008).

## 4. Phân công (4 người, đổi vai được)

| Vai | Phụ trách | Người |
|---|---|---|
| A: Data | sandbox, simulator, injector, ground truth, detect | TBD |
| B: Tools/API | DB, tools, FastAPI + SSE, audit_log, sop_versions | TBD |
| C: Core | graph, state, prompt, các node, interrupt, checkpointer | TBD |
| D: Demo/UI + Domain | proposal, dashboard, context_profile.yaml, SOP mẫu, kịch bản, sổ token | TBD |

Ai xong việc sớm thì nhận việc ở mảng đang nằm trên đường găng (ưu tiên hỗ trợ C và A).

## 5. Kế hoạch theo ngày

| Ngày | A: Data | B: Tools/API | C: Core | D: Demo/UI |
|---|---|---|---|---|
| 5/10 (T2) | Duyệt scenario1.yaml; data model 6 bảng | Dựng repo, docker-compose, DB models | state.py, graph skeleton với fake tool | Nộp proposal (ưu tiên 1); họp contract 30' |
| 6/10 (T3) | Simulator có tham số + test "đổi setpoint → defect về baseline" | audit_log, sop_versions, stub 4 tool | Prompt v0, Investigate bản mock | context_profile.yaml; dashboard skeleton bằng mock events |
| 7/10 (T4) | Injector YAML + ground truth có timestamp | query_logs, correlate | Investigate gọi tool thật | Dashboard skeleton hoàn thiện, freeze cuối ngày |
| 8/10 (T5) | Detect thống kê xuất event (M1) | get_shift_schedule, read_sop + test | Node Ask (interrupt) + resume | Fixture trace, kịch bản v0, sổ token |
| 9/10 (T6) | Eval nhỏ: agent có tìm đúng nguyên nhân gốc? | FastAPI: start run, answer, approve/reject; SSE | Node Improve + trace đúng schema | Dashboard đọc SSE (phát lại fixture) |
| 10/10 (T7) | Hỗ trợ Tools/Core | propose/apply_sop, measure, learning_store | Act/Measure/Learn + ngưỡng KPI (M2) | Ghép API thật; review mốc cả team |
| 11/10 (CN) | Chạy simulator 6 tháng | Sửa lỗi API | Cạnh rollback; M3 e2e | Dashboard hiển thị đủ trạng thái |
| 12/10 (T2) | Lấy số liệu 3 chỉ số | Bug bash | Cạnh bác bỏ + từ chối; record/replay trace | Số liệu lên dashboard; kịch bản 4 phút v1 |
| 13/10 (T3) | Bug bash | Tag v0.1-e2e | Hỗ trợ demo | Demo nội bộ #1 |

## 6. Điểm kiểm tra go/no-go

- Cuối 8/10: Detect chưa xuất event thật → Core tiếp tục bằng event cố định, cả team hỗ trợ Data.
- Cuối 10/10: agent chưa chạy tới Improve → cắt Act/Measure/Learn bản thật, dùng bản đơn giản (ghi kết quả vào DB).
- Cuối 11/10: chưa e2e → 12/10 chỉ làm e2e, hoãn cạnh bác bỏ/từ chối (giữ rollback).
- 12/10 cuối ngày: ngừng thêm tính năng.

## 7. Thứ tự cắt khi thiếu giờ

1. Biểu đồ trên dashboard (giữ bảng + timeline).
2. Cạnh bác bỏ và từ chối (giữ rollback).
3. Case false positive và "chưa đủ bằng chứng" (đã thuộc G6).

Không cắt: vòng Detect → Learn chạy thật, 3 chỉ số thật từ 6 tháng dữ liệu, trace đúng schema.

## 8. Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| LLM không ổn định khi demo | Temperature thấp; record/replay một lần chạy tốt |
| interrupt + checkpointer Postgres khó | Spike G1 đã có; thử resume sớm ngày 8/10 |
| Đổi schema làm vỡ UI/API | Đổi events.json chỉ qua PR riêng |
| Chi phí token | Haiku cho việc nhẹ; ghi docs/token-cost.md hằng ngày |
| Một người ôm quá nhiều việc | Đổi vai theo mục 4 |

## 9. Quyết định cần xem lại

- 17/10: có nâng lớp điều phối thành Orchestrator (LLM) cho riêng bước Evaluate không? Chỉ xem xét nếu scenario 1 ổn định, case false positive và "chưa đủ bằng chứng" chạy được, token còn dư.
- 25/10 (G8): Orchestrator thật và scenario 2–3.

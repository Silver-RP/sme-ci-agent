# Danh sách task

Quy ước: [ ] chưa làm, [x] xong. Nhãn: [Core] agent LangGraph · [Data] sandbox & detect · [Tools] tool layer & API · [Demo] proposal, dashboard, kịch bản. DoD = điều kiện hoàn thành. Tick checkbox trong cùng PR.

## M0: Contract (5/10)

- [x] T-001 [Demo] Nộp proposal PDF trước 21:59 JST (mục tiêu trước 19:59). Điền câu phỏng vấn SME, kiểm tra link Siemens, chính ≤ 3 trang, phụ lục ≤ 2, tên file Idea-Proposal_SME-Continuous-Improvement-Agent.pdf. Mở lại file sau khi upload. Owner: TBD
- [x] T-002 [Core] Họp 30': chốt events.json v0.1 và interface 4 tool (Pydantic); xác nhận phân vai và lịch dời; ghi vào docs/decisions.md. Owner: TBD
- [x] T-003 [Tools] Repo chạy được: docker compose up -d db, uv run pytest xanh, .env.example, ruff. DoD: clone mới chạy 3 lệnh trong README là xong. Owner: TBD
- [x] T-004 [Data] Duyệt data/scenarios/scenario1.yaml: chốt nguyên nhân gốc, ground truth, nhiễu. Owner: TBD

## M1: Sandbox + Detect + Tools v1 (8/10)

- [x] T-010 [Data] Data model 6 bảng (kpi_log, machine_log, shift_schedule, inventory, supplier, sop) + simulator có tham số. DoD: test "đổi setpoint → defect về baseline" xanh. Due 6/10
- [x] T-011 [Data] Anomaly injector đọc YAML + ground truth ẩn có timestamp inject; có nguyên nhân tái diễn. DoD: sinh 6 tháng dữ liệu có ground truth. Due 7/10
- [x] T-012 [Data] Detect thống kê: baseline, control limits, xuất anomaly event đúng schema. DoD: bắt đúng anomaly của scenario 1, không báo bảo trì có kế hoạch là lỗi thật. Due 8/10
- [x] T-013 [Tools] DB models + migration: runs, events, audit_log, sop_versions, learning_store. Due 6/10
- [x] T-014 [Tools] query_logs, correlate, get_shift_schedule, read_sop (chỉ đọc) + test. Due 8/10
- [x] T-015 [Demo] data/context_profile.yaml (KPI, nhóm giả thuyết Ishikawa, SOP mẫu). Due 6/10
- [x] T-016 [Demo] Khởi tạo Next.js (yarn) và dashboard skeleton (bảng anomaly + timeline trace) chạy bằng mock events; freeze 7/10. Due 7/10
- [x] T-017 [Core] state.py trung tính + graph skeleton nối fake tool; Investigate bản mock. Due 6/10

## M2: Agent core + API (10/10)

- [x] T-020 [Core] System prompt + node Investigate (5 Whys, giả thuyết + confidence), LLM tự chọn tool. Due 7/10
- [x] T-021 [Core] Node Ask (interrupt) + resume từ checkpointer Postgres. Due 8/10
- [x] T-022 [Core] Node Improve (đề xuất + lý giải); trace đúng schema, có agent và domain. Due 9/10
- [x] T-023 [Tools] propose_sop/apply_sop (cần duyệt, có phiên bản), measure (before/after, MTTD/MTTR), learning_store. Due 10/10
- [x] T-024 [Core] Node Act/Measure/Learn; điều phối bằng cạnh điều kiện theo ngưỡng KPI. Due 10/10
- [x] T-025 [Tools] FastAPI: start run, answer, approve/reject; SSE stream trace. Due 9/10
- [x] T-026 [Demo] Dashboard đọc SSE (phát lại fixture qua đúng endpoint), sau đó ghép API thật. Due 10/10

## M3: End-to-end (11/10)

- [ ] T-030 [All] Chạy một vòng Detect → Learn trên dashboard thật; ghi lỗi vào issue list trong docs/decisions.md. Due 11/10
- [ ] T-031 [Data] Chạy simulator đủ 6 tháng. Due 11/10

## M4: v0.1-e2e (13/10)

- [ ] T-040 [Core] 3 cạnh quay lại: bác bỏ/bổ sung thông tin, từ chối đề xuất, rollback. Due 12/10
- [ ] T-041 [Core] Temperature thấp + record/replay một lần chạy tốt. Due 12/10
- [ ] T-042 [Data] Lấy số liệu 3 chỉ số (defect %, MTTD/MTTR, tỷ lệ tái diễn). Due 12/10
- [ ] T-043 [Demo] Số liệu lên dashboard; kịch bản 4 phút v1 (docs/demoscript.md). Due 12/10
- [ ] T-044 [Tools] Sổ chi phí token docs/token-cost.md (cập nhật hằng ngày). Due 13/10
- [ ] T-045 [All] Bug bash 12/10, tag v0.1-e2e, demo nội bộ #1 13/10.

## Backlog sau 13/10 (G6 → G8)

- [ ] Scenario ẩn (tồn kho hụt vì defect, hoặc 2 nguyên nhân cùng lúc)
- [ ] Case "chưa đủ bằng chứng" và case false positive hoàn chỉnh
- [ ] Tập demo #2, cập nhật ngân hàng Q&A
- [ ] Freeze 20/10, tag v0.2-freeze, video backup, checklist Tokyo
- [ ] Scenario 2–3 và Orchestrator (quyết định lại 17/10 và 25/10)

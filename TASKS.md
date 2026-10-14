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

- [x] T-030 [All] Chạy một vòng Detect → Learn trên dashboard thật; ghi lỗi vào issue list trong docs/decisions.md. Due 11/10
- [x] T-031 [Data] Chạy simulator đủ 6 tháng. Due 11/10

## M4: v0.1-e2e (13/10)

- [x] T-040 [Core] 3 cạnh quay lại: bác bỏ/bổ sung thông tin, từ chối đề xuất, rollback. Due 12/10
- [x] T-041 [Core] Temperature thấp + record/replay một lần chạy tốt. Due 12/10. Owner: auto-dev R10a. (Temperature đã thay bằng `LLM_EFFORT` ở R9h; còn phần record/replay, phục vụ FR-07.)
- [x] T-042 [Data] Lấy số liệu 3 chỉ số (defect %, MTTD/MTTR, tỷ lệ tái diễn). Due 12/10. Owner: auto-dev R10b2 (sau R10b1, tức sau khi D1 #66 của vai A merge).
- [ ] T-043 [Demo] Số liệu lên dashboard; kịch bản 4 phút v1 (docs/demoscript.md). Due 12/10. Owner: auto-dev R11d (ADR-011; trước là vai D #64). Kịch bản v1 nay là `docs/demo-storyboard.md`.
- [x] T-044 [Tools] Sổ chi phí token docs/token-cost.md (cập nhật mỗi lần chạy LLM thật). Owner: leader/Claude (ADR-011). Có từ 14/10, ghi lại 2 lần đo 12/10.
- [ ] T-045 [All] Bug bash bấm tay toàn kịch bản demo, demo nội bộ. Owner: leader (ADR-011; tag v0.1-e2e đã có 12/10). Làm sau R11d, trước cổng v0.2.

## Mốc backend auto-dev (lập lại 14/10, ADR-011; không gắn ngày)

Từ 14/10 leader + auto-dev làm cả việc của vai A, D, Q (ADR-011); bỏ ngày cũ, leader tự đặt ngày. Chi tiết, thứ tự, pre-mortem và thứ tự cắt: `docs/autodev/ROADMAP.md` mục "Kế hoạch lại 14/10"; bảng mốc: `docs/autodev/PROJECT_STATE.md` mục "Tầm nhìn". Chỉ số [A..] theo `docs/eval/criteria.md`: mốc xong khi chỉ số của nó **đo được** (có lệnh và số), không chỉ khi test xanh.

- [x] R10a (10–11/10): API storyboard (FR-09..12), T-041 record/replay; H-13, H-16, H-26. [A5 LLM giả, A8 `--repeat`]
- [ ] Đo nền LLM thật sau R10a (leader cho phép, ≤ 2 USD): A1 + chi phí mỗi run vào `docs/token-cost.md`
- [x] R10c (11–12/10, ngay sau R10a): lưu run/event/checkpointer vào Postgres (H-15), H-14, H-19, H-20, H-37, H-38. [A6 `test_invariants.py`]
- [x] Audit 3 (sau R10c, PR #86): B1 = 0,71, chưa đạt ngưỡng ≤ 0,5 [B1]
- [x] R10ch (sửa nhanh sau audit 3, PR #91): H-31, H-45, H-47, H-48, H-50, H-51, H-54. [A5 LLM giả đo thật: đúng 1,00/1,00, luôn sai (b) = 0]
- [x] R10b1 (12/10, **sau khi D1 #66 của vai A merge**; vai A review phần dữ liệu): dữ liệu theo hợp đồng D1 (`production_log`, `material_batches`, simulator nhị thức, `import_data.py` + V01–V09, dùng file mẫu/file sai của D2). D1 chưa merge sáng 12/10 thì leader quyết.
- [x] R10b2 (12–13/10): điều 3 (H-11, T-042, `/metrics` thật, `scripts/metrics_report.py` có đối chứng; giả định lấy nguồn từ D3); H-33, H-39 (H-31 đã đóng ở R10ch). [A7, A4] PR #132; 4 giả định còn "giả định, chờ D3".
- [x] Cổng 13/10 (`docs/eval/criteria.md` mục 3) → tag v0.1-e2e (leader duyệt 12/10, biên bản `docs/qa/gate-v0.1-e2e.md`; H-32 sửa trước freeze); cổng UI FR-01..05 (vai D). R10b2 trễ thì A7 không thuộc cổng 13/10, chuyển sang cổng 20/10 (leader quyết).
- [x] R10e (12/10): câu chữ tiếng Việt từ config, `GET /config/domain` (#114), Measure không hỏi lặp (H-34, #111), Learn `cause_status` (H-32), `/metrics` trung thực (H-65 a, c, d, e), ví dụ sinh lại (H-66). [A4 theo nguyên nhân: right 5/5, wrong 0/5] PR #138; 6 vitest của vai D cần cập nhật kỳ vọng.
- [ ] P4 tối thiểu (phiên chat, trước chuỗi 1): xem ROADMAP mục "Kế hoạch lại 14/10", việc 0.
- [ ] Chuỗi 1, R11c: ADR-010 phía backend (`labels` + thuật ngữ qua `/config/domain`, prompt dùng nhãn, `new_content`/SOP gốc tiếng Việt); H-52, H-53, H-55. `plan/R11c.md`
- [ ] Chuỗi 1, R11a: trường `signal`, bằng chứng thật theo vòng (H-63, H-18, H-56), H-36. [sau mốc đo A4/A5 LLM thật] `plan/R11a.md`
- [ ] Chuỗi 1, R11d (việc vai D cũ): #139 (6 vitest + lỗi nghĩa `n_after`), H-65 b/f/g, H-67, H-68, H-69, #141 (nhãn từ API, mã ở chú thích, chip, "trích nguyên văn", thuật ngữ); FR còn thiếu; ảnh chụp 1920×1080 trong PR. `plan/R11d.md` (viết trước chuỗi) [`verify.py` xanh cả `dashboard`]
- [ ] Nghiên cứu (phiên chat, song song chuỗi 1; việc vai A cũ): D3 `docs/research/reflow_domain.md` có nguồn; D5 `docs/research/scoring.md`; định dạng kịch bản `docs/research/scenarios.md`.
- [ ] Tập giữ lại niêm phong (phiên cách ly, ADR-011): ≥ 4 kịch bản ngoài repo, SHA-256 trong `docs/research/holdout-seal.md`; leader duyệt đáp án.
- [ ] Chuỗi 2, R11b: luật chấm theo mã theo D5 (H-28), loader + injector theo định dạng, tập dev khó ≥ 4 (H-29), eval A1–A3 trên DB sạch, lưu kết quả thô, chấm tập giữ lại (kiểm mã băm), ghi run để phát lại, A8 LLM thật → audit 5. [A1 tập giữ lại ≥ 0,7]
- [ ] Đo LLM thật (leader cho phép từng lần, ≤ 3 USD/lần): A4/A5 sau chuỗi 1; A1–A3 tập giữ lại sau R11b; ghi `docs/token-cost.md`.
- [ ] R12: lỗ hổng audit 5, H-60, H-61, H-62, H-64 (nguồn D3), D6 bộ dữ liệu demo, `docs/qa/responsible-ai.md` (Q5), `docs/qa/rehearsal-checklist.md` (Q7) → cổng v0.2 (`docs/qa/gate-v0.2-freeze.md`) → leader tag `v0.2-freeze`
- [ ] Leader (không thay được): bug bash bấm tay (T-045), diễn tập ≥ 2 lần, video dự phòng, slide trình bày, ngân hàng Q&A

## Backlog sau 13/10 (G6 → G8)

- [ ] Scenario ẩn (tồn kho hụt vì defect, hoặc 2 nguyên nhân cùng lúc)
- [ ] Case "chưa đủ bằng chứng" và case false positive hoàn chỉnh
- [ ] Tập demo #2, cập nhật ngân hàng Q&A
- [ ] Checklist Tokyo (khi leader đặt lịch)
- [ ] Scenario 2–3 và Orchestrator: ngoài kế hoạch lại 14/10 (chỉ xét lại khi leader yêu cầu)

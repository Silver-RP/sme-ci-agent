# Các quyết định kiến trúc (ADR ngắn)

Mỗi quyết định ghi: bối cảnh, quyết định, hệ quả. Sửa quyết định = thêm mục mới, không xóa mục cũ.

## ADR-001: MVP dùng một agent trung tâm, không multi-agent

- Bối cảnh: quỹ giờ khoảng 160–180 giờ công đến 13/10, chỉ có 1 scenario, nên chưa có gì để điều phối. Sơ đồ có nhiều "agent" nhưng Detect là code thống kê, Investigate/Improve là node cùng graph, Act/Measure/Learn là tool.
- Quyết định: một agent LangGraph; không có Agent Manager dùng LLM. Mô tả là "agent trung tâm gọi các tool chuyên biệt".
- Hệ quả: Orchestrator và agent chuyên biệt (Quality, Inventory, Supplier, Operations) nằm ở Next Step. Xem lại 17/10 và 25/10.

## ADR-002: Điều phối bằng cạnh điều kiện, rollback theo ngưỡng KPI

- Quyết định: chuyển bước, hỏi người, rollback do rule và ngưỡng KPI đặt trước; người xác nhận. LLM không tự quyết định rollback.
- Hệ quả: demo ổn định, dễ giải thích, rẻ token.

## ADR-003: events.json là hợp đồng backend ↔ dashboard

Mỗi event có agent (quality | investigation | improvement | system) và domain. Đổi schema chỉ qua PR riêng.

## ADR-004: Bố cục repo

data/ và tests/ nằm ở gốc repo (bản workflow gốc không rõ). Đổi lại nếu team muốn đặt trong backend/.

## ADR-005: Dashboard đơn giản

Chỉ bảng + timeline trace, ít biểu đồ. Đóng băng skeleton sau 2 ngày (7/10).

## ADR-006: Sonnet cho suy luận, Haiku cho việc rẻ

Tên model cấu hình trong .env. Ghi chi phí token hằng ngày.

## ADR-007: Chỉ dùng synthetic data

Không dữ liệu thật hay dữ liệu cá nhân trong MVP. API key chỉ ở .env, không commit.

## ADR-008: Lịch dời (chờ team xác nhận)

M1 dời từ 3/10 sang 8/10, M2 từ 8/10 sang 10/10; giữ nguyên 13/10 và 20/10.
Trạng thái: đã chốt (leader xác nhận 2026-10-08, xem ADR-009).

## ADR-009: Chốt contract M0 (T-002)

- Bối cảnh: contract M0 (events.json v0.1, interface 4 tool, phân vai, lịch) được hiện thực trước qua auto-dev (R4–R6) thay vì họp trước khi code.
- Quyết định (leader xác nhận 2026-10-08): giữ nguyên `docs/schema/events.json` hiện tại làm v0.1, và interface 4 tool chỉ đọc trong `backend/tools/readonly.py` (`query_logs`, `correlate`, `get_shift_schedule`, `read_sop`, nhận `ToolContext` và tham số tường minh). Lịch dời theo ADR-008.
- Hệ quả: đổi events.json hay chữ ký 4 tool từ nay phải qua PR riêng và báo trong sync. Phân vai trong docs/PLAN.md mục 4 điền khi có đủ người.

## ADR-010: Mọi chữ hiện trên UI bằng tiếng Việt; giữ thuật ngữ ngành quen dùng

- Bối cảnh (2026-10-12, leader thử dashboard với LLM thật sau R10e): câu do code sinh đã là tiếng Việt, nhưng UI vẫn lộ mã (`wrong_setpoint`, `defect_rate`, `zone3_setpoint_c`), SOP v1/v2 tiếng Anh, ghi chú log tiếng Anh. Nguyên nhân: prompt bảo LLM giữ nguyên tên mã; quy tắc ngôn ngữ R10e bỏ sót `new_content` của SOP; SOP gốc và ghi chú simulator viết tiếng Anh; bảng nhãn nằm cứng trong `dashboard/lib/strings.ts`.
- Quyết định (leader chốt 2026-10-12):
  1. Mọi chữ hiện trên UI là tiếng Việt. Mã (KPI, giả thuyết, nhóm, tham số, trạng thái) vẫn tiếng Anh trong code, API, DB.
  2. **Thuật ngữ ngành quen dùng giữ nguyên** (SOP, KPI, setpoint, operator…), giải nghĩa ở lần đầu xuất hiện, theo một bảng thuật ngữ trong domain config. Không dịch gượng.
  3. Chỗ bắt buộc không phải tiếng Việt (dữ liệu nguồn của khách, ví dụ ghi chú log) thì UI hiện dạng "trích nguyên văn" có nhãn và dòng giải nghĩa.
- Chia việc theo nguyên tắc "chữ do ai sinh thì người đó chịu":
  - Backend: khối `labels` + bảng thuật ngữ trong `data/context_profile.yaml`, trả qua `GET /config/domain`; prompt đưa bảng nhãn vào và yêu cầu câu văn dùng nhãn, không dùng mã; thêm `new_content` vào quy tắc ngôn ngữ; ghi chú simulator tiếng Việt.
  - Frontend (vai D): hiện nhãn lấy từ `/config/domain` (bỏ bảng nhãn viết cứng), mã để ở chú thích; mã còn sót trong câu LLM hiện thành chip có nhãn; kiểu hiển thị "trích nguyên văn".
  - Vai A: nội dung SOP gốc tiếng Việt (#122).
- Hệ quả: thêm `labels` vào `/config/domain` là thêm trường, ghi vào `docs/schema/payloads.md`; không đổi `events.json`.

## ADR-011: Leader + auto-dev tiếp quản các vai A, D, Q; tập giữ lại soạn bằng phiên cách ly

- Bối cảnh (2026-10-14 tối): sau D1, D2 (vai A) và FR-01..05 (vai D), việc còn lại của ba vai (D3–D6, #139, #141, Q1–Q7) đứng yên từ 12/10, trong khi điều 1 (0%) và giao diện ADR-010 nằm trên đường găng. Mọi mốc backend còn lại (R11b, R12) đang chờ sản phẩm của team.
- Quyết định (leader chốt 2026-10-14):
  1. Leader + Claude/auto-dev làm **toàn bộ** việc còn lại của vai A, D, Q. Issue #63, #64, #65, #139, #141 chuyển về leader; thành viên được báo một lần (comment), vẫn giữ quyền repo. PR của thành viên gửi tới vẫn được xem như trước.
  2. **Gỡ mọi mốc thời gian:** mọi ngày, hạn, lịch đã đặt trước đây (freeze 20/10, Pitch Day 24/10, Demo Day 07/11, Đợt UI, Due trong TASKS, ngày trong brief và plan/Rx.md) **vô hiệu**. Việc xếp theo giá trị và chi phí (`docs/autodev/ROADMAP.md`); khi cần, leader đặt lại ngày. Cổng "freeze" gọi là **cổng v0.2** (tag `v0.2-freeze` giữ tên), không gắn ngày.
  3. **Tập giữ lại (holdout) cho điều 1** không còn do vai A soạn. Thay bằng **phiên cách ly**: một phiên Claude riêng chỉ đọc hợp đồng dữ liệu, ghi chú ngành (D3), đặc tả chấm (D5), định dạng kịch bản; **không** đọc `backend/`, prompt, tập dev hay kết quả eval. Phiên đó soạn ≥ 4 kịch bản, lưu **ngoài repo** tới lúc chấm; mã băm SHA-256 từng file ghi vào repo ngay khi soạn xong (niêm phong). Leader đọc đáp án và duyệt trước khi niêm phong. Khi trình bày ra ngoài nêu rõ cách soạn này.
  4. Nguyên tắc "người kiểm khác người làm" của vai Q giữ bằng: reviewer + supervisor độc lập cho code; leader bấm tay (bug bash, diễn tập) cho giao diện; audit 5 cho cả hệ.
- Hệ quả: `docs/eval/criteria.md` mục 1, 3, 5 sửa theo; `team-task-boundaries` hết hiệu lực; auto-dev được sửa `dashboard/` (cả phần trình bày), `docs/research/`, `data/scenarios/`, `docs/qa/`. Kiến trúc (ADR-001..006) không đổi.

## ADR-012: Dồn lực phát triển auto-dev; SME CI Agent là dự án thử

- Bối cảnh (2026-10-15): sau phân tích mở rộng và nghiên cứu thị trường (ngoài repo), leader chọn tập trung vào công cụ làm ra sản phẩm thay vì sản phẩm.
- Quyết định (leader chốt 2026-10-15):
  1. Từ phiên sau, **100% nỗ lực cho auto-dev** (`docs/autodev/`, `.autodev/`, `.claude/`).
  2. **Mục tiêu auto-dev:** leader chỉ đưa mục tiêu và kết quả mong muốn; auto-dev tự phân tích, hỏi thông tin cần thiết, lập kế hoạch, tự điều phối giữa các vai để hoàn thành dự án.
  3. SME CI Agent quay về vai **dự án thử**: mốc R chỉ chạy khi kiểm chứng một khả năng của plugin. Kế hoạch "Kế hoạch lại 14/10" tạm giữ, không chủ động chạy.
- Chốt ở phiên phân tích (leader, 2026-10-15):
  4. **Thước đo "xong" của auto-dev:** B7 can thiệp của leader ≤ 1 / mốc; B8 ≥ 80% mốc tự xong (plan → merge không dừng); USD / mốc (B5). Cổng chất lượng giữ B1 ≤ 0,5 (ROADMAP bảng B).
  5. **Ngân sách:** chạy đến khi hết hạn mức (runner dừng khi chạm hạn mức tuần, chờ khi chạm hạn mức 5 giờ, như P4). Không đặt trần USD riêng.
  6. **Phạm vi ADR-001:** "một agent, không multi-agent, không Agent Manager" là luật của **sản phẩm** SME CI Agent. Không áp cho plugin auto-dev; auto-dev được tự điều phối nhiều vai (planner, developer, reviewer, supervisor, auditor).
- Hệ quả: ROADMAP plugin thêm P10–P13 và chỉ số B7, B8 (phân tích khoảng cách 15/10). Kiến trúc sản phẩm (ADR-001..006) không đổi.

## Việc cần sửa sau khi chạy (log lỗi M3)

### T-030 lần 1 (2026-10-09, LLM thật `claude-sonnet-5-5`, chạy qua API của `demo.sh`, người trả lời trung tính)
1. **Chặn (đã sửa ở R9h, PR #49):** lần gọi LLM đầu lỗi `TypeError: Messages.create() got an unexpected keyword argument 'temperature'`. SDK `anthropic` 1.11 đã bỏ `temperature`. Test của H-23 chỉ dùng client giả. Nay dùng `output_config.effort`, kèm test đối chiếu với chữ ký SDK thật.
2. **Kết quả tốt (bằng chứng cho điều 1, một mẫu):**
   - Agent tự gọi `query_logs` (machine_log), `correlate`, `get_shift_schedule`.
   - Từ machine_log, agent kết luận đúng nguyên nhân: zone3 setpoint M02 bị đổi từ 180 lên 195 °C lúc 2026-03-10T22:00, confidence 0,8.
   - Agent loại giả thuyết "thay ca" nhờ lịch ca (defect vẫn cao khi người cũ quay lại).
   - Không cần người gợi ý. Run `run_c72860d2`, khoảng 16 giây.
3. **Lỗi: đề xuất có `action` đúng nhưng không có `sop_proposal`.**
   - Đề xuất là `action = {zone3_setpoint_c, M02, 180}`.
   - Act trả `sop_applied.applied=false` ("proposal has no SOP change"), Measure trả `not_applied`, Learn lưu `outcome: no_change`, run vẫn `completed`.
   - Hệ quả: vòng không khép, dù chẩn đoán và hành động đều đúng.
   - Đây là mặt ngược của H-27 (audit 2: `sop_change` thiếu `action`).
   - Cần quyết thiết kế:
     - (a) hành động tham số được áp dụng và đo ngay cả khi không đổi SOP, với điều kiện đã có người duyệt; hoặc
     - (b) Improve bắt buộc có cả `action` lẫn `sop_proposal`, và yêu cầu LLM sửa lại nếu thiếu.

     Đề xuất của supervisor: (b) cho demo, vì vòng Detect → Learn cần SOP có phiên bản; kèm test với câu trả lời LLM thiếu `sop_proposal`.
4. **Hạn chế:**
   - Tool `correlate` báo không kiểm được vì chuỗi setpoint trong cửa sổ là hằng số (LLM tự ghi nhận điều này). Liên quan H-29.
   - Run kết thúc `completed` trong khi Measure `not_applied`; UI nên phân biệt trường hợp này (H-24).
5. **Chưa làm:**
   - Người dùng xem vòng trên dashboard (`?source=live`).
   - `uv run python scripts/eval_rootcause.py --llm real --seeds 2` (từ R9h script tự nạp file biến môi trường).

### T-030 lần 2 (2026-10-09 23:3x, sau R9i; cùng cách chạy)
- **Chẩn đoán vẫn đúng** (run `run_43db524f`): giả thuyết `machine` "Wrong setpoint… zone3_setpoint_c" có confidence 0,85. LLM xét giả thuyết người thay ca nhưng chỉ cho 0,3.
- **Lỗi H-43:** Improve yêu cầu sửa 2 lần rồi lỗi `ProposalError: sop_change.sop_id 'PLACEHOLDER_NEEDS_VALID_SOP_ID' is not a known SOP`. Run vào trạng thái `error` (retryable), đúng hành vi R9i, nhưng vòng vẫn không khép.
  - Nguyên nhân: prompt của Improve không có danh sách SOP (id, phiên bản, nội dung hiện tại); lượt điều tra không gọi `read_sop`; thông báo khi yêu cầu sửa lại không nêu id hợp lệ.
  - Sửa ở R9ih.

### T-030 lần 3 (2026-10-09 23:5x, sau R9ih; cùng cách chạy): vòng khép kín
- Run `run_ceded1f1` đi đủ các bước Detect → Investigate (3 tool) → Improve → duyệt (alice) → Act → Measure → Learn → `completed`.
- Chẩn đoán đúng: `wrong_setpoint` 0,8; `training_gap/new_operator` 0,3.
- `action` = `zone3_setpoint_c` M02 → 180. SOP-RFL-001 sinh bản mới, kèm bước kiểm setpoint và ghi log thay đổi.
- Measure `measured`, `passed` true: defect_rate 0,063 → 0,019 (target 0,02). Learn lưu `outcome: success`.
- Còn để ý:
  - `base_version` của SOP-RFL-001 đã lên 40 vì DB demo dùng chung, cộng dồn qua mọi lần chạy. Trước buổi demo nên reset DB demo hoặc dùng DB riêng.
  - Người trả lời trung tính không được hỏi lần nào, vì confidence 0,8 ≥ ngưỡng. Nhánh "hỏi người" với LLM thật chưa được thử (liên quan H-29: bài toán quá dễ).
- Còn lại cho T-030: người dùng chạy một vòng trên dashboard (`?source=live`) và chạy `uv run python scripts/eval_rootcause.py --llm real --seeds 2`.

### T-030 lần 4: người dùng tự chạy (2026-10-10)
- **Dashboard** (`?source=live`, LLM thật, run `run_25553654`): bấm Start run thì chỉ hiện ô Decided by / Reason, **không thấy thẻ đề xuất** (Review proposal: Change, Rationale, SOP cũ → mới). Trong khi đó backend vẫn báo `pending.type=approval`, `kind=proposal`, đủ `proposal` (wrong_setpoint 0,85) và `current_sop`. Lỗi ở phần trình bày của dashboard. Đăng ký **H-44**, giao team frontend; nếu cần thì R10 thêm test vitest đọc đúng payload R9i (có `action`, `sop_proposal`).
- **Terminal** (`run_scenario.py --llm real --answer "Không có thêm thông tin." --approver alice`, run `run_9754fbfe`): 12 event, đi trọn tới `learning_saved` và `run_finished`. Trong learning_store: `outcome: success`, nguyên nhân "Wrong setpoint… zone3 180 → 195 °C" (0,8), defect_rate 0,063 → 0,021.
- **Eval** (`eval_rootcause.py --llm real --seeds 2`): accuracy 50%, ask_rate 0%, khoảng 12,5k token.
  - Hàm chấm `is_correct` đòi mô tả chứa nguyên văn "wrong setpoint", trong khi LLM thật hay diễn đạt bằng lời khác ("Zone 3 setpoint … raised from 180 to 195"). Nhiều khả năng đây là sai do cách chấm (H-28), không phải agent sai. Sửa ở R11: giả thuyết mang mã nguyên nhân có cấu trúc, chấm theo mã.
  - ask_rate 0% vì bài toán quá dễ (H-29).
- Ghi chú môi trường: shell của người dùng còn kích hoạt venv cũ ở Desktop, `uv` cảnh báo `VIRTUAL_ENV ... does not match`. Không ảnh hưởng kết quả; gõ `deactivate` để tắt.
- **Kết luận T-030:** vòng Detect → Learn chạy được với LLM thật (3 lần thành công qua API và CLI). Các lỗi đã ghi: H-42, H-43 (đã sửa), H-44, H-28, H-29. Tick T-030.

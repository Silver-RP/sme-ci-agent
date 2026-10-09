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

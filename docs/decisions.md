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

(để trống)

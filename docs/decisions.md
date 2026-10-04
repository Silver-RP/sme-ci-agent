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
Trạng thái: đề xuất. Ghi "đã chốt" sau buổi họp M0.

## Việc cần sửa sau khi chạy (log lỗi M3)

(để trống)

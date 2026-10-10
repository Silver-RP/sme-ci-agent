# Báo cáo mốc R10ch (sửa nhanh sau audit 3)

## Tóm tắt so với tiêu chí cấp mốc
1. **verify + smoke sạch:** đạt (`verify.py`: sạch so với baseline, 583 pytest, 1 xfail có sẵn; `--smoke`: 4/4 ok).
2. **Tái hiện H-45, H-47, H-48, H-50, H-51 không còn:** đạt bằng test (TestClient + Postgres thật, session đọc riêng). Chưa chạy lại bằng uvicorn thật.
3. **A5 trên 5 seed (42..46) LLM giả:** LLM đúng (a) = 1,00, (b) = 1,00; LLM luôn sai (b) = 0,00; không áp dụng gì: `passed` không bao giờ true (KPI giữ 0,060–0,062, baseline 0,02). Số liệu do developer/reviewer đo, supervisor cần tự chạy lại để ghi vào PROJECT_STATE.

## Task
| Task | Trạng thái | Vòng | Commit |
|---|---|---|---|
| dev-01 H-45, H-31: commit bản SOP trước checkpoint | DONE | 1 | 1a5f7fd |
| dev-02 H-48: kiểm `change_time` lúc bắt đầu, `POST /runs/{id}/close` | DONE | 1 | 4455a6b |
| dev-03 H-47, H-50, H-51: khôi phục run sau restart | DONE | 1 | b562d22 |
| dev-04 H-54: A5(b) đọc `passed`, có đối chứng | DONE | 1 | 2eec698, f500ce1 |

Không có task BLOCKED. Verify bị hook chặn: 0. Hook SubagentStop chạy đủ cả 4 task (hook_runs 52→55+).

## Điều chỉnh (a)/(b)
- (a) dev-04: tiêu chí "đỏ trên main" không áp dụng cho code (code đã đúng; chỉ phép đo cũ sai). Chỉ sửa test.
- (a) dev-02: `change_time` có múi giờ bị từ chối hẳn (giờ sandbox không múi giờ).
- (a) dev-03: sửa thứ tự event lỗi theo hậu tố id (run đóng bằng `/close` khôi phục thành `running` do sắp theo `(ts, event_id)`).

## Đề xuất (c) / việc treo
- Cửa sổ kill giữa commit `apply_sop` và checkpoint `applied`: retry có thể tạo bản SOP trùng; chưa có test. Đề xuất R11a.
- Số retry suy ra từ chuỗi event lỗi (phụ thuộc định dạng event_id), không có cột riêng.
- Run chờ duyệt mà LLM chưa dựng được lúc restart bị đánh dấu `error`, phải `/retry`.
- A5 đối chứng mức run chỉ chứng minh không có Measure; chưa thử đột biến code để xem test đỏ.
- `POST /runs` chạy detect thêm một lần; H-59 mục "events khôi phục theo `ts` giây" còn mở.
- Cập nhật PROJECT_STATE (supervisor): đóng H-45, H-31, H-47, H-48, H-50, H-51, H-54; bỏ câu "retries về 0 sau restart"; ghi `POST /runs/{id}/close` vào payloads (đã cập nhật `docs/schema/payloads.md`); chạy `python3 .autodev/metrics.py --write`.
- Hook plugin: không phát hiện lỗi. Lưu ý guard chặn `sed -i` và `python3` qua stdin (đúng thiết kế).

## Cách chạy thử
`python3 .autodev/verify.py --smoke`; `uv run pytest -q tests/test_demo_llm_branches_r10a.py -s -k a5` để in số A5.

## Thời gian
Bắt đầu 06:13 UTC, kết thúc ~08:05 UTC 10/10 (~1 giờ 50 phút, chủ yếu developer/reviewer tuần tự). Xem `/usage` để điền cột "% hạn mức".

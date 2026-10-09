# Báo cáo mốc R9i: đề xuất của LLM phải đủ và hợp lệ

## Tóm tắt so với tiêu chí cấp mốc
1. `verify.py` và `verify.py --smoke` sạch: **đạt** (442 pytest).
2. Có `action` không có `sop_proposal` (dạng T-030 lần 1) → yêu cầu sửa lại, sửa đủ thì tới Measure `measured`; sửa hỏng quá giới hạn → lỗi retryable, không `completed`/`not_applied`: **đạt** (dev-01).
3. Có `sop_proposal` không có `action` (H-27) → xử lý tương tự, không có bản SOP mới khi chưa đo: **đạt** (dev-01).
4. `action` NaN/inf, ngoài min/max trong YAML, máy khác anomaly (H-30) → yêu cầu sửa lại: **đạt** (dev-02).
5. `test_measure_h06.py` không còn khoá hành vi cũ: **đạt** (dev-01 sửa dòng 62–70; dev-02 sửa thêm 2 test).

Đóng: H-27, H-30, H-41, H-42.

## Task
| Task | Trạng thái | Vòng | Commit |
|---|---|---|---|
| dev-01 đủ `action` + `sop_proposal` (H-42, H-27, H-41) | DONE | 1 | 509a11a |
| dev-02 kiểm miền giá trị `action` (H-30) | DONE | 1 | 65076dd |

Review: `.autodev/reviews/R9i-dev-01-r1.json`, `R9i-dev-02-r1.json` (cả hai PASS).

## BLOCKED / việc cần người quyết
Không có.

## Điều chỉnh (a)/(b)
- Developer sửa các test cũ khoá hành vi sai: `test_act` (2), `test_api::test_two_runs_are_isolated_and_repeatable`, `test_improve`, `test_measure_r8::test_proposal_without_sop_change_is_not_saved_as_success`, `test_measure_h06` (dòng 62–70 và 2 test dùng máy lạ, vì Improve từ chối trước Measure). Ý định kiểm tra không đổi.
- Fixture `docs/schema/examples/` sinh lại (chỉ khác run_id/ts); `payloads.md` cập nhật. `events.json` không đổi.

## Đề xuất (c) chờ duyệt
Không có. Gợi ý non-blocking (ngoài phạm vi): thêm unit test trực tiếp cho `action_level` với máy lạ (phòng thủ ở tầng Measure); Act tự vệ ném `ValueError` nên run `error` không có cờ retryable riêng (hiếm gặp).

## Verify so với baseline
`python3 .autodev/verify.py`: sạch, không lỗi mới. `--smoke`: alembic, run_scenario (LLM giả), data_report, demo.sh --check đều ok.

## Cách chạy thử
`python3 .autodev/verify.py --smoke`. Chạy lại T-030 với LLM thật (`eval_rootcause.py --llm real`) sau khi merge.

## Plugin
Hook SubagentStop chạy đủ cho cả hai task (hook_runs 35 → 37). Không phát hiện lỗi plugin. Lưu ý quy ước tên file review: `dev-01-r1.json` đã bị R9h dùng; R9i dùng tiền tố `R9i-`.

## Thời gian
Bắt đầu ~13:50Z, xong task ~14:15Z (~25 phút; developer dev-01 ~9 phút, dev-02 ~7,5 phút). Xem `/usage` để điền cột "% hạn mức".

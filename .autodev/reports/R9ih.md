# Báo cáo mốc R9ih (sửa nhanh: Improve biết SOP nào đang có)

## Tóm tắt so với tiêu chí cấp mốc
1. verify và verify --smoke sạch (448 pytest): đạt.
2. Prompt Improve chứa danh mục SOP (id, version hiệu lực tính cả `sop_versions`, title, nội dung cắt theo `improve.max_evidence_item_chars`), lấy từ config/DB: đạt.
3. `sop_id` lạ → thông báo sửa lại liệt kê id hợp lệ; LLM giả sai rồi đúng → `kpi_measured.status == "measured"`: đạt. Đóng H-43.

## Task
| Task | Trạng thái | Vòng | Commit |
|---|---|---|---|
| dev-01 | DONE | 1 | 3467282 |

## BLOCKED
Không có.

## Điều chỉnh (a)/(b)
Không có.

## Đề xuất (c)
Không có. Non-blocking của reviewer: chưa test riêng fallback config khi DB trống.

## Verify so với baseline
`verify.py` sạch; reviewer chạy lại `--smoke` sạch (alembic, run_scenario, data_report, demo.sh --check). Hook SubagentStop chạy bình thường (hook_runs 37→38). Test H-43 đỏ trước khi sửa (6 test).

## Cách chạy thử
`python3 .autodev/verify.py --smoke`. Người dùng chạy lại T-030 với LLM thật để xác nhận vòng khép.

## Thời gian
Bắt đầu 14:29Z, developer ~5 phút, reviewer ~4 phút, xong ~14:40Z. Xem `/usage` để điền cột "% hạn mức".

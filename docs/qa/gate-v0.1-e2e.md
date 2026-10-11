# Cổng go/no-go 13/10 (tag v0.1-e2e): phần backend

Bản ghi tạm phía backend (leader + Claude), lập 12/10 trên `main` `8e2c3ea`. Biên bản chính của cổng và demo nội bộ #1 là `docs/qa/demo-1.md` (T-045, vai Q); file này chỉ ghi số đo và nguồn để leader quyết tag.

Luật cổng: `docs/eval/criteria.md` mục 3. Luật "đạt theo cấu tạo": `criteria.md` mục 2 (một phần chỉ được tính khi kết quả đổi được lúc agent làm sai).

## Kết quả

| Mục | Ngưỡng v0.1 | Số đo | Nguồn | Kết luận |
|---|---|---|---|---|
| A6 bất biến an toàn | 0 vi phạm | 0 vi phạm | `uv run pytest tests/test_invariants.py`; audit 4 chạy lại (`docs/audits/2026-10-12.md`) | đạt |
| A8 độ tin cậy demo | 10/10, LLM giả | **10/10, p95 0,8 s** (từng run 0,4–0,8 s); dashboard tải được | `scripts/demo.sh --fresh-db --check --repeat 10`, chạy 12/10, đầu ra `passed 10/10; p95 0.8s`, `RUN CHECK PASSED`, `CHECK PASSED` | đạt |
| A4 vòng khép khi đúng | ≥ 0,9, LLM giả, 5 seed | `right` 5/5 = 1,0 | `uv run python scripts/eval_rootcause.py --until learn --seeds 5`; R10b2 (#132) và audit 4 cùng số | **đạt theo số, có cờ H-32** (xem dưới) |
| A5 rollback khi sai | (a) 1,0; (b) ≥ 0,8, LLM giả | (a) 1,0; (b) 1,0 | `uv run pytest tests/test_demo_llm_branches_r10a.py -k a5 -s`; audit 4 chạy lại; đối chứng "LLM luôn sai" (b) = 0 (H-54 đóng ở R10ch) | đạt |
| A7 3 chỉ số | tính được, cùng seed cho cùng số | seed 42: tỷ lệ lỗi 0,0204 / 0,0208; MTTD 8 / 72 giờ; MTTR 24 / 44 giờ; tái diễn 0,25 / 0,5 (có / không agent); chạy lại cùng số | `uv run python scripts/metrics_report.py --months 6 --seed 42`; audit 4 chạy lại | đạt ngưỡng v0.1 (độ tin yếu: H-64; điều 3 leader chốt 67%) |
| UI FR-01..05 | có PR | #116 (giao diện mới, FR-01/H-44), #117 (FR-04/H-46), #118 (FR-05/H-49), đã merge | GitHub | đạt theo chữ của luật; ô FR trong #64 chưa tick |

## Cờ cần leader quyết

1. **H-32 (A4):** audit 4 chạy `eval_rootcause.py --until learn --seeds 5` được `right` 100% và cả `wrong` 100%, tức Measure vẫn `passed` khi người duyệt sai `action`. Nếu áp luật "đạt theo cấu tạo" thì A4 có thể tính 0 tới khi sửa. Ngưỡng cổng v0.1 chỉ ghi "≥ 0,9", nên theo chữ vẫn đạt.
2. **Việc M4 ngoài luật cổng còn mở:** T-043 (số liệu lên dashboard, kịch bản 4 phút; vai D), T-044 (sổ chi phí token; vai Q), T-045 (bug bash, demo nội bộ, `demo-1.md`; vai Q).
3. **Rủi ro demo (audit 4, không chặn cổng):** H-65 (`/metrics` không nói số từ LLM giả), H-66 (ví dụ `docs/schema/examples/` cũ), H-67 (thẻ đo "900 / 6 điểm"), H-68 (kẹt sau Close), H-69 (tải lại trang "thinking" mãi).

## Quyết định

Leader 12/10: **go**. A4 tính đạt theo chữ của ngưỡng v0.1; H-32 là việc phải sửa trước freeze 20/10 (khi đó A4 không được đạt theo cấu tạo). Tag `v0.1-e2e` đặt trên commit merge PR này. T-043, T-044, T-045 tiếp tục, không chặn tag.

## Ghi chú môi trường demo

Lần đo A8 đầu tiên trượt ở bước dashboard: `dashboard/node_modules` thiếu thư viện mới từ #116 (`clsx`, `lucide-react`, `@tailwindcss/postcss`). Sửa bằng `yarn install --frozen-lockfile` trong `dashboard/`, rồi xoá cache `dashboard/.next/` (Turbopack giữ lỗi phân giải module cũ). Máy demo cần làm hai bước này sau mỗi lần merge PR đổi `dashboard/package.json`.

# Tiêu chí đánh giá đo được (leader duyệt 2026-10-10)

Tài liệu dùng chung cho cả team. Thay cho "% đạt" do audit ước lượng: mỗi điều cần kiểm chứng (`docs/PLAN.md` mục 1) có chỉ số đo bằng **lệnh**, lặp lại được (cùng seed cho cùng số), có **mốc nền** và **ngưỡng**. Chỉ số của plugin auto-dev (B1–B6) ở `docs/autodev/ROADMAP.md` bảng B; bảng tự sinh bằng `python3 .autodev/metrics.py`.

## 1. Cách đánh giá thực tế áp dụng
- **Tập dev và tập giữ lại (như eval mô hình học máy).**
  - Tập dev: kịch bản do backend/auto-dev soạn, dùng khi phát triển.
  - Tập giữ lại: kịch bản do vai A soạn (D4), backend không xem trước khi chấm.
  - Báo cáo riêng hai con số. **Chỉ tập giữ lại được tính vào điều 1**, để tránh "tự đúng" (H-28).
- **Thời gian phát hiện tính từ lúc lỗi xảy ra (như vận hành nhà máy).** MTTD đo khi Detect chạy theo dòng thời gian (mỗi ca chỉ thấy dữ liệu đến ca đó), không nhìn lại cả 6 tháng.
- **Có đối chứng.** Chỉ số trước/sau so với đường "không có agent": phát hiện và sửa thủ công theo giả định có nguồn (D3 của vai A, `docs/research/reflow_domain.md`).
- **Nhiều seed, ghi chi phí.** Mỗi lần chạy LLM thật ghi vào `docs/token-cost.md` (vai Q, Q6): lệnh, seed, kết quả, USD.

## 2. Chỉ số sản phẩm
| Mã | Chỉ số | Định nghĩa đo | Nền (10/10) | Ngưỡng v0.1 (13/10) | Ngưỡng freeze (20/10) | Lệnh đo (mốc làm) |
|---|---|---|---|---|---|---|
| A1 | Độ đúng nguyên nhân top-1 | tỷ lệ run có nhóm + **mã nguyên nhân** cuối cùng = ground truth | chưa đo được: eval chấm theo chuỗi (H-28); LLM giả chỉ kiểm bộ chấm (right 100%, wrong 0%) | tập dev ≥ 0,7 | **tập giữ lại ≥ 0,7**, tập dev ≥ 0,8 | `eval_rootcause.py --llm real --set dev\|holdout --seeds 3` (R11a, R11b) |
| A2 | Hỏi người đúng lúc | precision và recall của "có hỏi" so với nhãn `expect: ask` của kịch bản | chưa có nhãn; LLM giả "unsure": hỏi 100% | recall ≥ 0,8 | precision ≥ 0,6, recall ≥ 0,8 | như A1 |
| A3 | Báo động giả | số đề xuất trên kịch bản `expect: none` (không bất thường, bảo trì có kế hoạch) | chưa đo trong eval | 0 | 0 trên ≥ 2 kịch bản | như A1 |
| A4 | Vòng khép khi đúng | tỷ lệ run có `kpi_measured.passed = true` khi người duyệt đúng `action` | 1 run LLM thật (T-030) | ≥ 0,9 (LLM giả, 5 seed) | ≥ 0,9 (LLM thật, 3 seed) | eval `--until learn` (R10b2) |
| A5 | Rollback khi sai | (a) tỷ lệ đề xuất rollback khi `action` sai; (b) tỷ lệ đạt sau điều tra lại, trong giới hạn vòng của YAML | 1 test e2e | (a) = 1,0; (b) ≥ 0,8 (LLM giả, 5 seed) | như v0.1, thêm LLM thật 3 seed | `SME_DEMO_SCENARIO=rollback` (R10a) + eval |
| A6 | Bất biến an toàn | số vi phạm: áp dụng không duyệt, thiếu dòng `audit_log`, sửa bảng nguồn, LLM tự duyệt | từng test riêng | 0 | 0 qua `tests/test_invariants.py` (đầu vào ngẫu nhiên) | `uv run pytest tests/test_invariants.py` (R10c) |
| A7 | 3 chỉ số trên 6 tháng | tỷ lệ lỗi trước/sau (trọng số theo sản lượng); MTTD (giờ, từ lúc inject tới `anomaly_detected`); MTTR (giờ, tới khi KPI về ngưỡng); tỷ lệ tái diễn (có/không `learning_store`) | không có (H-11) | tính được, cùng seed cho cùng số | agent tốt hơn đối chứng ở cả 3 | `scripts/metrics_report.py --months 6 --seed N` (R10b2) |
| A8 | Độ tin cậy demo | `demo.sh --check` trọn vòng: số lần đạt trong 10 lần liên tiếp; run LLM thật thành công trên 5; p95 thời gian một run; USD trên run | chỉ kiểm khởi động | 10/10 (LLM giả) | 10/10, LLM thật 5/5, p95 ≤ 30 s | `demo.sh --check --repeat 10` (R10a) |

### % đạt (thay cho ước lượng)
Mỗi chỉ số quy về điểm `min(giá trị / ngưỡng freeze, 1)`. Chỉ số "càng ít càng tốt" (A3, A6) được 1 khi bằng ngưỡng và 0 khi vượt.
- Điều 1 = trung bình A1 (tập giữ lại), A2, A3.
- Điều 2 = trung bình A4, A5, A6.
- Điều 3 = trung bình 3 phần của A7.
- A8 là cổng demo, không tính vào %. Chỉ số chưa đo được tính 0.

Audit vẫn tìm lỗ hổng (H-xx) nhưng không còn tự đặt %.

## 3. Cổng go/no-go
- **13/10, tag v0.1-e2e:**
  - A6 = 0; A8 = 10/10 (LLM giả); A4, A5 đạt ngưỡng v0.1; A7 tính được.
  - UI FR-01..05 có PR. Không đạt thì leader quyết.
- **20/10, freeze:**
  - mọi ngưỡng freeze của mục 2;
  - A1 trên tập giữ lại có số. Thiếu đề của vai A thì ghi rõ giới hạn khi pitch, và điều 1 không được báo quá 60%.

Vai Q ghi kết quả từng cổng vào biên bản go/no-go (`docs/qa/demo-1.md`), kèm lệnh và đầu ra.

## 4. Yêu cầu với kịch bản (cho D4, D5 của vai A)
Mỗi kịch bản YAML cần:
- `expect`: `conclude` | `ask` | `none`;
- `ground_truth.cause_code`: mã nguyên nhân thuộc `hypothesis_groups` trong `data/context_profile.yaml`, kèm máy và thời điểm;
- `set`: `dev` | `holdout`;
- độ khó đo được: độ lớn anomaly theo σ, số giả thuyết gây nhiễu, bằng chứng trực tiếp hay gián tiếp.

## 5. Ai đo, khi nào
| Chỉ số | Ai chạy | Khi nào |
|---|---|---|
| A4–A8 (LLM giả) | runner auto-dev, supervisor kiểm | mỗi mốc có liên quan; trước mỗi cổng |
| A1–A5 (LLM thật) | vai Q, leader cho phép từng lần, ≤ 2 USD/ngày | sau R10a (đo nền), R11a, R11b, trước freeze |
| B1–B6 (plugin) | leader/Claude, `python3 .autodev/metrics.py --write` | sau mỗi mốc và mỗi audit |

# Giao việc: nghiên cứu dữ liệu đầu vào và kịch bản (vai A: Data)

- **Người giao:** leader. **Ngày:** 2026-10-10.
- **Người nhận:** thành viên phụ trách nghiên cứu và chuẩn hoá dữ liệu.
- **Đọc file này trước tiên;** mọi tài liệu khác được dẫn link ở mục 7.

## 1. Bối cảnh trong 1 phút

**SME CI Agent** là một AI agent giúp doanh nghiệp sản xuất nhỏ (SME) cải tiến liên tục (Continuous Improvement), dự thi Vietnam Japan AI Hackathon 2026. Mốc tham khảo:

| Mốc | Ngày |
|---|---|
| v0.1-e2e | 13/10 |
| Freeze code | 20/10 |
| Pitch Day | 24/10 |
| Demo Day | 07/11 |

Agent chạy một vòng 8 bước: Observe → **Detect** (thống kê, không LLM) → **Investigate** (LLM gọi tool chỉ đọc) → **Ask** (hỏi người khi thiếu bằng chứng) → **Improve** (đề xuất thay đổi và SOP mới) → **Act** (áp dụng, *chỉ sau khi người duyệt*) → **Measure** (đo KPI trước/sau) → **Learn** (lưu bài học).

Kịch bản demo hiện có (`data/scenarios/scenario1.yaml`):
- Xưởng hàn reflow: 3 máy (M01–M03), 3 ca/ngày, 6 tháng dữ liệu **mô phỏng**.
- Ngày 10/3, ca đêm đổi setpoint nhiệt vùng 3 của máy M02 từ 180 lên 195 °C mà không cập nhật SOP. Tỷ lệ lỗi tăng từ khoảng 2% lên khoảng 6%.
- Agent phải tìm ra nguyên nhân, đề xuất khôi phục 180 °C và thêm bước kiểm tra vào SOP; người duyệt; KPI về lại khoảng 2%.

Ba điều dự án phải chứng minh (`docs/PLAN.md` mục 1):
1. Agent tìm **đúng nguyên nhân gốc** (so với đáp án ẩn) và **biết hỏi người** khi chưa đủ bằng chứng.
2. Đề xuất được duyệt làm **KPI cải thiện**; nếu không thì rollback và điều tra lại.
3. Đo được **3 chỉ số trước/sau** trên 6 tháng dữ liệu mô phỏng: tỷ lệ lỗi (%), MTTD/MTTR (thời gian phát hiện/khắc phục), tỷ lệ tái diễn.

## 2. Vì sao cần việc này (vấn đề hiện tại)

Phần code đã chạy được vòng đầy đủ với LLM thật (T-030, ngày 9–10/10): agent tự tìm đúng nguyên nhân setpoint, KPI giảm từ 6,3% về 2,1%. Nhưng một **audit độc lập** (`docs/audits/2026-10-09_2.md`) kết luận rằng kết quả đó **chưa phải bằng chứng thuyết phục**, vì dữ liệu và kịch bản quá dễ và quá "đo ni đóng giày":

| Vấn đề | Mã | Hệ quả |
|---|---|---|
| Anomaly lệch khoảng 10σ so với nhiễu (6,2% so với nền 2%, độ lệch chuẩn 0,4%); machine_log ghi thẳng "đổi setpoint 180 → 195" đúng lúc bắt đầu | H-29 | Ai cũng đoán ra, nên không chứng minh được năng lực điều tra |
| Tool `correlate` gần như trả sẵn nhãn nguyên nhân (r ≈ 0,98); các nhóm người, môi trường, nguyên liệu không có tín hiệu | H-29 | Giả thuyết gây nhiễu không thể được kiểm chứng thật |
| Agent không bao giờ cần hỏi người (confidence 0,8 ngay lần đầu) | H-29 | Chưa chứng minh được điều 1b ("biết hỏi") với LLM thật |
| Eval chấm bằng cách tìm chữ "wrong setpoint" trong câu mô tả | H-28 | LLM thật diễn đạt khác thì bị chấm sai (eval thật: 50%) |
| Dữ liệu nhập là **tỷ lệ** theo ca, không phải số đếm; chưa có định dạng nhập cho SME | — | Không trả lời được câu hỏi "doanh nghiệp đưa dữ liệu vào thế nào?" khi pitch |
| Chỉ có một kịch bản và một nguyên nhân | — | Không đo được độ đúng thật, không có tỷ lệ tái diễn có ý nghĩa |

Leader đã quyết (10/10):
- chuẩn hoá ở mức **hợp đồng dữ liệu + nhập CSV**;
- giao việc phân tích kỹ phần dữ liệu và kịch bản cho một người riêng (bạn);
- phần code do nhóm và auto-dev hiện thực **sau khi** tài liệu của bạn được duyệt.

## 3. Mục tiêu

Trả lời được ba câu hỏi, và viết thành tài liệu mà người code có thể hiện thực **không phải đoán**:

1. **Dữ liệu:** một SME sản xuất (bắt đầu với hàn reflow / lắp ráp điện tử) thực tế có những dữ liệu gì, ở dạng nào (Excel, giấy, MES), và hợp đồng dữ liệu tối thiểu nào vừa đủ cho agent mà SME vẫn chuẩn bị được?
2. **Kịch bản:** bộ kịch bản mô phỏng nào đủ **thực tế** và đủ **khó** để chứng minh 3 điều ở mục 1, nhất là "tìm đúng nguyên nhân" và "biết hỏi người"?
3. **Chấm điểm:** đáp án ẩn (ground truth) nên biểu diễn thế nào để chấm tự động **theo mã nguyên nhân** chứ không theo chữ; và đo độ khó của mỗi kịch bản bằng gì?

## 4. Sản phẩm cần giao (deliverables)

Viết bằng **Markdown và YAML**; không cần viết code Python (auto-dev hiện thực). Mỗi sản phẩm một PR, nhánh `feat/data-<tên>`, một người review.

| # | Sản phẩm | File | Đạt khi |
|---|---|---|---|
| D1 | **Hợp đồng dữ liệu bản chốt** | sửa `docs/schema/data_contract.md` (đang là bản đề xuất v0.1) | Trả lời 3 câu hỏi ở mục 6 của file đó; mỗi bảng có cột, kiểu, đơn vị, ràng buộc, cột bắt buộc; có lý do thực tế (SME có dữ liệu này không, lấy từ đâu); luật kiểm hợp lệ đủ cụ thể để viết test |
| D2 | **File mẫu CSV** | `data/templates/*.csv` | Mỗi bảng 5–10 dòng ví dụ hợp lệ, cộng 1 file lỗi cố ý cho mỗi luật V01–V09 (để test validator) |
| D3 | **Ghi chú thực tế ngành** | `docs/research/reflow_domain.md` | Khoảng giá trị thực tế (tỷ lệ lỗi điển hình, nhiễu theo ca, cỡ lô, setpoint vùng nhiệt, các nguyên nhân lỗi phổ biến và dấu vết của chúng trong log), **kèm nguồn tham khảo**. Ghi rõ chỗ nào là giả định |
| D4 | **Danh mục kịch bản** | `docs/research/scenarios.md` + bản nháp YAML `data/scenarios/draft/*.yaml` | Ít nhất 4 kịch bản (xem gợi ý mục 5), mỗi kịch bản có: câu chuyện, tham số, dấu vết để lại trong từng bảng, đáp án ẩn **có mã nguyên nhân**, mức độ khó, hành vi mong đợi của agent (kết luận / hỏi người / không làm gì) |
| D5 | **Đặc tả chấm điểm** | `docs/research/scoring.md` | Đáp án biểu diễn thế nào (mã nguyên nhân từ `hypothesis_groups`, máy, thời điểm); thế nào là đúng, sai, đúng một phần; chỉ số eval (độ đúng, tỷ lệ hỏi người đúng lúc, báo động giả); cách đo độ khó (ví dụ độ lớn anomaly/σ, số giả thuyết gây nhiễu, bằng chứng có trực tiếp không) |
| D6 | **Đề xuất bộ dữ liệu cho demo** | mục cuối của `scenarios.md` | Chọn kịch bản nào chạy live, kịch bản nào làm dự phòng; vì sao kể chuyện tốt trong 4 phút (`docs/demo-storyboard.md`) |

**Thứ tự đề xuất:** D1 + D2 trước, vì sprint code tiếp theo (R10) cần hợp đồng dữ liệu. Sau đó D3 → D4 → D5 → D6. Hạn cụ thể do leader đặt; xem mục 8.

## 5. Gợi ý hướng nghiên cứu (không bắt buộc theo)

- **Mức độ khó** nên có thang, ví dụ:
  - L1: hiện tại, rõ ràng;
  - L2: anomaly nhỏ (khoảng 3–4σ), dấu vết gián tiếp;
  - L3: hai nguyên nhân chồng nhau, hoặc nguyên nhân thật không có dòng log trực tiếp;
  - L4: thiếu bằng chứng, nên agent đúng ra **phải hỏi người**.
- **Ý tưởng kịch bản:**
  - setpoint trôi dần thay vì đổi một lần;
  - lô nguyên liệu kém chỉ ảnh hưởng một máy;
  - người mới chưa được đào tạo ở ca đêm;
  - nhiệt độ/độ ẩm mùa hè;
  - bảo trì có kế hoạch (báo động giả, agent không nên đổi SOP);
  - tái diễn sau khi đã học (để đo tỷ lệ tái diễn và MTTD/MTTR).
- **Nhiễu thật hơn:** sinh **số đếm** (số lỗi theo phân phối nhị thức trên sản lượng) thay vì tỷ lệ cộng nhiễu chuẩn.
- **Mỗi nhóm Ishikawa phải có tín hiệu kiểm chứng được** trong dữ liệu. Nếu không có tín hiệu thì agent chỉ có thể đoán, và nên hỏi người.
- **Tham khảo:** SPC / control chart (luật Western Electric), Ishikawa 6M, 8D / A3 problem solving, dữ liệu lỗi điển hình của SMT/reflow (voiding, solder bridge, tombstone), MTTD/MTTR trong bảo trì.

## 6. Ràng buộc bắt buộc (không được vi phạm)

- **Chỉ dùng dữ liệu synthetic.** Không thu thập hay đưa vào repo dữ liệu thật của doanh nghiệp nào, không dữ liệu cá nhân. Mã người vận hành là mã ẩn danh (`OP-017`).
- **Tên trung tính.** KPI là giá trị của một cột, không phải tên cột; không đặt tên bảng/cột theo "defect".
- **KPI, nhóm giả thuyết (Ishikawa), SOP, ngưỡng nằm trong `data/context_profile.yaml`.** Kịch bản không hard-code chúng.
- **Agent chỉ đọc dữ liệu nguồn.** Mọi thay đổi SOP phải có người duyệt. Rollback do ngưỡng KPI và người xác nhận, không do LLM quyết.
- **Không đổi `docs/schema/events.json`** (hợp đồng backend ↔ dashboard). Nếu cần thì ghi đề xuất cho leader.
- **Phạm vi MVP:** scenario 1 (sản xuất, tỷ lệ lỗi). Kịch bản khác **cùng ngành**; chưa làm đa ngành, chưa làm ánh xạ cột tuỳ biến.
- Đáp án ẩn chỉ dùng để chấm, **không bao giờ** được lộ vào dữ liệu agent đọc (ví dụ: không ghi "nguyên nhân là X" trong cột note).

## 7. Tài liệu và công cụ có sẵn

| Cần | Ở đâu |
|---|---|
| Kế hoạch, 3 điều cần kiểm chứng, thứ tự cắt | `docs/PLAN.md` |
| Quy tắc dự án | `CLAUDE.md` |
| Hợp đồng dữ liệu đề xuất (điểm xuất phát của D1) | `docs/schema/data_contract.md` |
| Schema bảng hiện tại (6 bảng) | `backend/sandbox/schema.py` |
| Kịch bản hiện tại | `data/scenarios/scenario1.yaml` |
| KPI, nhóm Ishikawa, SOP, ngưỡng | `data/context_profile.yaml` |
| Bộ sinh dữ liệu | `backend/sandbox/simulator.py`, `injector.py` |
| Lỗ hổng liên quan dữ liệu | `docs/audits/2026-10-09_2.md` (H-28, H-29), `docs/autodev/PROJECT_STATE.md` |
| Kết quả chạy LLM thật | `docs/decisions.md` mục "Việc cần sửa sau khi chạy" |
| Storyboard demo (để chọn D6) | `docs/demo-storyboard.md` |

Lệnh hữu ích (cần Docker Desktop đang chạy và `uv sync` một lần):

```bash
uv run python scripts/gen_data.py --seed 42     # sinh 6 tháng dữ liệu ra CSV (data/generated/) + ground_truth.json
uv run python scripts/data_report.py            # Detect bắt anomaly nào, có báo động giả không
uv run python scripts/run_scenario.py           # chạy một vòng agent với LLM giả (miễn phí)
uv run python scripts/eval_rootcause.py         # eval nguyên nhân (LLM giả)
```

Chạy với LLM thật (`--llm real`) tốn credit API của leader; hỏi trước khi chạy.

## 8. Cách làm việc

- **Nhánh `feat/data-<tên>`**, commit `feat:` / `docs:`, PR vào `main`, một người review trong 12 giờ. Không đẩy thẳng lên `main`.
- **Câu hỏi về phạm vi và quyết định thiết kế:** hỏi leader. Câu hỏi về code hiện tại: hỏi leader, hoặc mở issue trên GitHub.
- **Điểm kiểm (leader chốt ngày; gợi ý):**
  1. Sau 1 ngày: bản nháp D1 + câu trả lời 3 câu hỏi, để R10 bắt đầu.
  2. Sau 2–3 ngày: D3 + D4 (bản nháp 4 kịch bản).
  3. Trước freeze (20/10): D5 + D6 chốt.
- **Sau khi D1 được duyệt:** auto-dev hiện thực validator, nhập CSV, simulator số đếm (R10). Sau D4 + D5: kịch bản khó và eval chấm theo mã (R11). Bạn review PR của các mốc đó ở phần dữ liệu.
- **Ngoài phạm vi:** viết code backend, UI dashboard (bạn frontend làm), đổi kiến trúc agent.

## 9. Từ vựng

| Từ | Nghĩa |
|---|---|
| KPI | Chỉ số theo dõi, ví dụ `defect_rate` (tỷ lệ lỗi) |
| Anomaly | Đoạn KPI vượt giới hạn kiểm soát (control limit) |
| Ground truth / đáp án ẩn | Nguyên nhân thật trong kịch bản; chỉ dùng để chấm |
| Ishikawa / 6M | Nhóm nguyên nhân: máy, phương pháp, nguyên liệu, môi trường, con người, đo lường |
| SOP | Quy trình thao tác chuẩn, có phiên bản |
| MTTD / MTTR | Thời gian từ khi sự cố bắt đầu đến khi phát hiện / đến khi khắc phục |
| Tỷ lệ tái diễn | Sự cố cùng loại lặp lại sau khi đã học |
| σ (sigma) | Độ lệch chuẩn của nhiễu; "10σ" nghĩa là lệch rất xa, quá dễ thấy |
| Eval | Chạy agent nhiều lần trên kịch bản có đáp án để đo độ đúng |

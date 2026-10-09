# Giao việc: giao diện demo SME CI Agent (vai D: Demo/UI)

- **Người giao:** leader (kiêm BA). **Ngày:** 2026-10-10.
- **Người nhận:** thành viên frontend.
- **Trạng thái:** bản yêu cầu v1. Thay đổi yêu cầu sẽ ghi ở mục 12.

## 1. Bối cảnh và mục tiêu

SME CI Agent là AI agent giúp xưởng sản xuất nhỏ cải tiến liên tục. Vòng 8 bước:
1. **Detect:** thống kê phát hiện KPI bất thường.
2. **Investigate:** LLM tự đọc log.
3. **Ask:** hỏi người khi thiếu bằng chứng.
4. **Improve:** đề xuất hành động và SOP mới.
5. **Act:** áp dụng, chỉ sau khi người duyệt.
6. **Measure:** đo KPI trước/sau.
7. **Learn:** lưu bài học (phiếu kaizen).
8. **Rollback:** nếu KPI không đạt, đề xuất quay về SOP trước, người xác nhận.

Backend đã chạy trọn vòng với LLM thật (ngày 9–10/10). **Giao diện hiện là điểm yếu nhất:** khi chạy thật, màn duyệt **không hiện thẻ đề xuất** (H-44); timeline in chữ thô; kết quả đo hiện `passed=`.

**Mục tiêu sản phẩm (đo được):**
1. Trên **màn chiếu**, trong demo **4 phút** (`docs/demo-storyboard.md`), giám khảo nhìn mỗi màn **dưới 10 giây** là hiểu: agent đang làm gì, vì sao, người quyết gì, kết quả ra sao.
2. Người duyệt ra quyết định được **chỉ bằng thông tin trên một màn**, không cần mở log.
3. Demo **không bao giờ chết trên sân khấu**:
   - LLM chậm thì có trạng thái chờ rõ ràng;
   - lỗi thì có Thử lại;
   - mất mạng hoặc LLM thì có chế độ phát lại run đã ghi.

## 2. Người dùng

| Vai | Họ cần |
|---|---|
| **Người duyệt** (quản đốc / QA lead, ví dụ `alice`) | Hiểu đề xuất, so SOP cũ → mới, duyệt / từ chối / bổ sung thông tin, thấy kết quả |
| **Người trình bày** (thành viên đội) | Điều khiển nhịp demo: bắt đầu, chờ, chọn nhánh (đạt / rollback), phát lại khi sự cố |
| **Khán giả** (giám khảo) | Hiểu câu chuyện từ xa: chữ lớn, màu có nghĩa, ít chữ |

## 3. Phạm vi và ranh giới

- **Bạn làm:** toàn bộ phần trình bày trong `dashboard/` (`app/`, `components/`, style, chuỗi hiển thị), test giao diện (vitest; Playwright nếu muốn).
- **Dùng chung, sửa phải báo trong PR:** `dashboard/lib/api.ts`, `lib/validate.ts`, `lib/sources.ts`, `lib/useRunEvents.ts`. Backend có thể sửa các file này khi API đổi.
- **Backend / auto-dev làm:** API, dữ liệu, logic agent, fixture. Từ mốc R9, auto-dev **không sửa** phần trình bày.
- **Hợp đồng:** `docs/schema/events.json` (vỏ event, **không đổi**), `docs/schema/payloads.md` (payload và API), ví dụ thật `docs/schema/examples/*.json` (8 nhánh). Cần trường mới thì mở issue, không tự đổi hợp đồng.
- **Ngoài phạm vi:** đăng nhập/phân quyền thật, đa ngôn ngữ đầy đủ (chỉ cần tách chuỗi), mobile, biểu đồ phức tạp (PLAN mục 7 cho phép cắt biểu đồ đầu tiên).

## 4. Hiện trạng code (để bắt đầu nhanh)

- **Stack:** Next.js 16, React 19, TypeScript, vitest + Testing Library. Lệnh: `yarn dev | lint | test | build`. Node ≥ 22.13.
- **Ba nguồn dữ liệu** chọn bằng query string (`app/page.tsx`):

  | URL | Nguồn |
  |---|---|
  | `?source=fixture` (mặc định) | phát lại `dashboard/fixtures/scenario1.json` |
  | `?source=live` | gọi backend thật |
  | `?source=sse&run=<id>` | chỉ xem event |

- **Component có sẵn:** `RunView`, `LiveRun`, `RunControls` (nút Start / Answer / Approve…), `ProposalCard`, `Timeline`, `AnomalyTable`.
- **Chạy cả hệ thống với LLM giả, miễn phí:** `bash scripts/demo.sh`, mở `http://localhost:3000/?source=live`. LLM thật: `SME_LLM=real bash scripts/demo.sh`, tốn credit, hỏi leader trước.
- **Lỗi đã biết thuộc phần của bạn:** H-44 (thẻ đề xuất không hiện), H-35 (chưa theo payload R9: `action`, halt `options`, `retryable`), H-24 (kết quả run và `passed: null`), một phần H-13 (sau Retry, luồng event không mở lại).

## 5. Yêu cầu chức năng

Mức ưu tiên: **M** = Must (phải có trước v0.1), **S** = Should (trước freeze), **C** = Could.

Dữ liệu: `pending` lấy từ `GET /runs/{id}`; `event` lấy từ SSE `GET /runs/{id}/events`. Trường chi tiết xem `payloads.md`.

### FR-01 Duyệt đề xuất (màn S5) [M]: sửa H-44
**User story:** Là người duyệt, tôi muốn thấy đủ vì sao, làm gì, SOP đổi thế nào và kỳ vọng gì trên một màn, để quyết định trong 30 giây.

**Dữ liệu:** `pending.type == "approval"`, `pending.kind == "proposal"`:
- `proposal.hypothesis` {group, description, confidence};
- `proposal.change`, `proposal.rationale`, `proposal.evidence_refs`;
- `proposal.action` {parameter, machine_id, value};
- `proposal.expected_kpi`;
- `proposal.sop_proposal` {sop_id, base_version, new_content};
- `pending.current_sop` {sop_id, version, content};
- `pending.proposal_id`, `pending.proposal_hash`;
- `GET /config/approvers`.

**Tiêu chí chấp nhận:**
1. *Cho* pending lấy nguyên văn từ `docs/schema/examples/run-happy.json` (payload sau R9i), *khi* render, *thì* hiện đủ 5 khối:
   - **Vì sao:** nhóm, mô tả, thanh độ tin cậy;
   - **Làm gì:** câu "Máy M02: `zone3_setpoint_c` → 180" và mô tả `change`;
   - **SOP cũ → mới:** so khác biệt từng dòng; dòng thêm xanh, dòng bỏ đỏ; ghi "v*N* → v*N+1*";
   - **Kỳ vọng:** KPI, chiều, mục tiêu;
   - **Người duyệt và nút.**
2. Nếu `new_content` trùng `current_sop.content` thì hiện "Nội dung SOP không đổi".
3. Người duyệt chọn từ dropdown `/config/approvers`. Chưa chọn thì các nút bị khoá.
4. Ba nút **Duyệt**, **Từ chối**, **Bác bỏ giả thuyết / bổ sung thông tin**. Nút thứ ba bắt buộc nhập lý do (khoá nút khi trống). Gửi đi kèm `proposal_id` và `kind` (đã có trong `decideApproval`).
5. Trong lúc gửi, khoá nút và hiện "Đang gửi…". Nhận **409** thì tự tải lại trạng thái và báo "Đề xuất đã thay đổi, xem lại". Nhận **422** thì hiện thông báo của backend.
6. Mô tả dài quá 3 dòng thì có "Xem thêm"; không làm tràn màn.

### FR-02 Điều tra trực tiếp (màn S3) [M]
**User story:** Là khán giả, tôi muốn thấy agent đang làm gì trong 15–20 giây chờ LLM, để tin rằng nó thực sự điều tra.

**Dữ liệu:** event `tool_called` {tool, arguments, ok}, `hypothesis_updated` {hypotheses[], insufficient_evidence}, `anomaly_detected`.

**Tiêu chí chấp nhận:**
1. Mỗi `tool_called` là một thẻ, tên dễ hiểu:
   - `detect` → "Quét KPI";
   - `query_logs` → "Đọc log máy";
   - `correlate` → "Tìm tương quan";
   - `get_shift_schedule` → "Xem lịch ca";
   - `read_sop` → "Đọc SOP";
   - tool lạ thì hiện tên gốc.

   Thẻ kèm tham số chính (máy, khoảng thời gian) và dấu ✓ / ✗ theo `ok`.
2. Bảng giả thuyết theo nhóm Ishikawa, có thanh confidence, sắp giảm dần; giả thuyết dẫn đầu được làm nổi.
3. Khi run `running` mà chưa có event mới, hiện chỉ báo "Agent đang phân tích…" có hoạt ảnh. **Không có màn trắng quá 2 giây.**
4. Không in JSON thô ở bất kỳ đâu trên màn chính. Có thể có nút "Chi tiết" để xem JSON.

### FR-03 Kết quả đo (màn S6) [M]
**Dữ liệu:** `kpi_measured` {status, passed, before, after, target, direction, n_before, n_after, min_samples_after?, reason?}.

**Tiêu chí chấp nhận:**
1. `status == "measured"`: hai số lớn **Trước** và **Sau** dạng %; mũi tên theo `direction`; mục tiêu; nhãn **Đạt** (xanh) hoặc **Chưa đạt** (đỏ cam) theo `passed`; dòng nhỏ ghi số mẫu.
2. `insufficient_evidence`: "Chưa đủ dữ liệu sau thay đổi (n_after / min_samples_after)".
3. `not_applied`: "Chưa áp dụng thay đổi" kèm `reason`.
4. Không bao giờ hiện `null`, `undefined`, `passed=`.

### FR-04 Trạng thái run, lỗi và Thử lại [M]: H-24, H-13
**Tiêu chí chấp nhận:**
1. Thanh trạng thái phân biệt được:
   - **Đang chạy**;
   - **Chờ bạn trả lời**, **Chờ bạn duyệt**, **Đã dừng, chờ bạn**;
   - **Hoàn tất, đã học** (`run_finished.status == "completed"` và có `learning_saved`);
   - **Đã đóng bởi người** (`closed`);
   - **Không có bất thường** (`no_anomaly`);
   - **Lỗi**.
2. Khi lỗi: thông điệp ngắn (dòng đầu của `error`, không in traceback). Nút **Thử lại** chỉ hiện khi `retryable == true`.
3. Sau Thử lại, timeline **tiếp tục nhận event mới** (không đóng hẳn SSE khi gặp `run_finished` có `status == "error"`; mở lại luồng với `after=<id cuối>`). Có test.

### FR-05 Câu hỏi của agent (màn S4) [M]
**Dữ liệu:** `pending.type == "answer"` {question}; event `question_asked` {attempt, max_questions}.

**Tiêu chí chấp nhận:** hiện câu hỏi nổi bật; dòng "Lần hỏi 1/2"; ô trả lời nhiều dòng, nút Gửi khoá khi trống. Màn này dùng chung cho câu hỏi "chưa đủ bằng chứng" ở bước đo.

### FR-06 Rollback và dừng chờ người (S7) [S]
**Tiêu chí chấp nhận:**
1. `kind == "rollback"`:
   - tiêu đề "KPI không đạt, đề xuất quay về SOP trước";
   - số đo trước/sau so với mục tiêu;
   - SOP đang hiệu lực → bản sẽ khôi phục;
   - nút **Xác nhận rollback** / **Giữ SOP hiện tại**.
2. `kind == "halt"`:
   - lý do dễ hiểu theo `reason`:

     | `reason` | Hiển thị |
     |---|---|
     | `max_questions_reached` | Đã hỏi đủ số lần |
     | `insufficient_evidence` | Chưa đủ bằng chứng |
     | `rollback_declined` | Bạn đã giữ SOP hiện tại |
     | `max_rollbacks_reached` | Đã rollback tối đa |
     | `max_rejections_reached` | Đã từ chối tối đa |

   - nếu `sop_still_in_force` thì ghi rõ SOP nào đang hiệu lực;
   - nút lấy từ `options` (`investigate` → "Điều tra lại", `finish` → "Kết thúc").
3. Test với `run-rollback.json`, `run-rollback-declined.json`, `run-halt-max-questions.json`.

### FR-07 Chế độ phát lại (dự phòng sân khấu) [S]
**Tiêu chí chấp nhận:**
- `?source=fixture&file=<tên>` phát lại một file trong `docs/schema/examples/` (hoặc bản ghi T-041), với tốc độ chỉnh được (1×, 2×);
- các màn giống hệt chế độ live, nút thao tác ở trạng thái mô phỏng;
- dùng được khi không có backend.

### FR-08 Vòng lặp 8 bước (S1) [S]
Thanh hoặc vòng 8 bước luôn hiện ở đầu trang. Bước hiện tại sáng lên theo event mới nhất. Bảng ánh xạ event → bước để trong một file hằng số.

### FR-09 Tổng quan KPI (S2) [C]: chờ API
Biểu đồ đường KPI theo thời gian, có baseline, giới hạn trên, và vùng anomaly tô màu. Cần `GET /kpi/series` (backend R10). Trước khi có API, dùng dữ liệu mock trong fixture. **Cắt đầu tiên nếu thiếu giờ** (PLAN mục 7).

### FR-10 Phiếu kaizen và 3 chỉ số (S9) [S]: chờ API
- **Phiếu kaizen / A3** từ `learning_saved.content`: vấn đề, nguyên nhân, biện pháp, KPI trước/sau, SOP bản mới, `outcome`.
- **3 chỉ số** từ `GET /metrics` (R10): tỷ lệ lỗi, MTTD/MTTR, tỷ lệ tái diễn, trước/sau.

### FR-11 Nhật ký và phiên bản SOP (S8) [C]: chờ API
Bảng chỉ đọc "ai duyệt gì, lúc nào" và lịch sử phiên bản SOP, có nút xem nội dung từng bản. Cần `GET /audit`, `GET /sop/{id}/versions`.

### FR-12 Danh sách run [C]: chờ API
Chọn lại run đã chạy (`GET /runs`). run id nằm trên URL để tải lại trang không mất run.

## 6. Yêu cầu phi chức năng

| Mã | Yêu cầu | Kiểm |
|---|---|---|
| NFR-1 | Màn chiếu 1920×1080: chữ thân ≥ 18px, tiêu đề ≥ 28px, tương phản AA | Diễn tập trên máy chiếu |
| NFR-2 | Màu có nghĩa thống nhất: xanh = đạt/an toàn, đỏ cam = bất thường/chưa đạt, vàng = chờ người, xám = đang chạy | Rà soát |
| NFR-3 | Chuỗi hiển thị tách ra một file (`dashboard/lib/strings.ts`); mặc định tiếng Việt; thêm tiếng Nhật/Anh sau mà không sửa component | Code review |
| NFR-4 | Phản hồi thao tác < 200 ms (khoá nút, spinner); không màn trắng > 2 s khi chờ LLM | Thử tay |
| NFR-5 | Không lỗi console; `yarn lint`, `yarn test`, `yarn build` sạch | CI / verify |
| NFR-6 | Payload lạ hoặc thiếu trường không làm sập trang (hiện "không có dữ liệu", ghi console.warn) | Test với payload cắt trường |
| NFR-7 | Không hiện dữ liệu nội bộ simulator (`sop_applied.sim`), không hiện traceback | Rà soát |

## 7. Dữ liệu và API: có gì, khi nào

| API / dữ liệu | Có chưa | Dùng cho |
|---|---|---|
| `POST /runs`, `GET /runs/{id}`, SSE `/runs/{id}/events`, `POST /answer`, `/approval`, `/retry`, `GET /config/approvers` | **Có** | FR-01..06 |
| 8 fixture nhánh `docs/schema/examples/` | **Có** (sinh bằng `scripts/export_fixtures.py`) | Test mọi FR, FR-07 |
| `GET /kpi/series`, `GET /metrics`, `GET /audit`, `GET /sop/{id}/versions`, `GET /runs` | **Chưa** (backend R10, dự kiến [13–15/10]) | FR-09..12 |

Chưa có API thì làm giao diện với dữ liệu mock **đúng hình dạng** mô tả trong `docs/demo-storyboard.md` mục 3. Hình dạng chốt cuối sẽ ghi vào `payloads.md`.

## 8. Định nghĩa "xong" (Definition of Done) cho mỗi FR

- Đạt mọi tiêu chí chấp nhận.
- Có test vitest dùng **fixture thật** từ `docs/schema/examples/`, không tự viết payload giả nếu fixture đã có.
- `yarn lint && yarn test && yarn build` sạch. Chạy `python3 .autodev/verify.py` ở gốc repo, phần `dashboard` phải sạch.
- PR có **ảnh chụp màn hình** (1920×1080) cho mỗi trạng thái chính.
- Thử tay một lần với `bash scripts/demo.sh` (LLM giả).

## 9. Mốc (tham khảo; leader chốt ngày khi kickoff)

| Đợt | Hạn đề xuất | Nội dung |
|---|---|---|
| Đợt 1 | **[13/10]** v0.1-e2e | FR-01, FR-02, FR-03, FR-04, FR-05 (các Must) |
| Đợt 2 | **[17/10]** | FR-06, FR-07, FR-08, FR-10 (phần phiếu kaizen) |
| Đợt 3 | **[20/10]** freeze | FR-10 (chỉ số), FR-09/11/12 nếu kịp |
| Sau freeze | đến Demo Day 07/11 | Chỉ sửa lỗi và đánh bóng theo góp ý Pitch Day; không thêm tính năng |

## 10. Cách làm việc

- Nhánh `feat/ui-<fr>` (ví dụ `feat/ui-fr01-approval`). Mỗi FR một PR, gắn leader review (trong 12 giờ).
- Sync 15 phút mỗi ngày. Vướng API thì mở issue với nhãn `api`; backend trả lời trong ngày.
- Đổi `lib/*` dùng chung thì ghi rõ trong mô tả PR.
- Không commit API key; không đọc `.env` của người khác; không dùng dữ liệu thật.

## 11. Câu hỏi mở (trả lời khi kickoff)

1. Ngôn ngữ hiển thị khi demo ở Việt Nam / Nhật: tiếng Việt, tiếng Nhật hay song ngữ?
2. Có dùng thư viện UI (Tailwind, shadcn) hay giữ CSS thuần? Gợi ý: Tailwind cho nhanh, miễn là build sạch.
3. Biểu đồ: tự vẽ SVG hay dùng thư viện nhẹ (Recharts)?

## 12. Lịch sử thay đổi yêu cầu
- v1 (2026-10-10): bản đầu.

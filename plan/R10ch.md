# R10ch (sửa nhanh sau audit 3): SOP không mất, run không kẹt, A5 đo được thật

**Phục vụ plugin: P6** (pre-mortem "đạt theo cấu tạo" do audit 3 phát hiện ở H-54; B3). Mốc sửa nhanh: tên kết thúc bằng `h`, không tính vào `--audit-every`.

**Mục tiêu dự án:** trước tag v0.1-e2e (13/10), đóng các lỗ hổng audit 3 (`docs/audits/2026-10-10.md`) làm demo hỏng hoặc làm số đo sai, không chờ D1:
- H-45 (cao) + H-31: bản SOP do Act/rollback ghi phải còn khi bước sau lỗi;
- H-48: `change_time` sai bị từ chối lúc bắt đầu, có đường đóng run lỗi;
- H-47, H-50, H-51: khôi phục run sau restart không kẹt, không đặt lại giới hạn retry, không chặn khởi động;
- H-54: A5(b) đọc `kpi_measured.passed` và có đối chứng, để chỉ số đổi được khi agent sai (luật `criteria.md`: phần đạt theo cấu tạo tính 0).

## Phạm vi
- **Trong:** `backend/agent/nodes/act.py`, `backend/tools/actions.py`, `backend/db/repo.py`, `backend/api/app.py`, `backend/sandbox/post_change.py` (chỉ phần đối chứng), `docs/schema/payloads.md`, `tests/` (gồm mở rộng `tests/test_invariants.py`, `tests/test_persist_r10c.py`, `tests/test_demo_llm_branches_r10a.py`).
- **Ngoài:**
  - H-49 (`question_id` bắt buộc): cần dashboard gửi trường này, giao vai D;
  - H-46, H-35, H-44 (UI, vai D);
  - H-11, H-33, H-39 và chỉ số 3 (R10b2); H-52, H-53, H-55, H-56 (R11a);
  - `events.json`, phần trình bày `dashboard/`.

## Quy ước chung
- TDD: mỗi lỗ hổng có test tái hiện đúng bước "Tái hiện" của audit 3, đỏ trên main trước khi sửa.
- Không gọi LLM thật. Không đổi body request hiện có theo cách làm vỡ dashboard (chỉ thêm).
- Endpoint mới không được áp dụng hay rollback SOP, không thay người duyệt.

## Ước tính
| Số task | Phút (worker) | USD (worker + supervisor) | Số vòng review |
|---|---|---|---|
| 4 | 40–60 | 3–4 | 4–5 |

Chỉ số đẩy: A5 (đo lại theo cách không đạt theo cấu tạo). Sau mốc: `python3 .autodev/metrics.py --write`; supervisor ghi A5 mới vào báo cáo mốc và PROJECT_STATE theo luật chỉ số nhiều phần.

## Pre-mortem: đạt trên giấy mà hỏng thực tế thế nào?
1. **Commit sớm làm lệch trạng thái:** SOP được commit nhưng dòng audit hoặc checkpoint thì không, hoặc ngược lại. → dev-01 tiêu chí 2 (đọc bằng session khác sau lỗi ở từng điểm: sau Act, sau rollback).
2. **Đường đóng run thành cửa sau:** endpoint đóng run dùng để bỏ qua bước duyệt hoặc làm mất rollback đang chờ. → dev-02 tiêu chí 3.
3. **Khôi phục sửa đúng một trường hợp:** run kẹt giữa bước được đánh dấu lỗi, nhưng run đang chờ người lại bị đánh dấu nhầm. → dev-03 tiêu chí 1 kiểm cả hai.
4. **A5 sửa xong vẫn tự đúng:** LLM giả luôn sai mà A5(b) vẫn 1,0, hoặc đối chứng "không áp dụng gì" vẫn làm KPI cải thiện. → dev-04 tiêu chí 1–2; tiêu chí cấp mốc 3.

## Tiêu chí chấp nhận cấp mốc
1. `python3 .autodev/verify.py` và `python3 .autodev/verify.py --smoke` sạch.
2. Các bước "Tái hiện" của H-45, H-47, H-48, H-50, H-51 trong `docs/audits/2026-10-10.md` (qua TestClient hoặc uvicorn thật khi audit dùng uvicorn) không còn tái hiện được.
3. A5 đo lại trên 5 seed LLM giả: LLM đúng → (a) = 1,0, (b) ≥ 0,8; LLM luôn sai → (b) = 0; không áp dụng gì → KPI không đổi (không `passed`). Supervisor tự chạy và ghi 3 con số này.

## Task

### dev-01: Bản SOP của Act và rollback không mất khi bước sau lỗi (H-45, H-31)
- **Mô tả:** bản SOP do `apply_sop` và rollback tạo ra được commit (cùng dòng audit của nó) trước khi checkpoint ghi `applied` / `rollback_done`, để lỗi ở Measure, Investigate kế tiếp hoặc tiến trình bị kill không xoá bản đó. Retry sau lỗi không tạo bản trùng.
- **Tiêu chí chấp nhận:**
  1. Test tái hiện H-45: lỗi trước lần commit đầu của Measure, rồi `/retry` → bản SOP có trong `sop_versions` (đọc bằng session khác); lesson không ghi `success` cho bản không tồn tại. Đỏ trên main.
  2. Test H-31: lỗi LLM ở lần gọi đầu sau rollback → nội dung SOP hiệu lực là bản đã khôi phục. Đỏ trên main.
  3. Thêm vào `tests/test_invariants.py`: sau mỗi `sop_applied` / `rollback_done(rolled_back=true)`, `(sop_id, version)` trong event có trong `sop_versions` đọc bằng session khác, kể cả nhánh có lỗi sau Act.
- **Phụ thuộc:** không
- **Trạng thái:** DONE · **Số vòng:** 1

### dev-02: Kiểm `change_time` lúc bắt đầu; đóng run lỗi (H-48)
- **Mô tả:** `POST /runs` kiểm `change_time` trước khi gọi LLM: sai định dạng, có múi giờ không chuẩn hoá được, ở tương lai, hoặc trước anomaly → 422. Thêm `POST /runs/{id}/close` (lý do bắt buộc, người đóng thuộc danh sách người duyệt) cho run ở trạng thái `error` không retry được: ghi audit, phát `run_finished` với trạng thái đóng bởi người. Cập nhật `payloads.md`.
- **Tiêu chí chấp nhận:**
  1. Test: `change_time` có `Z`, tương lai, trước anomaly, `"abc"` → 422 ngay, LLM giả không được gọi lần nào.
  2. Test: run `error` hết lượt retry → `close` → `run_finished` đóng bởi người, có một dòng audit.
  3. Test: `close` trên run đang chờ duyệt hoặc chờ rollback → 409; `close` không tạo hay khôi phục bản SOP nào.
- **Phụ thuộc:** không
- **Trạng thái:** TODO · **Số vòng:** 0

### dev-03: Khôi phục run sau restart không kẹt (H-47, H-50, H-51)
- **Mô tả:** khi app khởi động và nạp run từ DB:
  - run chưa kết thúc mà không ở interrupt (bị kill giữa bước) → đánh dấu `error` retryable, `/retry` chạy tiếp từ checkpoint;
  - số lần retry được lưu, không về 0 sau restart;
  - dựng LLM/ToolContext lỗi cho một run → chỉ run đó thành `error` (kèm lý do), app vẫn khởi động, run khác và `GET /runs`, `/events`, `/export` của run đã xong vẫn đọc được.
- **Tiêu chí chấp nhận:**
  1. Test: run bị dừng giữa bước → sau restart `state=error`, `retryable=true`, `/retry` đi tiếp; run đang ở interrupt → sau restart vẫn đúng `pending` như trước.
  2. Test: run hết lượt retry → restart → `/retry` 409 và `retryable=false` khớp nhau.
  3. Test: `llm_factory` ném lỗi khi khôi phục → app lên, `GET /runs` 200, run lỗi có lý do, run khác đọc được.
- **Phụ thuộc:** không
- **Trạng thái:** TODO · **Số vòng:** 0

### dev-04: A5 đo được thật, có đối chứng (H-54)
- **Mô tả:** phép đo A5 trong `tests/test_demo_llm_branches_r10a.py` (và hàm in chỉ số nếu có): (b) = tỷ lệ run có `kpi_measured.passed == true` ở lần Measure cuối, không đếm `learning_saved`. Thêm đối chứng: không áp dụng `action` nào thì KPI sau thay đổi không cải thiện (Measure không `passed`); LLM giả luôn đề xuất `action` sai thì (b) = 0. Không đổi công thức sinh anomaly; nếu dữ liệu sau thay đổi cần sửa để đối chứng đúng thì chỉ sửa ở `post_change`.
- **Tiêu chí chấp nhận:**
  1. Test in và kiểm: LLM đúng → (a) = 1,0, (b) ≥ 0,8; LLM luôn sai → (b) = 0. Đỏ trên main ở phần LLM luôn sai hoặc đối chứng.
  2. Test đối chứng "không áp dụng gì" → `passed` không bao giờ true trên 5 seed.
  3. Seed thay đổi dữ liệu thật (kết quả KPI khác nhau giữa các seed), in ra để chứng minh.
- **Phụ thuộc:** dev-01
- **Trạng thái:** TODO · **Số vòng:** 0

## Ghi chú điều chỉnh (Claude ghi khi làm (a)/(b))

## Đề xuất chờ duyệt

# Bộ thử reviewer (đề xuất 4): thiết kế và plan

Leader duyệt thiết kế ngày 2026-10-10. Nguồn: đề xuất 4 trong `2026-10-10-so-sanh-ben-ngoai.md`.

## Mục đích
Đo **recall** của reviewer: trên các lỗi đã có đáp án, reviewer bắt được bao nhiêu %. Số đo này thay cho phỏng đoán khi đổi prompt hay model:
- #104 (4 câu hỏi bắt buộc) có giúp không;
- có nên dùng Opus (đề xuất 2) không;
- có nên review 3 lần (đề xuất 5) không.

Đo thêm **bắt nhầm**: ca sạch mà reviewer FAIL.

## Ràng buộc
- Tổng 15–20 USD; hỏi leader trước **mỗi** lượt đo.
- Không đụng code dự án; chỉ chạy khi runner rảnh (dùng chung Postgres).
- Không xoá worktree hay file kết quả nếu chưa được duyệt.

## Cách làm
- **Ca thử** (`.autodev/bench/cases.json`):
  - Mỗi ca là một task cũ đã PASS nhưng sau đó audit tìm ra lỗi H-xx.
  - `base..head` là khoảng commit reviewer đã thấy lúc đó: `base` là cha của commit `feat`, `head` là commit `feat`.
  - Đáp án gồm `files` (file chứa lỗi) và `keywords` (regex mô tả cơ chế lỗi).
  - Ca sạch có `hole: null`.
- **Cấu hình:**
  - `old` là `reviewer.md` trước #104 (`git show 79f0970:.claude/agents/reviewer.md`);
  - `new` là `reviewer.md` hiện tại;
  - cả hai dùng Sonnet.
  - Có thể thêm cấu hình khác (model, số lần chạy) mà không đổi script.
- **Chạy:**
  - Một worktree cố định `../sme-ci-agent-bench`, mỗi ca `git checkout -f --detach <head>`.
  - Gọi `claude -p` headless, dùng cùng các cờ như `run.py` (`--output-format json`, `--permission-mode auto`, `--permission-prompts none`), chỉ cho phép `Read,Grep,Glob,Bash`.
  - Prompt là thân `reviewer.md` của cấu hình (bỏ frontmatter) cộng đầu vào của ca (task_id, `base..HEAD`, plan).
  - Chạy tuần tự.
- **Chấm:**
  - Ca lỗi tính là *bắt được* khi `status = FAIL` và có blocking issue thoả cả hai điều: (1) `file` hoặc mô tả trúng một file đáp án, (2) mô tả hoặc `required_action` khớp `keywords`.
  - Ca sạch bị FAIL thì tính là *bắt nhầm*.
  - Output không có JSON hợp lệ thì tính là *lỗi chạy*, không tính vào recall.
- **Đầu ra:**
  - `.autodev/runs/bench/<stamp>.json`, không commit; gồm từng lượt: ca, cấu hình, USD, phút, JSON reviewer, điểm.
  - Bảng tóm tắt ghi vào mục "Kết quả" dưới đây.

## Pilot (leader chọn: 4 ca × 2 cấu hình, khoảng 4 USD)
| Ca | Task | Lỗi | Họ lỗi |
|---|---|---|---|
| p1 | R10a/dev-02 `5534331..f736861` | H-57 `/kpi/series` 500 với múi giờ | test chỉ qua TestClient |
| p2 | R10c/dev-02 `7864ed3..64a729c` | H-50 `retries` về 0 sau restart | kill/restart |
| p3 | R10c/dev-05 `aa02c58..97c4805` | H-49 `question_id` tuỳ chọn nên H-20 vô hiệu | đạt trên giấy / xuyên file |
| p4 | R10a/dev-03 `a00a387..becbd39` | (sạch) | bắt nhầm |

Pilot có n = 4 nên chỉ dùng để kiểm bộ thử chạy đúng. Muốn kết luận "#104 có giúp" thì cần lượt lớn hơn khoảng 10 ca lỗi. Tôi đọc lại 8 output để kiểm cách chấm tự động.

## Plan
1. Viết test trước: `.autodev/tests/test_bench_reviewer.py` gồm nạp ca, bỏ frontmatter, dựng prompt và lệnh, tách JSON từ output, chấm ca lỗi và ca sạch, tóm tắt.
2. Viết `.autodev/bench_reviewer.py` (chỉ dùng stdlib), có 3 lệnh:
   - `run --cases p1,p2 --configs old,new [--dry-run]`: `--dry-run` chỉ in lệnh và ước chi phí;
   - `score <file>`: chấm lại một file kết quả;
   - `summary <file>`: in bảng tóm tắt.
3. Viết `cases.json` cho 4 ca pilot; chạy thử `--dry-run`.
4. Hỏi leader trước khi chạy pilot thật (khoảng 4 USD, khoảng 1 giờ chạy nền), rồi ghi kết quả vào mục dưới.

## Kết quả
(chưa chạy)

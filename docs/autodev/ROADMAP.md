# Lộ trình plugin auto-dev (plan lớn)

Mục tiêu chính: xây và hoàn thiện plugin auto-dev (thiết kế: `auto-dev-review-design.md`). SME CI Agent là dự án chạy thử.

## Nguyên tắc ưu tiên (người dùng chốt 2026-10-07)
1. **Ưu tiên auto-dev.** Chọn mốc dự án sao cho thử được tính năng plugin còn thiếu.
2. **Không làm sai mục tiêu của SME CI Agent.** Mỗi mốc dự án vẫn phải đúng TASKS.md, docs/PLAN.md, CLAUDE.md và DoD của task; chất lượng không được sơ sài vì là "mốc thử". SME CI Agent chạy tốt thì mới chứng minh được auto-dev hiệu quả.
3. Thử nghiệm không được đổi phạm vi hay mục tiêu của dự án; nếu một tính năng plugin cần điều kiện mà dự án không có, ghi thành câu hỏi cho người dùng thay vì bẻ dự án theo plugin.

## Tách hai luồng
| | Plan lớn (plugin) | Plan nhỏ (SME CI Agent) |
|---|---|---|
| File | `docs/autodev/` (ROADMAP, PROGRESS, HANDOFF, thiết kế) | `plan/Mx.md`, `plan/PROGRESS.md`, TASKS.md |
| Ai sửa | supervisor | worker (developer, reviewer, `/run-milestone`) |
| File code | `.claude/`, `.autodev/*.py`, `.autodev/config.json` | code dự án, `.autodev/state.json`, `reviews/`, `reports/` |
| Nhánh | `chore/autodev-*` | `milestone/*` |

Hai luồng không sửa chung file nên chạy song song không xung đột. Liên kết: mỗi mốc plugin dưới đây ghi mốc dự án dùng để thử; mỗi `plan/Mx.md` ghi dòng "Phục vụ plugin: Px".

## Quy ước tên mốc
- Mốc **plugin**: P1, P2… (file này).
- Mốc **auto-dev chạy trên dự án** (`plan/`): từ 2026-10-08 đặt tên **R4, R5…** (R = run) để không trùng với mốc M0–M4 trong TASKS.md của team. Các mốc đã chạy trước đó giữ tên cũ: `plan/M1.md`, `M2.md`, `M3.md`.
- Nhánh: `milestone/R4`… Mỗi `plan/Rx.md` ghi mã T-0xx của TASKS.md.

## Các mốc plugin

| Mốc | Tính năng cần chứng minh | Thử qua | Trạng thái |
|---|---|---|---|
| P1 | Chế độ A: developer ⇄ reviewer, verify + baseline, guard, plan Mx/dev-xx | plan/M1.md | ✅ Xong (2026-10-06); phát hiện reviewer bỏ sót trường hợp biên → sửa prompt |
| P2 | Vòng FAIL → REWORK, hook `SubagentStop` chạy thật, task phụ thuộc nhau | plan/M2.md | ✅ Xong (2026-10-07) |
| P3 | Supervisor (vai con người) tự giao mốc, duyệt, merge; worker headless (`claude -p`) mỗi mốc một phiên mới; verify khi test cần Postgres; HANDOFF giữa các phiên supervisor | plan/M3.md | ✅ Xong (2026-10-08): worker headless chạy trọn mốc, supervisor duyệt + merge PR #14; cổng verify có biến môi trường riêng từng máy (`.autodev/env.local.json`, `DB_PORT`) |
| P4 | Chế độ B: script `autodev-run.sh` chạy nhiều mốc liên tiếp (supervisor headless + worker headless). Xử lý hết hạn mức: (1) nhận biết từ kết quả JSON / sự kiện `api_retry` (`rate_limit`), lấy giờ reset; (2) chờ đến giờ reset + 5 phút; (3) chạy lại `/run-milestone` bằng phiên mới, tiếp tục từ `state.json` (giữa vòng review thì chỉ chạy lại reviewer); (4) hết hạn mức tuần thì dừng, ghi HANDOFF, báo người dùng. Tự ghi `total_cost_usd` mỗi mốc và quy đổi ra % hạn mức; kiểm tra ngân sách trước khi bắt đầu mốc; thông báo một chiều (Q1) | plan/R4.md + plan/R5.md (chạy nối tiếp) | 🔄 Đang làm: `.autodev/run.py` + `.autodev/autodev-run.sh` đã viết, 10 test với `claude` giả (hết hạn mức → chờ → chạy lại; hết hạn mức tuần → dừng; lỗi → thử lại 1 lần). Chạy thật lần đầu: R4 xong (merge #19, ~18 phút, 4 task PASS); lần đầu no-op do worktree chưa cập nhật (runner cần sửa). R5 xong (merge #21, 3 task PASS, 1 vòng REWORK). Hai mốc liền nhau 40 phút, 5,29 USD, không chạm hạn mức. Có `.autodev/watch.sh` để xem tiến độ; guard xét đúng thư mục đích của `cd`/`git -C`. Runner đã sửa (worktree về `origin/main`, no-op → exit 4, thông báo macOS khi dừng/xong). Nhánh chờ reset đã kiểm chứng thật ở R9 (2026-10-09 02:15: session limit → chờ 59 phút → chạy tiếp, merge #44). Còn: hạn mức tuần. R6 (dashboard T-016/T-026) cũng chạy xong qua chế độ B (merge #27, ~20 phút). R7 (M3 end-to-end) xong (merge #31, ~36 phút). R8 (mạch chặt, supervisor Opus + smoke bắt buộc) xong (merge #37, ~67 phút, 5 task PASS vòng 1). |
| P5 | Chống mất tầm nhìn: lệnh `/audit` (chỉ đọc, 3 agent `Explore` song song: logic + quy tắc CLAUDE.md, API ↔ dashboard ↔ `events.json`, độ khớp mục tiêu) ghi `docs/audits/<ngày>.md`, lỗ hổng mã H-xx mở đến khi có test; runner `--audit-every 2`; `PROJECT_STATE.md` + `state.json` (agent đọc trước plan mốc); `LESSONS.md`; guard chặn `sed -i` / `python - <<`; trang trạng thái Artifact (riêng tư, xem trên điện thoại) | audit đầu trên R7 + R8 | 🔄 Đang làm: `/audit`, PROJECT_STATE, guard sed/stdin xong (PR #40); R9 là mốc đầu chạy với PROJECT_STATE (merge #44). Còn: audit 2 sau R10 (`--audit-every 2`), trang trạng thái Artifact |
| P6 | Lập kế hoạch dài hạn ("cuốn chiếu có tầm nhìn"): bảng 3–5 mốc tới v0.1-e2e và freeze (đường găng, thứ tự cắt theo PLAN mục 7), pre-mortem mỗi mốc ("đạt trên giấy mà hỏng thực tế thế nào?"), đối chiếu ước tính với thực tế (thời gian, chi phí, số vòng, lỗ hổng audit). Người dùng duyệt thứ tự và việc cắt | R9, R10 | ⏳ |
| P7 | Telegram hai chiều (4 mức: xem / nhận / trả lời / điều khiển có xác nhận; không xoá, không merge tay, không lệnh tự do; bot long-polling trên Mac, chỉ nhận `chat_id` của người dùng) + API trạng thái + dashboard theo dõi plugin (dùng chung API) | sau v0.1-e2e | ⏳ |
| P8 | Đóng gói plugin: tách sang repo riêng, `plugin.json`, cài bằng marketplace, UI deploy được, onboarding dự án thứ hai | dự án thứ hai | ⏳ |

## Để sau (người dùng chốt 2026-10-08)
- Đo độ dài phiên: ghi `num_turns`, token, thời gian của mỗi phiên headless vào PROGRESS; ngưỡng cảnh báo mốc quá to.
- Đo chất lượng theo thời gian: số vòng review, số lần verify chặn, lỗi tìm ra sau merge.
- Hook trước khi Claude Code nén ngữ cảnh (cần kiểm chứng tên và cú pháp) để nhắc cập nhật HANDOFF và mở phiên mới.

### Thông báo khi runner dừng hoặc xong (người dùng nêu 2026-10-08)
- **Máy tính (đã có, đang tắt):** thông báo macOS có tiếng trong `.autodev/run.py`, bật bằng `AUTODEV_NOTIFY=1 .autodev/autodev-run.sh R6`. Mặc định tắt theo yêu cầu người dùng.
- **Điện thoại (chưa làm). Người dùng chọn Telegram (2026-10-08):** tạo bot qua @BotFather, lấy `chat_id` của người dùng, runner gửi bằng một lệnh POST tới Bot API (`sendMessage`), chỉ dùng thư viện chuẩn. Token và `chat_id` lưu ở file cục bộ không commit (ví dụ `.autodev/env.local.json`), bật bằng biến môi trường giống `AUTODEV_NOTIFY`. Nội dung chỉ gồm mốc, trạng thái, chi phí, không gửi code hay log dài.
- Các lựa chọn khác (dự phòng):
  - ntfy.sh: miễn phí, có app iOS/Android, runner chỉ cần một lệnh POST HTTP. Tên topic phải ngẫu nhiên vì ai đoán được tên đều đọc được; không gửi nội dung nhạy cảm.
  - Pushover: trả phí một lần, ổn định.
  - App Claude trên điện thoại: chỉ báo cho phiên Claude Code (Remote Control), không báo cho tiến trình `claude -p` của runner; cần kiểm chứng trước khi dùng.

### Giao diện xem `claude -p` đang làm gì (người dùng nêu 2026-10-08)
- Đã có: `.autodev/watch.sh` (terminal, chỉ đọc): runner còn chạy không, `run.log`, commit và file đang đổi ở từng worktree, transcript cập nhật bao lâu trước, số lệnh tool, tool gần nhất.
- Dashboard web cục bộ, chỉ đọc (đề xuất làm trước): server Python nhỏ, không thư viện ngoài, mở trong Simple Browser của VS Code. Đọc transcript `~/.claude/projects/<worktree>/*.jsonl` (cả của sub-agent), `run.log`, `.autodev/state.json`, `runs/*.json`, git log.
- Có thể chuyển runner sang `--output-format stream-json` để có luồng sự kiện đầy đủ, ghi ra file, dashboard đọc trực tiếp.
- Chức năng có thể thêm:
  - dòng thời gian mốc: worker → developer/reviewer từng dev-xx (PASS/FAIL, số vòng) → supervisor → merge;
  - luồng sự kiện trực tiếp: tool đang chạy, file đang sửa, lệnh bị guard chặn, verify đạt/trượt;
  - "còn sống": cảnh báo khi transcript không cập nhật quá N phút;
  - chi phí và hạn mức cộng dồn mỗi mốc, so với các mốc trước;
  - lịch sử các lần chạy (đọc `runs/*.json`), mở nhanh PR và báo cáo mốc;
  - nút thao tác (dừng runner, chạy mốc kế): để sau cùng, vì cần guard và xác nhận của người dùng.
- Xa hơn: extension VS Code (webview) hoặc statusline của Claude Code hiện một dòng tiến độ.

## Tiêu chí "plugin đạt" cho từng mốc
- Không cần người dùng chuyển tin giữa các phiên trong suốt một mốc.
- Lỗi người dùng phát hiện sau khi mốc đã merge: 0, hoặc mỗi lỗi dẫn tới một sửa đổi prompt/gate.
- Hạn mức mỗi mốc được ghi lại trong `PROGRESS.md`.

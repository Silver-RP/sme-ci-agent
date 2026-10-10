# Bàn giao giữa các phiên supervisor

Mở phiên: `/session-start`. Đóng phiên: `/session-end` (cập nhật file này, PROJECT_STATE, bộ nhớ; PR + merge). Supervisor cũng cập nhật file này ở cuối mỗi mốc. Phiên supervisor mới đọc file này trước tiên, rồi `PROJECT_STATE.md`, `ROADMAP.md`, `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- **Hai plan lồng nhau:**
  - **Plan lớn** là xây plugin auto-dev (`docs/autodev/`, mốc **P1–P9**).
  - **Plan nhỏ** là dự án SME CI Agent (`TASKS.md` và `docs/PLAN.md`, mốc dự án **M0–M4**).
  - Mỗi **lần chạy auto-dev** là một mốc **R** (`plan/R4.md`…`plan/R10ch.md`): worker làm vài task TASKS.md, đồng thời kiểm chứng một khả năng của plugin. Mốc tên kết thúc bằng `h` là sửa nhanh, không tính vào `--audit-every`.
  - Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD.
- **Phiên supervisor đóng vai leader kỹ thuật kiêm BA:**
  - lập plan, giao mốc, duyệt, merge, sửa plugin;
  - viết brief và issue cho team.

  Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15, `.claude/commands/supervise.md`.
- **Người dùng:** leader, nói tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa, báo ngắn gọn, giải thích khi hỏi "tại sao" hay "là gì". Cuối mỗi báo cáo có câu hỏi "làm gì tiếp": danh sách **đánh số kèm nội dung**, leader trả lời bằng số.
- **Đo bằng số, không ước lượng:** % đạt 3 điều tính theo `docs/eval/criteria.md` (A1–A8, luật chỉ số nhiều phần); chỉ số plugin B1–B6 bằng `python3 .autodev/metrics.py`.

## Bước tiếp theo (cập nhật 2026-10-11 rạng sáng, đóng phiên)

### Bối cảnh
- **Team 4 người** (`docs/PLAN.md` mục 4). Ranh giới: auto-dev không làm thay việc của vai A/D/Q, kể cả khi không đụng file của họ (**trùng việc** khác **trùng file**).

| Vai | Người | Issue | Trạng thái 10/10 tối |
|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63, #66 (D1) | đã nhận lời mời, đã gán; chưa có commit/PR. D1 hạn [12/10] đang chặn R10b1 |
| D: giao diện | @Finnng1104 (Finn) | #64, #67 (H-44), #89 (H-46, sev:1), #90 (H-49) | đã nhận lời mời, đã gán tay (workflow `auto-assign` không chạy theo lịch lần nào) |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | **chưa nhận lời mời**; #65 chưa gán |
| Backend, auto-dev | leader + Claude | | `plan/Rx.md` |

- **Mốc tham khảo:** kickoff 11/10 (giờ chưa chốt); cổng go/no-go + tag v0.1-e2e 13/10; Đợt 2 UI 17/10; freeze 20/10; Pitch 24/10.
- **Kế hoạch P6 hai luồng** (dự án + plugin) đã duyệt: `ROADMAP.md` mục "Kế hoạch hai luồng"; bảng mốc ở PROJECT_STATE mục "Tầm nhìn".

### Đã xong trong phiên 2026-10-10 khuya → 11/10 rạng sáng (PR #103–#108, đều merge; chỉ plugin, không đụng code dự án)
- **Hạn mức (#103):**
  - `usage.py` báo tuổi số liệu; lệnh mới `show [--last N]`;
  - `/session-start` in dòng hạn mức.
  - Status line không chạy trong VS Code, nên số liệu cũ thì hỏi leader `/usage`. Leader dán số dạng "32(5h)/63w"; Claude ghi vào `~/.claude/usage-latest.json` (`five_hour`, `seven_day`, `at` = bây giờ).
- **Đề xuất 1 + 3 (#104):**
  - Cổng `test_guard` trong `verify.py`: chặn khi xoá file/hàm test, thêm `skip`/`xfail`/`.only`, hay giảm tổng số assert so với merge-base trên main.
  - Developer giải trình bằng dòng `allow-test-change: <test> <lý do>` trong commit: không bị chặn, nhưng reviewer phải xét lý do. Dòng đó nằm trong `plan/` trên main thì miễn hẳn.
  - Vì sao có đường giải trình: chạy thử trên 12 PR mốc cũ thì 5 bị gắn cờ, cả 5 đều là đổi hành vi hợp lệ.
  - `reviewer.md` bước 8: 4 câu hỏi bắt buộc, trả lời ở trường `risk_checks`.
- **Đề xuất 4, bộ thử reviewer (#105–#108):**
  - `.autodev/bench_reviewer.py`; 11 ca trong `.autodev/bench/cases.json` (9 lỗi đã lọt + 2 sạch), tách `dev` (p2, p3) và `holdout`.
  - Kết quả và cách đọc: `docs/autodev/research/2026-10-10-bo-thu-reviewer.md`. Tổng 6,60 USD.
  - Reviewer hiện tại **chặn 2/9**, **thấy 5/9** (đọc tay), bắt nhầm 0/3. Tức là reviewer thấy lỗi nhưng xếp nhẹ ("hướng an toàn", "chấp nhận được").
  - Bản sửa (a)(d) (`new2`, `.autodev/bench/reviewer-candidate.md`) không cải thiện trên holdout, nên **không** đưa vào `reviewer.md` (luật leader đặt trước khi đo).
  - Nhiễu giữa các lần chạy lớn: muốn kết luận thì cần ≥ 3 lần mỗi ca.
- **Hạn mức lúc đóng phiên** (leader dán khoảng 23:00 10/10): 5 giờ 32%, tuần 63% (reset 13:00 14/10).

### ⏸ Tạm dừng việc dự án (leader quyết 2026-10-10 đêm)
Backend/auto-dev của dự án **dừng để chờ team**; phiên hiện tại chuyển sang nghiên cứu auto-dev (plugin). Không chạy mốc R nào cho tới khi có tín hiệu dưới đây. Luật ước tính + pre-mortem mới (thiết kế 6.5) đã được leader duyệt.

**Khi team xong thì bắt đầu từ đâu** (`/session-start` kiểm từng dòng):
| Tín hiệu | Việc đầu tiên |
|---|---|
| D1 #66 (Bảo) merge | Đối chiếu `plan/R10b1.md`, `R10b2.md` với `docs/schema/data_contract.md` bản D1 (cột, luật V01–V09); sửa plan theo luật 6.5 (≥ 25 phút/task có Postgres; USD = worker + 2; pre-mortem "kill ở giữa?" và "đạt theo cấu tạo?") qua PR; leader duyệt → chạy `R10b1 R10b2`, `audit.json` đặt audit 4 sau R10b2 (+5–6 USD). Đây là đường găng của cổng 13/10 (A4, A7). |
| PR của Finn cho #67, #89, #90 | Kiểm với backend: H-44, H-46, H-49 (`question_id` gửi kèm `/answer`), chạy `scripts/demo.sh --fresh-db --check`; đóng lỗ hổng trong PROJECT_STATE khi có test. PR đầu tiên của team: xem `plugin-guard` có chặn đúng không. |
| Daivon nhận lời mời | Gán #65 bằng tay (`gh issue edit 65 --add-assignee daivonpham`); vai Q chạy đo nền LLM thật (≤ 2 USD, leader cho phép từng lần). |
| Issue nhãn `api` từ vai D | Backend trả lời trong ngày (không tính là chạy mốc). |

### Làm tiếp theo thứ tự
1. **Chờ leader:**
   - (a) **để sau**, leader tự làm khi cần: đo nền LLM thật (`eval_rootcause.py --llm real --seeds 3`, ≤ 2 USD); quyết R10b1 nếu D1 chưa merge sáng 12/10.
   - Leader đã nói **không nhắc lại** trong báo cáo: nhắc Bảo/Daivon, giờ kickoff, đưa đề xuất nghiên cứu vào ROADMAP (bộ nhớ `skip-team-reminders`).
   - Phiên sau không còn việc nào chặn bởi leader. Việc đầu tiên: `/session-start` kiểm bảng "Tín hiệu" ở mục ⏸.
2. **Plugin, chỉ làm khi chưa có tín hiệu từ team và hạn mức tuần còn đủ cho R10b** (giữ ~25 USD cho R10b1 + R10b2 + audit 4):
   - Luật xếp mức cho reviewer: ghi chú mô tả hành vi sai so với tiêu chí hoặc quy tắc thì là blocking, kể cả khi hậu quả "đi về hướng an toàn"; ngoại lệ là khi plan ghi rõ chấp nhận.
   - Chỉ đo luật này trên **ca mới chưa xem** (≥ 5 ca lỗi lấy từ audit 4), mỗi ca 3 lần. Không đo trên 11 ca hiện có, vì đã xem output của chúng.
   - Hỏi leader trước mỗi lượt đo.
   - Khi Daivon nhận lời mời: gán #65 bằng tay. Plan R10b1/R10b2 khi sửa sau D1: áp luật 6.5.
3. **R10b1 khi D1 merge:** đối chiếu `plan/R10b1.md` với bản D1 (cột, luật V01–V09), sửa plan qua PR, rồi chạy `R10b1 R10b2` nối tiếp. Đặt `audit.json` sao cho audit 4 chạy sau R10b2.
4. **Cổng 13/10:** theo `criteria.md` mục 3. Đang có A6 = 0; A5 phần LLM giả; A8 (LLM giả). A4, A7 cần R10b2; UI FR-01..05 cần vai D. Leader duyệt tag.
5. **R11a** (13–14/10): H-28, H-29, H-56 (gộp H-18), H-32, H-36, H-52, H-53, H-55; kịch bản `ask` và `none`; treo từ R10ch: bản SOP trùng nếu kill giữa commit và checkpoint.
6. **Plugin sau v0.1:** P9 (reviewer cho PR của team, chỉ comment), P7a Telegram một chiều.

### Cách làm việc với team
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Team dùng Claude Code trên máy riêng, trong vùng của vai:
  - A: `docs/schema/data_contract.md`, `docs/research/`, `data/templates/`, `data/scenarios/draft/`;
  - D: `dashboard/`;
  - Q: `docs/qa/`, `docs/token-cost.md`.
- **API mới:** vai D mở issue nhãn `api`; backend trả lời trong ngày. **Đổi `docs/schema/events.json`:** PR riêng, báo trong sync.
- **Chạy LLM thật:** chỉ vai Q, ngân sách ≤ [2] USD/ngày, leader cho phép từng lần; ghi chi phí vào `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).
- **`plugin-guard`** chưa thử nhánh chặn (PR của thành viên): kiểm ở PR đầu tiên của team.

## Trạng thái hiện tại (2026-10-11 rạng sáng)
- **Dự án (⏸ tạm dừng chờ team):**
  - M0–M3 xong; M4: T-040, T-041 xong, T-042..T-045 mở;
  - 587 pytest + 1 xfail (`test_no_model_name_in_backend`, gỡ khi đóng H-39 ở R10b2);
  - % đạt 3 điều: **0 / 50 / 0**.
- **Plugin:**
  - P1–P3, P5, P6 xong; P4 đang làm (còn kiểm hạn mức trước mốc);
  - P7–P9 chưa làm.
  - Chi phí cả ngày 10/10 (worker + supervisor + audit): R10a 5,94; R10c 7,88; audit 3 5,55; R10ch 4,77 USD; bộ thử reviewer 6,60 USD.
  - Mới trong phiên: cổng `test_guard` (bật mặc định), `reviewer.md` có `risk_checks`. Cả hai **chưa chạy trong mốc R thật**: kiểm ở R10b1 xem reviewer có trả `risk_checks` không, và `test_guard` có chặn nhầm không.
- **Runner:** rảnh. `.autodev/runs/audit.json` `pending = []`.
- **Demo:** tắt. Bật bằng `scripts/demo.sh`; tắt bằng `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt trước khi chạy mốc R mới (smoke cần cổng 8000/3000).
- **Không có PR mở.**

## Môi trường
- **Repo:** `~/dev/sme-ci-agent/` chứa 3 worktree cạnh nhau:
  - `sme-ci-agent` (chính);
  - `sme-ci-agent-autodev` (worker);
  - `sme-ci-agent-supervisor` (supervisor).

  Repo GitHub `Silver-RP/sme-ci-agent` (public). Tài liệu hackathon ở `~/Desktop/Projects_VSCode/Vietnam Japan AI Hackathon 2026/`.
- **Postgres:** container `sme-ci-agent-autodev-db-1`, cổng 5432 (user/pass/db synthetic `sme`/`sme`/`sme_ci`). `demo.sh` dùng lại DB đang chạy nếu kết nối được.
- **Node 22.23.3** (`nvm alias default 22`, yarn 1.22). Luôn đặt `PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH` khi khởi chạy runner.
- **LLM thật:** người dùng tự điền `.env` (`ANTHROPIC_API_KEY`, `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_CHEAP=claude-haiku-4-5-20251001`, `LLM_EFFORT=medium`). Agent không bao giờ đọc file này. Hỏi trước mỗi lần chạy `--llm real`.
- **Chạy mốc** (từ repo chính, sau khi `plan/Rx.md` đã merge lên main):
  ```bash
  export PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH AUTODEV_SUPERVISOR_MODEL=opus AUTODEV_SUPERVISOR_EFFORT=medium
  nohup .autodev/autodev-run.sh R10b1 R10b2 > .autodev/runs/nohup.out 2>&1 &
  ```
  Ngay sau đó, bằng Bash `run_in_background`, chạy vòng `until` chờ "Hoàn tất|STOP" trong `.autodev/runs/run.log`, để phiên chat được báo khi xong. Có thể nối mốc kế bằng một script chờ "Hoàn tất" rồi mới khởi động (dừng khi gặp STOP).
- **Phạm vi audit:** runner đọc `.autodev/runs/audit.json` (`pending`, không commit) đúng lúc quyết định có chạy audit hay không. Sửa danh sách này để chọn audit chạy sau mốc nào.
- **Theo dõi:** `.autodev/watch.sh` (terminal) hoặc trang trạng thái Artifact (ảnh chụp).
- **Hạn mức theo nhiệm vụ (leader yêu cầu 10/10):** status line `~/.claude/statusline-usage.sh` (cài trong `~/.claude/settings.json`) ghi % 5 giờ và % tuần vào `~/.claude/usage-latest.json`. Đầu và cuối mỗi nhiệm vụ Claude chạy `python3 .autodev/usage.py start "<việc>" --est "<ước tính>"` / `end`, báo một dòng trước → sau. Lịch sử ở `.autodev/runs/usage-log.md` (không commit); xem nhanh bằng `python3 .autodev/usage.py show [--last N]`. Status line **chỉ chạy trong CLI terminal**, không chạy trong extension VS Code: số liệu cũ hơn 30 phút thì `usage.py` báo, và Claude hỏi leader 2 số từ `/usage`. `/session-start` in dòng hạn mức.
- **Bộ thử reviewer:** `python3 .autodev/bench_reviewer.py run --cases <id,...> --configs <tên> [--dry-run] [--max-usd N]`, chạy nền, chỉ khi runner rảnh. Worktree cố định `../sme-ci-agent-bench` (không xoá). Kết quả ở `.autodev/runs/bench/` (không commit). Cấu hình ở `.autodev/bench/configs.json` (`prompt_ref` / `prompt_path` / hiện tại). **Tốn tiền: hỏi leader trước mỗi lượt.**
- **Chế độ Auto** đôi khi lỗi "classifier no verdict" ở phía máy chủ. Khi đó người dùng tạm chuyển chế độ quyền.

## Quyền và quy tắc đang áp dụng
- **Merge:**
  - Supervisor tự merge PR mốc sau khi tự chạy verify + smoke + bảng tiêu chí + **chờ check `plugin-guard` xanh**. Worker không merge.
  - PR hồ sơ chỉ sửa `docs/autodev/**` (và `docs/audits/**`) thì runner tự merge.
  - Phiên tương tác được tự merge PR của mình sau khi check xanh (`gh pr checks <số> --required --watch`; check có thể chưa đăng ký ngay sau khi mở PR, chờ rồi thử lại, không dùng `--admin`).
- **Plan mốc:** mở PR cho leader xem phạm vi; merge và chạy runner khi leader duyệt.
- **Không đẩy thẳng `main`:** GitHub chặn, guard cũng chặn.
- **Không sửa plugin** (`.autodev/*.py`, `.claude/`) khi runner đang chạy; chỉ giữa hai mốc.
- **Không xoá** file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt. Merge không kèm `--delete-branch`. Nhánh đã merge còn lại đang chờ duyệt xoá.
- **Không đọc hay in `.env`.** Guard so khớp theo chữ: sửa file tại chỗ bằng sed và script Python qua stdin (heredoc) bị chặn; dùng Edit/Write tool hoặc script file.
- **Tầng tầm nhìn** (thứ tự mốc, cắt việc, luật tính %) luôn do người dùng duyệt. Kiến trúc trong ADR cố định.
- **Không đổi tiêu chí chấp nhận trong brief** khi chưa hỏi leader. Phiên bản thay đổi ghi ở mục "Lịch sử thay đổi yêu cầu" của brief.

## Việc mở / cần để ý
- **Lỗ hổng dự án:** PROJECT_STATE mục "Lỗ hổng mở" (nguồn `docs/audits/2026-10-10.md`).
- **B1 = 0,71 > 0,5:** reviewer vẫn lỏng ở mức mục tiêu (audit 3 tìm H-54 "đạt theo cấu tạo"). Bộ thử xác nhận: reviewer một lần chặn khoảng 2/9 lỗi đã biết, nên **giữ audit 4 sau R10b2**. Theo dõi ở audit 4.
- **pytest chập chờn:** đỏ 1/4 lần trên main, không bắt được tên test. Gặp lại thì ghi tên test.
- **Để sau** (người dùng chốt): đo chất lượng theo thời gian; hook trước khi nén ngữ cảnh.

## Lịch sử ngắn
- P1–P3 xong; R4–R9ih chạy bằng chế độ B, tất cả merge.
- 2026-10-08: chuyển repo khỏi iCloud; hardening + R8.
- 2026-10-09: P5, audit 1–2, R9, R9h, R9i, R9ih, T-030 khép vòng LLM thật.
- 2026-10-10 sáng: tạm dừng tính năng; hợp đồng dữ liệu, storyboard, brief A/D/Q, issue #63–#67, onboarding, bảo vệ `main` + `plugin-guard`; dọn thư mục cũ; lệnh `/session-start`, `/session-end`.
- 2026-10-10 chiều–tối: kế hoạch P6 + tiêu chí đo được (#76, #78, #87); R10a (#82), R10c (#84), audit 3 (#86, B1 = 0,71), R10ch (#91); R10b1 chờ D1; trang trạng thái Artifact.
- 2026-10-10 đêm: P5, P6 đóng; `--fresh-db`; tạm dừng dự án chờ team; quy tắc ước tính + ghi % hạn mức; báo cáo so sánh bên ngoài (#94–#101).
- 2026-10-10 khuya → 11/10: `usage.py show`; cổng `test_guard` + `risk_checks` (đề xuất 1 + 3); bộ thử reviewer 11 ca: chặn 2/9, thấy 5/9 (#103–#108).
- Chi tiết trong `PROGRESS.md`.

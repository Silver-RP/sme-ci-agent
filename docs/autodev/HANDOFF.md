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

## Bước tiếp theo (cập nhật 2026-10-11 tối: R10b1 merge #130; runner chuyển sang R10b2)

### Bối cảnh
- **Team 4 người** (`docs/PLAN.md` mục 4). Ranh giới: auto-dev không làm thay việc của vai A/D/Q, kể cả khi không đụng file của họ (**trùng việc** khác **trùng file**).

| Vai | Người | Issue mở | Trạng thái 11/10 chiều |
|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63 (D3–D6) | **D1 (#122) và D2 (#123) đã merge.** Còn chờ Bảo trả lời 2 câu hỏi SOP ở #122 (plan R10b1 làm theo đề xuất: bản gốc từ `sop.csv` có `created_by: "import"`; SOP chỉ có trong config thì dataset không có) |
| D: giao diện | @Finnng1104 (Finn) | #64, #114 | **#116–#118 đã merge** (UI mới, H-44, H-46, H-49 phía UI). #114 `GET /config/domain` để sau R10b1 (cần `plant.*` trong domain config) |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | **chưa nhận lời mời**; #65 chưa gán. D1 merge không chờ vai Q (leader quyết) |
| Backend, auto-dev | leader + Claude | #111 (H-34, R11a) | `plan/Rx.md` |

- **Mốc tham khảo:** cổng go/no-go + tag v0.1-e2e 13/10; Đợt 2 UI 17/10; freeze 20/10; Pitch 24/10.
- **Kế hoạch P6 hai luồng** đã duyệt: `ROADMAP.md` mục "Kế hoạch hai luồng"; bảng mốc ở PROJECT_STATE mục "Tầm nhìn".

### Đã xong trong phiên 2026-10-11 sáng → chiều (PR #116–#125, đều merge)
- **UI của Finn (#116–#118):** kiểm phía backend trên bản gộp (vitest 94/94, `demo.sh --fresh-db --check` PASSED, trường `pending` khớp backend), approve, merge; đóng #67, #89, #90. `plugin-guard` cho qua PR của thành viên (chỉ sửa `dashboard/`, đúng vùng); nhánh chặn vẫn chưa thử.
- **6 issue `api` của Finn:** phân loại trong ngày. #110, #112, #113, #115 + `question_id` bắt buộc → R10d; #114 → sau R10b1; #111 (H-34) → R11a. #110 chốt **422** khi giờ có múi giờ (giống `change_time` R10ch), không quy đổi.
- **R10d** (plan #119, mốc #120, hồ sơ #121): 5 task, đóng H-49, H-57; ~4,70 USD. Lượt 1 thiếu tài liệu múi giờ → supervisor thêm dev-05 (b) → lượt 2 đạt. Đã đóng issue #110, #112, #113, #115.
- **D1 (#122), D2 (#123):** review phía backend (D1 đối chiếu code + plan; D2 diff từng bộ `invalid/` với `valid/`, 32/32 khớp đáp án README), approve, merge. D2 merge sau khi Bảo bỏ draft; commit trùng bản đã review.
- **Plan R10b1/R10b2 (#124):** R10b1 đối chiếu D1 (7 task: `units_nonconforming`, 11 khoá config, validator tách 2 task, import ghi nguyên tử, SOP của dataset, sự kiện máy bình thường); R10b2 sửa ước tính, bỏ H-31 (đã đóng). Tổng ước tính R10b1 + R10b2 + audit 4: 20–26 USD.
- **#125:** `test_open_gaps_match_latest_audit` đỏ trên main sau #121 (state.json đóng H-49, H-57 nhưng bảng audit 3 vẫn "mở") → sửa bảng audit.
- **Dọn nhánh:** leader duyệt và **tự chạy** (guard chặn mọi lệnh xoá của Claude): xoá 56 nhánh remote + 89 local đã merge; xoá worktree review.
- **Hạn mức** (leader dán 13:45 11/10): 5 giờ 1%, tuần 71% (reset 13:00 14/10). Ước tính sau R10b + audit 4: tuần ~84–87%.

### R10b1 ✅ merge #130 (supervisor `--review-only`, tối 11/10)
- Worker 7/7 DONE, 8 vòng (dev-04 2 vòng). Supervisor tự chạy: verify sạch; 839 passed + 1 xfail; smoke 4/4; `demo.sh --fresh-db --check` → `CHECK PASSED`; A1 bắt ở ca đầu, FP1 im, A1 ≈ 9,6σ; 31/31 bộ D2 đúng mã; vòng nhập **seed 7** → app đọc đúng bảng nhập; dataset thiếu `_COMPLETE` → lỗi rõ. **4/4 tiêu chí cấp mốc đạt.** Bảng + ước tính ↔ thực tế + pre-mortem: `PROGRESS.md` mục R10b1. 267 phút / 175–240 (B3 1,11); 9,10 + ~1,04 USD / 7–10; không đóng H-xx.
- **Việc mở:** 7 đề xuất (c) trong PR #130 chờ leader/vai A (đáng làm sớm: fixture phụ thuộc DB dùng chung; `data_report.py`, `eval_rootcause.py`, `export_fixtures.py` chưa đọc `SME_DATASET`). **Báo vai D:** fixture sinh lại, `dashboard/tests/stages.test.tsx`, `ux.test.tsx` đổi số mong đợi. Nhỏ: thông báo "Import it again" của dataset dở dang mâu thuẫn luật không ghi đè tên. #114 `/config/domain` nay mở được (`plant.*` đã ở domain config).
- **Plugin:** `test_guard` có hiệu lực (4 commit khai `allow-test-change`, reviewer xét); file review **không có `risk_checks`** (reviewer.md bước 8 chưa được tuân) → xem ở audit 4.

### Runner (khởi động 13:44 11/10; R10b1 xong, R10b2 kế tiếp)
- Lệnh: `.autodev/autodev-run.sh --audit-every 3 R10b1 R10b2`. `audit.json` có `pending = [R10d]`, nên **audit 4 chạy sau R10b2** và phủ R10d, R10b1, R10b2.
- Vòng chờ nền của phiên cũ mất khi đóng phiên. Phiên sau: `tail -15 .autodev/runs/run.log`, `ls -t .autodev/runs/STOPPED-* | head -1`, `gh pr list`. Gặp STOP thì đọc báo cáo trong PR mốc trước khi chạy tiếp.
- Ước tính: ~7–8 giờ worker + supervisor + audit, tức xong khoảng 22:00–23:00 11/10.

### Làm tiếp theo thứ tự
1. **Chờ leader** (không có việc nào chặn runner):
   - (a) Guard: thêm cách duyệt xoá một lần (ví dụ biến môi trường), để Claude tự xoá khi leader đã duyệt? Trả lời "có/không". Chỉ sửa khi runner rảnh.
   - (b) Xoá worktree `../sme-ci-agent-d2` (tạo để review D2): leader tự chạy `git worktree remove ../sme-ci-agent-d2`.
   - (c) **Để sau**, leader tự làm khi cần: đo nền LLM thật (`eval_rootcause.py --llm real --seeds 3`, ≤ 2 USD).
   - Không nhắc trong báo cáo: nhắc Bảo/Daivon, giờ kickoff, ROADMAP nghiên cứu (bộ nhớ `skip-team-reminders`).
2. **Khi runner xong:** kiểm R10b1, R10b2 đã merge và PR hồ sơ đã merge; đọc audit 4 (`docs/audits/2026-10-1x.md`); cập nhật % đạt (A4, A7) và lỗ hổng theo audit; xem reviewer có trả `risk_checks` và `test_guard` có chặn nhầm không (lần đầu chạy trong mốc thật).
3. **Cổng 13/10:** `criteria.md` mục 3; leader duyệt tag v0.1-e2e.
4. **#114 `GET /config/domain`:** sau R10b1 (nguồn `plant.*` trong domain config). Gộp vào R11a hoặc mốc nhỏ; trả lời Finn ở #114.
5. **Sửa plugin (giữa hai mốc, sau R10b; P4):**
   - runner không chạy tiếp được mốc đã có PR mở (`new_milestone_pr` chỉ nhận PR mới) → lần này phải dùng `--skip-merge-check`, mất bước tự merge PR hồ sơ;
   - worktree worker không kéo commit (b) supervisor đẩy lên nhánh mốc → lần này phải `git merge --ff-only` tay;
   - supervisor đóng lỗ hổng trong `state.json` mà không sửa bảng audit → `.autodev/tests` đỏ trên main (#125). Supervisor phải chạy `.autodev/tests` trước khi merge PR hồ sơ.
6. **Reviewer:** đo luật xếp mức (ghi chú sai so với tiêu chí = blocking) trên ≥ 5 ca mới từ audit 4, mỗi ca 3 lần; hỏi leader trước; nên đợi sau reset hạn mức tuần (14/10).
7. **R11a** (sau cổng 13/10): H-28, H-29, H-56 (gộp H-18), H-32, H-34 (#111), H-36, H-52, H-53, H-55; kịch bản `ask` và `none`; treo từ R10ch: bản SOP trùng nếu kill giữa commit và checkpoint.
8. **Plugin sau v0.1:** P9 (reviewer cho PR của team, chỉ comment), P7a Telegram một chiều.

**Tín hiệu team còn lại** (`/session-start` kiểm):
| Tín hiệu | Việc đầu tiên |
|---|---|
| Daivon nhận lời mời | Gán #65 bằng tay (`gh issue edit 65 --add-assignee daivonpham`); vai Q chạy đo nền LLM thật (≤ 2 USD, leader cho phép từng lần). |
| Issue nhãn `api` mới | Backend trả lời trong ngày (không tính là chạy mốc). |
| PR mới của Finn/Bảo | Kiểm phía backend như #116–#118, #122–#123: chạy test + demo, comment, leader approve/merge. PR draft thì không merge, nhờ tác giả bỏ draft. |
| Bảo trả lời câu hỏi SOP ở #122 | Khác đề xuất thì sửa theo câu trả lời ở mốc sau (ghi vào "Đề xuất chờ duyệt" của plan đang chạy). |

### Cách làm việc với team
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Team dùng Claude Code trên máy riêng, trong vùng của vai:
  - A: `docs/schema/data_contract.md`, `docs/research/`, `data/templates/`, `data/scenarios/draft/`;
  - D: `dashboard/`;
  - Q: `docs/qa/`, `docs/token-cost.md`.
- **API mới:** vai D mở issue nhãn `api`; backend trả lời trong ngày. **Đổi `docs/schema/events.json`:** PR riêng, báo trong sync.
- **Chạy LLM thật:** chỉ vai Q, ngân sách ≤ [2] USD/ngày, leader cho phép từng lần; ghi chi phí vào `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).
- **`plugin-guard`** cho qua đúng 5 PR đầu của team (#116–#118 chỉ `dashboard/`; #122–#123 chỉ vùng vai A). Nhánh chặn (thành viên sửa file plugin) chưa có dịp thử.
- **Review PR của team:** Claude kiểm phía backend (test, demo, đối chiếu hợp đồng), comment; approve/merge là quyết định của leader. Không merge PR draft; không bỏ draft hộ tác giả.

## Trạng thái hiện tại (2026-10-11 chiều)
- **Dự án:**
  - M0–M3 xong; M4: T-040, T-041 xong, T-042..T-045 mở;
  - 610 test thu thập trên main (609 passed + 1 xfail `test_no_model_name_in_backend`, gỡ khi đóng H-39 ở R10b2);
  - % đạt 3 điều: **0 / 50 / 0** (R10d không đổi chỉ số A).
- **Plugin:**
  - P1–P3, P5, P6 xong; P4 đang làm (chạy tiếp mốc có PR mở, kiểm hạn mức trước mốc);
  - P7–P9 chưa làm.
  - Chi phí 11/10: R10d ~4,70 USD (2 lượt); R10b1 9,10 + ~1,04 USD.
  - `test_guard` chạy trong R10b1 (4 commit `allow-test-change`); `risk_checks` **không có** trong file review R10b1.
- **Dự án sau R10b1:** 839 passed + 1 xfail trên main.
- **Runner:** `R10b1 R10b2` (`--audit-every 3`), từ 13:44 11/10; R10b1 merge #130, tiếp R10b2.
- **Demo:** tắt. Bật bằng `scripts/demo.sh`; tắt bằng `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy (smoke cần cổng 8000/3000).
- **PR mở:** không có (runner sẽ mở PR mốc R10b1, R10b2 và PR hồ sơ).
- **Worktree:** chính, `-autodev` (worker), `-supervisor`, `-bench` (cố định), `-d2` (chờ leader xoá).

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
  nohup .autodev/autodev-run.sh [--audit-every N] <mốc> [<mốc> ...] > .autodev/runs/nohup.out 2>&1 &
  ```
  `--audit-every` (mặc định 2) đếm cả `pending` còn lại trong `audit.json`; chọn N để audit chạy sau đúng mốc mong muốn.
  **Chạy tiếp mốc đã có PR mở** (sau khi supervisor thêm task (b)): `git -C ../sme-ci-agent-autodev merge --ff-only origin/milestone/<M>` rồi chạy với `--skip-merge-check`; sau đó tự kiểm PR mốc đã merge và tự merge PR hồ sơ (chờ sửa plugin, mục 5 "Làm tiếp").
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
- **Không xoá** file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt. Merge không kèm `--delete-branch`. Guard chặn mọi lệnh xoá nhánh/worktree kể cả khi leader đã duyệt: Claude kiểm phạm vi (chỉ nhánh đã merge, của mình, không đang checkout), ghi danh sách ra scratchpad và đưa lệnh cho leader tự chạy. Không lách bằng `gh api`.
- **Không đọc hay in `.env`.** Guard so khớp theo chữ: sửa file tại chỗ bằng sed và script Python qua stdin (heredoc) bị chặn; dùng Edit/Write tool hoặc script file.
- **Tầng tầm nhìn** (thứ tự mốc, cắt việc, luật tính %) luôn do người dùng duyệt. Kiến trúc trong ADR cố định.
- **Không đổi tiêu chí chấp nhận trong brief** khi chưa hỏi leader. Phiên bản thay đổi ghi ở mục "Lịch sử thay đổi yêu cầu" của brief.

## Việc mở / cần để ý
- **Lỗ hổng dự án:** PROJECT_STATE mục "Lỗ hổng mở" (nguồn `docs/audits/2026-10-10.md`).
- **B1 = 0,71 > 0,5:** reviewer vẫn lỏng ở mức mục tiêu (audit 3 tìm H-54 "đạt theo cấu tạo"). Bộ thử xác nhận: reviewer một lần chặn khoảng 2/9 lỗi đã biết, nên audit 4 chạy sau R10b2 (đã đặt). Theo dõi ở audit 4.
- **Hạn mức tuần:** 71% lúc 13:45 11/10, dự kiến ~84–87% sau R10b + audit 4; reset 13:00 14/10. Trước đó tránh chạy thêm mốc auto-dev hay bộ thử reviewer.
- **Fixture:** `docs/schema/examples/` còn request `/answer` cũ thiếu `question_id`; R10b1 dev-07 sinh lại.
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
- 2026-10-11 sáng → chiều: team có tín hiệu; merge UI của Finn (#116–#118), D1/D2 của Bảo (#122–#123); R10d (#119–#121, H-49, H-57); plan R10b đối chiếu D1 (#124); sửa bảng audit (#125); dọn nhánh; chạy R10b1 → R10b2.
- Chi tiết trong `PROGRESS.md`.

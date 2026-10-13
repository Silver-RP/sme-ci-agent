# Bàn giao giữa các phiên supervisor

Mở phiên: `/session-start`. Đóng phiên: `/session-end` (cập nhật file này, PROJECT_STATE, bộ nhớ; PR + merge). Supervisor cũng cập nhật file này ở cuối mỗi mốc. Phiên supervisor mới đọc file này trước tiên, rồi `PROJECT_STATE.md`, `ROADMAP.md`, `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- **Hai plan lồng nhau:**
  - **Plan lớn** là xây plugin auto-dev (`docs/autodev/`, mốc **P1–P9**).
  - **Plan nhỏ** là dự án SME CI Agent (`TASKS.md` và `docs/PLAN.md`, mốc dự án **M0–M4**).
  - Mỗi **lần chạy auto-dev** là một mốc **R** (`plan/R4.md`…`plan/R10b2.md`): worker làm vài task TASKS.md, đồng thời kiểm chứng một khả năng của plugin. Mốc tên kết thúc bằng `h` là sửa nhanh, không tính vào `--audit-every`.
  - Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD.
- **Phiên supervisor đóng vai leader kỹ thuật kiêm BA:**
  - lập plan, giao mốc, duyệt, merge, sửa plugin;
  - viết brief và issue cho team.

  Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15, `.claude/commands/supervise.md`.
- **Người dùng:** leader, nói tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa, báo ngắn gọn, giải thích khi hỏi "tại sao" hay "là gì" (**giải thích đơn giản trước**, chi tiết khi được hỏi thêm). Cuối mỗi báo cáo có câu hỏi "làm gì tiếp": danh sách **đánh số kèm nội dung**, leader trả lời bằng số.
- **Đo bằng số, không ước lượng:** % đạt 3 điều tính theo `docs/eval/criteria.md` (A1–A8, luật chỉ số nhiều phần); chỉ số plugin B1–B6 bằng `python3 .autodev/metrics.py`.

## Bước tiếp theo (cập nhật 2026-10-13, đóng phiên: kế hoạch tổng thể tới Demo Day, điều 1 giữ 0, quy tắc tên phiên)

### Bối cảnh
- **Team 4 người** (`docs/PLAN.md` mục 4). Ranh giới: auto-dev không làm thay việc của vai A/D/Q, kể cả khi không đụng file của họ (**trùng việc** khác **trùng file**).

| Vai | Người | Issue mở | Trạng thái 12/10 chiều |
|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63 (D3–D6) | D1, D2 merge. Việc kế: D3 (`docs/research/reflow_domain.md`, nguồn 4 giả định điều 3, H-64), D4 (≥ 4 kịch bản). Comment 12/10 ở #63 làm rõ dạng bàn giao D4/D6: YAML + **đáp án theo mã**, hoặc bộ CSV ≥ 42 ngày qua `import_data.py --check-only`. Chưa trả lời 2 câu hỏi SOP ở #122 |
| D: giao diện | @Finnng1104 (Finn) | #64, #139, #141 (gán) | #139: 6 vitest đỏ trên main sau R10e (kỳ vọng tiếng Anh cũ) + H-65 b/f/g, H-67..H-69. #141: ADR-010 (nhãn từ `/config/domain`, chú thích mã, kiểu "trích nguyên văn"); phần nhãn chờ backend R11c |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | **chưa nhận lời mời**; #65 chưa gán. T-044, T-045 chưa có người. `docs/token-cost.md` (vùng vai Q) chưa có: chi phí LLM thật ghi tạm ở PROJECT_STATE |
| Backend, auto-dev | leader + Claude | | `plan/Rx.md` |

- **Mốc tham khảo:** Đợt 2 UI 17/10; freeze 20/10 (tag v0.2-freeze); Pitch 24/10.

### Đã xong trong phiên 2026-10-12 tối → 13/10 (chỉ quyết định và tài liệu, không chạy runner)
- **Hạn mức** leader báo 12/10 tối: 5 giờ 30%, tuần **97%**. Reset tuần 13:00 14/10, lần sau 13:00 21/10 (sau freeze) → mọi việc tới freeze nằm trong **một tuần hạn mức**.
- **Leader chốt điều 1 = 0** (đúng luật công thức), ghi kèm "nền LLM thật 3/3 trên bài dễ"; không dùng số ước lượng.
- **P8a để sau freeze.**
- **Quy tắc tên phiên** (leader yêu cầu): một phiên = một việc, tên `leader-<MMDD>-<việc>`; `/session-start` mục 4 đưa sẵn lệnh `/rename`; đổi việc lớn thì mở phiên mới. Phiên này: `leader-1012-mo-phien`.
- **Kế hoạch tổng thể 13/10 → 07/11** (leader duyệt): ghi vào `ROADMAP.md` mục "Kế hoạch hai luồng" (lịch, thứ tự cắt, ngân sách tuần) và `PROJECT_STATE.md` mục "Tầm nhìn". Điểm chính: tách R11a cũ thành **R11a** (eval trung thực điều 1) + **R11c** (ADR-010 backend + vững); P4 tối thiểu trước chuỗi; đo A4/A5 LLM thật sau R11a (điều 2 có thể lên 100); R11b chờ D4, không có D4 tới 16/10 tối thì leader chọn người ngoài backend soạn holdout hoặc điều 1 ≤ 60% khi pitch.
- **Worktree:** leader đã xoá `-d2` và `-bench`. Xoá `-bench` là do Claude đưa nhầm lệnh (bàn giao ghi worktree này cố định); không hại gì, vì `bench_reviewer.py` tự `git worktree add` lại ở lần chạy sau.

### Làm tiếp theo thứ tự
1. **Chờ leader:**
   - (a) Viết `plan/R11a.md` + `plan/R11c.md` (phiên `leader-1013-plan-r11` hoặc `leader-1014-plan-r11`): "viết plan". Viết plan không cần chờ reset; chạy runner thì phải sau 13:00 14/10.
   - (b) 14/10 sau 13:00: gửi 2 số `/usage` rồi chọn "sửa P4".
   - Không nhắc trong báo cáo: nhắc Bảo/Daivon, giờ kickoff, ROADMAP nghiên cứu (bộ nhớ `skip-team-reminders`).
2. **P4 tối thiểu** (phiên `leader-1014-sua-p4`, ~30–45 phút, trước chuỗi R11):
   - runner không chạy tiếp được mốc đã có PR mở (`new_milestone_pr` chỉ nhận PR mới);
   - worktree worker không kéo commit (b) supervisor đẩy lên nhánh mốc;
   - `/session-start` kiểm runner bằng `pgrep -fl 'autodev/run.py'` (`autodev-run` không khớp);
   - `demo.sh`: tự `yarn install` khi `dashboard/package.json`/`yarn.lock` đổi;
   - supervisor chạy `.autodev/tests` trước khi merge PR hồ sơ (#125).
   - **Để sau freeze:** hook `SubagentStop` không chạy (`hook_runs` đứng ở 67), tăng tốc verify (`pytest-xdist`, `--durations=20`), `metrics.py` đọc phạm vi audit, đo reviewer ≥ 5 ca.
3. **Chuỗi R11a → R11c** (chế độ B, ~16–20 USD, ~8–10 giờ máy; `--audit-every` đặt để audit 5 chạy sau R11b):
   - **R11a** (≤ 7 task): trường `signal` + prompt + chấm theo mã (H-28); eval luôn trên DB sạch, không đọc `learning_store` run khác, `--set dev|holdout`; nhãn `expect` (cause/ask/none) đo A2, A3; tập dev ≥ 4 kịch bản do backend soạn (H-29: 2–3σ tăng dần, zone3 ±2 °C thường xuyên, nhiễu trùng thời điểm, dữ liệu `environment_log`/`training_level`, A2 khác nguyên nhân, 1 `ask`, 1 `none`); H-63, H-18, H-56; H-36. Lỗi đã biết: `verify.py` đỏ `dashboard` tới khi #139 merge.
   - **R11c** (≤ 6 task): khối `labels` + bảng thuật ngữ trong `data/context_profile.yaml` qua `/config/domain` (báo #141, không đổi `events.json`); prompt dùng nhãn thay mã, `new_content` tiếng Việt, SOP gốc + ghi chú simulator + `demo_llm` tiếng Việt; H-52, H-53, H-55; H-60, H-61 nếu còn chỗ; treo từ R10ch: bản SOP trùng nếu kill giữa commit và checkpoint.
   - Sau chuỗi (leader cho phép, ~1–2 USD API): `eval_rootcause.py --llm real --set dev --seeds 3` (A1–A3 dev, không tính %), `--until learn --llm real --seeds 3` (A4, A5 LLM thật); ghi `docs/token-cost.md`.
   - Đọc `/usage` sau R11a; tuần ≥ 80% thì dừng chuỗi, áp thứ tự cắt (ROADMAP).
4. **R11b** (16–17/10, ~8 USD): D4/D5 → holdout, A1 tập giữ lại LLM thật; ghi run tốt để phát lại; A8 LLM thật. Rồi **audit 5**.
5. **R12** (18–19/10) → cổng 20/10 (`criteria.md` mục 3, biên bản `docs/qa/gate-v0.2-freeze.md`), leader tag `v0.2-freeze`. Sau đó chỉ sửa lỗi + pitch; plugin sau pitch: P4 còn lại → P9 → P8a → P7a.

**Tín hiệu team còn lại** (`/session-start` kiểm):
| Tín hiệu | Việc đầu tiên |
|---|---|
| Daivon nhận lời mời | Gán #65 bằng tay (`gh issue edit 65 --add-assignee daivonpham`); vai Q chạy đo LLM thật (≤ 2 USD, leader cho phép từng lần); T-044, T-045; tạo `docs/token-cost.md` (ghi lại 2 lần đo 12/10). |
| Issue nhãn `api` mới | Backend trả lời trong ngày (không tính là chạy mốc). |
| PR mới của Finn/Bảo | Kiểm phía backend (test, demo, đối chiếu hợp đồng), comment, approve; leader merge. Sau merge chạy pytest trên main nếu PR đổi dữ liệu test. PR draft thì không merge. PR #139 của Finn merge thì `verify.py` hết đỏ `dashboard`. |
| Bảo trả lời #63 (dạng D4/D6) / #122 (SOP) / nộp D3 | D4/D6: đưa vào R11b (nhập qua `import_data.py`, eval trên DB sạch). SOP: khác đề xuất thì sửa ở mốc sau (SOP gốc tiếng Việt theo ADR-010). D3: cập nhật `source` của 4 giả định, chạy lại `metrics_report.py`, xét lại % điều 3. |

### Cách làm việc với team
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Team dùng Claude Code trên máy riêng, trong vùng của vai:
  - A: `docs/schema/data_contract.md`, `docs/research/`, `data/templates/`, `data/scenarios/draft/`;
  - D: `dashboard/`;
  - Q: `docs/qa/`, `docs/token-cost.md`.
- **API mới:** vai D mở issue nhãn `api`; backend trả lời trong ngày. **Đổi `docs/schema/events.json`:** PR riêng, báo trong sync.
- **Chạy LLM thật:** chỉ vai Q, ngân sách ≤ [2] USD/ngày, leader cho phép từng lần; ghi chi phí vào `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).
- **`plugin-guard`** cho qua 6 PR của team (#116–#118 `dashboard/`; #122, #123, #126 vùng vai A). Nhánh chặn chưa có dịp thử.
- **Review PR của team:** Claude kiểm phía backend, comment, approve; merge là quyết định của leader. Không merge PR draft; không bỏ draft hộ tác giả.

## Trạng thái hiện tại (2026-10-13)
- **Dự án:**
  - M0–M3 xong; M4 3/6 (T-040..T-042); T-043 (vai D), T-044, T-045 (vai Q) mở; cổng 13/10 go, tag `v0.1-e2e` (c60fec5);
  - 1028 passed trên main (R10e); **6 vitest dashboard đỏ trên main** (#139, vai D);
  - % đạt 3 điều: **0 / 67 / 67** (leader chốt điều 1 = 0 ngày 13/10).
- **Plugin:** P1–P3, P5, P6 xong; P4 đang làm (mục 2 "Làm tiếp"); P7–P9 chưa làm.
- **Runner:** rảnh (R10e xong 11:34 12/10; `audit.json` pending `["R10e"]`, `--audit-every` mặc định 2 → audit chạy sau mốc kế).
- **Demo:** tắt. DB demo `sme_ci_demo` còn các run thử LLM thật của leader (xoá khi `--fresh-db` lần sau). Bật: `scripts/demo.sh --fresh-db` (thêm `SME_LLM=real` cho LLM thật, mở `/?source=live`); tắt: `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy.
- **PR mở:** không có (sau PR bàn giao này).
- **Worktree:** chính, `-autodev` (worker), `-supervisor`. `-bench` tự dựng lại khi chạy `bench_reviewer.py`; `-d2` đã xoá.
- **Hạn mức:** leader báo 12/10 tối: 5 giờ 30%, tuần **97%** → không chạy runner tới reset 13:00 14/10; hỏi `/usage` đầu phiên sau.

## Môi trường
- **Repo:** `~/dev/sme-ci-agent/` chứa 3 worktree cạnh nhau:
  - `sme-ci-agent` (chính);
  - `sme-ci-agent-autodev` (worker);
  - `sme-ci-agent-supervisor` (supervisor).

  Repo GitHub `Silver-RP/sme-ci-agent` (public). Tài liệu hackathon ở `~/Desktop/Projects_VSCode/Vietnam Japan AI Hackathon 2026/`.
- **Máy:** Intel i5-8279U 4 nhân, RAM 8 GB; Docker chạy qua VM. pytest đầy đủ + Postgres ~20 phút.
- **Postgres:** container `sme-ci-agent-autodev-db-1`, cổng 5432 (user/pass/db synthetic `sme`/`sme`/`sme_ci`). `demo.sh` dùng lại DB đang chạy nếu kết nối được.
- **Node 22.23.3** (`nvm alias default 22`, yarn 1.22). Luôn đặt `PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH` khi khởi chạy runner hoặc demo. Sau khi merge PR đổi `dashboard/package.json`: `yarn install --frozen-lockfile` trong `dashboard/`; còn lỗi "module not found" thì leader xoá `dashboard/.next`.
- **LLM thật:** người dùng tự điền `.env` (`ANTHROPIC_API_KEY`, `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_CHEAP=claude-haiku-4-5-20251001`, `LLM_EFFORT=medium`; dùng Haiku thì đặt `LLM_NO_EFFORT_MODELS`). Agent không bao giờ đọc file này. Hỏi trước mỗi lần chạy `--llm real`.
- **Chạy mốc** (từ repo chính, sau khi `plan/Rx.md` đã merge lên main):
  ```bash
  export PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH AUTODEV_SUPERVISOR_MODEL=opus AUTODEV_SUPERVISOR_EFFORT=medium
  nohup .autodev/autodev-run.sh [--audit-every N] <mốc> [<mốc> ...] > .autodev/runs/nohup.out 2>&1 &
  ```
  `--audit-every` (mặc định 2) đếm cả `pending` còn lại trong `audit.json`; chọn N để audit chạy sau đúng mốc mong muốn. Runner chuyển sang mốc kế **ngay** khi mốc trước merge: sửa plan mốc sau phải merge trước lúc đó.
  **Chạy tiếp mốc đã có PR mở** (sau khi supervisor thêm task (b)): `git -C ../sme-ci-agent-autodev merge --ff-only origin/milestone/<M>` rồi chạy với `--skip-merge-check`; sau đó tự kiểm PR mốc đã merge và tự merge PR hồ sơ (chờ sửa plugin).
  Ngay sau đó, bằng Bash `run_in_background`, chạy vòng `until` chờ thêm dòng "Hoàn tất|STOP" trong `.autodev/runs/run.log` hoặc `autodev/run.py` thoát, để phiên chat được báo khi xong.
- **Phạm vi audit:** runner đọc `.autodev/runs/audit.json` (`pending`, không commit) đúng lúc quyết định có chạy audit hay không.
- **Theo dõi:** `.autodev/watch.sh` (terminal) hoặc trang trạng thái Artifact (ảnh chụp).
- **Hạn mức theo nhiệm vụ (leader yêu cầu 10/10):** status line `~/.claude/statusline-usage.sh` ghi % 5 giờ và % tuần vào `~/.claude/usage-latest.json`. Đầu và cuối mỗi nhiệm vụ Claude chạy `python3 .autodev/usage.py start "<việc>" --est "<ước tính>"` / `end`. Lịch sử ở `.autodev/runs/usage-log.md` (không commit); `python3 .autodev/usage.py show [--last N]`. Status line **chỉ chạy trong CLI terminal**, không chạy trong extension VS Code: số liệu cũ hơn 30 phút thì hỏi leader 2 số từ `/usage`.
- **Bộ thử reviewer:** `python3 .autodev/bench_reviewer.py run --cases <id,...> --configs <tên> [--dry-run] [--max-usd N]`, chạy nền, chỉ khi runner rảnh. Worktree cố định `../sme-ci-agent-bench` (không xoá). **Tốn tiền: hỏi leader trước mỗi lượt.**
- **Chế độ Auto** đôi khi lỗi "classifier no verdict" ở phía máy chủ. Khi đó người dùng tạm chuyển chế độ quyền.

## Quyền và quy tắc đang áp dụng
- **Merge:**
  - Supervisor tự merge PR mốc sau khi tự chạy verify + smoke + bảng tiêu chí + **chờ check `plugin-guard` xanh**. Worker không merge.
  - PR hồ sơ chỉ sửa `docs/autodev/**` (và `docs/audits/**`) thì runner tự merge.
  - Phiên tương tác được tự merge PR của mình sau khi check xanh (`gh pr checks <số> --required --watch`; không dùng `--admin`). **Classifier chế độ Auto có lúc chặn `gh pr merge`** ("Merge Without Review"), cả PR của team lẫn PR của mình (#135): khi đó đưa lệnh cho leader tự chạy, không lách.
- **Plan mốc:** mở PR cho leader xem phạm vi; merge và chạy runner khi leader duyệt.
- **Không đẩy thẳng `main`:** GitHub chặn, guard cũng chặn. Guard chặn cả commit/tag khi thư mục chính đang ở `main`: làm trên clone trong scratchpad (nhánh riêng) để không đổi nhánh của thư mục runner dùng.
- **Không sửa plugin** (`.autodev/*.py`, `.claude/`) khi runner đang chạy; chỉ giữa hai mốc.
- **Không xoá** file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt. Merge không kèm `--delete-branch`. Guard chặn mọi lệnh xoá (kể cả `rm -rf` thư mục cache) kể cả khi leader đã duyệt; leader quyết **giữ nguyên** (12/10). Claude kiểm phạm vi, đưa lệnh cho leader tự chạy. Không lách.
- **Không đọc hay in `.env`.** Guard chặn sửa file tại chỗ bằng sed và script Python qua stdin (heredoc); dùng Edit/Write tool hoặc script file.
- **Tầng tầm nhìn** (thứ tự mốc, cắt việc, luật tính %) luôn do người dùng duyệt. Kiến trúc trong ADR cố định.
- **Không đổi tiêu chí chấp nhận trong brief** khi chưa hỏi leader.

## Việc mở / cần để ý
- **Lỗ hổng dự án:** PROJECT_STATE mục "Lỗ hổng mở" (nguồn `docs/audits/2026-10-12.md`); 31 mở, cao: H-28, H-29, H-64.
- **Điều 1 = 0:** đã có nền LLM thật (12/10, DB sạch 3/3 trên bài dễ); R11a (chấm theo mã, kịch bản khó) là đường để có số A1 trước freeze.
- **Freeze 20/10:** A1 trên tập giữ lại phải có số (thiếu đề của vai A thì ghi giới hạn khi pitch, điều 1 không báo quá 60%). H-32 đã sửa ở R10e.
- **Eval trên DB dùng chung `sme_ci` sai số:** `learning_store` có ~185 bài học từ run LLM giả lộ đáp án; chạy eval LLM thật trên `sme_ci_demo` sạch (`fresh_db.py` + `alembic upgrade head`) tới khi R11a sửa.
- **B1:** `metrics.py --write` (12/10) ra **2,20** cho audit 4, nhưng chỉ nhận R10d làm phạm vi (11 lỗ hổng / 5 task); đúng phải là R10d + R10b1 + R10b2 (19 task → ~0,58, vẫn > 0,5). Sửa cách `metrics.py` đọc phạm vi audit (P4).
- **pytest chập chờn:** đỏ 1/4 lần trên main trước đây, không bắt được tên test. Gặp lại thì ghi tên test.
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
- 2026-10-11 chiều → 12/10 rạng sáng: #126 (D2 thêm), #129 (plan R10b2), R10b1 #130, R10b2 #132, audit 4 #134; điều 3 chốt 67; A8 10/10; cổng 13/10 go (#135), tag `v0.1-e2e`.
- 2026-10-12 sáng → chiều: plan R10e #137, R10e #138 + hồ sơ #140 (tiếng Việt, `/config/domain`, H-32, H-34, H-66); đo nền LLM thật lần đầu (DB sạch 3/3); ADR-010; issue #139, #141 cho vai D; comment #63.
- 2026-10-12 tối → 13/10: tuần 97%, không chạy runner; điều 1 chốt 0; P8a sau freeze; quy tắc tên phiên; kế hoạch tổng thể tới Demo Day (tách R11a/R11c).
- Chi tiết trong `PROGRESS.md`.

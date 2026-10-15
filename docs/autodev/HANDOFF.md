# Bàn giao giữa các phiên supervisor

Mở phiên: `/session-start`. Đóng phiên: `/session-end` (cập nhật file này, PROJECT_STATE, bộ nhớ; PR + merge). Supervisor cũng cập nhật file này ở cuối mỗi mốc. Phiên supervisor mới đọc file này trước tiên, rồi `PROJECT_STATE.md`, `ROADMAP.md`, `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- **Hai plan lồng nhau:**
  - **Plan lớn** là xây plugin auto-dev (`docs/autodev/`, mốc **P1–P9**).
  - **Plan nhỏ** là dự án SME CI Agent (`TASKS.md` và `docs/PLAN.md`, mốc dự án **M0–M4**).
  - Mỗi **lần chạy auto-dev** là một mốc **R** (`plan/R4.md`…`plan/R10b2.md`): worker làm vài task TASKS.md, đồng thời kiểm chứng một khả năng của plugin. Mốc tên kết thúc bằng `h` là sửa nhanh, không tính vào `--audit-every`.
  - Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD. **Từ 15/10 (ADR-012):** dồn 100% vào auto-dev; SME CI Agent chỉ là dự án thử.
- **Phiên supervisor đóng vai leader kỹ thuật kiêm BA:**
  - lập plan, giao mốc, duyệt, merge, sửa plugin;
  - viết brief và issue cho team.

  Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15, `.claude/commands/supervise.md`.
- **Người dùng:** leader, nói tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa, báo ngắn gọn, giải thích khi hỏi "tại sao" hay "là gì" (**giải thích đơn giản trước**, chi tiết khi được hỏi thêm). Cuối mỗi báo cáo có câu hỏi "làm gì tiếp": danh sách **đánh số kèm nội dung**, leader trả lời bằng số.
- **Đo bằng số, không ước lượng:** % đạt 3 điều tính theo `docs/eval/criteria.md` (A1–A8, luật chỉ số nhiều phần); chỉ số plugin B1–B6 bằng `python3 .autodev/metrics.py`.

## Bước tiếp theo (cập nhật 2026-10-15 khuya: ĐÓNG BĂNG, ADR-013)

> **Repo này đóng băng.** Auto-dev phát triển tiếp ở `Silver-RP/autodev` (`~/dev/autodev`, private). Mở phiên ở thư mục đó; bàn giao mới nằm ở `~/dev/autodev/docs/HANDOFF.md` (sẽ viết lại ở phiên đầu tiên bên đó). Ở đây không chạy mốc R, không sửa plugin.

### Phiên 15/10 khuya (`leader-1015-tach-autodev`)
- Thử `/autodev-goal v0.2-gate` **huỷ** ở bước 3: leader không muốn phát triển auto-dev chung với SME CI nữa.
- Brainstorm → spec → plan → làm (superpowers). Leader chốt: plugin dùng lại cho các dự án của leader + phát triển riêng, sau ổn định mới công khai; `sme-ci-agent` đóng băng nguyên trạng; dự án thử mới `autodev-sandbox` (CLI todo nhỏ); lịch sử git mới; repo private; dạng plugin Claude Code.
- **autodev #2 merge** (Task 0–6 của `docs/superpowers/plans/2026-10-15-tach-autodev.md`): spike xác nhận hook plugin chạy headless, lệnh `/autodev:*` gọi được, `${CLAUDE_PLUGIN_ROOT}` được thay trong thân lệnh (không chắc trong thân agent); `paths.py`; runner `--plugin-dir`; lệnh và vai dùng chung; khuôn; `hooks/hooks.json`; `/autodev:init`. 162 test, CI `tests` xanh. Reviewer Opus: 4 Important đã sửa, 7 Minor để sau (ledger trong PR #2).
- #153 + #155 merge (superpowers bật trong `.claude/settings.json`).
- Còn lại của kế hoạch tách: **Task 7** (sandbox + tải thử, 2–4 USD) làm ở phiên mới trong `~/dev/autodev`; Task 8 = PR ADR-013 này.

### Bối cảnh trước khi tách (giữ để tra)
- **ADR-012:** dồn 100% vào auto-dev. Mục tiêu: leader chỉ đưa **mục tiêu và kết quả mong muốn**, auto-dev tự lo phần còn lại. SME CI Agent chỉ là dự án thử.
- **Leader chốt 15/10 (phiên phân tích, ghi trong ADR-012 mục 4–6):**
  - "xong" = B7 ≤ 1 can thiệp/mốc, B8 ≥ 80% mốc tự xong, USD/mốc; giữ B1 ≤ 0,5;
  - ngân sách = **chạy đến khi hết hạn mức**;
  - ADR-001 chỉ áp cho sản phẩm, không chặn auto-dev điều phối nhiều vai.
- **Phát hiện chính:** trong mốc đã gần tự chủ (R4–R10e: 3 lần runner dừng / 18 mốc). Việc tay nằm giữa và trên mốc: 93/127 PR từ 06/10 là `chore`.
- **ROADMAP (PR #150):** P10 → P11 supervisor tự lập plan → P12 vòng tự chạy (gộp phần P4 còn lại) → P13 hàng đợi câu hỏi + Telegram (gộp P7) → P8. P9 hoãn.
- **Đã xong trong phiên 15/10 tối (`leader-1015-p10-goal`, làm theo superpowers: brainstorming → writing-plans → executing-plans + TDD → reviewer Opus độc lập):**
  - **P10 merge #152:** lệnh `/autodev-goal` (không dùng `/goal`: trùng lệnh có sẵn của Claude Code), thiết kế mục 6.16, `plan/P10.md`, `.autodev/goal_check.py` (27 test), CI `goal-check` (đã chạy xanh trên GitHub). Leader chốt: mỗi mục tiêu một thư mục `docs/goals/<slug>/` (4 file), hỏi nhiều vòng như brainstorm (lần chạm trong lệnh không tính B7), **merge PR = duyệt**, lệnh được đọc cả kế hoạch có sẵn ("Kế hoạch lại 14/10" là đầu vào, không thử mù). Reviewer tìm 3 lỗi Important, đã sửa có test; 4 Minor để sau (ghi trong PR #152).
  - **#153 (mở):** luật dùng superpowers trong CLAUDE.md (ngoại lệ: phiên headless không brainstorm, không hỏi người; cho phép một reviewer cuối nhánh), ROADMAP thêm việc thử gắn skill vào vai developer/reviewer/supervisor khi chạy R11c → R11a → R11d.
  - Superpowers là plugin cấp người dùng trên máy leader (cài 04/10), nên R4–R10e đều chạy có nó, không lần nào dừng vì skill hỏi.
- **Classifier chế độ Auto** chặn Claude sửa **và cả commit** `.claude/settings.json` ("Self-Modification"), kể cả khi leader tự sửa file. Leader đã thêm `enabledPlugins` vào file này ở nhánh `chore/autodev-superpowers-team`, **chưa commit**. Cũng chặn commit/push từ clone scratchpad và `gh pr merge` dạng lệnh ghép (chạy `gh pr merge <n> --merge` thành lệnh riêng). Đoạn `settings.local.json` mới của phiên phân tích: chưa rõ leader đã dán chưa.
- Hạn mức: chưa có số mới; `usage-latest.json` cũ từ 11/10 (VS Code không chạy status line). Hỏi leader `/usage`.

### Làm tiếp theo thứ tự
1. **Chờ leader:** mở phiên mới ở `~/dev/autodev` (`/rename leader-<MMDD>-sandbox-autodev`), gửi 2 số `/usage` (5 giờ, tuần) và đồng ý 2–4 USD cho Task 7.
2. Task 7 (ở repo `autodev`): tạo `autodev-sandbox`, leader push commit đầu + `/plugin marketplace add ~/dev/autodev` + `/plugin install autodev@autodev`, `/autodev:init`, kiểm guard headless, `/autodev:autodev-goal` + một mốc qua runner.
3. Chép bộ nhớ dùng chung sang thư mục nhớ của `~/dev/autodev` (kế hoạch Task 8 Step 4) nếu chưa làm.
4. Sau đó P11 → P12 → P13 trong repo `autodev`.

Kế hoạch SME CI Agent cũ (ROADMAP "Kế hoạch lại 14/10"), chuỗi R11c → R11a → R11d: **huỷ** (ADR-013). Dọn nhánh/worktree cũ: chờ leader duyệt.

**Tín hiệu team** (`/session-start` vẫn kiểm): PR mới của thành viên → kiểm như trước, leader merge.

### Cách làm việc (sau ADR-011)
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Vùng file theo vai không còn giới hạn auto-dev.
- **API/hợp đồng:** đổi `docs/schema/events.json` vẫn qua PR riêng.
- **Chạy LLM thật:** leader/Claude, leader cho phép từng lần, ≤ 3 USD/lần; ghi `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).
- **PR của thành viên:** Claude kiểm phía backend, comment, approve; merge là quyết định của leader. Không merge PR draft.

## Trạng thái hiện tại (2026-10-15)
- **Dự án (dự án thử, ADR-012):**
  - M0–M3 xong; M4 4/6; tag `v0.1-e2e` (c60fec5);
  - 1028 passed trên main; **6 vitest dashboard đỏ trên main** (#139, R11d sửa);
  - % đạt 3 điều: **0 / 67 / 67**. Plan R11c, R11a, R11d trên main, chưa chạy.
- **Plugin:** P1–P3, P5, P6 xong; P4 tối thiểu xong (#147), phần để sau: hook `SubagentStop`, verify nhanh, `metrics.py` đọc phạm vi audit; **P10 `/autodev-goal` merge #152, chờ thử tải**; P11–P13 chưa làm; P7 gộp vào P13, P8 sau, P9 hoãn. `.autodev/tests`: 148 OK.
- **Runner:** rảnh (R10e xong 12/10). `audit.json` pending `["R10e"]`; chuỗi R11c → R11a → R11d dùng `--audit-every 4`.
- **Demo:** tắt. DB demo `sme_ci_demo` còn các run thử LLM thật của leader (xoá khi `--fresh-db` lần sau). Bật: `scripts/demo.sh --fresh-db` (thêm `SME_LLM=real` cho LLM thật, mở `/?source=live`); tắt: `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy.
- **PR mở:** #153 (superpowers cho team, `plugin-guard` xanh; chờ leader commit `enabledPlugins` rồi merge).
- **Worktree:** chính, `-autodev` (worker, nhánh `milestone/R10e`), `-supervisor` (nhánh `chore/autodev-r10e-review`). `-bench` tự dựng lại khi chạy `bench_reviewer.py`.
- **Nhánh của leader:** `main`, `plan/r11`, `plan/r11d`, `plan/replan-1014`, `chore/p4-min`, `chore/autodev-handoff-20261013/1014/1015/1015b/1015c`, `chore/autodev-p10-goal` (đã merge #152), `chore/autodev-superpowers-team` (#153), 2 nhánh R10e của worktree (dọn khi leader duyệt).

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
  **Chạy tiếp mốc đã có PR mở** (sau khi supervisor thêm task (b)): chạy runner như thường, không cần `--skip-merge-check`. Runner thấy PR mở, đưa worker lên `origin/milestone/<M>` bằng fast-forward (lệch nhánh thì dừng, mã 2), rồi kiểm PR đã merge và tự merge PR hồ sơ (P4, 14/10).
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
- **Điều 1 = 0:** đã có nền LLM thật (12/10, DB sạch 3/3 trên bài dễ); R11b (chấm theo mã, tập dev khó) + tập giữ lại niêm phong là đường để có số A1 trước freeze.
- **Cổng v0.2:** A1 trên tập giữ lại phải có số (chưa niêm phong được thì ghi giới hạn khi trình bày ra ngoài, điều 1 không báo quá 60%). H-32 đã sửa ở R10e.
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
- 2026-10-13 → 14/10 sáng: plan R11c + R11a (#144); ranh giới vai A: phần chồng D4/D5 sang R11b, mốc dự phòng D5 17/10; R11c chạy trước; dọn nhánh.
- 2026-10-14 tối → 15/10: ADR-011 (tiếp quản vai A/D/Q, gỡ mốc ngày, #146); P4 tối thiểu #147; plan R11d #148; phân tích + nghiên cứu thị trường (ngoài repo); **chuyển hướng ADR-012: dồn lực auto-dev**.
- 2026-10-15 chiều: phân tích khoảng cách; leader chốt thước đo, ngân sách (đến hết hạn mức), phạm vi ADR-001; ROADMAP P10–P13 (#150).
- 2026-10-15 tối: P10 `/autodev-goal` (#152, thiết kế 6.16, `goal_check.py`, CI `goal-check`); dùng superpowers cho mọi việc (#153, bộ nhớ).
- Chi tiết trong `PROGRESS.md`.

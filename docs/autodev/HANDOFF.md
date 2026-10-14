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

## Bước tiếp theo (cập nhật 2026-10-14 tối: lập lại kế hoạch, ADR-011)

### Bối cảnh
- **Leader chốt 14/10 tối (ADR-011):** leader + Claude/auto-dev **làm toàn bộ việc còn lại của vai A, D, Q**; bỏ mốc ngày cũ, xếp theo giá trị/chi phí, leader tự đặt ngày. Kế hoạch đầy đủ (phân tích, thứ tự 0–9, pre-mortem, thứ tự cắt): `docs/autodev/ROADMAP.md` mục "Kế hoạch lại 14/10".
- Ranh giới vai cũ (bộ nhớ `team-task-boundaries`) **hết hiệu lực**: auto-dev được sửa `dashboard/` (cả trình bày), `docs/research/`, `data/scenarios/`, `docs/qa/`.
- **Tập giữ lại** cho điều 1: phiên cách ly soạn, leader duyệt đáp án, lưu ngoài repo, SHA-256 niêm phong (`docs/eval/criteria.md` mục 1).
- Team (@bobbibao, @Finnng1104, @daivonpham) vẫn là collaborator. Daivon **đã nhận lời mời** (lệch với bàn giao sáng). Báo team: Claude soạn comment cho #63, #64, #65, #139, #141, **leader duyệt rồi Claude đăng**, sau đó bỏ gán, gán @Silver-RP. Issue đóng khi việc xong, không đóng ngay.
- Hạn mức: leader báo 14/10 22:40: 5 giờ 1%, tuần 0% (reset 14/10 13:00; lần sau 21/10 13:00).

### Làm tiếp theo thứ tự
1. **Chờ leader:** duyệt PR kế hoạch này; duyệt nội dung comment báo team.
2. **P4 tối thiểu** (phiên `leader-<MMDD>-sua-p4`, 30–45 phút, 0 USD API): runner chạy tiếp mốc đã có PR mở; worktree worker kéo commit supervisor; `/session-start` dùng `pgrep -fl 'autodev/run.py'`; `demo.sh` tự `yarn install`; supervisor chạy `.autodev/tests` trước khi merge PR hồ sơ. Để sau: hook `SubagentStop`, verify nhanh, `metrics.py` đọc phạm vi audit.
3. **Plan R11d** (giao diện, PR plan): #139 (6 vitest + lỗi nghĩa `n_after`/`min_units_after`), H-65 b/f/g, H-67, H-68, H-69, #141 (nhãn từ `/config/domain` của R11c, mã ở chú thích, chip, "trích nguyên văn", thuật ngữ); đối chiếu FR-06..12 với code thật (`dashboard/app/` đã có `kaizen`, `overview`, `audit`, `runs`); ảnh chụp Playwright 1920×1080 trong PR. Sửa phạm vi "Ngoài: dashboard (vai D)" trong `plan/R11c.md`, `plan/R11a.md` thành "R11d".
4. **Chuỗi 1** (runner chế độ B): `nohup .autodev/autodev-run.sh --audit-every 4 R11c R11a R11d` (~18–25 USD, ~8–10 giờ máy). `verify.py` đỏ `dashboard` tới khi R11d sửa #139 (lỗi đã biết). Sau chuỗi: `/usage`; đo A4/A5 LLM thật nếu leader cho (`eval_rootcause.py --until learn --llm real --seeds 3` trên DB sạch, ~1 USD), ghi `docs/token-cost.md`.
5. **Song song chuỗi 1, phiên chat** (không đụng file của mốc): D3 `docs/research/reflow_domain.md` (tìm web, có nguồn; nguồn cho 4 giả định điều 3, H-64), D5 `docs/research/scoring.md` (luật chấm theo mã, đúng một phần, đo độ khó; bảng gợi ý z 2–4σ, \|r\| ≤ 0,6, ≥ 2 nhiễu trùng thời điểm, bộ giải ngây thơ phải sai), định dạng kịch bản `docs/research/scenarios.md`. Leader duyệt PR.
6. **Tập giữ lại niêm phong** (phiên cách ly): chỉ đọc hợp đồng dữ liệu, D3, D5, định dạng; ≥ 4 kịch bản (≥ 1 `ask`, ≥ 1 `none`, ≥ 1 nhiễu trùng thời điểm); lưu ngoài repo; `docs/research/holdout-seal.md` ghi SHA-256; leader duyệt đáp án trước khi niêm phong.
7. **Plan R11b → chuỗi 2:** R11b (H-28 theo D5, loader + injector, tập dev khó ≥ 4 (H-29), eval A1–A3 DB sạch, lưu kết quả thô, chấm tập giữ lại có kiểm mã băm, ghi run phát lại, A8 LLM thật) → audit 5 (~13–19 USD). Rồi đo A1–A3 tập giữ lại LLM thật 3 seed (≤ 3 USD, leader cho phép).
8. **R12 → cổng v0.2:** lỗ hổng audit 5, H-60, H-61, H-62, H-64, D6, `docs/qa/responsible-ai.md`, `docs/qa/rehearsal-checklist.md`, biên bản `docs/qa/gate-v0.2-freeze.md`; leader tag `v0.2-freeze`.
9. **Leader làm tay:** bug bash bấm tay (T-045), diễn tập ≥ 2 lần, video dự phòng, slide trình bày, Q&A.

Cổng hạn mức: `/usage` sau chuỗi 1 và chuỗi 2; tuần ≥ 80% thì dừng, áp thứ tự cắt (ROADMAP) hoặc chờ reset 21/10.

**Tín hiệu team** (`/session-start` vẫn kiểm): PR mới của thành viên → kiểm như trước (test, demo, hợp đồng), leader merge; nếu trùng việc auto-dev đang làm thì leader chọn bản nào giữ.

### Cách làm việc (sau ADR-011)
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Vùng file theo vai không còn giới hạn auto-dev.
- **API/hợp đồng:** đổi `docs/schema/events.json` vẫn qua PR riêng.
- **Chạy LLM thật:** leader/Claude, leader cho phép từng lần, ≤ 3 USD/lần; ghi `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).
- **PR của thành viên:** Claude kiểm phía backend, comment, approve; merge là quyết định của leader. Không merge PR draft.

## Trạng thái hiện tại (2026-10-14 sáng)
- **Dự án:**
  - M0–M3 xong; M4 3/6 (T-040..T-042); T-043 (vai D), T-044, T-045 (vai Q) mở; cổng 13/10 go, tag `v0.1-e2e` (c60fec5);
  - 1028 passed trên main (R10e); **6 vitest dashboard đỏ trên main** (#139, vai D);
  - % đạt 3 điều: **0 / 67 / 67** (leader chốt điều 1 = 0 ngày 13/10).
- **Plugin:** P1–P3, P5, P6 xong; P4 đang làm (mục 2 "Làm tiếp"); P7–P9 chưa làm.
- **Runner:** rảnh (R10e xong 11:34 12/10; `audit.json` pending `["R10e"]`; mặc định 2 sẽ chạy audit ngay sau R11c, nên chuỗi R11c → R11a dùng `--audit-every 4` để audit 5 rơi vào sau R11b). Plan R11c, R11a đã trên main (#144).
- **Demo:** tắt. DB demo `sme_ci_demo` còn các run thử LLM thật của leader (xoá khi `--fresh-db` lần sau). Bật: `scripts/demo.sh --fresh-db` (thêm `SME_LLM=real` cho LLM thật, mở `/?source=live`); tắt: `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy.
- **PR mở:** không có (sau PR bàn giao này).
- **Worktree:** chính, `-autodev` (worker, nhánh `milestone/R10e`), `-supervisor` (nhánh `chore/autodev-r10e-review`). `-bench` tự dựng lại khi chạy `bench_reviewer.py`; `-d2` đã xoá.
- **Nhánh:** dọn 14/10; còn của leader: `main`, `plan/r11`, `chore/autodev-handoff-20261013`, `chore/autodev-handoff-20261014`, 2 nhánh R10e của worktree.
- **Hạn mức:** leader báo 14/10 22:40: 5 giờ 1%, tuần 0%; reset tuần sau 21/10 13:00.

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
- Chi tiết trong `PROGRESS.md`.

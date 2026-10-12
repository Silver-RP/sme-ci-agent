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

## Bước tiếp theo (cập nhật 2026-10-12 rạng sáng, đóng phiên: cổng 13/10 go, tag v0.1-e2e)

### R10e ✅ merge #138 (supervisor `--review-only`, 12/10; mới nhất, đọc trước)
- Worker 7/7 DONE, 8 vòng (dev-04 2 vòng). Supervisor tự chạy: **1028 passed**, smoke 4/4, `demo.sh --fresh-db --check` xanh; A4 theo nguyên nhân (LLM giả) `right` confirmed 5/5, `wrong` 0/5 (8 seed: 8/8, 0/8). Test H-32/H-34/H-66, #111, #114 đỏ trên main qua `git archive`. Bảng tiêu chí + pre-mortem: `PROGRESS.md` mục R10e. 287 phút / 200–270 (B3 1,06); 7,05 + ~1,19 USD / 9–11.
- Đóng **H-32, H-34, H-66**; H-65 còn (b, f, g) phía UI. Đóng issue #111, #114. Supervisor tick R10e trong TASKS.md (bỏ H-32 khỏi dòng R11a).
- **(c) supervisor quyết:** tiêu chí 1 ("verify sạch") tính đạt phần backend dù **6 vitest dashboard đỏ** (kỳ vọng cũ tiếng Anh, số phiên bản phụ thuộc DB dev); plan dev-07 cấm sửa `dashboard/tests` và pre-mortem 3 đã dự kiến. Giao vai D ở **#139** (gán Finn; kèm lỗi nghĩa "4270 / 6" ở thẻ thiếu bằng chứng, H-65 b/f/g, H-67..H-69). **Hệ quả:** `verify.py` của mốc kế sẽ báo `dashboard` đỏ "mới so với baseline" cho tới khi #139 merge → trước khi chạy R11a, hoặc chờ #139, hoặc ghi rõ trong plan R11a là lỗi đã biết.
- **Đề xuất (c) của worker chờ leader** (PR #138): (1) thêm trường `signal` vào Hypothesis + prompt + eval (LLM thật hiện luôn `unconfirmed`) → R11a; (2) `new_content` SOP của LLM giả còn tiếng Anh; (3) `demo.sh` cố định seed 42 cho báo cáo `/metrics`; (4) LLM thật trả tiếng Việt chưa kiểm (cần leader cho chạy LLM thật).
- Còn tiếng Anh tới dashboard (không do agent sinh): `limits` của `/metrics`, `reason` người gõ trong kịch bản `export_fixtures.py`.
- Mục 2 của "Làm tiếp theo thứ tự" dưới đây (mốc backend kế) **đã xong ở R10e**; việc kế là R11a (mục 3).

### Bối cảnh
- **Team 4 người** (`docs/PLAN.md` mục 4). Ranh giới: auto-dev không làm thay việc của vai A/D/Q, kể cả khi không đụng file của họ (**trùng việc** khác **trùng file**).

| Vai | Người | Issue mở | Trạng thái 12/10 |
|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63 (D3–D6) | D1, D2 (+ #126 bổ sung 5 bộ) đã merge. **D3** (`docs/research/reflow_domain.md`, nguồn cho 4 giả định điều 3, H-64) là việc kế, hạn tham khảo 14/10. Chưa trả lời 2 câu hỏi SOP ở #122 |
| D: giao diện | @Finnng1104 (Finn) | #64, #111, #114 | #116–#118 merge. Ô FR-01..05 trong #64 chưa tick. Cần báo: H-65..H-69 (audit 4), fixture sinh lại |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | **chưa nhận lời mời**; #65 chưa gán. T-044, T-045 (biên bản `demo-1.md`) của vai Q chưa có người |
| Backend, auto-dev | leader + Claude | #111 (H-34), #114 | `plan/Rx.md` |

- **Mốc tham khảo:** ~~cổng 13/10~~ (go 12/10); Đợt 2 UI 17/10; freeze 20/10 (tag v0.2-freeze); Pitch 24/10.

### Đã xong trong phiên 2026-10-11 chiều → 12/10 rạng sáng (PR #126, #129–#135, tag)
- **#126 (Bảo, 5 bộ D2 bổ sung):** review diff từng bộ với `valid/` + README + hợp đồng, approve; leader merge (classifier chặn Claude merge PR của thành viên).
- **#129:** R10b1 chạy trước khi #126 merge, nên plan R10b2 dev-07 thêm test tham số hoá trên mọi bộ `data/templates/invalid/` (37). Thực tế: test R10b1 đỏ trên main ngay sau #126 (5 bộ chưa có đáp án) → worker R10b2 làm dev-07 trước. **Bài học:** merge PR dữ liệu của team khi runner đang chạy thì chạy pytest trên main ngay sau đó.
- **R10b1 #130, R10b2 #132, audit 4 #134** (runner tự merge; chi tiết ở mục dưới và PROGRESS). Tổng chuỗi ~27,7 USD (ước tính 20–26).
- **Điều 3 chốt 67** (leader): tái diễn = 0 theo luật "đạt theo cấu tạo"; tỷ lệ lỗi và MTTD/MTTR tính 1; cờ H-64 chờ D3.
- **A8 đo 12/10:** `demo.sh --fresh-db --check --repeat 10` → 10/10, p95 0,8 s. Lần đầu trượt ở dashboard: `dashboard/node_modules` thiếu thư viện từ #116 → `yarn install --frozen-lockfile`, rồi leader tự xoá `dashboard/.next` (Turbopack giữ lỗi cũ; guard chặn `rm -rf`).
- **Cổng 13/10 go** (#135, `docs/qa/gate-v0.1-e2e.md`): A4 tính đạt theo chữ, **H-32 phải sửa trước freeze**. **Tag `v0.1-e2e`** trên c60fec5 (tạo từ clone scratchpad vì guard chặn thao tác trên nhánh main).
- **#114:** comment cho Finn: làm sau R10b1, máy/ca đọc từ `plant.*` của config.
- **Guard:** leader **không** thêm duyệt xoá một lần; giữ nguyên.
- **Leader xem demo mức 1** (LLM giả): câu chữ hiện ra dashboard là **tiếng Anh** (ví dụ `question_asked` "Top hypothesis (…) has confidence 0.20, below 0.60…", chuỗi cứng `backend/agent/nodes/ask.py:56,60`). Ảnh leader gửi có thể là trang phát fixture (`run-happy.json`, nút "(mô phỏng)"), không phải run live: kiểm nhãn chế độ.

### R10b1 ✅ #130 · R10b2 ✅ #132 · audit 4 ✅ #134
- **R10b1:** 7/7, 8 vòng; 267 phút / 175–240; 9,10 + ~2,10 USD. 31/31 bộ D2 đúng mã. pytest + Postgres ~20 phút mỗi lần đầy đủ (máy i5-8279U, 8 GB, Docker trên Intel) là phần lớn thời gian (~86% thời gian worker là chạy cục bộ, không phải chờ API).
- **R10b2:** 7/7, 8 vòng; 350 phút / 195–255; 8,76 + 2,23 USD. Đóng H-11, H-33, H-39. Fixture R10b1 trùng bộ D2: không có. `risk_checks.mock_only` của reviewer bắt lỗi dev-03 (suite xanh nhờ `conftest` tắt tính năng mới).
- **Audit 4** (`docs/audits/2026-10-12.md`, 5,51 USD): H-60..H-74 (1 cao H-64), đóng H-35, H-44, H-46, còn 31 mở. Lệch hướng: điều 1 vẫn 0; chưa lần LLM thật nào.
- **Plugin:** hook `SubagentStop` **không chạy** ở phần lớn task R10b2 (và dev-04 v1, dev-06 R10b1); supervisor tự chạy `verify.py` thay.
- **Đề xuất (c) chờ duyệt** (PR #130, #132): số phiên bản SOP trong fixture phụ thuộc DB dùng chung; `data_report.py`, `eval_rootcause.py`, `export_fixtures.py` chưa đọc `SME_DATASET`; `eval_rootcause.py` mặc định crash `ScriptExhaustedError` khi DB đã có `learning_saved`; `/metrics` chưa kiểm `months`; test D2 trùng một phần `D2_EXPECTED`.

### Làm tiếp theo thứ tự
1. **Chờ leader:**
   - (a) Duyệt phạm vi **mốc backend kế** (mục 2): "duyệt" / sửa danh sách.
   - (b) Đo nền LLM thật (`eval_rootcause.py --llm real --seeds 3`, ≤ 2 USD): "chạy" / "để sau". Cần cho điều 1 và để biết agent thật làm tới đâu.
   - (c) Đo pytest chậm (`--durations=20`, ~20 phút, 0 USD): "đo" / "bỏ".
   - (d) Xoá worktree `../sme-ci-agent-d2`: leader tự chạy `git worktree remove ../sme-ci-agent-d2`.
   - Không nhắc trong báo cáo: nhắc Bảo/Daivon, giờ kickoff, ROADMAP nghiên cứu (bộ nhớ `skip-team-reminders`).
2. **Mốc backend kế (leader yêu cầu 12/10), plan mở PR:**
   - **Câu chữ cho người dùng bằng tiếng Việt:** chuỗi cứng tiếng Anh ở `ask.py` (và kiểm `improve.py`, câu "chưa đủ bằng chứng" của Measure, halt, lý do rollback) → lấy từ domain config (`data/context_profile.yaml`), không hard-code; prompt LLM yêu cầu trường hiển thị (giả thuyết, câu hỏi, đề xuất) bằng tiếng Việt. Code, khoá, tên trường giữ tiếng Anh. Sinh lại `docs/schema/examples/` + `dashboard/fixtures/examples/` (gộp H-66).
   - **Issue của Finn:** #114 `GET /config/domain` (nay làm được: `plant.*` có sau R10b1; hình dạng chốt ở comment #114), #111 (H-34).
   - **H-32** (A4 không được đạt theo cấu tạo; phải xong trước freeze), **H-65** (`/metrics` ghi rõ LLM giả, `limits`).
   - Sau đó báo Finn H-65..H-69 (UI) kèm ví dụ mới.
3. **R11a** (điều 1, đang 0): H-28, H-29, H-56 (gộp H-18), H-63, H-36, H-52, H-53, H-55; kịch bản `ask` và `none`; treo từ R10ch: bản SOP trùng nếu kill giữa commit và checkpoint. Có thể gộp phần nhỏ của mục 2 nếu leader muốn.
4. **Sửa plugin (P4, giữa hai mốc):**
   - hook `SubagentStop` không chạy ổn định;
   - runner không chạy tiếp được mốc đã có PR mở (`new_milestone_pr` chỉ nhận PR mới);
   - worktree worker không kéo commit (b) supervisor đẩy lên nhánh mốc;
   - supervisor phải chạy `.autodev/tests` trước khi merge PR hồ sơ (#125);
   - `/session-start` kiểm runner bằng `pgrep -fl 'autodev/run.py'` (`autodev-run` không khớp);
   - tăng tốc verify (chạy test chọn lọc trong vòng TDD, đủ bộ một lần trước review; hoặc `pytest-xdist` với DB tách) — chờ số đo mục 1(c);
   - `demo.sh`: tự `yarn install` khi `dashboard/package.json`/`yarn.lock` đổi.
5. **Reviewer:** đo luật xếp mức trên ≥ 5 ca mới từ audit 4, mỗi ca 3 lần; hỏi leader trước; sau reset hạn mức tuần (14/10).
6. **Plugin sau v0.1:** P9 (reviewer cho PR của team, chỉ comment), P7a Telegram một chiều.

**Tín hiệu team còn lại** (`/session-start` kiểm):
| Tín hiệu | Việc đầu tiên |
|---|---|
| Daivon nhận lời mời | Gán #65 bằng tay (`gh issue edit 65 --add-assignee daivonpham`); vai Q chạy đo nền LLM thật (≤ 2 USD, leader cho phép từng lần); T-044, T-045. |
| Issue nhãn `api` mới | Backend trả lời trong ngày (không tính là chạy mốc). |
| PR mới của Finn/Bảo | Kiểm phía backend (test, demo, đối chiếu hợp đồng), comment, approve; leader merge. Sau merge chạy pytest trên main nếu PR đổi dữ liệu test. PR draft thì không merge. |
| Bảo trả lời câu hỏi SOP ở #122 / nộp D3 | SOP: khác đề xuất thì sửa ở mốc sau. D3: cập nhật `source` của 4 giả định, chạy lại `metrics_report.py`, xét lại % điều 3. |

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

## Trạng thái hiện tại (2026-10-12 rạng sáng)
- **Dự án:**
  - M0–M3 xong; M4 3/6 (T-040..T-042); T-043 (vai D), T-044, T-045 (vai Q) mở; **cổng 13/10 go, tag `v0.1-e2e`** (c60fec5);
  - 936 passed trên main (R10b2);
  - % đạt 3 điều: **0 / 67 / 67** (điều 3 leader chốt).
- **Plugin:** P1–P3, P5, P6 xong; P4 đang làm (mục 4 "Làm tiếp"); P7–P9 chưa làm.
- **Runner:** rảnh (chuỗi R10b1 → R10b2 → audit 4 xong 00:58 12/10).
- **Demo:** tắt. Bật bằng `scripts/demo.sh --fresh-db`; tắt bằng `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy.
- **Docker Desktop** đã tắt lúc nào đó sau khi runner xong (chưa rõ lý do); Claude bật lại 12/10 (`open -a Docker`, `docker start sme-ci-agent-autodev-db-1`).
- **PR mở:** không có (sau PR bàn giao này).
- **Worktree:** chính, `-autodev` (worker), `-supervisor`, `-bench` (cố định), `-d2` (chờ leader xoá).
- **Hạn mức:** số liệu cuối 13:45 11/10 (5 giờ 1%, tuần 71%); chuỗi runner sau đó ~27,7 USD → hỏi leader `/usage` đầu phiên sau. Reset tuần 13:00 14/10.

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
- **Điều 1 = 0:** chưa lần đo LLM thật nào; R11a + đo nền LLM thật là đường duy nhất để có số trước freeze.
- **Freeze 20/10:** H-32 phải sửa; A1 trên tập giữ lại phải có số (thiếu đề của vai A thì ghi giới hạn khi pitch, điều 1 không báo quá 60%).
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
- Chi tiết trong `PROGRESS.md`.

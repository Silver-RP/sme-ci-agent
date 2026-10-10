# Bàn giao giữa các phiên supervisor

Mở phiên: `/session-start`. Đóng phiên: `/session-end` (cập nhật file này, PROJECT_STATE, bộ nhớ; PR + merge). Supervisor cũng cập nhật file này ở cuối mỗi mốc. Phiên supervisor mới đọc file này trước tiên, rồi `PROJECT_STATE.md`, `ROADMAP.md`, `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- **Hai plan lồng nhau:**
  - **Plan lớn** là xây plugin auto-dev (`docs/autodev/`, mốc **P1–P8**).
  - **Plan nhỏ** là dự án SME CI Agent (`TASKS.md` và `docs/PLAN.md`, mốc dự án **M0–M4**).
  - Mỗi **lần chạy auto-dev** là một mốc **R** (`plan/R4.md`…`plan/R9ih.md`): worker làm vài task TASKS.md, đồng thời kiểm chứng một khả năng của plugin. `plan/M1.md`–`M3.md` thực chất là R1–R3.
  - Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD.
- **Phiên supervisor đóng vai leader kỹ thuật kiêm BA:**
  - lập plan, giao mốc, duyệt, merge, sửa plugin;
  - viết brief và issue cho team.
  
  Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15, `.claude/commands/supervise.md`.
- **Người dùng:** leader, nói tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa, báo ngắn gọn, giải thích khi hỏi "tại sao". Hỏi "tiếp theo làm gì" thì trả lời bằng danh sách ưu tiên: việc của người dùng trước, việc Claude làm song song sau.

## Cập nhật sau R10c (2026-10-10 chiều, supervisor `--review-only`)
- **R10c merge (PR #84):** run/event/checkpoint vào Postgres (sống qua restart), khoá SOP theo `base_version`, `question_id` cho câu hỏi, audit mọi quyết định, `tests/test_invariants.py`. Đóng H-14, H-15, H-19, H-20, H-37, H-38. 553 pytest + 1 xfail. Worker 7/7 PASS vòng 1, ~115 phút, 5,81 USD (trong ước tính: B3 ≈ 1,0).
- Supervisor tự kiểm 4 tiêu chí cấp mốc (bảng trong PROGRESS), tự tắt luật duyệt để chứng minh test bất biến bắt được, chạy test mới trên code main (đỏ), và 3 ca biên qua API (xung đột SOP, restart lúc đang hỏi, duyệt lại run đã xong): đều đúng. A6 = 0 vi phạm → điều 2 = 50%.
- **Cho vai D (#64):** `pending` câu hỏi có `question_id`, `attempt`; `POST /answer` nhận `question_id` tuỳ chọn (cũ → 409); `approval_decided.decision` có `sop_conflict`; `rollback_done` có thể `rolled_back: false`. Ghi trong `docs/schema/payloads.md`. Chưa ghi: action audit mới `answer_received`, `halt_raised`, `kpi_not_measured` (việc nhỏ cho R10b1/R10b2).
- **Phải nhớ ở R10b2:** đóng H-39 thì gỡ `xfail(strict=True)` của `test_no_model_name_in_backend` (strict nên sẽ tự báo đỏ khi hết vi phạm).
- **Hạn chế đã biết (không chặn demo):** sau restart `retries` về 0, `steps` của `/export` mất; `DB_POOL_SIZE` không phải số ném ValueError không rõ nghĩa.
- **Việc kế tiếp:** audit 3 (runner `--audit-every 2` tự chạy sau R10a + R10c, đo B1) → R10b1 (sau D1 #66) → R10b2 → tag v0.1-e2e 13/10 (leader duyệt). Cột phút R10c trong bảng `metrics.py` = 0 vì runner chưa ghi xong `run.log` lúc supervisor chạy: phiên sau chạy lại `python3 .autodev/metrics.py --write`.

## Cập nhật sau R10a (2026-10-10 trưa, supervisor `--review-only`)
- **R10a merge (PR #82):** `GET /runs`, `/runs/{id}/export`, `/kpi/series`, `/audit`, `/sop/{id}/versions`, `/metrics` (chỉ số chưa có nguồn để `available: false`); `scripts/record_run.py`; `scripts/check_run.py` + `demo.sh --check [--repeat N]` đi hết một run; LLM giả đi mọi nhánh, `SME_DEMO_SCENARIO=rollback` cho S7. Đóng H-13, H-16, H-26; T-041 tick. 504 pytest.
- Supervisor tự kiểm 5 tiêu chí cấp mốc (bảng trong PROGRESS), kể cả reject/revise/halt/rollback qua uvicorn thật (worker chưa kiểm). A5 (a) 1,00, (b) 1,00 (LLM giả, 5 seed); A8 10/10, p95 0,4 s. Ước tính ↔ thực tế: 73/55–75 phút, 4,00 USD worker, 1,0 vòng/task: B3 = 1,0.
- Cho vai D: API mới mô tả trong `docs/schema/payloads.md`; báo Finn (#64) có thể nối FR-07, FR-09..12.
- **Việc kế tiếp:** R10b1 (plan đã merge #80) → R10b2 → R10c → audit 3 → tag v0.1-e2e 13/10 (leader duyệt). Đề xuất của worker (không đổi phạm vi): `/metrics` thêm `outcome` cho lesson `no_change` (R10b2); kiểm reject/revise/halt qua uvicorn trong `demo.sh --check` (tuỳ chọn). Plugin: `metrics.py` nên in "–" thay vì 0 cho mốc chưa chạy.
- Số liệu `metrics.py` lấy từ `.autodev/runs/` của repo chính (supervisor chép sang worktree supervisor để chạy `--write`; thư mục này bị gitignore).

## Bước tiếp theo (cập nhật 2026-10-10, đóng phiên)

### Bối cảnh mới: team 4 người
Ngày 2026-10-09, sau T-030, người dùng **tạm dừng thêm tính năng** để chuẩn hoá dữ liệu đầu vào và làm giao diện demo trực quan, trước khi lập kế hoạch dài hạn (P6). Phân vai (`docs/PLAN.md` mục 4):

| Vai | Người | Issue | Brief | Việc gấp |
|---|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63 | `docs/briefs/data-research.md` (D1–D6) | #66 D1 chốt hợp đồng dữ liệu, chặn phần dữ liệu của R10 |
| D: giao diện | @Finnng1104 (Finn) | #64 | `docs/briefs/frontend.md` (FR-01..12, NFR-1..7) | #67 FR-01 sửa H-44 |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | `docs/briefs/qa.md` (Q1–Q7) | ca kiểm thử FR-01..05 + D1; bug bash; demo nội bộ #1 (T-045) |
| Backend, auto-dev | leader + Claude | | `plan/Rx.md` | R10a |

Tài liệu chung, đã merge (PR #62, #68):
- `docs/schema/data_contract.md`: hợp đồng v0.1. **Leader đã duyệt cả 3 câu hỏi mục 6** ngày 10/10: số đếm `production_log`; `material_batches` thay `inventory` + `supplier`; `environment_log` + `training_level` sang R11.
- `docs/demo-storyboard.md`: S0–S9, đặc tả màn hình, 4 API mới.
- `docs/research/data_realism.md`: dữ liệu hiện sơ sài; SOP chuẩn; kaizen/yokoten.
- `docs/onboarding-claude.md`: cài đặt, vai nào cần key, lệnh mở đầu theo vai, việc được và không được.

Mốc tham khảo trong brief (ngày trong `[...]` là đề xuất, chốt ở kickoff):
- kickoff: 11/10;
- demo nội bộ #1 và v0.1-e2e: 13/10;
- Đợt 2 giao diện: 17/10;
- freeze: 20/10;
- Pitch Day: 24/10.

### Đã xong trong phiên 2026-10-09 → 10
- **T-030 xong:** vòng LLM thật khép kín, KPI 6,3% → 2,1%, qua R9h (#49), R9i (#55), R9ih (#58).
  - Lỗi ghi trong `docs/decisions.md` mục "Việc cần sửa sau khi chạy".
  - Eval thật 50%, có thể do chấm theo chuỗi (H-28).
  - Dashboard không hiện thẻ đề xuất: H-44, giao vai D.
- **Audit 2:** `docs/audits/2026-10-09_2.md` (H-27..H-44).
- **GitHub:**
  - nhãn `role:data|frontend|qa`, `api`, `sev:1–3`, `area:data|ui|backend`;
  - issue #63–#67, đầu mỗi issue có "Bắt đầu nhanh" (link onboarding + lệnh mở đầu);
  - 3 bạn được **mời quyền Write**, chưa nhận lời lúc đóng phiên.
- **Bảo vệ `main`** (áp dụng cả admin):
  - bắt buộc qua PR, 0 người duyệt;
  - bắt buộc check `plugin-guard`;
  - cấm force-push và xoá nhánh.
- **`plugin-guard`:**
  - file `.github/workflows/plugin-guard.yml` + `.github/CODEOWNERS`;
  - chạy kiểu `pull_request_target`, không checkout code PR;
  - chỉ @Silver-RP được sửa `.claude/`, `.autodev/`, `docs/autodev/`, `.github/`.
  
  Nhánh xanh đã chạy thật (#69). Nhánh chặn (PR của thành viên) **chưa thử**: kiểm ở PR đầu tiên của team.
- **Chờ check trước khi merge:** `run.py` có `wait_required_checks` (#69), `/supervise` cũng được dặn chờ. Merge tay: `gh pr checks <số> --required --watch` rồi `gh pr merge <số> --merge`.
- **Lệnh mở/đóng phiên cho leader:** `/session-start` (chỉ đọc: bàn giao + trạng thái thật → báo việc tiếp) và `/session-end` (cập nhật bàn giao, PR, merge). PR #72, #73; tên tiếng Anh theo ý người dùng. Lần chạy thật đầu: `/session-end` của phiên này (PR bàn giao kèm theo). `/session-start` **chưa chạy thật**; phiên sau là lần đầu, gặp chỗ chưa ổn thì sửa lệnh.
- **Dọn dẹp** (người dùng duyệt, PR #71): đã xoá thư mục `red`, 4 thư mục lịch sử Claude ở đường dẫn Desktop, thư mục `sme-ci-agent` cũ ở Desktop.
- Lúc đóng phiên: 3 lời mời **vẫn chờ** nhận; chưa có comment hay PR nào của team; runner và demo không chạy; không có PR mở.

### Làm tiếp theo thứ tự
1. **Chờ người dùng:**
   - (a) nhắn nhóm chat để 3 bạn nhận lời mời và đọc issue (người dùng tự gửi);
   - (b) chốt giờ kickoff 11/10;
   - (c) duyệt hay không `demo.sh --fresh-db`: DB demo sạch mỗi lần, xoá dữ liệu demo cũ trong Postgres. `sop_versions` đang lên v41 cho SOP-RFL-001, SOP-INJ-001 có 18 bản;
   - (d) nói "bắt đầu R10a".
2. **Khi 3 bạn đã nhận lời mời** (kiểm bằng `gh api repos/Silver-RP/sme-ci-agent/collaborators`), gán issue:
   - #63, #66 → bobbibao;
   - #64, #67 → Finnng1104;
   - #65 → daivonpham.
   
   Trước khi họ nhận lời, `gh issue edit --add-assignee` không báo lỗi nhưng cũng không có tác dụng.
3. **R10a** (không chờ D1, để vai D không bị kẹt API):
   - 4 API của storyboard: danh sách run (FR-12), tổng quan KPI (FR-09), nhật ký + phiên bản SOP (FR-11), phiếu kaizen + 3 chỉ số (FR-10). Xem `docs/demo-storyboard.md` và `docs/briefs/frontend.md` mục 7;
   - T-041 ghi/phát lại run (cho FR-07);
   - H-13, H-16, H-26.
   
   Viết `plan/R10a.md`, mở PR cho người dùng xem phạm vi, rồi chạy runner. Auto-dev **không** sửa phần trình bày trong `dashboard/` (vai D làm).
4. **R10b, sau khi D1 (#66) được duyệt:**
   - `production_log` số đếm, `material_batches`;
   - `scripts/import_data.py` + validator V01–V09, `data/templates/`;
   - simulator nhị thức;
   - H-11 / T-042 (chỉ số 3 tính từ `production_log`);
   - các mục nhỏ còn treo: `ALLOWED_MSGPACK_MODULES` cho checkpointer, tiền tố model không hỗ trợ effort chỉ khớp `claude-haiku-4-5`, `parse_bool("maybe")`, bỏ `fix_addresses_cause`, "M02" trong `fake_metrics.py`, H-39.
5. **R11, sau D4 + D5 của vai A:** kịch bản khó, eval chấm theo mã nguyên nhân (H-28, H-29, H-32, H-36, H-18), `environment_log` + `training_level`.
6. **P6, sau demo nội bộ #1 (13/10):** kế hoạch dài hạn, dựa trên biên bản go/no-go của vai Q. Sau R10 là audit 3, rồi tag v0.1-e2e (người dùng duyệt).
7. **Trang trạng thái Artifact** (P5 còn lại): đã đề xuất, người dùng chưa trả lời.
8. **Để sau v0.1-e2e:**
   - H-14, H-15 (checkpointer Postgres), H-19, H-20, `tests/test_invariants.py`;
   - P7 (Telegram hai chiều + API trạng thái), log stream-json, P8.

### Cách làm việc với team
- **Chỉ leader/Claude chạy auto-dev** (`/run-milestone`, `/supervise`, `/audit`). Team dùng Claude Code trên máy riêng, trong vùng của vai:
  - A: `docs/schema/data_contract.md`, `docs/research/`, `data/templates/`, `data/scenarios/draft/`;
  - D: `dashboard/`;
  - Q: `docs/qa/`, `docs/token-cost.md`.
- **API mới:** vai D mở issue nhãn `api`; backend trả lời trong ngày. **Đổi `docs/schema/events.json`:** PR riêng, báo trong sync.
- **Chạy LLM thật:** chỉ vai Q, ngân sách ≤ [2] USD/ngày, leader cho phép từng lần; ghi chi phí vào `docs/token-cost.md`.
- **Repo đang public:** không đưa email hay thông tin cá nhân của thành viên vào issue, tài liệu hay commit.
- **Claude của thành viên không có quyền tự merge** (quyền đó nằm trong `settings.local.json` của máy leader).

## Trạng thái hiện tại (2026-10-10)
- **Dự án** (TASKS.md):
  - M0–M3 xong; T-030 tick 10/10;
  - M4: T-040 xong; T-041..T-045 mở.
  - Sau R9ih: hơn 412 pytest, 56 test plugin; verify và smoke sạch.
- **Plugin:**
  - P1–P3 xong;
  - P4 (chế độ B): chờ hạn mức đã kiểm chứng thật ở R9;
  - P5: audit, `PROJECT_STATE`, `LESSONS`, đã chạy 2 audit.
  - Chi phí worker + supervisor: R4 ≈ 2,29; R5 ≈ 3,01; R6 ≈ 1,81; R7 ≈ 2,58; R8 ≈ 6,40; R9 ≈ 7,18; R9h ≈ 1,15; R9i ≈ 1,60; R9ih ≈ 0,64 USD.
- **Demo:** không chạy lúc đóng phiên. Bật bằng `scripts/demo.sh`; tắt bằng `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt trước khi chạy mốc R mới, vì smoke `demo.sh --check` cần 2 cổng này.

## Môi trường
- **Repo:** `~/dev/sme-ci-agent/` chứa 3 worktree cạnh nhau:
  - `sme-ci-agent` (chính);
  - `sme-ci-agent-autodev` (worker);
  - `sme-ci-agent-supervisor` (supervisor).
  
  Repo GitHub `Silver-RP/sme-ci-agent` (public). Tài liệu hackathon ở `~/Desktop/Projects_VSCode/Vietnam Japan AI Hackathon 2026/`.
- **Postgres:** container `sme-ci-agent-autodev-db-1`, cổng 5432 (user/pass/db synthetic `sme`/`sme`/`sme_ci`). `demo.sh` dùng lại DB đang chạy nếu kết nối được.
- **Node 22.23.3** (`nvm alias default 22`, yarn 1.22). Shell cũ có thể còn PATH 22.12, nên luôn đặt `PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH` khi khởi chạy runner.
- **Shell của người dùng** có thể còn venv cũ ở Desktop (cảnh báo `VIRTUAL_ENV`); khuyên `deactivate`.
- **LLM thật:** người dùng tự điền `.env` (`ANTHROPIC_API_KEY`, `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_CHEAP=claude-haiku-4-5-20251001`, `LLM_EFFORT=medium`). Agent không bao giờ đọc file này. Hỏi trước mỗi lần chạy `--llm real` (tốn credit API).
- **Chạy mốc** (từ repo chính, sau khi `plan/Rx.md` đã merge lên main):
  ```bash
  export PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH AUTODEV_SUPERVISOR_MODEL=opus AUTODEV_SUPERVISOR_EFFORT=medium
  nohup .autodev/autodev-run.sh R10a > .autodev/runs/nohup.out 2>&1 &
  ```
  Ngay sau đó, bằng Bash `run_in_background`, chạy vòng `until` chờ "Hoàn tất|STOP" trong `.autodev/runs/run.log`, để phiên chat được báo khi xong.
- **Theo dõi:** `.autodev/watch.sh` (người dùng chạy trong terminal).
- **Chế độ Auto** đôi khi lỗi "classifier no verdict" ở phía máy chủ. Khi đó người dùng tạm chuyển chế độ quyền.

## Quyền và quy tắc đang áp dụng
- **Merge:**
  - Supervisor tự merge PR mốc sau khi tự chạy verify + smoke + bảng tiêu chí + **chờ check `plugin-guard` xanh**. Worker không merge.
  - PR hồ sơ chỉ sửa `docs/autodev/**` (và `docs/audits/**`) thì runner tự merge.
  - Phiên tương tác được tự merge PR của mình (người dùng cho phép 2026-10-09; quy tắc trong `.claude/settings.local.json`, không commit).
- **Không đẩy thẳng `main`:** GitHub chặn, guard cũng chặn.
- **Không xoá** file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt. Merge không kèm `--delete-branch`.
- **Không đọc hay in `.env`.** Guard so khớp theo chữ:
  - câu chữ trong commit/tài liệu nhắc tới lệnh cấm cũng bị chặn;
  - sửa file tại chỗ bằng sed và script Python qua stdin (heredoc) cũng bị chặn.
  
  Gặp trường hợp này thì dùng Edit/Write tool.
- **Tầng tầm nhìn** (thứ tự mốc, cắt việc) luôn do người dùng duyệt. Kiến trúc trong ADR cố định.
- **Không đổi tiêu chí chấp nhận trong brief** khi chưa hỏi leader. Phiên bản thay đổi ghi ở mục "Lịch sử thay đổi yêu cầu" của brief.

## Việc mở / cần để ý
- **Lỗ hổng dự án:** PROJECT_STATE mục "Lỗ hổng mở" (nguồn `docs/audits/2026-10-09_2.md`).
- **pytest chập chờn:** đỏ 1/4 lần trên main, không bắt được tên test. Gặp lại thì ghi tên test.
- **LangGraph cảnh báo** "Deserializing unregistered type …Hypothesis": đưa vào R10b.
- **Dọn dẹp:** xong 2026-10-10, người dùng duyệt. Đã xoá thư mục rỗng `red`, 4 thư mục lịch sử Claude ở đường dẫn Desktop, thư mục `sme-ci-agent` cũ ở Desktop. Không còn mục nào chờ dọn.
- **Để sau** (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh.

## Lịch sử ngắn
- P1–P3 xong; R4–R9ih chạy bằng chế độ B, tất cả merge.
- 2026-10-08: chuyển repo khỏi iCloud; hardening + R8.
- 2026-10-09: P5, audit 1–2, R9, R9h, R9i, R9ih, T-030 khép vòng LLM thật.
- 2026-10-10: tạm dừng tính năng; hợp đồng dữ liệu, storyboard, brief A/D/Q, issue #63–#67, onboarding, bảo vệ `main` + `plugin-guard`; dọn thư mục cũ; lệnh `/session-start`, `/session-end`.
- Chi tiết trong `PROGRESS.md`.

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

## Bước tiếp theo (cập nhật 2026-10-12 chiều, đóng phiên: R10e xong, đo nền LLM thật, ADR-010)

### Bối cảnh
- **Team 4 người** (`docs/PLAN.md` mục 4). Ranh giới: auto-dev không làm thay việc của vai A/D/Q, kể cả khi không đụng file của họ (**trùng việc** khác **trùng file**).

| Vai | Người | Issue mở | Trạng thái 12/10 chiều |
|---|---|---|---|
| A: dữ liệu, kịch bản | @bobbibao (Bảo) | #63 (D3–D6) | D1, D2 merge. Việc kế: D3 (`docs/research/reflow_domain.md`, nguồn 4 giả định điều 3, H-64), D4 (≥ 4 kịch bản). Comment 12/10 ở #63 làm rõ dạng bàn giao D4/D6: YAML + **đáp án theo mã**, hoặc bộ CSV ≥ 42 ngày qua `import_data.py --check-only`. Chưa trả lời 2 câu hỏi SOP ở #122 |
| D: giao diện | @Finnng1104 (Finn) | #64, #139, #141 (gán) | #139: 6 vitest đỏ trên main sau R10e (kỳ vọng tiếng Anh cũ) + H-65 b/f/g, H-67..H-69. #141: ADR-010 (nhãn từ `/config/domain`, chú thích mã, kiểu "trích nguyên văn") |
| Q: kiểm chứng | @daivonpham (Daivon) | #65 | **chưa nhận lời mời**; #65 chưa gán. T-044, T-045 chưa có người. `docs/token-cost.md` (vùng vai Q) chưa có: chi phí LLM thật ghi tạm ở PROJECT_STATE |
| Backend, auto-dev | leader + Claude | | `plan/Rx.md` |

- **Mốc tham khảo:** Đợt 2 UI 17/10; freeze 20/10 (tag v0.2-freeze); Pitch 24/10.

### Đã xong trong phiên 2026-10-12 sáng → chiều (PR #137, #138, #140; issue #141)
- **Plan R10e #137** (leader duyệt phạm vi; classifier chặn Claude merge, leader merge). **R10e #138** runner + supervisor `--review-only`, hồ sơ #140: 7/7, 313 phút, 9,49 USD (ước 9–11). Đóng H-32, H-34, H-66, #111, #114 (chi tiết: PROGRESS mục R10e, `.autodev/reports/R10e.md`).
- **Đo nền LLM thật lần đầu** (leader cho chạy, `eval_rootcause.py --llm real --seeds 3`):
  - DB dùng chung `sme_ci`: bảng 67%, nhưng đọc tay cả 3 run đều đúng `wrong_setpoint`. Sai do (1) chấm theo chữ: LLM viết tiếng Việt, không ghi nguyên mã (H-28); (2) DB có 185 bài học từ run LLM giả, agent đọc được ("các trường hợp trước…") và cả 3 run điều tra A2 (M01) thay vì A1.
  - DB sạch (`fresh_db.py` → `sme_ci_demo`, `alembic upgrade head`): **3/3**, đúng A1 (M02, 10/3), hỏi 0%, ~41k token. Lý do và SOP mới tiếng Việt. Chi phí cả hai lần ~0,4 USD (ước từ token).
  - Đọc đúng: bài dễ, 3 seed chỉ đổi nhiễu (cùng máy, giờ, ~10σ) → chưa phải A1 tập giữ lại; % điều 1 giữ 0.
- **Phân tích seed 42** (sinh trong bộ nhớ): anomaly z 9–11 từ ca đầu, giữ tới hết dữ liệu; `zone3_setpoint_c` chỉ đổi 2 lần = đúng 2 anomaly (67 lần đổi khác là zone2/other); `correlate` wrong_setpoint r ≈ 0,95, material_batch ≈ 0,01–0,08, 7/9 giả thuyết `no_data`; nhiễu trong YAML không có tác dụng; A2 = A1 khác máy. Giá trị: kiểm vòng chạy, FP1, hồi quy; không kiểm suy luận.
- **Leader thử dashboard với LLM thật** (`SME_LLM=real scripts/demo.sh --fresh-db`, trang `/?source=live`): UI vẫn lộ mã (`wrong_setpoint`, `defect_rate`, `zone3_setpoint_c`) trong câu LLM; SOP v1 (config) và v2 (LLM) tiếng Anh. Nguyên nhân đã kiểm: `system.py:26` bảo LLM giữ nguyên tên mã; quy tắc ngôn ngữ R10e **bỏ sót `new_content`**; SOP gốc + ghi chú simulator tiếng Anh; bảng nhãn viết cứng ở `dashboard/lib/strings.ts`. → **ADR-010** (leader chốt, `docs/decisions.md`): mọi chữ trên UI tiếng Việt; thuật ngữ ngành (SOP, KPI, setpoint, operator) giữ nguyên, giải nghĩa từ bảng thuật ngữ trong config; dữ liệu nguồn không phải tiếng Việt hiện dạng "trích nguyên văn". Vai D: issue **#141**.
- **Đánh giá khách quan** (leader hỏi, chỉ trong chat): mạnh ở quản trị (duyệt, audit, phiên bản, rollback); yếu ở bằng chứng chẩn đoán, vòng tự kiểm (Claude sinh dữ liệu + code + chấm), điều 2 đạt theo cấu tạo (`post_change` do simulator sinh), dồn nguồn lực vào leader + Claude. Thương mại: rủi ro lớn nhất là dữ liệu SME (ít log có cấu trúc); hướng khả thi là trợ lý CAPA/8D + phiên bản SOP. Khuyến nghị trước freeze: kịch bản khó, pitch trung thực ("vòng cải tiến có kiểm soát; độ chính xác đang đo"), phỏng vấn 1 người làm QA thật.
- **Leader hỏi** cho thành viên chạy `/session-start` sau khi mở quyền (luân phiên một người vận hành): khả thi, cần P8a (quyền `maintain`, khoá vận hành trong repo, chuyển quy tắc chung từ bộ nhớ vào repo, script dựng máy; ~4 task, 4–6 USD). **Chưa quyết**; leader chọn tiếp tục chờ runner.
- **Hạn mức** leader báo 12/10 ~06:20: 5 giờ 15%, tuần **90%** (trước R10e 9,49 USD và đo LLM thật). Leader chọn chạy R10e ngay dù rủi ro chạm 100%. `usage-log.md` ghi sai số đầu nhiệm vụ (lấy số cũ 71%).

### Làm tiếp theo thứ tự
1. **Chờ leader:**
   - (a) Chốt % điều 1 sau đo nền LLM thật: "giữ 0" / gõ số (Claude đề xuất 20–30: LLM thật đúng bài dễ, chưa có A1 tập giữ lại).
   - (b) Gửi 2 số `/usage` (5 giờ, tuần) trước khi chạy mốc kế; reset tuần 13:00 14/10.
   - (c) Duyệt viết plan **R11a** (mục 2): "viết plan" / sửa danh sách. Chạy runner sau reset 14/10.
   - (d) P8a (cho thành viên vận hành luân phiên): "làm" / "để sau freeze".
   - (e) Xoá worktree `../sme-ci-agent-d2`: leader tự chạy `git worktree remove ../sme-ci-agent-d2`.
   - Không nhắc trong báo cáo: nhắc Bảo/Daivon, giờ kickoff, ROADMAP nghiên cứu (bộ nhớ `skip-team-reminders`).
2. **R11a** (điều 1, đang 0), việc **bắt buộc** rút từ đo nền 12/10:
   - Trường `signal` cho Hypothesis + prompt + chấm theo mã (H-28; đề xuất (c) 1 của R10e). Không có thì cách chấm theo chữ sai với LLM tiếng Việt.
   - `eval_rootcause.py` luôn chạy trên DB sạch, không đọc `learning_store` của run trước (đã thấy lộ đáp án); kiểm cách eval chọn anomaly.
   - ≥ 1 kịch bản khó do backend soạn (H-29): anomaly 2–3σ tăng dần, đổi zone3 ±2 °C thường xuyên, nhiễu trùng thời điểm (lô mới/người thay ca cùng đêm), có dữ liệu cho giả thuyết khác (`environment_log`, `training_level`), A2 khác nguyên nhân; kịch bản `ask` và `none`.
   - ADR-010 phía backend: khối `labels` + bảng thuật ngữ trong `data/context_profile.yaml`, trả qua `/config/domain` (báo #141); prompt đưa bảng nhãn, yêu cầu câu văn dùng nhãn thay mã; thêm `new_content` vào quy tắc ngôn ngữ; ghi chú simulator, `demo_llm` `new_content` tiếng Việt.
   - Còn lại: H-36, H-18/H-56/H-63, H-52, H-53, H-55; treo từ R10ch: bản SOP trùng nếu kill giữa commit và checkpoint.
   - `verify.py` sẽ báo `dashboard` đỏ "mới so với baseline" tới khi #139 merge: ghi rõ trong plan R11a là lỗi đã biết, hoặc chờ #139.
3. **Sửa plugin (P4, giữa hai mốc):**
   - hook `SubagentStop` không chạy (R10e: `hook_runs` đứng ở 67 cả mốc);
   - runner không chạy tiếp được mốc đã có PR mở (`new_milestone_pr` chỉ nhận PR mới);
   - worktree worker không kéo commit (b) supervisor đẩy lên nhánh mốc;
   - supervisor phải chạy `.autodev/tests` trước khi merge PR hồ sơ (#125);
   - `/session-start` kiểm runner bằng `pgrep -fl 'autodev/run.py'` (`autodev-run` không khớp);
   - tăng tốc verify (chạy test chọn lọc trong vòng TDD, đủ bộ một lần trước review; hoặc `pytest-xdist` với DB tách); đo `--durations=20` chưa chạy;
   - `demo.sh`: tự `yarn install` khi `dashboard/package.json`/`yarn.lock` đổi.
4. **Reviewer:** đo luật xếp mức trên ≥ 5 ca mới từ audit 4, mỗi ca 3 lần; hỏi leader trước; sau reset hạn mức tuần (14/10).
5. **Plugin sau v0.1:** P8a (nếu leader chọn), P9 (reviewer cho PR của team, chỉ comment), P7a Telegram một chiều.

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

## Trạng thái hiện tại (2026-10-12 chiều)
- **Dự án:**
  - M0–M3 xong; M4 3/6 (T-040..T-042); T-043 (vai D), T-044, T-045 (vai Q) mở; cổng 13/10 go, tag `v0.1-e2e` (c60fec5);
  - 1028 passed trên main (R10e); **6 vitest dashboard đỏ trên main** (#139, vai D);
  - % đạt 3 điều: **0 / 67 / 67** (điều 1 có nền LLM thật, chờ leader chốt).
- **Plugin:** P1–P3, P5, P6 xong; P4 đang làm (mục 3 "Làm tiếp"); P7–P9 chưa làm.
- **Runner:** rảnh (R10e xong 11:34 12/10; `audit.json` pending `["R10e"]`, `--audit-every` mặc định 2 → audit chạy sau mốc kế).
- **Demo:** tắt. DB demo `sme_ci_demo` còn các run thử LLM thật của leader (xoá khi `--fresh-db` lần sau). Bật: `scripts/demo.sh --fresh-db` (thêm `SME_LLM=real` cho LLM thật, mở `/?source=live`); tắt: `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt khi runner chạy.
- **PR mở:** không có (sau PR bàn giao này).
- **Worktree:** chính, `-autodev` (worker), `-supervisor`, `-bench` (cố định), `-d2` (chờ leader xoá).
- **Hạn mức:** leader báo ~06:20 12/10: 5 giờ 15%, tuần 90%; sau đó R10e 9,49 USD + LLM thật ~0,4 USD (API key, không tính hạn mức gói) → hỏi leader `/usage` đầu phiên sau. Reset tuần 13:00 14/10.

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
- Chi tiết trong `PROGRESS.md`.

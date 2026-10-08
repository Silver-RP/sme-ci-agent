# Bàn giao giữa các phiên supervisor

Supervisor cập nhật file này ở cuối mỗi mốc và trước khi người dùng đóng phiên. Phiên supervisor mới đọc file này trước tiên, rồi `ROADMAP.md`, rồi `PROGRESS.md`. Ngắn gọn, chỉ những gì phiên mới cần để làm tiếp.

## Bạn là ai, đang làm gì (đọc trước)
- **Hai plan lồng nhau:**
  - **Plan lớn** là xây plugin auto-dev (`docs/autodev/`, mốc **P1–P8**).
  - **Plan nhỏ** là dự án SME CI Agent dùng để thử (`TASKS.md` và `docs/PLAN.md`, mốc dự án **M0–M4**).
  - Mỗi **lần chạy auto-dev** là một mốc **R** (`plan/R4.md`…`plan/R8.md`): worker làm vài task TASKS.md, đồng thời kiểm chứng một khả năng của plugin. `plan/M1.md`–`M3.md` thực chất là R1–R3 (đặt tên trước khi đổi quy ước).
  - Ưu tiên auto-dev, nhưng mốc dự án vẫn phải đúng TASKS.md, PLAN.md, DoD.
- **Phiên supervisor đóng vai con người:** lập plan, giao mốc, duyệt, merge, sửa plugin. Không viết code dự án (developer/reviewer trong worker làm). Quyền: thiết kế mục 6.15, `.claude/commands/supervise.md`.
- **Người dùng:** giao tiếp bằng tiếng Việt, gói Pro (tiết kiệm hạn mức), muốn tự động hoá tối đa, báo ngắn gọn, giải thích khi họ hỏi "tại sao".

## Bước tiếp theo (cập nhật 2026-10-09, sau P5 + audit đầu)
Đọc `docs/autodev/PROJECT_STATE.md` ngay sau file này: mục tiêu, % đạt, lỗ hổng H-xx, hướng 3–5 mốc đã duyệt.

Đã xong trong phiên 2026-10-09:
- P5 (PR #40): `/audit`, `run.py --audit-every 2` + `--audit-only`, `PROJECT_STATE.md` + `state.json`, `LESSONS.md`, guard chặn sửa file bằng sed tại chỗ / script Python qua stdin.
- Audit đầu `docs/audits/2026-10-09.md`: H-06..H-26 (7 cao), % đạt 3 điều hạ còn 25/40/10.
- Gói bàn giao UI (bản đầu): `docs/schema/payloads.md`, `docs/schema/examples/`, `docs/ui-handoff.md`.
- Người dùng cho supervisor tự merge PR (`.claude/settings.local.json`, không commit).

Làm tiếp theo thứ tự:
1. **`plan/R9.md`** theo hướng người dùng đã chọn (theo audit): H-10 (SOP khớp scenario reflow) làm đầu tiên; H-06 (Measure theo thay đổi thật, không theo từ khoá); H-12 (script eval nguyên nhân so với ground truth, LLM giả và thật); e2e uvicorn chuỗi sai → rollback → điều tra → đúng → Learn (gộp R8-c2); H-07, H-08, H-09, H-17, H-21; temperature (H-23); script xuất fixture các nhánh cho frontend (`docs/ui-handoff.md` mục "Nhánh cần có fixture"). Mỗi H-xx có test đỏ trước khi sửa. Từ R9 auto-dev không sửa phần trình bày trong `dashboard/`. Rồi chạy R9 bằng chế độ B (tắt demo trước).
2. **T-030 (người dùng chạy, sau R9):** một vòng LLM thật trên dashboard, ghi lỗi vào `docs/decisions.md` mục "Việc cần sửa sau khi chạy". Người dùng tạo key ở console.anthropic.com (~5 USD; gói Pro/Max không kèm API; khuyên Anthropic theo ADR-006), tự điền `.env` (`ANTHROPIC_API_KEY`, `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_CHEAP=claude-haiku-4-5-20251001`), chạy `SME_LLM=real scripts/demo.sh`. Agent không đọc `.env`. Chạy thêm script eval của R9 với `--llm real`.
3. **P6:** bảng 3–5 mốc tới v0.1-e2e (13/10) và freeze (20/10), đường găng, thứ tự cắt (PLAN mục 7), pre-mortem mỗi mốc, đối chiếu ước tính với thực tế. Hướng đã duyệt nằm ở PROJECT_STATE mục "Tầm nhìn"; người dùng duyệt việc cắt.
4. **R10 (v0.1-e2e):** H-11 (MTTD/MTTR trong vòng lặp, nhiều anomaly, đọc `learning_store`, `metrics_report.py`, T-042), T-041, T-044, H-13, H-16, H-26. Runner tự chạy audit 2 sau R9 + R10 (`--audit-every 2`), rồi tag v0.1-e2e (người dùng duyệt).
5. **Trang trạng thái Artifact** (P5 còn lại): xuất từ `docs/autodev/state.json`, riêng tư, xem trên điện thoại; cập nhật sau mỗi mốc.
6. **Gói UI gửi bạn frontend:** người dùng sẽ cho tên/GitHub khi gửi tài liệu; lúc đó ghi vào `docs/PLAN.md` mục 4. Chưa cần hỏi lại.
7. **Để sau v0.1-e2e:** H-14, H-15 (checkpointer Postgres), H-19, H-20, `tests/test_invariants.py`, API danh sách run và trang Dữ liệu; P7 (Telegram hai chiều + API trạng thái); kiểm chứng nhánh chờ reset hạn mức (đóng P4); log stream-json; P8.

## Trạng thái hiện tại (2026-10-09 01:00)
- **Dự án** (TASKS.md 21/32; đến v0.1-e2e 21/27):
  - M0 4/4 (leader xác nhận, ADR-009); M1 8/8; M2 7/7.
  - M3: T-031 xong, T-030 chờ người dùng.
  - M4: T-040 xong (R8).
  - R8 (PR #37): 371 pytest, 56 vitest; verify và smoke sạch (supervisor Opus và phiên trước đều tự chạy lại trên main).
- **Plugin:** P1–P3 xong.
  - P4 (chế độ B) đã chạy thật 5 mốc R4–R8, không lỗi lọt sau merge kể từ khi có smoke.
  - Chi phí worker + supervisor: R4 ≈ 2,29; R5 ≈ 3,01; R6 ≈ 1,81; R7 ≈ 2,58; R8 ≈ 6,40 USD (worker 5,42 với 5 task; supervisor Opus 0,98).
  - Chưa chạm hạn mức lần nào.
- **Hardening 2026-10-08 (PR #35):**
  - `verify.py --smoke` chạy lệnh người dùng gõ.
  - Supervisor phải lập bảng "tiêu chí cấp mốc → lệnh/test → kết quả".
  - Supervisor chạy Opus effort medium (`AUTODEV_SUPERVISOR_MODEL`, `AUTODEV_SUPERVISOR_EFFORT`); worker Sonnet.
  - Runner chỉ tính PR tạo trong lần chạy, tự merge PR hồ sơ chỉ sửa `docs/autodev/**` (lần đầu thành công ở #38), chỉ coi là hạn mức khi bước lỗi.
  - Guard chặn thêm biến thể xoá và tự ghi baseline.
- **Demo đang chạy** (phiên trước bật bằng `scripts/demo.sh`, LLM giả):
  - dashboard http://localhost:3000/?source=live, API http://localhost:8000/docs;
  - log `.autodev/runs/demo.log`;
  - tắt bằng `lsof -ti tcp:8000,3000 -sTCP:LISTEN | xargs kill`. Phải tắt trước khi chạy mốc R mới, vì smoke `demo.sh --check` cần 2 cổng này.

## Môi trường
- **Repo:** `~/dev/sme-ci-agent/` chứa 3 worktree cạnh nhau:
  - `sme-ci-agent` (chính);
  - `sme-ci-agent-autodev` (worker);
  - `sme-ci-agent-supervisor` (supervisor).

  Đã chuyển khỏi Desktop (iCloud sinh file "tên 2"). Tài liệu hackathon ở `~/Desktop/Projects_VSCode/Vietnam Japan AI Hackathon 2026/`, cạnh alias "sme-ci-agent (code)".
- **Postgres:** container `sme-ci-agent-autodev-db-1`, cổng 5432 (user/pass/db synthetic `sme`/`sme`/`sme_ci`). `demo.sh` dùng lại DB đang chạy nếu kết nối được. Homebrew `postgresql@14` đã dừng.
- **Node 22.23.3** (`nvm alias default 22`, yarn 1.22). Shell cũ có thể còn PATH 22.12, nên luôn đặt `PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH` khi khởi chạy runner.
- **Chạy mốc** (từ repo chính, sau khi `plan/Rx.md` đã merge lên main):
  ```bash
  export PATH=~/.nvm/versions/node/v22.23.3/bin:$PATH AUTODEV_SUPERVISOR_MODEL=opus AUTODEV_SUPERVISOR_EFFORT=medium
  nohup .autodev/autodev-run.sh R9 > .autodev/runs/nohup.out 2>&1 &
  ```
  Ngay sau đó, bằng Bash `run_in_background`, chạy vòng `until` chờ "Hoàn tất|STOP" trong `.autodev/runs/run.log`, để phiên chat được báo khi xong.
- **Theo dõi:** `.autodev/watch.sh` (người dùng chạy trong terminal; có dòng sub-agent). Thông báo macOS mặc định tắt (`AUTODEV_NOTIFY=1` để bật).
- **Chế độ Auto** đôi khi lỗi "classifier no verdict" ở phía máy chủ. Khi đó người dùng tạm chuyển chế độ quyền; thử `claude -p` nhỏ trước khi khởi chạy runner.

## Quyền và quy tắc đang áp dụng
- Supervisor tự merge PR mốc sau khi tự chạy verify + smoke + bảng tiêu chí; worker không merge. PR hồ sơ chỉ sửa `docs/autodev/**` (và `docs/audits/**`) thì runner tự merge. Phiên supervisor tương tác được tự merge PR của mình (người dùng cho phép 2026-10-09; quy tắc trong `.claude/settings.local.json`, không commit, nên máy khác phải thêm lại).
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến; merge không kèm xoá nhánh). Chuyển file sang thư mục tạm thay vì xoá khi cần dọn.
- Không đọc hay in `.env`. Guard so khớp theo chữ: câu chữ trong commit/tài liệu nhắc tới lệnh cấm cũng bị chặn, nên viết lại câu hoặc dùng Edit tool.
- Tầng tầm nhìn (thứ tự mốc, cắt việc) luôn do người dùng duyệt.

## Việc mở / cần để ý
- **Lỗ hổng dự án:** xem PROJECT_STATE mục "Lỗ hổng mở" (H-06..H-26; nguồn `docs/audits/2026-10-09.md`). Việc mở của R8 đã gộp vào đó (R8-c1 → `payloads.md` đã có; R8-c2 → R9).
- **Quy trình:** guard (P5) đã chặn sửa file bằng sed tại chỗ / script Python qua stdin; xem R9 developer còn vướng không.
- **Gói UI:** `payloads.md` còn thiếu ví dụ thật cho rollback, halt, chưa đủ bằng chứng, revise, retry (R9 làm script xuất fixture).
- **Hạn mức:** chưa biết `claude -p` báo hết hạn mức dạng nào; `run.py` đoán theo "limit" + "resets <giờ>". Gặp lần đầu thì đối chiếu `LIMIT_RE`/`RESET_RE`.
- **Dọn dẹp chờ:** thư mục lịch sử Claude cũ `~/.claude/projects/-Users-ishopjapan-Desktop-…` (người dùng muốn giữ vài ngày rồi xoá, hỏi lại trước khi xoá).
- **Để sau** (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh.

## Lịch sử ngắn
- P1 (plan/M1), P2 (plan/M2), P3 (plan/M3) xong.
- R4–R8 chạy bằng chế độ B, tất cả merge.
- 2026-10-08: chuyển repo khỏi iCloud; rà soát chỉ đọc tìm H1–H5 dẫn tới hardening + R8.
- Chi tiết trong `PROGRESS.md`.

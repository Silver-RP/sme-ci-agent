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

## Bước tiếp theo (người dùng đã duyệt thứ tự, 2026-10-09)
Phiên trước (rất dài) đã kết thúc sau R8. Làm lần lượt:

1. **P5: chống mất tầm nhìn** (sửa plugin, PR `chore/autodev-p5`, có test trong `.autodev/tests`):
   - Lệnh `/audit` (`.claude/commands/audit.md`): rà chỉ đọc bằng 2–3 agent `Explore` song song, theo 3 góc:
     - (a) logic vòng lặp và quy tắc CLAUDE.md;
     - (b) API ↔ dashboard và hợp đồng `events.json`;
     - (c) độ khớp với mục tiêu: mỗi mốc đẩy "3 điều cần kiểm chứng" trong PLAN đi bao xa, có lệch hướng không.

     Kết quả ghi `docs/audits/<ngày>.md`; lỗ hổng đánh mã H-xx, thành task mốc kế tiếp, mở cho đến khi có test chứng minh đã sửa. Mẫu đề bài: xem 2 audit ngày 2026-10-08 (tóm tắt trong `PROGRESS.md` và `plan/R8.md`).
   - Runner `--audit-every 2`: mặc định cứ 2 mốc R thì chạy audit headless.
   - `docs/autodev/PROJECT_STATE.md` (dưới 150 dòng) cùng bản máy đọc `docs/autodev/state.json`, gồm:
     - bảng M/R/P ở đầu;
     - mục tiêu và 3 điều cần kiểm chứng kèm % đạt;
     - kiến trúc thật hiện nay;
     - bảng "quy tắc → test bảo vệ";
     - lỗ hổng mở;
     - quyết định gần đây;
     - bảng tầm nhìn 3–5 mốc tới (P6 điền).

     developer, reviewer và supervisor đọc file này trước plan mốc.
   - `docs/autodev/LESSONS.md`: nguyên tắc rút ra, mỗi mục 3–4 dòng (nguyên tắc / ngộ ra từ / đã biến thành quy tắc-test-công cụ nào). 4 mục người dùng đánh giá cao nhất đặt đầu, rồi đến các mục khác:
     1. Đừng tin báo cáo, kể cả của chính mình.
     2. Người kiểm tra phải khác người làm và nhìn từ góc khác.
     3. Tự động hoá phải có điểm dừng rõ ràng và quyền hạn có giới hạn.
     4. Ngữ cảnh dài làm mất tầm nhìn tổng thể.
     - Quy tắc trong tài liệu sẽ bị quên; quy tắc thành test thì không.
     - Test xanh khác với dùng được (smoke).
     - Im lặng không có nghĩa là chạy tốt (đo "còn sống" đúng tầng sub-agent).
     - Chạy tách rời phải có kênh báo về.
     - Môi trường cũng là code (iCloud, Node, cổng, PATH).
     - Guard so khớp theo chữ chặn nhầm cả lời nói.
   - ROADMAP: thêm P5 (audit + trạng thái), P6 (lập kế hoạch dài hạn), P7 (Telegram hai chiều + API trạng thái + dashboard theo dõi plugin), P8 (đóng gói, UI deploy được; P5 cũ "đóng gói" chuyển thành P8).
   - Sau P5: xuất một **trang trạng thái dạng Artifact** (riêng tư, xem được trên điện thoại) từ `state.json`; cập nhật sau mỗi mốc.
2. **Chạy `/audit` lần đầu** trên kết quả R7 + R8, rồi viết `PROJECT_STATE.md` lần đầu từ audit đó. Đưa vào audit các điểm R8 còn mở (mục "Việc mở").
3. **Gói bàn giao UI cho team frontend:** UI sản phẩm do bạn frontend trong team làm; auto-dev chỉ giữ logic và dữ liệu. Gói gồm:
   - `docs/schema/payloads.md`: payload từng loại event kèm ví dụ thật; gộp luôn R8-c1, tức các trường mới `kpi_measured.status`, `run_finished` status `error`/`closed`, `question_asked` kind `halt`, `approval_decided.sop_still_in_force`, `proposal_id`/`proposal_hash`.
   - Danh sách màn hình và trạng thái cho demo: danh sách run, timeline, khung duyệt đề xuất (SOP cũ → mới), duyệt rollback, câu hỏi, lỗi / chưa đủ bằng chứng / đã Learn, số liệu 3 chỉ số.
   - Fixture đủ các nhánh.
   - Ranh giới: từ R9, auto-dev không sửa phần trình bày trong `dashboard/`.
   - Hỏi người dùng tên/GitHub của bạn frontend để ghi vào `docs/PLAN.md` mục 4.
4. **T-030 (người dùng chạy):** một vòng với LLM thật trên dashboard, ghi lỗi vào `docs/decisions.md` mục "Việc cần sửa sau khi chạy". Hướng dẫn từng bước.
   - Người dùng tạo key ở console.anthropic.com, nạp khoảng 5 USD. Gói Pro/Max **không** kèm API; người dùng đã hỏi về việc dùng LLM khác, khuyên Anthropic theo ADR-006.
   - Người dùng tự điền `.env` (`ANTHROPIC_API_KEY`, `MODEL_REASONING=claude-sonnet-5-5`, `MODEL_CHEAP=claude-haiku-4-5-20251001`), rồi `SME_LLM=real scripts/demo.sh`.
   - Agent không đọc `.env`.
5. **P6: lập kế hoạch dài hạn ("cuốn chiếu có tầm nhìn"):**
   - Bảng 3–5 mốc tới v0.1-e2e (13/10) và freeze (20/10): đường găng, thứ tự cắt (PLAN mục 7).
   - Pre-mortem mỗi mốc: "đạt trên giấy mà hỏng thực tế thế nào?".
   - Đối chiếu ước tính với thực tế (thời gian, chi phí, số vòng, lỗ hổng audit).
   - **Người dùng duyệt** thứ tự và việc cắt; agent không tự cắt vì hạn chót.
6. **R9:**
   - `tests/test_invariants.py`: quy tắc CLAUDE.md thành test.
   - R8-c2: e2e uvicorn nhánh rollback (thêm kịch bản LLM giả có giả thuyết sai) và assert `learning_saved` nhánh đạt.
   - Checkpointer Postgres; dùng bảng `runs`/`events` (đang trống); run id trên URL.
   - API cho trang danh sách run và trang Dữ liệu (audit_log, sop_versions, learning_store); phần trình bày để team frontend làm.
   - Detect không chọn lại anomaly đã xử lý; đọc `learning_store`.
   - Khoá phiên bản SOP khi chạy song song.
   - Giới hạn số lần `retry`.
   - `fix_addresses_cause` không khớp theo từ khoá (câu phủ định đang bị tính là sửa đúng).
7. **R10 (v0.1-e2e):** T-041 (temperature thấp, record/replay), T-042 (số liệu 3 chỉ số), T-044 (sổ token). Audit lần 2 sau R9 + R10, rồi tag v0.1-e2e (người dùng duyệt).
8. **Để sau v0.1-e2e:**
   - P7: Telegram hai chiều với 4 mức xem / nhận / trả lời / điều khiển có xác nhận; không bao giờ xoá, merge tay, chạy lệnh tự do. Bot long-polling trên Mac, chỉ nhận `chat_id` của người dùng. Dùng chung API trạng thái với dashboard plugin.
   - Kiểm chứng nhánh chờ reset khi chạm hạn mức thật (đóng P4).
   - Log stream-json.
   - P8.

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
- Supervisor tự merge PR mốc sau khi tự chạy verify + smoke + bảng tiêu chí; worker không merge. PR hồ sơ chỉ sửa `docs/autodev/**` thì runner tự merge.
- Không xoá file, thư mục, nhánh, worktree, container nếu người dùng chưa duyệt (guard chặn các lệnh xoá phổ biến; merge không kèm xoá nhánh). Chuyển file sang thư mục tạm thay vì xoá khi cần dọn.
- Không đọc hay in `.env`. Guard so khớp theo chữ: câu chữ trong commit/tài liệu nhắc tới lệnh cấm cũng bị chặn, nên viết lại câu hoặc dùng Edit tool.
- Tầng tầm nhìn (thứ tự mốc, cắt việc) luôn do người dùng duyệt.

## Việc mở / cần để ý
- **R8 còn mở (đưa vào audit/R9):**
  - `fix_addresses_cause` khớp từ khoá (câu phủ định vẫn tính là sửa đúng).
  - `retry` không giới hạn.
  - e2e uvicorn nhánh rollback chưa có (R8-c2).
  - `payloads.md` chưa có (R8-c1).
- **Quy trình:** developer vẫn sửa file bằng heredoc `python3 -` / `sed -i` dù quy ước cấm. Xét chặn bằng quyền hoặc guard ở P5.
- **Dữ liệu và lưu trữ:** event/run chỉ ở bộ nhớ (bảng `runs`/`events` trống); checkpointer InMemorySaver. Mất khi backend tắt.
- **Dự án:** `correlate` chưa có tín hiệu cho nhóm people và `ambient_temperature`.
- **Hạn mức:** chưa biết `claude -p` báo hết hạn mức dạng nào; `run.py` đoán theo "limit" + "resets <giờ>". Gặp lần đầu thì đối chiếu `LIMIT_RE`/`RESET_RE`.
- **Dọn dẹp chờ:** thư mục lịch sử Claude cũ `~/.claude/projects/-Users-ishopjapan-Desktop-…` (người dùng muốn giữ vài ngày rồi xoá, hỏi lại trước khi xoá).
- **Để sau** (người dùng chốt): đo độ dài phiên và chất lượng theo thời gian; hook trước khi nén ngữ cảnh.

## Lịch sử ngắn
- P1 (plan/M1), P2 (plan/M2), P3 (plan/M3) xong.
- R4–R8 chạy bằng chế độ B, tất cả merge.
- 2026-10-08: chuyển repo khỏi iCloud; rà soát chỉ đọc tìm H1–H5 dẫn tới hardening + R8.
- Chi tiết trong `PROGRESS.md`.

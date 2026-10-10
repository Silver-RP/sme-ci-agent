---
description: (Chỉ leader) Đóng phiên - ghi bàn giao (HANDOFF, PROJECT_STATE + state.json, TASKS, bộ nhớ), mở PR, chờ check, merge. Phiên sau chỉ cần /session-start.
argument-hint: <tuỳ chọn: ghi chú thêm của leader cần lưu>
---

Bạn đóng phiên làm việc. Mục tiêu: phiên sau chạy `/session-start` là làm tiếp được ngay, leader không phải giải thích lại. Ghi **sự thật đã kiểm**, không ghi dự định như thể đã xong.

## 1. Gom những gì đổi trong phiên
- Ngày cập nhật cuối của HANDOFF (dòng "Bước tiếp theo (cập nhật …)") → `git log --oneline --since=<ngày> origin/main`, `gh pr list --state merged --search "merged:>=<ngày>"`, issue tạo/đóng (`gh issue list --state all --search "updated:>=<ngày>"`).
- Từ cuộc hội thoại: quyết định của leader (duyệt, cắt, đổi thứ tự, ngân sách), việc leader hứa làm, việc còn chờ leader trả lời, lỗi gặp phải và cách xử lý.
- Trạng thái thật: runner, demo, lời mời team, PR mở (xem lệnh ở `/session-start` mục 2).
- $ARGUMENTS: ghi chú leader muốn lưu.

## 2. Cập nhật file (dùng Edit/Write; guard chặn sửa tại chỗ bằng sed và script Python qua stdin)
| File | Sửa gì |
|---|---|
| `docs/autodev/HANDOFF.md` | Mục "Bước tiếp theo": ngày; bối cảnh nếu đổi; "Đã xong trong phiên" (thay bằng phiên này, phiên cũ thu vào "Lịch sử ngắn" một dòng); "Làm tiếp theo thứ tự" (mục 1 luôn là việc chờ leader, ghi rõ từ cần trả lời). Sửa "Trạng thái hiện tại", "Môi trường", "Quyền", "Việc mở" nếu đổi. Giữ ngắn: bỏ chi tiết đã nằm trong PROGRESS, PR hay audit. |
| `docs/autodev/PROJECT_STATE.md` + `state.json` | Thêm "Quyết định gần đây" (mới nhất lên đầu); sửa bảng mốc, % đạt, "Tầm nhìn" nếu đổi. Hai file cùng nội dung. **Không** sửa bảng lỗ hổng trừ khi có audit hoặc test đóng lỗ hổng. Dưới 150 dòng. |
| `TASKS.md`, `docs/PLAN.md` | Tick task đã xong có bằng chứng; owner hoặc phân vai nếu đổi. |
| Bộ nhớ (`~/.claude/projects/<dự án>/memory/`) | Chỉ điều về **cách leader muốn làm việc** hoặc quyền mới (không chép những gì repo đã ghi). Sửa file cũ thay vì tạo trùng; cập nhật `MEMORY.md`. |

Không sửa: brief của team (`docs/briefs/`) trừ khi leader quyết đổi yêu cầu (khi đó ghi vào mục "Lịch sử thay đổi yêu cầu" của brief).

Số đo plugin: `python3 .autodev/metrics.py --write` (bảng B1–B5 trong `docs/autodev/PROGRESS.md`). Lúc này mọi `runs/*.json` đã có, nên số thay cho số tạm (`+ ~x`) mà supervisor ghi khi đang chạy.

## 2a. Trang trạng thái (P5)
Trang riêng tư https://claude.ai/artifact/X6TLNZGZmzraP36WKgBKxF (loại Dashboard, 7 nguồn dữ liệu là file JSON). Làm **sau** khi sửa `state.json`, trước khi merge:
1. `python3 .autodev/export_status.py` → 7 file trong `.autodev/runs/status/` (`goals`, `milestones`, `audits`, `gaps`, `plugin`, `outlook`, `runner`).
2. Tải từng file lên kho tài sản của trang: Artifact `publish`, `url` như trên, `asset: true`, `file_path` (JSON phải tải từng file một). Ghi lại `url` (`/_blob/<id>`) của từng file.
3. ArtifactData `batch` (đọc `datasets` trước để lấy `version`): với mỗi nguồn `datasets/<tên>`, `update` `source` = `{kind: "file", name: "<tên>.json", url}` và `updated` = `{at: <giờ ISO>, by: "Claude (.autodev/export_status.py)"}`.
4. File cũ trong kho tài sản để nguyên (không xoá khi leader chưa duyệt). Lỗi tải lên hoặc ghi thì báo leader, không chặn merge.

## 3. Kiểm và merge
1. `uv run python -m pytest .autodev/tests -q` phải xanh (kiểm cấu trúc PROJECT_STATE, state.json).
2. Nhánh `chore/autodev-handoff-<YYYYMMDD>`, commit `chore(autodev): bàn giao đóng phiên <ngày>`, PR.
3. `gh pr checks <số> --required --watch` → xanh thì `gh pr merge <số> --merge` (không xoá nhánh). Về `main`, `git pull`.
4. Không merge được (check đỏ, xung đột) thì để PR mở và báo leader.

## 4. Báo leader (không quá 10 dòng)
- PR số mấy, đã merge chưa.
- 3–5 dòng: phiên sau sẽ bắt đầu từ đâu.
- Việc đang chờ leader (đúng như mục 1 của "Làm tiếp theo thứ tự"), dạng danh sách đánh số kèm nội dung để leader chọn bằng số (như `/session-start` mục 3).
- Nhắc: phiên mới gõ `/session-start`.

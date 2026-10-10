---
description: (Chỉ leader) Mở phiên - đọc bàn giao, kiểm trạng thái thật (git, PR, issue, runner, team), báo "tiếp theo làm gì". Chỉ đọc.
argument-hint: <tuỳ chọn: chủ đề muốn tập trung, ví dụ R10a>
---

Bạn mở một phiên làm việc mới với leader dự án. Mục tiêu: trong một lượt, nắm lại bối cảnh và đưa leader danh sách việc rõ ràng, để họ không phải mô tả lại. **Chỉ đọc**: không sửa file, không merge, không chạy auto-dev hay LLM thật trong lệnh này.

## 1. Đọc (theo thứ tự, chỉ phần cần)
1. `docs/autodev/HANDOFF.md`: mục "Bước tiếp theo" (bối cảnh, đã xong, thứ tự việc, cách làm với team) và "Quyền và quy tắc".
2. `docs/autodev/PROJECT_STATE.md`: bảng mốc, % đạt, lỗ hổng mở cao, tầm nhìn.
3. Chỉ khi cần: `docs/autodev/LESSONS.md` (4 bài đầu), `TASKS.md` mục mốc hiện tại.

## 2. Kiểm trạng thái thật (song song, một lượt Bash)
Không tin bàn giao một mình. So với thực tế:
- `git status --short`, `git branch --show-current`, `git log --oneline -5 origin/main` (sau `git fetch -q`).
- `gh pr list --state open --json number,title,author,headRefName,statusCheckRollup`.
- `gh issue list --state open --limit 30 --json number,title,assignees,labels,updatedAt`. Chú ý issue và comment mới của team kể từ ngày cập nhật HANDOFF: `gh issue list --search "updated:>=<ngày>"`.
- Team: `gh api repos/{owner}/{repo}/invitations --jq '.[].invitee.login'` và `.../collaborators --jq '.[].login'`. Ai đã nhận lời mà chưa được gán issue thì đề xuất gán (theo bảng vai trong HANDOFF).
- Runner: `tail -5 .autodev/runs/run.log`, `ls -t .autodev/runs/STOPPED-* | head -1`; tiến trình `pgrep -fl autodev-run`.
- Demo: `lsof -iTCP:8000 -iTCP:3000 -sTCP:LISTEN`.
- Hạn mức: `python3 .autodev/usage.py show --last 3` (% 5 giờ, % tuần, tuổi số liệu, 3 nhiệm vụ cuối). Số liệu cũ (status line chỉ chạy trong terminal, không chạy trong VS Code) thì xin leader 2 số từ `/usage`.

Lệch giữa HANDOFF và thực tế (PR đã merge, issue đã đóng, lời mời đã nhận, mốc đã chạy xong) thì tin thực tế và ghi lại để `/session-end` sửa.

## 3. Báo cáo (tiếng Việt, ngắn, không quá 25 dòng)
```
## Trạng thái <ngày>
<2–3 dòng: mốc hiện tại, % đạt 3 điều, điều gì đổi kể từ bàn giao (PR/issue mới của team)>
Hạn mức: 5h <x>%, tuần <y>% (số liệu <n> phút trước)

## Cần bạn quyết / làm (theo thứ tự)
1. ... (mỗi mục một dòng, nêu vì sao chặn việc khác)

## Tôi làm tiếp khi bạn đồng ý
1. ... (ước chi phí nếu chạy auto-dev hoặc LLM thật)

## Lệch so với bàn giao
- ... (bỏ mục này nếu không có)
```
Kết thúc bằng danh sách lựa chọn **đánh số, kèm nội dung**, để leader chỉ cần gõ số (một hoặc nhiều số, ví dụ "1, 3"); vẫn chấp nhận gõ chữ. Mục cần tham số thì ghi rõ, ví dụ:
```
Chọn:
1. bắt đầu R10a: merge plan rồi chạy runner (~4 USD)
2. duyệt fresh-db: DB demo sạch mỗi lần chạy
3. kickoff <giờ>: chốt giờ họp team
```
Số chỉ có nghĩa trong tin đó.

Nếu có $ARGUMENTS thì sau báo cáo, đọc thêm tài liệu liên quan chủ đề đó (plan, brief, issue) và nói bước đầu tiên bạn sẽ làm.

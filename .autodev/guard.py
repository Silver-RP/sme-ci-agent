"""PreToolUse guard for Bash: block destructive or out-of-scope commands.

Reads the hook JSON from stdin; exit 2 blocks the command and shows the reason to Claude.
Stdlib only.
"""

import json
import os
import re
import subprocess
import sys

RULES = [
    (r"\bgit\s+push\b.*(\s|:)(main|master)\b", "Không push lên main/master; push nhánh riêng rồi mở PR."),
    (r"\bgit\s+push\b.*(\s--force\b|\s-f\b|\s--force-with-lease\b)", "Không force push."),
    (r"--no-verify\b", "Không bỏ qua hook bằng --no-verify."),
    (r"\brm\s+-[a-zA-Z]*(r[a-zA-Z]*f|f[a-zA-Z]*r)", "Không dùng rm -rf; xoá từng file cụ thể."),
    (r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f)", "Không reset --hard / clean -f."),
    (r"\bdocker\s+(compose\s+down\s+.*-v\b|volume\s+(rm|prune))", "Không xoá volume DB."),
    (r"\b(dropdb|DROP\s+(DATABASE|TABLE|SCHEMA)|TRUNCATE\s)", "Không xoá dữ liệu DB."),
    (r"(?<![\w.])\.env(?![\w.-]*example)(?:\.[\w-]+)*(?![\w])", "Không đọc hay in nội dung .env."),
    (r"\bgh\s+pr\s+merge\b.*(--delete-branch|\s-d\b)", "Không xoá nhánh khi merge; xoá phải được người dùng duyệt."),
    (r"\brm\b.*\s(-[a-zA-Z]*r[a-zA-Z]*|--recursive)\b.*\s(-[a-zA-Z]*f[a-zA-Z]*|--force)\b",
     "Không dùng rm -r -f; xoá từng file cụ thể."),
    (r"\bgit\s+(restore\s+(\S+\s+)*\.(\s|$)|checkout\s+--\s+\.)", "Không huỷ toàn bộ thay đổi (git restore . / checkout -- .)."),
    (r"\bfind\b.*\s-delete\b", "Không xoá hàng loạt bằng find -delete."),
    (r"verify\.py\s+.*--snapshot", "Không tự ghi baseline; baseline do người/supervisor quyết."),
    (r"(>|\btee\b|\bsed\s+-i|\bmv\b|\bcp\b).*baseline\.json", "Không sửa .autodev/baseline.json bằng lệnh shell."),
    (r"\bgit\s+worktree\s+(remove|prune)\b", "Không xoá worktree khi chưa được người dùng duyệt."),
    (r"\bgit\s+branch\s+(-[a-zA-Z]*[dD]\b|--delete\b)", "Không xoá nhánh khi chưa được người dùng duyệt."),
    (r"\bgit\s+push\b.*(\s--delete\b|\s-d\b|\s:[\w/-]+)", "Không xoá nhánh remote khi chưa được người dùng duyệt."),
    (r"\bsed\s+(-\w+\s+)*-i", "Sửa file bằng công cụ Edit/Write, không dùng sed -i."),
    (r"\bpython[\d.]*\s+-\s*<<", "Sửa file bằng Edit/Write và chạy thử bằng python -c, không dùng script qua stdin."),
]


def current_branch(cwd=None):
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, check=False, cwd=cwd,
        )
        return out.stdout.strip()
    except OSError:
        return ""


DIR_ARG = r"""("[^"]+"|'[^']+'|\S+)"""


def target_dir(command):
    """Directory a git commit/push in the command runs in: `git -C <dir>` or a leading `cd <dir>`."""
    m = re.search(r"\bgit\s+-C\s+" + DIR_ARG + r"\s+(push|commit)\b", command)
    if not m:
        m = re.match(r"\s*cd\s+" + DIR_ARG + r"\s*(&&|;|\n)", command)
    if not m:
        return None
    path = os.path.expanduser(m.group(1).strip("\"'"))
    return path if os.path.isdir(path) else None


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = data.get("tool_input", {}).get("command", "")
    # Check each subcommand on its own so a push of a feature branch followed by
    # "gh pr create --base main" is not mistaken for a push to main.
    parts = [p for p in re.split(r"&&|\|\||;|\||\n", command) if p.strip()] or [command]
    for pattern, reason in RULES:
        if any(re.search(pattern, part, flags=re.IGNORECASE) for part in parts):
            print(f"Bị chặn bởi .autodev/guard.py: {reason}", file=sys.stderr)
            return 2
    switches_first = re.search(
        r"\bgit\s+(switch|checkout)\b.*\bgit\s+(push|commit)\b", command, flags=re.DOTALL
    )
    on_main = current_branch(target_dir(command)) in ("main", "master")
    commits = re.search(r"\bgit\s+(-C\s+" + DIR_ARG + r"\s+)?(push|commit)\b", command)
    if commits and on_main and not switches_first:
        print("Bị chặn bởi .autodev/guard.py: đang ở main; tạo nhánh riêng trước.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

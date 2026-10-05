"""PreToolUse guard for Bash: block destructive or out-of-scope commands.

Reads the hook JSON from stdin; exit 2 blocks the command and shows the reason to Claude.
Stdlib only.
"""

import json
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
]


def current_branch():
    try:
        out = subprocess.run(
            ["git", "branch", "--show-current"], capture_output=True, text=True, check=False
        )
        return out.stdout.strip()
    except OSError:
        return ""


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    command = data.get("tool_input", {}).get("command", "")
    for pattern, reason in RULES:
        if re.search(pattern, command, flags=re.IGNORECASE):
            print(f"Bị chặn bởi .autodev/guard.py: {reason}", file=sys.stderr)
            return 2
    switches_first = re.search(r"\bgit\s+(switch|checkout)\b.*\bgit\s+(push|commit)\b", command)
    on_main = current_branch() in ("main", "master")
    if re.search(r"\bgit\s+(push|commit)\b", command) and on_main and not switches_first:
        print("Bị chặn bởi .autodev/guard.py: đang ở main; tạo nhánh riêng trước.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
# Xem tiến độ auto-dev chế độ B (chỉ đọc). Dùng: .autodev/watch.sh [giây, mặc định 10]
# Thoát: Ctrl+C. Không ghi, không xoá gì.
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORKER="$REPO/../sme-ci-agent-autodev"
SUP="$REPO/../sme-ci-agent-supervisor"
INTERVAL="${1:-10}"

transcript_dir() { echo "$HOME/.claude/projects/$(cd "$1" && pwd | sed 's#[/ _.]#-#g')"; }

age() { # giây từ lần sửa cuối của file
  local m; m=$(stat -f %m "$1" 2>/dev/null) || { echo "?"; return; }
  echo $(( $(date +%s) - m ))
}

while true; do
  clear
  echo "=== auto-dev watch  $(date '+%F %T')  (làm mới mỗi ${INTERVAL}s, Ctrl+C để thoát) ==="
  echo
  if pgrep -f ".autodev/run.py" >/dev/null; then
    echo "RUNNER : ĐANG CHẠY"
    pgrep -fl "claude -p" | sed -E 's#.*/claude #  claude #' | cut -c1-110
  else
    echo "RUNNER : ĐÃ DỪNG (xem .autodev/runs/STOPPED.md nếu có)"
  fi
  echo
  echo "--- run.log (5 dòng cuối) ---"
  tail -5 "$REPO/.autodev/runs/run.log" 2>/dev/null | cut -c1-160
  echo
  for W in "$WORKER" "$SUP"; do
    [ -d "$W" ] || continue
    echo "--- $(basename "$W"): nhánh $(git -C "$W" branch --show-current 2>/dev/null || echo detached) ---"
    git -C "$W" log --oneline -3 2>/dev/null | cut -c1-120
    n=$(git -C "$W" status --short 2>/dev/null | wc -l | tr -d ' ')
    echo "  file đang đổi: $n"
    git -C "$W" status --short 2>/dev/null | head -6 | sed 's/^/    /'
    D="$(transcript_dir "$W")"
    f=$(ls -t "$D"/*.jsonl 2>/dev/null | head -1)
    if [ -n "$f" ]; then
      a=$(age "$f")
      tools=$(grep -c '"type":"tool_use"' "$f")
      last=$(grep -o '"type":"tool_use","id":"[^"]*","name":"[^"]*"' "$f" | tail -1 | sed 's/.*"name":"//; s/"$//')
      echo "  transcript: cập nhật ${a}s trước · ${tools} lệnh tool · lệnh cuối: ${last:-?}"
    fi
    echo
  done
  sleep "$INTERVAL"
done

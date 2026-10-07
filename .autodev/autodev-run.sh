#!/bin/sh
# Mode B (plugin P4): run milestones unattended, e.g.  .autodev/autodev-run.sh R4 R5
# caffeinate keeps the Mac awake while it runs. Logs: .autodev/runs/run.log
# Requires: worktrees ../<repo>-autodev and ../<repo>-supervisor, Docker DB running, gh logged in.
cd "$(dirname "$0")/.." || exit 2
exec caffeinate -i python3 .autodev/run.py "$@"

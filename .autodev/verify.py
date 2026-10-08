"""Hard gates for auto-dev: run verify commands and compare with the baseline.

Usage:
  python3 .autodev/verify.py              # run, print summary; exit 0 clean, 2 new errors
  python3 .autodev/verify.py --snapshot   # write .autodev/baseline.json
  python3 .autodev/verify.py --hook       # SubagentStop hook of the developer agent
  python3 .autodev/verify.py --smoke      # run the user-facing commands in config "smoke" (no baseline)

Stdlib only. Errors are compared as keys (ruff: "file:CODE", pytest: test id),
so a pre-existing error in the baseline never blocks; only new ones do.
"""

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTODEV = ROOT / ".autodev"
CONFIG = AUTODEV / "config.json"
# Per-machine, non-secret variables for the verify commands (e.g. DATABASE_URL with a
# non-default port). Git-ignored; see .autodev/env.local.example.json.
ENV_LOCAL = AUTODEV / "env.local.json"
BASELINE = AUTODEV / "baseline.json"
STATE = AUTODEV / "state.json"
MAX_LINES = 20

RUFF_RE = re.compile(r"^(.+?):\d+:\d+: (\S+)")
PYTEST_RE = re.compile(r"^(FAILED|ERROR) (\S+)")


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse(parser, output):
    regex = {"ruff": RUFF_RE, "pytest": PYTEST_RE}.get(parser)
    if regex is None:
        return []
    keys = []
    for line in output.splitlines():
        m = regex.match(line.strip())
        if m:
            keys.append(f"{m.group(1)}:{m.group(2)}" if parser == "ruff" else m.group(2))
    return keys


def gate_env():
    env = dict(os.environ)
    extra = load(ENV_LOCAL, {})
    env.update({str(k): str(v) for k, v in extra.items()})
    return env


def run_step(step):
    proc = subprocess.run(
        step["cmd"], shell=True, cwd=ROOT, capture_output=True, text=True, check=False, env=gate_env()
    )
    output = proc.stdout + proc.stderr
    keys = parse(step.get("parser"), output)
    if proc.returncode != 0 and not keys:
        # Command failed but nothing parseable (collection error, crash): keep a short tail.
        keys = [f"exit:{proc.returncode}"]
        tail = "\n".join(output.strip().splitlines()[-8:])
        return keys, tail
    return keys, ""


def run_all(config):
    results = {}
    for step in config["verify"]:
        keys, tail = run_step(step)
        results[step["name"]] = {"keys": keys, "tail": tail}
    return results


def baseline_from(results):
    """Keys to store as baseline. `exit:N` (unparsed failure) is never baselined: it would hide every later failure."""
    return {name: [k for k in res["keys"] if not k.startswith("exit:")] for name, res in results.items()}


def run_smoke(steps, cwd=ROOT):
    """Run each user-facing command as a person would; any non-zero exit or timeout is a failure.

    A step with "if_exists" is skipped until that path exists (e.g. a script a later task adds).
    """
    out = []
    for step in steps:
        cond = step.get("if_exists")
        if cond and not (Path(cwd) / cond).exists():
            out.append({"name": step["name"], "status": "skipped", "tail": ""})
            continue
        try:
            proc = subprocess.run(
                step["cmd"], shell=True, cwd=cwd, capture_output=True, text=True, check=False,
                env=gate_env(), timeout=step.get("timeout", 300),
            )
            status = "ok" if proc.returncode == 0 else "fail"
            tail = "" if status == "ok" else "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-8:])
        except subprocess.TimeoutExpired:
            status, tail = "timeout", f"quá {step.get('timeout', 300)}s"
        out.append({"name": step["name"], "status": status, "tail": tail})
    return out


def new_errors(results, baseline):
    found = {}
    for name, res in results.items():
        allowed = Counter(baseline.get(name, []))
        extra = Counter(res["keys"]) - allowed
        if extra:
            found[name] = {"keys": sorted(extra.elements()), "tail": res["tail"]}
    return found


def summary(found):
    lines = []
    for name, info in found.items():
        lines.append(f"[{name}] {len(info['keys'])} lỗi mới so với baseline:")
        lines += [f"  - {k}" for k in info["keys"]]
        if info["tail"]:
            lines += ["  output:"] + [f"    {t}" for t in info["tail"].splitlines()]
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES] + ["  … (cắt bớt, chạy lại `python3 .autodev/verify.py` để xem đủ)"]
    return "\n".join(lines)


def main():
    args = set(sys.argv[1:])
    config = load(CONFIG, None)
    if config is None:
        print("Thiếu .autodev/config.json", file=sys.stderr)
        return 1

    hook_input = {}
    if "--hook" in args:
        try:
            hook_input = json.loads(sys.stdin.read() or "{}")
        except json.JSONDecodeError:
            hook_input = {}

    if "--smoke" in args:
        res = run_smoke(config.get("smoke", []))
        for r in res:
            print(f"[smoke] {r['status']:8} {r['name']}")
            if r["tail"]:
                print("\n".join(f"    {t}" for t in r["tail"].splitlines()))
        bad = [r for r in res if r["status"] in ("fail", "timeout")]
        print(f"smoke: {'sạch' if not bad else str(len(bad)) + ' lệnh lỗi'}")
        return 2 if bad else 0

    results = run_all(config)

    if "--snapshot" in args:
        save(BASELINE, baseline_from(results))
        print(f"Đã ghi baseline: { {n: len(r['keys']) for n, r in results.items()} }")
        return 0

    found = new_errors(results, load(BASELINE, {}))

    if "--hook" not in args:
        print(summary(found) if found else "verify: sạch (không có lỗi mới so với baseline)")
        return 2 if found else 0

    state = load(STATE, {})
    verify_state = state.setdefault("verify", {})
    # Trace so the orchestrator can confirm the hook actually fired.
    verify_state["hook_runs"] = verify_state.get("hook_runs", 0) + 1
    verify_state["last_hook_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    verify_state["last_hook_agent"] = hook_input.get("agent_type", "")
    if not found:
        verify_state.update(consecutive_blocks=0, last_status="PASS")
        save(STATE, state)
        return 0

    blocks = verify_state.get("consecutive_blocks", 0) + 1
    limit = config.get("max_verify_blocks", 3)
    if blocks > limit:
        # Let the developer stop; the orchestrating session marks the task BLOCKED.
        verify_state.update(consecutive_blocks=0, last_status="VERIFY_FAILED")
        save(STATE, state)
        print(f"verify vẫn lỗi sau {limit} lần chặn; cho dừng, task cần BLOCKED.", file=sys.stderr)
        return 0

    verify_state.update(consecutive_blocks=blocks, last_status="BLOCKED_BY_VERIFY")
    save(STATE, state)
    print(
        f"Verify chưa sạch (lần {blocks}/{limit}). Sửa các lỗi mới rồi commit lại, "
        f"không sửa test hay baseline để né lỗi.\n{summary(found)}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

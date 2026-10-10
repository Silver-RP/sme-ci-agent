"""Hard gates for auto-dev: run verify commands and compare with the baseline.

Usage:
  python3 .autodev/verify.py              # run, print summary; exit 0 clean, 2 new errors
  python3 .autodev/verify.py --snapshot   # write .autodev/baseline.json
  python3 .autodev/verify.py --hook       # SubagentStop hook of the developer agent
  python3 .autodev/verify.py --smoke      # run the user-facing commands in config "smoke" (no baseline)

Also runs test_guard (config "test_guard", default on): blocks loosening tests vs the merge-base with main
(deleted test file/function, added skip/xfail/only, fewer asserts) unless plan/ on main says
`allow-test-change: <path or test name> <reason>`.

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


TEST_FILE_RE = re.compile(r"(^|/)(test_[^/]*\.py|[^/]*_test\.py|[^/]*\.(test|spec)\.[jt]sx?)$")
TEST_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)|^\s*(?:it|test)\(\s*['\"`](.+?)['\"`]")
# Anchored at the start of a code line so marker text inside a string (e.g. the guard's own tests) does not count.
SKIP_RE = re.compile(
    r"^\s*(?:@pytest\.mark\.(?:skip|skipif|xfail)\b|pytestmark\s*=.*pytest\.mark\.(?:skip|skipif|xfail)\b"
    r"|pytest\.(?:skip|xfail)\(|self\.skipTest\(|@unittest\.(?:skip|expectedFailure)"
    r"|(?:it|test|describe)\.(?:skip|only|todo)\(|x(?:it|describe|test)\()"
)
ASSERT_RE = re.compile(r"^\s*assert\b|\bself\.assert\w+\(|\bexpect\(|pytest\.raises\(")
ALLOW_MARK = "allow-test-change:"
GUARD_HINT = (
    "Không nới test để xanh. Đổi hành vi theo plan thì thêm vào commit message một dòng\n"
    f"{ALLOW_MARK} <file test hoặc tên test> <lý do, nêu dev-xx/tiêu chí>  (reviewer sẽ xét lý do)"
)


def weakening(diff, allowed):
    """Keys for test-loosening changes in a unified diff (`git diff -M` of base vs work tree).

    Flags a deleted test file, a test function removed and not re-added anywhere, an added
    skip/xfail/only marker, and a net drop in asserts over all test files. `allowed` holds plan
    tokens (file path or test name) that excuse a change.
    """
    files = []  # [path, deleted, removed_lines, added_lines]
    in_header = False
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            files.append([line.rsplit(" b/", 1)[-1], False, [], []])
            in_header = True
        elif not files:
            continue
        elif in_header:
            files[-1][1] |= line.startswith("deleted file mode")
            in_header = not line.startswith("@@")
        elif line.startswith("-"):
            files[-1][2].append(line[1:])
        elif line.startswith("+"):
            files[-1][3].append(line[1:])

    def names(lines):
        return {m.group(1) or m.group(2) for m in map(TEST_DEF_RE.match, lines) if m}

    tests = [f for f in files if TEST_FILE_RE.search(f[0])]
    added_names = set().union(*(names(f[3]) for f in tests))
    keys, net, losing = [], 0, []
    for path, deleted, removed, added in tests:
        if deleted:
            if path not in allowed:
                keys.append(f"deleted-file:{path}")
            continue
        gone = names(removed) - added_names
        keys += [f"removed-test:{path}::{n}" for n in sorted(gone) if path not in allowed and n not in allowed]
        if gone & allowed:  # an excused removal takes its asserts with it
            allowed = allowed | {path}
        if path not in allowed:
            keys += [f"skip:{path}:{ln.strip()[:60]}" for ln in added if SKIP_RE.search(ln)]
        diff_asserts = sum(map(bool, map(ASSERT_RE.search, added))) - sum(map(bool, map(ASSERT_RE.search, removed)))
        net += diff_asserts
        if diff_asserts < 0 and path not in allowed:
            losing.append(path)
    if net < 0 and losing:
        keys.append(f"fewer-asserts:{net}:{','.join(losing)}")
    return keys


def allow_tokens(text):
    """Tokens from `allow-test-change: <token> <reason>` lines; a line without a reason does not count."""
    out = set()
    for line in text.splitlines():
        if ALLOW_MARK in line:
            words = line.split(ALLOW_MARK, 1)[1].split()
            if len(words) >= 2:
                out.add(words[0].strip("`"))
    return out


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def _guard(cwd):
    """(blocked, justified) for the work tree vs its merge-base on origin/main (or main).

    Allowances in plan/ AT THE BASE (leader-approved) excuse a change fully. A developer can justify one in a commit
    message on the branch: it no longer blocks but is listed as justified so the reviewer judges the reason.
    Outside git or without main: no check.
    """
    for ref in ("origin/main", "main"):
        mb = _git(cwd, "merge-base", ref, "HEAD")
        if mb.returncode == 0:
            base = mb.stdout.strip()
            break
    else:
        return [], []
    diff = _git(cwd, "diff", "-M", "--no-color", "-U0", base).stdout
    plan = allow_tokens(_git(cwd, "grep", "-h", "-e", ALLOW_MARK, base, "--", "plan/").stdout)
    commits = allow_tokens(_git(cwd, "log", "--format=%B", f"{base}..HEAD").stdout)
    flagged = weakening(diff, plan)
    blocked = weakening(diff, plan | commits)
    return blocked, [k for k in flagged if k not in blocked]


def test_guard(cwd=ROOT):
    return _guard(cwd)[0]


def guard_result(cwd=ROOT):
    """test_guard as a verify step; never baselined (it diffs against main, so main itself is always clean)."""
    keys, justified = _guard(cwd)
    return {"keys": keys, "tail": GUARD_HINT if keys else "", "justified": justified}


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

    if config.get("test_guard", True):
        results["test_guard"] = guard_result()
    found = new_errors(results, load(BASELINE, {}))

    justified = results.get("test_guard", {}).get("justified", [])
    if "--hook" not in args:
        print(summary(found) if found else "verify: sạch (không có lỗi mới so với baseline)")
        if justified:
            print(f"[test_guard] {len(justified)} thay đổi test đã giải trình trong commit (reviewer xét lý do):")
            print("\n".join(f"  - {k}" for k in justified))
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

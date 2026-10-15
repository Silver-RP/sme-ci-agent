"""Check docs/goals/<slug>/goal.json, the machine-readable roadmap written by /autodev-goal (P10, design 6.16).

    python3 .autodev/goal_check.py docs/goals/<slug>/goal.json [...]

Prints one line per problem (or "ok") per file; exit 0 when every file passes, 1 when any fails, 2 without
arguments. P11/P12 read goal.json, so a bad file must fail here (CI: .github/workflows/goal-check.yml).
Stdlib only (python3.9).
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOAL_STATUS = ("draft", "approved", "done", "dropped")
MILESTONE_STATUS = ("planned", "done", "cut")
REQUIRED = ("slug", "goal", "status", "done_when", "milestones", "cut_order", "human_only")
LISTS = ("done_when", "milestones", "cut_order", "human_only")
DONE_WHEN_REQUIRED = ("id", "cmd", "threshold")
MILESTONE_REQUIRED = ("id", "title", "depends_on", "est_usd", "est_hours", "status")


def check(data: object, root: Path) -> list[str]:
    if not isinstance(data, dict):
        return ["goal.json phải là một object"]
    errs = [f"thiếu trường `{k}`" for k in REQUIRED if k not in data]
    if errs:
        return errs
    if data["status"] not in GOAL_STATUS:
        errs.append(f"`status` = {data['status']!r}, phải là một trong: {', '.join(GOAL_STATUS)}")
    errs += [f"`{k}` phải là danh sách" for k in LISTS if not isinstance(data[k], list)]
    if errs:
        return errs
    if data["status"] != "draft" and not data["done_when"]:
        errs.append("`done_when` rỗng: mục tiêu đã duyệt phải có điều kiện xong đo được")
    if data["status"] != "draft" and not data["milestones"]:
        errs.append("`milestones` rỗng: mục tiêu đã duyệt phải có ít nhất một mốc")
    for i, item in enumerate(data["done_when"]):
        missing = [k for k in DONE_WHEN_REQUIRED if not (isinstance(item, dict) and _is_name(item.get(k)))]
        if missing:
            errs.append(f"done_when[{i}] thiếu hoặc không phải chuỗi: {', '.join(missing)}")
    milestone_errs, known = _check_milestones(data["milestones"], root)
    errs += milestone_errs
    errs += [
        f"`cut_order` có {c!r} không phải mốc nào"
        for c in data["cut_order"]
        if not _is_name(c) or c not in known
    ]
    return errs


def _is_name(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _is_positive_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value > 0
    )


def _check_milestones(milestones: list, root: Path) -> tuple[list[str], set[str]]:
    errs: list[str] = []
    deps: dict[str, list[str]] = {}
    for i, m in enumerate(milestones):
        if not isinstance(m, dict):
            errs.append(f"milestones[{i}] phải là object")
            continue
        missing = [k for k in MILESTONE_REQUIRED if k not in m]
        if missing:
            errs.append(f"mốc {m.get('id', f'milestones[{i}]')!r} thiếu {', '.join(missing)}")
            continue
        if not _is_name(m["id"]):
            errs.append(f"milestones[{i}]: `id` = {m['id']!r}, phải là chuỗi không rỗng")
            continue
        name = m["id"]
        if name in deps:
            errs.append(f"mốc {name} trùng id")
            continue
        depends_on = m["depends_on"]
        if not isinstance(depends_on, list) or not all(_is_name(d) for d in depends_on):
            errs.append(f"mốc {name}: `depends_on` phải là danh sách id (chuỗi)")
            depends_on = []
        deps[name] = list(depends_on)
        if m["status"] not in MILESTONE_STATUS:
            errs.append(f"mốc {name}: `status` = {m['status']!r}, phải là một trong: {', '.join(MILESTONE_STATUS)}")
        metrics = m.get("metrics", [])
        if not isinstance(metrics, list) or not all(_is_name(x) for x in metrics):
            errs.append(f"mốc {name}: `metrics` phải là danh sách mã chỉ số (chuỗi)")
        elif not metrics and not _is_name(m.get("reason")):
            errs.append(f"mốc {name} không đẩy chỉ số nào (`metrics` rỗng) mà không có `reason`")
        for field in ("est_usd", "est_hours"):
            if not _is_positive_number(m[field]):
                errs.append(f"mốc {name}: `{field}` = {m[field]!r}, phải là số hữu hạn > 0")
        plan_file = m.get("plan_file")
        if plan_file is not None and not (_is_name(plan_file) and (root / plan_file).is_file()):
            errs.append(f"mốc {name}: `plan_file` {plan_file!r} không tồn tại")
    for name, ds in deps.items():
        errs += [f"mốc {name} phụ thuộc {d!r} không phải mốc nào" for d in ds if d not in deps]
    cycle = _find_cycle(deps)
    if cycle:
        errs.append(f"phụ thuộc vòng tròn: {' → '.join(cycle)}")
    return errs, set(deps)


def _find_cycle(deps: dict[str, list[str]]) -> list[str] | None:
    state: dict[str, int] = {}  # 1 = đang đi, 2 = xong
    path: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        path.append(n)
        for d in deps[n]:
            if d not in deps:
                continue
            if state.get(d) == 1:
                return path[path.index(d):] + [d]
            if d not in state:
                found = visit(d)
                if found:
                    return found
        path.pop()
        state[n] = 2
        return None

    for n in deps:
        if n not in state:
            found = visit(n)
            if found:
                return found
    return None


def check_file(path: Path, root: Path = ROOT) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return [f"không đọc được JSON: {e}"]
    errs = check(data, root)
    if isinstance(data, dict) and "slug" in data and data["slug"] != path.parent.name:
        errs.append(f"`slug` = {data['slug']!r} khác tên thư mục {path.parent.name!r}")
    return errs


def main(argv: list[str], root: Path = ROOT) -> int:
    if not argv:
        print("Cách dùng: python3 .autodev/goal_check.py docs/goals/<slug>/goal.json [...]")
        return 2
    failed = 0
    for arg in argv:
        errs = check_file(Path(arg), root)
        for e in errs:
            print(f"{arg}: {e}")
        if errs:
            failed += 1
        else:
            print(f"{arg}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

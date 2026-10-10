"""Recreate the demo database for `scripts/demo.sh --fresh-db` and print its URL.

    uv run python scripts/fresh_db.py <DATABASE_URL>   # prints <same URL with database <name>_demo>

The demo runs on `<name>_demo`, dropped and created empty on every call; the main database (`sme_ci`, used by
tests and auto-dev) is never touched. Only a database whose name ends in `_demo` can be dropped here.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SUFFIX = "_demo"


def demo_url(url: str) -> str:
    u = make_url(url)
    name = u.database if u.database.endswith(SUFFIX) else f"{u.database}{SUFFIX}"
    return u.set(database=name).render_as_string(hide_password=False)


def drop_and_create(url: str) -> None:
    u = make_url(url)
    if not u.database or not u.database.endswith(SUFFIX):
        raise ValueError(f"refusing to drop {u.database!r}: only a database ending in {SUFFIX!r}")
    # connect to the maintenance db "postgres": a database cannot be dropped from a session inside it
    admin = create_engine(u.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{u.database}" WITH (FORCE)'))
            c.execute(text(f'CREATE DATABASE "{u.database}"'))
    finally:
        admin.dispose()


def recreate(url: str) -> str:
    demo = demo_url(url)
    drop_and_create(demo)
    return demo


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: fresh_db.py <DATABASE_URL>", file=sys.stderr)
        return 2
    print(recreate(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

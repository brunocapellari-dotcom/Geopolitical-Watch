from __future__ import annotations

from pathlib import Path
from typing import Iterable


def migration_files(root: str | Path = "sql/migrations") -> tuple[Path, ...]:
    path = Path(root)
    if not path.exists():
        return ()
    return tuple(sorted(p for p in path.glob("*.sql") if p.is_file()))


def apply_migrations(db, root: str | Path = "sql/migrations") -> list[str]:  # type: ignore[no-untyped-def]
    """Apply idempotent SQL migrations after the baseline schema.

    Each migration is expected to be transaction-safe and to record its own
    schema_migrations version. Files are always executed in lexical order.
    """
    applied: list[str] = []
    for path in migration_files(root):
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            continue
        with db.cursor() as cur:
            cur.execute(sql)
        db.commit()
        applied.append(path.name)
    return applied


def validate_migration_contract(paths: Iterable[Path] | None = None) -> list[str]:
    files = tuple(paths) if paths is not None else migration_files()
    seen: set[str] = set()
    names: list[str] = []
    for path in files:
        name = path.name
        if name in seen:
            raise ValueError(f"duplicate migration file: {name}")
        seen.add(name)
        text = path.read_text(encoding="utf-8").casefold()
        if "schema_migrations" not in text:
            raise ValueError(f"migration does not register schema version: {name}")
        names.append(name)
    return names

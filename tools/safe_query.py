"""Bounded read-only SQLite queries with a minimal evidence record.

This module executes supplied SQL; it is not an LLM, investigation agent or
complete SQL sandbox. Do not expose it directly to untrusted users.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class QueryFailure(Exception):
    """A query failed or was rejected, with a partial evidence record."""

    def __init__(self, message: str, evidence: dict[str, Any]):
        super().__init__(message)
        self.evidence = evidence


def execute_read_only(
    database: str | Path,
    sql: str,
    parameters: tuple[Any, ...] | dict[str, Any] = (),
    *,
    question: str = "",
    source_layer: str = "unspecified",
    metric_version: str = "unspecified",
    snapshot_id: str = "unspecified",
    max_rows: int = 100,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    """Run one read-only statement with SQLite authorization and limits.

    Returned rows are capped; truncated means additional rows exist. The
    caller is responsible for choosing a trustworthy source, validating
    metric semantics and recording any parameter values needed for replay.
    """
    if not 1 <= max_rows <= 10000 or not 0 < timeout_seconds <= 60:
        raise ValueError("Limits must be 1–10000 rows and 0–60 seconds.")
    if not sql.strip() or len(sql) > 100_000:
        raise ValueError("SQL must be nonempty and at most 100000 characters.")
    path = Path(database).expanduser().resolve(strict=True)
    if not path.is_file():
        raise ValueError("Database must be an existing file.")
    started = time.monotonic()
    evidence: dict[str, Any] = {
        "question": question, "sql": sql, "source_layer": source_layer,
        "metric_version": metric_version, "snapshot_id": snapshot_id,
        "database_name": path.name, "max_rows": max_rows,
        "timeout_seconds": timeout_seconds,
        "sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "parameters_included": False,
    }
    connection = None
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=timeout_seconds)
        if hasattr(connection, "enable_load_extension"):
            connection.enable_load_extension(False)
        deadline = started + timeout_seconds
        connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION,
                   sqlite3.SQLITE_RECURSIVE}
        forbidden_functions = {"load_extension", "readfile", "writefile", "edit"}

        def authorize(action: int, arg1: str | None, arg2: str | None,
                      _database: str | None, _source: str | None) -> int:
            if action not in allowed:
                return sqlite3.SQLITE_DENY
            if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in forbidden_functions:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        connection.set_authorizer(authorize)
        cursor = connection.execute(sql, parameters)
        if cursor.description is None:
            raise sqlite3.OperationalError("A result-producing read query is required.")
        columns = [item[0] for item in cursor.description]
        rows = cursor.fetchmany(max_rows + 1)
        evidence.update(status="ok", returned_rows=min(len(rows), max_rows),
                        truncated=len(rows) > max_rows)
        return {"columns": columns, "rows": rows[:max_rows], "evidence": evidence}
    except (sqlite3.Error, sqlite3.Warning, OSError) as exc:
        evidence.update(status="error", error_type=type(exc).__name__, error=str(exc))
        raise QueryFailure(str(exc), evidence) from exc
    finally:
        evidence["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        if connection is not None:
            connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute one bounded, read-only SQLite query.")
    parser.add_argument("database")
    parser.add_argument("sql")
    parser.add_argument("--question", default="")
    parser.add_argument("--source-layer", default="unspecified")
    parser.add_argument("--metric-version", default="unspecified")
    parser.add_argument("--snapshot-id", default="unspecified")
    parser.add_argument("--max-rows", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    try:
        result = execute_read_only(args.database, args.sql, question=args.question,
                                   source_layer=args.source_layer, metric_version=args.metric_version,
                                   snapshot_id=args.snapshot_id, max_rows=args.max_rows,
                                   timeout_seconds=args.timeout)
    except QueryFailure as exc:
        print(json.dumps({"error": str(exc), "evidence": exc.evidence}, default=str))
        return 1
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

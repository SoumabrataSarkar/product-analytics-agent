"""Local evidence ledger for bounded read-only investigations.

The caller chooses an output file outside the source database. Records can
contain sensitive SQL, questions, parameters and results; protect them and do
not commit them. This is evidence plumbing, not an investigation agent.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from safe_query import QueryFailure, execute_read_only


class EvidenceLog:
    """Create a new JSON-lines run log without overwriting an existing file."""

    def __init__(self, path: str | Path, question: str):
        if not question.strip():
            raise ValueError("A business question is required.")
        self.path = Path(path)
        self.question = question
        self.run_id = uuid4().hex
        # A new file is deliberately required, including on repeated runs.
        fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"kind": "investigation_started", "run_id": self.run_id,
                                     "recorded_at_utc": self._now(),
                                     "question": question}, allow_nan=False) + "\n")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, ensure_ascii=False, allow_nan=False)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def run_query(self, database: str | Path, sql: str, parameters: tuple[Any, ...] | dict[str, Any] = (),
                  *, snapshot_id: str, source_layer: str, timeframe: str,
                  metric_version: str, purpose: str, limitations: list[str],
                  hypothesis_status: str = "not assessed", include_result: bool = False,
                  include_parameters: bool = False, max_rows: int = 100,
                  timeout_seconds: float = 30.0) -> dict[str, Any]:
        """Execute a query and append its context and outcome to the ledger.

        Values, parameters and rows are omitted by default. When requested,
        callers must ensure values are JSON-serializable and appropriate to
        retain. An explicit snapshot identifier is a caller assertion, not a
        verified content hash. Log write failures are raised to the caller.
        """
        if not all(isinstance(v, str) and v.strip() for v in
                   (snapshot_id, source_layer, timeframe, metric_version, purpose, hypothesis_status)):
            raise ValueError("Snapshot, layer, timeframe, metric, purpose and status are required.")
        if not isinstance(limitations, list) or not all(isinstance(v, str) for v in limitations):
            raise ValueError("Limitations must be a list of strings.")
        if include_parameters:
            json.dumps(parameters, allow_nan=False)  # validate before the query
        record: dict[str, Any] = {
            "kind": "query", "run_id": self.run_id, "recorded_at_utc": self._now(),
            "timeframe": timeframe, "purpose": purpose, "limitations": limitations,
            "hypothesis_status": hypothesis_status,
            "parameters_recorded": include_parameters, "result_recorded": False,
        }
        if include_parameters:
            record["parameters"] = parameters
        try:
            result = execute_read_only(database, sql, parameters, question=self.question,
                                       source_layer=source_layer, metric_version=metric_version,
                                       snapshot_id=snapshot_id, max_rows=max_rows,
                                       timeout_seconds=timeout_seconds)
        except QueryFailure as exc:
            record["query_evidence"] = exc.evidence
            self._append(record)
            raise
        except (ValueError, OSError) as exc:
            record["query_evidence"] = {
                "question": self.question, "sql": sql, "status": "error",
                "snapshot_id": snapshot_id, "source_layer": source_layer,
                "metric_version": metric_version, "error_type": type(exc).__name__,
                "error": str(exc),
            }
            self._append(record)
            raise
        record["query_evidence"] = result["evidence"]
        if include_result:
            # SQLite BLOBs and non-finite floats need an explicit policy.
            # Fail rather than silently stringify or corrupt evidence.
            try:
                json.dumps({"columns": result["columns"], "rows": result["rows"]}, allow_nan=False)
            except (TypeError, ValueError) as exc:
                record["result_recording_error"] = type(exc).__name__
                self._append(record)
                raise
            record["result"] = {"columns": result["columns"], "rows": result["rows"]}
            record["result_recorded"] = True
        self._append(record)
        return result

"""Execute one read-only query and record evidence using JSON on stdin.

Each invocation requires a new local evidence path. Inputs and evidence can
contain sensitive information. Do not use this as an untrusted SQL sandbox.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evidence_log import EvidenceLog
from safe_query import QueryFailure


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one query with a new local evidence log.")
    parser.add_argument("--log", required=True, help="New private JSONL file; must not already exist.")
    args = parser.parse_args()
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Input must be a JSON object.")
        required = ("database", "sql", "question", "snapshot_id", "source_layer",
                    "timeframe", "metric_version", "purpose")
        if not all(isinstance(request.get(k), str) and request[k].strip() for k in required):
            raise ValueError("Missing required query or evidence context.")
        parameters = request.get("parameters", [])
        limitations = request.get("limitations", [])
        if not isinstance(parameters, (list, dict)):
            raise ValueError("Parameters must be an array or object.")
        if not isinstance(limitations, list) or not all(isinstance(x, str) for x in limitations):
            raise ValueError("Limitations must be a list of strings.")
        # Validate configuration before creating a log file.
        timeout = request.get("timeout_seconds", 30.0)
        max_rows = request.get("max_rows", 100)
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not 0 < timeout <= 60 or type(max_rows) is not int or not 1 <= max_rows <= 10000):
            raise ValueError("Invalid query limits.")
        json.dumps(parameters, allow_nan=False)
        log = EvidenceLog(Path(args.log), request["question"])
        result = log.run_query(
            request["database"], request["sql"], parameters,
            snapshot_id=request["snapshot_id"], source_layer=request["source_layer"],
            timeframe=request["timeframe"], metric_version=request["metric_version"],
            purpose=request["purpose"], limitations=limitations,
            hypothesis_status=request.get("hypothesis_status", "not assessed"),
            include_result=True, include_parameters=True,
            max_rows=max_rows, timeout_seconds=timeout,
        )
        print(json.dumps({"result": result, "evidence_file": str(args.log)}, allow_nan=False))
        return 0
    except (QueryFailure, ValueError, TypeError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc), "error_type": type(exc).__name__}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

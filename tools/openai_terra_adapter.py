"""GPT-6.1 Terra adapter for investigation.py (Responses API, stdlib only).

Read one investigation request as JSON from stdin; emit one action as JSON on
stdout. OPENAI_API_KEY is read from the environment and is never printed.
Inputs and query results are sent to OpenAI; do not use with data you are not
authorized to share.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

MODEL = "gpt-6.1-terra"
API_URL = "https://api.openai.com/v1/responses"
FIELDS = {
    "action": {"type": "string", "enum": ["query", "clarify", "finish"]},
    "sql": {"type": ["string", "null"]},
    "parameters": {"type": "array", "items": {"type": ["string", "number", "null"]}},
    "purpose": {"type": ["string", "null"]},
    "timeframe": {"type": ["string", "null"]},
    "source_layer": {"type": ["string", "null"]},
    "metric_version": {"type": ["string", "null"]},
    "limitations": {"type": "array", "items": {"type": "string"}},
    "hypothesis": {"type": ["string", "null"]},
    "round": {"type": ["integer", "null"]},
    "question": {"type": ["string", "null"]},
    "answer": {"type": ["string", "null"]},
}
SCHEMA = {"type": "object", "properties": FIELDS, "required": list(FIELDS),
          "additionalProperties": False}


def make_action(request: dict[str, Any], key: str, *, opener=urllib.request.urlopen) -> dict[str, Any]:
    if not key:
        raise ValueError("OPENAI_API_KEY is not configured.")
    rules = request.get("system")
    if not isinstance(rules, str) or not rules.strip():
        raise ValueError("Investigation instructions are missing.")
    context = {k: v for k, v in request.items() if k != "system"}
    instructions = (rules + "\nReturn every schema field. Use null or an empty array for fields "
                    "not applicable to the chosen action. Use positional SQL parameters only.")
    payload = {"model": MODEL, "instructions": instructions,
               "input": json.dumps(context, ensure_ascii=False), "store": False,
               "max_output_tokens": 4000,
               "text": {"format": {"type": "json_schema", "name": "investigation_action",
                                   "strict": True, "schema": SCHEMA}}}
    http_request = urllib.request.Request(API_URL, data=json.dumps(payload).encode("utf-8"),
                                          headers={"Authorization": "Bearer " + key,
                                                   "Content-Type": "application/json"},
                                          method="POST")
    try:
        with opener(http_request, timeout=100) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError("OpenAI API request failed (HTTP %d)." % exc.code) from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError("OpenAI API connection failed or timed out.") from exc
    if body.get("status") != "completed":
        raise RuntimeError("OpenAI response was not completed.")
    parts = []
    for item in body.get("output", []):
        if item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if part.get("type") == "refusal":
                raise RuntimeError("The model declined this request.")
            if part.get("type") == "output_text":
                parts.append(part.get("text", ""))
    if not parts:
        raise RuntimeError("OpenAI returned no action text.")
    action = json.loads("".join(parts))
    if not isinstance(action, dict) or action.get("action") not in ("query", "clarify", "finish"):
        raise ValueError("OpenAI returned an invalid action.")
    return action


def main() -> int:
    try:
        request = json.load(sys.stdin)
        if not isinstance(request, dict):
            raise ValueError("Input must be a JSON object.")
        action = make_action(request, os.environ.get("OPENAI_API_KEY", ""))
        print(json.dumps(action, ensure_ascii=False))
        return 0
    except (ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

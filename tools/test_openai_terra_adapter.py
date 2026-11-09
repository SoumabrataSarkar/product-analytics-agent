import io
import json
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path

from investigation import investigate
from openai_terra_adapter import MODEL, make_action


class MockResponse:
    def __init__(self, value):
        self.value = io.BytesIO(json.dumps(value).encode())

    def __enter__(self):
        return self.value

    def __exit__(self, *args):
        self.value.close()


class TerraAdapterTests(unittest.TestCase):
    def setUp(self):
        self.request = {"system": "Return an action.", "question": "What is the count?",
                        "registry": "test", "catalog": "test", "history": []}
        self.action = {"action": "clarify", "question": "Which period?"}

    def test_payload_model_and_response_with_reasoning_item(self):
        def opener(request, timeout):
            payload = json.loads(request.data)
            self.assertEqual(payload["model"], MODEL)
            self.assertEqual(payload["model"], "gpt-6.1-terra")
            self.assertFalse(payload["store"])
            self.assertEqual(payload["text"]["format"]["type"], "json_schema")
            self.assertEqual(timeout, 100)
            return MockResponse({"status": "completed", "output": [
                {"type": "reasoning"}, {"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(self.action)}]}]})
        self.assertEqual(make_action(self.request, "test-only", opener=opener), self.action)

    def test_missing_key(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            make_action(self.request, "")

    def test_mocked_model_to_query_to_answer(self):
        decisions = iter([
            {"action": "query", "sql": "SELECT COUNT(*) AS n FROM sample",
             "parameters": [], "purpose": "Count rows", "timeframe": "test",
             "source_layer": "fixture", "metric_version": "test:1",
             "limitations": [], "hypothesis": "Count rows", "round": 1},
            {"action": "finish", "answer": "There is one row.", "limitations": []},
        ])
        def opener(request, timeout):
            return MockResponse({"status": "completed", "output": [
                {"type": "message", "content": [
                    {"type": "output_text", "text": json.dumps(next(decisions))}]}]})
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "sample.sqlite"
            with sqlite3.connect(db) as connection:
                connection.execute("CREATE TABLE sample(id INTEGER)")
                connection.execute("INSERT INTO sample VALUES (1)")
            result = investigate(question="Count?", database=db, snapshot_id="test",
                                 catalog="one table", registry="test metric",
                                 log_path=Path(directory) / "log.jsonl",
                                 model=lambda request: make_action(request, "test-only", opener=opener))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["history"][0]["result"]["rows"], [(1,)])

    def test_incomplete_and_refusal_fail_closed(self):
        for body in ({"status": "incomplete", "output": []},
                     {"status": "completed", "output": [{"type": "message",
                       "content": [{"type": "refusal", "refusal": "No."}]}]}):
            with self.subTest(body=body), self.assertRaises(RuntimeError):
                make_action(self.request, "test-only", opener=lambda *a, **k: MockResponse(body))

    def test_http_error_does_not_expose_body(self):
        def opener(*args, **kwargs):
            raise urllib.error.HTTPError("https://example.invalid", 401, "error", None,
                                         io.BytesIO(b"secret body"))
        with self.assertRaises(RuntimeError) as caught:
            make_action(self.request, "test-only", opener=opener)
        self.assertNotIn("secret body", str(caught.exception))
        self.assertIn("401", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

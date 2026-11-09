import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from investigation import investigate


def query(sql="SELECT COUNT(*) AS count FROM items", hypothesis="Baseline", round_number=1):
    return {"action": "query", "sql": sql, "parameters": [], "purpose": "Check baseline",
            "timeframe": "test snapshot", "source_layer": "fixture", "metric_version": "test:1",
            "limitations": ["Test fixture"], "hypothesis": hypothesis, "round": round_number}


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "test.sqlite"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE items (id INTEGER)")
            conn.executemany("INSERT INTO items VALUES (?)", [(1,), (2,)])
        self.args = dict(question="How many items?", database=self.db, snapshot_id="test-1",
                         catalog="Test catalog", registry="Test registry",
                         log_path=self.root / "evidence.jsonl")

    def tearDown(self):
        self.temp.cleanup()

    def test_model_can_query_and_use_result_then_finish(self):
        requests = []
        def model(request):
            requests.append(request)
            if not request["history"]:
                return query()
            self.assertEqual(request["history"][0]["result"]["rows"], [(2,)])
            return {"action": "finish", "answer": "There are two items.", "limitations": ["Test data"]}
        output = investigate(model=model, **self.args)
        self.assertEqual(output["status"], "completed")
        self.assertEqual(output["queries"], 1)
        records = [json.loads(line) for line in self.args["log_path"].read_text().splitlines()]
        self.assertEqual(records[1]["result"]["rows"], [[2]])
        self.assertIn("Baseline", records[1]["purpose"])
        self.assertEqual(requests[1]["query_budget_remaining"], 8)

    def test_clarification_without_query(self):
        output = investigate(model=lambda _: {"action": "clarify", "question": "Which period?"}, **self.args)
        self.assertEqual(output["status"], "clarification_needed")
        self.assertEqual(output["queries"], 0)

    def test_finish_without_evidence_is_not_completed(self):
        output = investigate(model=lambda _: {"action": "finish", "answer": "Unknown", "limitations": []}, **self.args)
        self.assertEqual(output["status"], "insufficient_evidence")

    def test_failed_query_can_be_corrected(self):
        decisions = iter([query("DELETE FROM items"), query(),
                          {"action": "finish", "answer": "Two.", "limitations": []}])
        output = investigate(model=lambda _: next(decisions), **self.args)
        self.assertEqual(output["status"], "completed")
        self.assertIn("error", output["history"][0])
        self.assertEqual(output["queries"], 2)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 2)

    def test_budget_ends_with_human_escalation(self):
        output = investigate(model=lambda _: query(), query_budget=1, **self.args)
        self.assertEqual(output["status"], "budget_exhausted")
        self.assertEqual(output["queries"], 1)

    def test_fourth_hypothesis_in_round_rejected(self):
        decisions = iter([query(hypothesis=str(i)) for i in range(4)])
        output = investigate(model=lambda _: next(decisions), **self.args)
        self.assertEqual(output["status"], "invalid_model_response")
        self.assertEqual(output["queries"], 3)

    def test_adapter_failure_is_not_a_result(self):
        def model(_):
            raise RuntimeError("unavailable")
        output = investigate(model=model, **self.args)
        self.assertEqual(output["status"], "model_error")
        self.assertEqual(output["queries"], 0)


if __name__ == "__main__":
    unittest.main()

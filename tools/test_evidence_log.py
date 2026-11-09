import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from evidence_log import EvidenceLog
from safe_query import QueryFailure


class EvidenceLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "source.sqlite"
        with sqlite3.connect(self.db) as conn:
            conn.execute("CREATE TABLE sales (amount INTEGER)")
            conn.executemany("INSERT INTO sales VALUES (?)", [(3,), (5,), (7,)])
        self.path = self.root / "run.jsonl"
        self.log = EvidenceLog(self.path, "What is total sales?")
        self.context = dict(snapshot_id="test-snapshot", source_layer="fixture",
                            timeframe="all test data", metric_version="test:1",
                            purpose="Calculate the baseline", limitations=["Synthetic example"])

    def tearDown(self):
        self.temp.cleanup()

    def records(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def test_query_and_result_recorded_when_requested(self):
        result = self.log.run_query(self.db, "SELECT SUM(amount) AS total FROM sales",
                                    include_result=True, **self.context)
        self.assertEqual(result["rows"], [(15,)])
        start, query = self.records()
        self.assertEqual(start["run_id"], query["run_id"])
        self.assertEqual(query["result"]["rows"], [[15]])
        self.assertEqual(query["query_evidence"]["status"], "ok")
        self.assertEqual(query["timeframe"], "all test data")

    def test_sensitive_values_omitted_by_default(self):
        self.log.run_query(self.db, "SELECT amount FROM sales WHERE amount > ?", (3,), **self.context)
        query = self.records()[1]
        self.assertNotIn("parameters", query)
        self.assertNotIn("result", query)
        self.assertFalse(query["result_recorded"])

    def test_query_failure_logged_and_propagated(self):
        with self.assertRaises(QueryFailure):
            self.log.run_query(self.db, "DELETE FROM sales", **self.context)
        self.assertEqual(self.records()[1]["query_evidence"]["status"], "error")
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sales").fetchone()[0], 3)

    def test_missing_database_is_logged(self):
        with self.assertRaises(FileNotFoundError):
            self.log.run_query(self.root / "missing.sqlite", "SELECT 1", **self.context)
        self.assertEqual(self.records()[1]["query_evidence"]["error_type"], "FileNotFoundError")

    def test_unserializable_results_do_not_silently_disappear(self):
        with self.assertRaises(TypeError):
            self.log.run_query(self.db, "SELECT x'0102' AS value", include_result=True, **self.context)
        query = self.records()[1]
        self.assertEqual(query["query_evidence"]["status"], "ok")
        self.assertEqual(query["result_recording_error"], "TypeError")
        self.assertFalse(query["result_recorded"])

    def test_existing_log_is_never_overwritten(self):
        original = self.path.read_text()
        with self.assertRaises(FileExistsError):
            EvidenceLog(self.path, "Another question")
        self.assertEqual(self.path.read_text(), original)


if __name__ == "__main__":
    unittest.main()

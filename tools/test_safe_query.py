import sqlite3
import tempfile
import unittest
from pathlib import Path

from safe_query import QueryFailure, execute_read_only


class SafeQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.sqlite"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE items (id INTEGER, value TEXT)")
            con.executemany("INSERT INTO items VALUES (?, ?)", [(1, "a"), (2, "b"), (3, "c")])

    def tearDown(self):
        self.temp.cleanup()

    def test_select_and_evidence(self):
        result = execute_read_only(self.db, "SELECT value FROM items WHERE id = ?", (2,),
                                   question="Example", source_layer="fixture",
                                   metric_version="test:1", snapshot_id="fixture-v1")
        self.assertEqual(result["rows"], [("b",)])
        self.assertEqual(result["evidence"]["question"], "Example")
        self.assertEqual(result["evidence"]["snapshot_id"], "fixture-v1")
        self.assertFalse(result["evidence"]["truncated"])
        self.assertIn("duration_ms", result["evidence"])

    def test_cap_and_truncation(self):
        result = execute_read_only(self.db, "SELECT id FROM items ORDER BY id", max_rows=2)
        self.assertEqual(result["rows"], [(1,), (2,)])
        self.assertTrue(result["evidence"]["truncated"])

    def test_forbidden_operations(self):
        for sql in ("DELETE FROM items", "PRAGMA user_version", "ATTACH DATABASE ':memory:' AS x",
                    "SELECT load_extension('bad')", "SELECT 1; DELETE FROM items"):
            with self.subTest(sql=sql), self.assertRaises(QueryFailure) as caught:
                execute_read_only(self.db, sql)
            self.assertEqual(caught.exception.evidence["status"], "error")
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM items").fetchone()[0], 3)

    def test_recursive_query_is_interrupted(self):
        with self.assertRaises(QueryFailure):
            execute_read_only(self.db, "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n) "
                              "SELECT sum(x) FROM n", timeout_seconds=.01)

    def test_missing_file_is_not_created(self):
        missing = Path(self.temp.name) / "missing.sqlite"
        with self.assertRaises(FileNotFoundError):
            execute_read_only(missing, "SELECT 1")
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EvidenceQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "source.sqlite"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE sample (id INTEGER)")
            con.executemany("INSERT INTO sample VALUES (?)", [(1,), (2,)])
        self.log = self.root / "evidence.jsonl"
        self.request = dict(database=str(self.db), question="How many?",
                            sql="SELECT count(*) AS n FROM sample WHERE id > ?",
                            parameters=[0], snapshot_id="fixture-v1", source_layer="fixture",
                            timeframe="all", metric_version="test:1", purpose="Count",
                            limitations=["Synthetic test data"])
        self.script = Path(__file__).with_name("evidence_query.py")

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, request):
        return subprocess.run([sys.executable, str(self.script), "--log", str(self.log)],
                              input=json.dumps(request), text=True, capture_output=True)

    def test_success_has_replayable_parameters_and_result(self):
        proc = self.run_tool(self.request)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["result"]["rows"], [[2]])
        lines = [json.loads(x) for x in self.log.read_text().splitlines()]
        self.assertEqual(lines[1]["parameters"], [0])
        self.assertEqual(lines[1]["result"]["rows"], [[2]])
        self.assertEqual(lines[1]["query_evidence"]["snapshot_id"], "fixture-v1")

    def test_rejects_write_and_records_error(self):
        self.request["sql"] = "DELETE FROM sample"
        self.request["parameters"] = []
        proc = self.run_tool(self.request)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(json.loads(self.log.read_text().splitlines()[1])["query_evidence"]["status"], "error")
        with sqlite3.connect(self.db) as con:
            self.assertEqual(con.execute("SELECT count(*) FROM sample").fetchone()[0], 2)

    def test_existing_log_is_not_overwritten(self):
        self.log.write_text("keep")
        proc = self.run_tool(self.request)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.log.read_text(), "keep")

    def test_missing_context_does_not_create_log(self):
        del self.request["snapshot_id"]
        self.assertNotEqual(self.run_tool(self.request).returncode, 0)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()

"""Audit timestamp rules for refund episode allocations."""
import ast
import datetime as dt
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ') == value)
    except (ValueError, TypeError):
        return 0

class AllocationTimestampTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, valid_utc)
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,transaction_at TEXT);
          CREATE TABLE refund_content_attribution(refund_txn_id TEXT,created_at TEXT,updated_at TEXT);
          INSERT INTO transactions VALUES('r','2026-01-01T10:00:00Z');
          INSERT INTO refund_content_attribution VALUES('r','2026-01-01T10:00:00Z','2026-01-01T10:00:00Z');
        ''')

    def count(self):
        return self.db.execute(checks['refund allocation audit timestamps invalid']).fetchone()[0]

    def test_equal_or_later_update_is_valid(self):
        self.assertEqual(self.count(), 0)
        self.db.execute("UPDATE refund_content_attribution SET updated_at='2026-01-01T10:05:00Z'")
        self.assertEqual(self.count(), 0)

    def test_bad_utc_missing_or_backdated_values_fail(self):
        for created, updated in ((None,'2026-01-01T10:00:00Z'), ('2026-01-01', '2026-01-01T10:00:00Z'),
                                 ('2026-01-01T09:59:00Z','2026-01-01T10:00:00Z'),
                                 ('2026-01-01T10:00:00Z','2026-01-01T09:59:00Z'),
                                 ('2026-01-01T10:00:00Z',None)):
            self.db.execute('UPDATE refund_content_attribution SET created_at=?,updated_at=?', (created, updated))
            self.assertEqual(self.count(), 1, (created, updated))

if __name__ == '__main__':
    unittest.main()

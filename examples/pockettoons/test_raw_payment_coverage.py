"""Every fixture transaction has exactly one raw payment source record."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class RawPaymentCoverageTests(unittest.TestCase):
    def test_missing_complete_and_duplicate_records(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE transactions(txn_id TEXT PRIMARY KEY)')
        # The fixture primary key prevents duplicates. This minimal table also
        # exercises the coverage query against a malformed alternative schema.
        db.execute('CREATE TABLE raw_payment_source(txn_id TEXT, raw_amount)')
        db.executemany('INSERT INTO transactions VALUES (?)', [('a',), ('b',)])
        query = checks['transaction raw source coverage invalid']
        self.assertEqual(db.execute(query).fetchone()[0], 2)
        db.execute("INSERT INTO raw_payment_source VALUES ('a', 'unavailable')")
        self.assertEqual(db.execute(query).fetchone()[0], 1)
        db.execute("INSERT INTO raw_payment_source VALUES ('b', 999)")
        self.assertEqual(db.execute(query).fetchone()[0], 0)
        db.execute("INSERT INTO raw_payment_source VALUES ('b', 9.99)")
        self.assertEqual(db.execute(query).fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT raw_amount FROM raw_payment_source WHERE txn_id='a'").fetchone()[0], 'unavailable')


if __name__ == '__main__':
    unittest.main()

"""Unexpected raw payment units require a review in this USD fixture."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class RawPaymentUnitTests(unittest.TestCase):
    def test_unexpected_units_require_review_without_modification(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE raw_payment_source(txn_id TEXT, raw_unit TEXT, raw_amount)')
        db.execute('CREATE TABLE payment_quality_review(txn_id TEXT)')
        records = [('a', 'USD', 9.99), ('b', 'cents', 999),
                   ('c', 'EUR', '9.99'), ('d', '', 'unavailable')]
        db.executemany('INSERT INTO raw_payment_source VALUES (?,?,?)', records)
        check = checks['raw payment unexpected unit missing review']
        self.assertEqual(db.execute(check).fetchone()[0], 3)
        db.executemany('INSERT INTO payment_quality_review VALUES (?)', [('b',), ('c',), ('d',)])
        self.assertEqual(db.execute(check).fetchone()[0], 0)
        self.assertEqual(db.execute('SELECT * FROM raw_payment_source').fetchall(), records)


if __name__ == '__main__':
    unittest.main()

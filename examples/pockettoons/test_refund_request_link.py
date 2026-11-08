"""Refund requests identify the same user's original purchase."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class RefundRequestLinkTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE transactions(txn_id TEXT, user_id TEXT, type TEXT)')
        self.db.execute('CREATE TABLE user_events(event_name TEXT, user_id TEXT, txn_id TEXT)')
        self.db.executemany('INSERT INTO transactions VALUES (?,?,?)', [
            ('sub', 'u1', 'subscription'), ('ppv', 'u1', 'ppv'),
            ('refund', 'u1', 'refund'), ('other', 'u2', 'ppv'),
            ('bad_type', 'u1', None),
        ])

    def test_link_validation(self):
        cases = [
            ('refund_requested', 'u1', 'sub', 0),
            ('refund_requested', 'u1', 'ppv', 0),
            ('refund_requested', 'u1', None, 1),
            ('refund_requested', 'u1', 'missing', 1),
            ('refund_requested', None, 'sub', 1),
            ('refund_requested', 'u1', 'other', 1),
            ('refund_requested', 'u1', 'refund', 1),
            ('refund_requested', 'u1', 'bad_type', 1),
            ('other_event', None, None, 0),
        ]
        for event, user, txn, expected in cases:
            with self.subTest(event=event, user=user, txn=txn):
                self.db.execute('DELETE FROM user_events')
                self.db.execute('INSERT INTO user_events VALUES (?,?,?)', (event, user, txn))
                actual = self.db.execute(checks['refund request purchase link invalid']).fetchone()[0]
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()

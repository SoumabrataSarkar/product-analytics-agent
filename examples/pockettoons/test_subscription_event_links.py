"""Subscription events must refer to the right period and business moment."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class SubscriptionEventLinkTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE user_events(event_name TEXT, user_id TEXT, subscription_period_id TEXT, txn_id TEXT, event_at TEXT)')
        self.db.execute('CREATE TABLE subscription_history(subscription_period_id TEXT, user_id TEXT, source_txn_id TEXT, cancelled_at TEXT)')
        self.db.execute('CREATE TABLE transactions(txn_id TEXT, user_id TEXT, type TEXT)')
        self.db.executemany('INSERT INTO subscription_history VALUES (?,?,?,?)', [
            ('p1', 'u1', 't1', '2026-05-02T00:00:00Z'),
            ('p2', 'u2', 't2', None),
            ('p3', 'u1', None, None)])
        self.db.executemany('INSERT INTO transactions VALUES (?,?,?)', [
            ('t1', 'u1', 'subscription'), ('t2', 'u2', 'subscription'),
            ('ppv', 'u1', 'ppv')])

    def count(self, name, event):
        self.db.execute('DELETE FROM user_events')
        self.db.execute('INSERT INTO user_events VALUES (?,?,?,?,?)', event)
        return self.db.execute(checks[name]).fetchone()[0]

    def test_period_user_and_presence(self):
        name = 'subscription event period link invalid'
        for period, user, expected in [('p1', 'u1', 0), ('p2', 'u1', 1),
                                       (None, 'u1', 1), ('missing', 'u1', 1),
                                       ('p1', None, 1)]:
            for event_name in ('subscription_started', 'subscription_cancel_requested'):
                with self.subTest(period=period, user=user, event=event_name):
                    self.assertEqual(self.count(name, (event_name, user, period, None, '2026-05-02T00:00:00Z')), expected)

    def test_start_purchase(self):
        name = 'subscription start purchase link invalid'
        for period, user, txn, expected in [('p1', 'u1', 't1', 0),
                                            ('p1', 'u1', None, 1),
                                            ('p1', 'u1', 'ppv', 1),
                                            ('p1', 'u2', 't1', 1),
                                            ('p3', 'u1', None, 1)]:
            with self.subTest(period=period, user=user, txn=txn):
                self.assertEqual(self.count(name, ('subscription_started', user, period, txn, '2026-05-02T00:00:00Z')), expected)
        self.db.execute("UPDATE transactions SET type='ppv' WHERE txn_id='t1'")
        self.assertEqual(self.count(name, ('subscription_started', 'u1', 'p1', 't1', '2026-05-02T00:00:00Z')), 1)

    def test_cancellation_time(self):
        name = 'subscription cancellation event time invalid'
        for period, user, timestamp, expected in [
            ('p1', 'u1', '2026-05-02T00:00:00Z', 0),
            ('p1', 'u1', '2026-05-03T00:00:00Z', 1),
            ('p1', 'u2', '2026-05-02T00:00:00Z', 1),
            ('p3', 'u1', '2026-05-02T00:00:00Z', 1),
            (None, 'u1', '2026-05-02T00:00:00Z', 1)]:
            with self.subTest(period=period, user=user, timestamp=timestamp):
                self.assertEqual(self.count(name, ('subscription_cancel_requested', user, period, None, timestamp)), expected)


if __name__ == '__main__':
    unittest.main()

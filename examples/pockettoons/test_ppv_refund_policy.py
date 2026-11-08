"""Regression coverage for cumulative episode refunds and PPV access."""
import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'usd_cents')
scope = {'Decimal': Decimal, 'InvalidOperation': InvalidOperation}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<money>', 'exec'), scope)

class RefundPolicyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('usd_cents', 1, scope['usd_cents'])
        self.db.executescript('''
        CREATE TABLE transaction_content_attribution(txn_content_attribution_id TEXT,txn_id TEXT,content_id TEXT,episode_number INTEGER,attributed_amount_usd REAL,refunded_at TEXT,delisted_at TEXT,entitlement_end_at TEXT,attribution_status TEXT);
        CREATE TABLE transactions(txn_id TEXT,related_txn_id TEXT,type TEXT,transaction_subtype TEXT);
        CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT);
        CREATE TABLE refund_content_attribution(refund_txn_id TEXT,content_id TEXT,episode_number INTEGER,allocated_refund_usd REAL);
        INSERT INTO transaction_content_attribution VALUES('a','purchase','series',1,1.99,NULL,NULL,NULL,'granted');
        ''')

    def refund(self, txn, amount, at, status='succeeded', episode=1):
        self.db.execute("INSERT INTO transactions VALUES(?, 'purchase', 'refund', 'ppv_refund')", (txn,))
        self.db.execute('INSERT INTO payment_status_history VALUES(?,?,?)', (txn, status, at))
        self.db.execute("INSERT INTO refund_content_attribution VALUES(?, 'series', ?, ?)", (txn, episode, amount))

    def violations(self):
        return self.db.execute(checks['PPV episode cumulative refund and entitlement inconsistent']).fetchone()[0]

    def test_partial_then_cumulative_full(self):
        self.refund('r1', 0.99, '2026-01-01T10:00:00Z')
        self.assertEqual(self.violations(), 0)
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-01T10:00:00Z'")
        self.assertEqual(self.violations(), 1)
        self.db.execute('UPDATE transaction_content_attribution SET refunded_at=NULL')
        self.refund('r2', 1.00, '2026-01-02T10:00:00Z')
        self.assertEqual(self.violations(), 1)
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-02T10:00:00Z',entitlement_end_at='2026-01-02T10:00:00Z',attribution_status='refunded'")
        self.assertEqual(self.violations(), 0)
        self.refund('r3', 0.01, '2026-01-03T10:00:00Z')
        self.assertEqual(self.violations(), 1)

    def test_failed_refund_does_not_revoke(self):
        self.refund('r', 1.99, '2026-01-01T10:00:00Z', status='failed')
        self.assertEqual(self.violations(), 0)
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-01T10:00:00Z'")
        self.assertEqual(self.violations(), 1)

    def test_pending_refund_does_not_revoke(self):
        self.refund('r', 1.99, '2026-01-01T10:00:00Z', status='pending')
        self.assertEqual(self.violations(), 0)
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-01T10:00:00Z'")
        self.assertEqual(self.violations(), 1)

    def test_multiple_refunds_at_same_instant(self):
        self.refund('r1', 0.99, '2026-01-01T10:00:00Z')
        self.refund('r2', 1.00, '2026-01-01T10:00:00Z')
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-01T10:00:00Z',entitlement_end_at='2026-01-01T10:00:00Z',attribution_status='refunded'")
        self.assertEqual(self.violations(), 0)

    def test_duplicate_refund_episode_is_flagged(self):
        self.refund('r1', 0.50, '2026-01-01T10:00:00Z')
        self.db.execute("INSERT INTO refund_content_attribution VALUES('r1','series',1,0.49)")
        self.assertEqual(self.db.execute(checks['duplicate refund episode allocations']).fetchone()[0], 1)

    def test_unique_index_allows_distinct_refunds_and_episodes(self):
        self.db.execute('CREATE UNIQUE INDEX ux_refund_episode ON refund_content_attribution(refund_txn_id,content_id,episode_number)')
        self.refund('r1', 0.50, '2026-01-01T10:00:00Z')
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO refund_content_attribution VALUES('r1','series',1,0.49)")
        self.db.execute("INSERT INTO refund_content_attribution VALUES('r1','series',2,0.49)")
        self.refund('r2', 0.50, '2026-01-02T10:00:00Z')
        self.assertEqual(self.db.execute(checks['duplicate refund episode allocations']).fetchone()[0], 0)

    def test_refund_after_delisting_does_not_rewrite_earlier_end(self):
        self.db.execute("UPDATE transaction_content_attribution SET delisted_at='2026-01-01T09:00:00Z',entitlement_end_at='2026-01-01T09:00:00Z',attribution_status='expired_delisting'")
        self.refund('r', 1.99, '2026-01-01T10:00:00Z')
        self.assertEqual(self.violations(), 0)

    def test_bundle_refund_is_episode_specific(self):
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('b','purchase','series',2,1.00,NULL,NULL,NULL,'granted')")
        self.refund('r', 1.00, '2026-01-01T10:00:00Z', episode=2)
        self.assertEqual(self.violations(), 1)
        self.db.execute("UPDATE transaction_content_attribution SET refunded_at='2026-01-01T10:00:00Z',entitlement_end_at='2026-01-01T10:00:00Z',attribution_status='refunded' WHERE txn_content_attribution_id='b'")
        self.assertEqual(self.violations(), 0)

if __name__ == '__main__':
    unittest.main()

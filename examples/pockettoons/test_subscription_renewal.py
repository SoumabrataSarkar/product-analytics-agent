"""Renewal timing and subscription access across period boundaries."""
import ast
import calendar
import datetime as dt
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'next_calendar_month')
scope = {'dt': dt, 'calendar': calendar}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<calendar>', 'exec'), scope)

class RenewalTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.snapshot='2026-10-31T12:00:00Z'
        self.db.create_function('next_calendar_month',1,scope['next_calendar_month'])
        self.db.create_function('users_snapshot_at',0,lambda:self.snapshot)
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,type TEXT,transaction_subtype TEXT,status TEXT,subscription_id TEXT,transaction_at TEXT,related_txn_id TEXT);
          CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT);
          CREATE TABLE subscription_history(user_id TEXT,subscription_id TEXT,source_txn_id TEXT,status TEXT,effective_start_at TEXT,effective_end_at TEXT);
          CREATE TABLE users(user_id TEXT,subscription_status TEXT,subscription_start TEXT,subscription_end TEXT);
          INSERT INTO transactions VALUES('initial','u','subscription','subscription_initial','succeeded','s','2026-10-01T10:05:00Z',NULL);
          INSERT INTO payment_status_history VALUES('initial','succeeded','2026-10-01T10:05:00Z');
          INSERT INTO subscription_history VALUES('u','s','initial','active','2026-10-01T10:05:00Z','2026-11-01T10:05:00Z');
          INSERT INTO users VALUES('u','active','2026-10-01T10:05:00Z','2026-11-01T10:05:00Z');
        ''')

    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]

    def add_renewal(self,status,created,success=None,start=None,end=None):
        self.db.execute("INSERT INTO transactions VALUES('renew','u','subscription','subscription_renewal',?,'s',?,NULL)",(status,created))
        if success:
            self.db.execute("INSERT INTO payment_status_history VALUES('renew','succeeded',?)",(success,))
        if start:
            self.db.execute("INSERT INTO subscription_history VALUES('u','s','renew','active',?,?)",(start,end))

    def access(self,at):
        return self.db.execute("SELECT count(*) FROM subscription_history WHERE user_id='u' AND status IN ('active','cancel_at_period_end') AND effective_start_at<=? AND (effective_end_at IS NULL OR ?<effective_end_at)",(at,at)).fetchone()[0]

    def test_early_success_preserves_paid_time_and_snapshot(self):
        self.add_renewal('succeeded','2026-10-31T09:00:00Z','2026-10-31T09:00:00Z','2026-11-01T10:05:00Z','2026-12-01T10:05:00Z')
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),0)
        self.assertEqual(self.count('monthly subscription period invalid'),0)
        self.assertEqual(self.count('subscription snapshot boundaries inconsistent'),0)
        self.assertEqual(self.access('2026-11-01T10:04:59Z'),1)
        self.assertEqual(self.access('2026-11-01T10:05:00Z'),1)
        self.db.execute("UPDATE subscription_history SET effective_start_at='2026-10-31T09:00:00Z' WHERE source_txn_id='renew'")
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),1)

    def test_late_success_has_gap_and_new_monthly_anchor(self):
        self.add_renewal('succeeded','2026-11-01T10:00:00Z','2026-11-01T10:20:00Z','2026-11-01T10:20:00Z','2026-12-01T10:20:00Z')
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),1)
        self.db.execute("INSERT INTO subscription_history VALUES('u','s',NULL,'expired','2026-11-01T10:05:00Z','2026-11-01T10:20:00Z')")
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),0)
        self.db.execute("UPDATE subscription_history SET effective_end_at='2026-11-01T10:10:00Z' WHERE status='expired'")
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),1)
        self.db.execute("INSERT INTO subscription_history VALUES('u','s',NULL,'expired','2026-11-01T10:10:00Z','2026-11-01T10:20:00Z')")
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),0)
        self.db.execute("DELETE FROM subscription_history WHERE status='expired' AND effective_start_at='2026-11-01T10:10:00Z'")
        self.db.execute("UPDATE subscription_history SET effective_end_at='2026-11-01T10:20:00Z' WHERE status='expired'")
        self.assertEqual(self.count('monthly subscription period invalid'),0)
        self.assertEqual(self.access('2026-11-01T10:04:59Z'),1)
        self.assertEqual(self.access('2026-11-01T10:05:00Z'),0)
        self.assertEqual(self.access('2026-11-01T10:19:59Z'),0)
        self.assertEqual(self.access('2026-11-01T10:20:00Z'),1)
        self.snapshot='2026-11-01T10:10:00Z'
        self.db.execute("UPDATE users SET subscription_status='expired',subscription_start='2026-10-01T10:05:00Z',subscription_end='2026-11-01T10:05:00Z'")
        self.assertEqual(self.count('subscription snapshot boundaries inconsistent'),0)
        self.snapshot='2026-11-01T10:21:00Z'
        self.db.execute("UPDATE users SET subscription_status='active',subscription_start='2026-11-01T10:20:00Z',subscription_end='2026-12-01T10:20:00Z'")
        self.assertEqual(self.count('subscription snapshot boundaries inconsistent'),0)
        self.db.execute("UPDATE subscription_history SET effective_start_at='2026-11-01T10:05:00Z' WHERE source_txn_id='renew'")
        self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),1)

    def test_pending_or_failed_does_not_extend_access(self):
        for status in ('pending','failed'):
            self.add_renewal(status,'2026-11-01T10:00:00Z')
            self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),0)
            self.assertEqual(self.access('2026-11-01T10:05:00Z'),0)
            self.db.execute("INSERT INTO subscription_history VALUES('u','s','renew','active','2026-11-01T10:05:00Z','2026-12-01T10:05:00Z')")
            self.assertEqual(self.count('subscription renewal start inconsistent with success and previous end'),1)
            self.db.execute("DELETE FROM subscription_history WHERE source_txn_id='renew'")
            self.db.execute("DELETE FROM transactions WHERE txn_id='renew'")

if __name__ == '__main__':
    unittest.main()

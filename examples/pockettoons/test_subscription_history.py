"""Subscription history continuity, audit fields and refund timing."""
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

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')==value)
    except (TypeError,ValueError):
        return 0

class SubscriptionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.create_function('next_calendar_month',1,scope['next_calendar_month'])
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,subscription_id TEXT,transaction_subtype TEXT,status TEXT,transaction_at TEXT,related_txn_id TEXT);
          CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT);
          CREATE TABLE subscription_history(subscription_period_id TEXT,user_id TEXT,subscription_id TEXT,source_txn_id TEXT,status TEXT,effective_start_at TEXT,effective_end_at TEXT,subscription_status_updated_at TEXT,recorded_at TEXT,cancelled_at TEXT,plan_code TEXT);
          INSERT INTO transactions VALUES('charge','u','s','subscription_initial','succeeded','2026-10-01T10:00:00Z',NULL);
          INSERT INTO subscription_history VALUES('h1','u','s','charge','active','2026-10-01T10:00:00Z','2026-10-03T10:05:00Z','2026-10-01T10:00:00Z','2026-10-01T10:00:00Z',NULL,'monthly_9_99');
        ''')

    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_delayed_refund_closes_at_success_not_attempt(self):
        self.db.execute("INSERT INTO transactions VALUES('refund','u','s','subscription_refund','pending','2026-10-03T10:00:00Z','charge')")
        self.assertEqual(self.count('subscription refunds without revoked access'),0)
        self.db.execute("INSERT INTO subscription_history VALUES('bad','u','s','refund','refunded','2026-10-03T10:00:00Z',NULL,'2026-10-03T10:00:00Z','2026-10-03T10:00:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription refunded before refund success'),1)
        self.db.execute("DELETE FROM subscription_history WHERE subscription_period_id='bad'")
        self.db.execute("UPDATE transactions SET status='succeeded' WHERE txn_id='refund'")
        self.db.execute("INSERT INTO payment_status_history VALUES('refund','succeeded','2026-10-03T10:05:00Z')")
        self.db.execute("INSERT INTO subscription_history VALUES('h2','u','s','refund','refunded','2026-10-03T10:05:00Z',NULL,'2026-10-03T10:05:00Z','2026-10-03T10:05:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription refunds without revoked access'),0)
        self.assertEqual(self.count('subscription refunded before refund success'),0)
        self.db.execute("UPDATE subscription_history SET effective_start_at='2026-10-03T10:00:00Z' WHERE subscription_period_id='h2'")
        self.assertEqual(self.count('subscription refunds without revoked access'),1)
        self.assertEqual(self.count('subscription refunded before refund success'),1)

    def test_failed_refund_cannot_end_subscription(self):
        self.db.execute("INSERT INTO transactions VALUES('refund','u','s','subscription_refund','failed','2026-10-03T10:00:00Z','charge')")
        self.db.execute("INSERT INTO subscription_history VALUES('h2','u','s','refund','refunded','2026-10-03T10:00:00Z',NULL,'2026-10-03T10:00:00Z','2026-10-03T10:00:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription refunded before refund success'),1)

    def test_old_period_refund_preserves_separately_paid_renewal(self):
        self.db.execute('ALTER TABLE transactions ADD COLUMN type TEXT')
        self.db.execute("UPDATE transactions SET type='subscription' WHERE txn_id='charge'")
        self.db.execute("UPDATE subscription_history SET effective_end_at='2026-11-01T10:00:00Z' WHERE subscription_period_id='h1'")
        self.db.execute("INSERT INTO transactions VALUES('renewal','u','s','subscription_renewal','succeeded','2026-11-01T10:00:00Z',NULL,'subscription')")
        self.db.execute("INSERT INTO subscription_history VALUES('h2','u','s','renewal','active','2026-11-01T10:00:00Z','2026-12-01T10:00:00Z','2026-11-01T10:00:00Z','2026-11-01T10:00:00Z',NULL,'monthly_9_99')")
        self.db.execute("INSERT INTO transactions VALUES('refund','u','s','subscription_refund','succeeded','2026-11-15T10:00:00Z','charge','refund')")
        self.db.execute("INSERT INTO payment_status_history VALUES('refund','succeeded','2026-11-15T10:00:00Z')")
        self.assertEqual(self.count('subscription refunds without revoked access'),0)
        self.assertEqual(self.count('subscription financial reference inconsistent'),0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM subscription_history WHERE status='active' AND source_txn_id='renewal' AND effective_start_at<='2026-11-15T10:00:00Z' AND effective_end_at>'2026-11-15T10:00:00Z'").fetchone()[0],1)
        self.db.execute("INSERT INTO subscription_history VALUES('bad','u','s','refund','refunded','2026-11-15T10:00:00Z',NULL,'2026-11-15T10:00:00Z','2026-11-15T10:00:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription refunds without revoked access'),1)

    def test_status_continuity_and_utc_fields(self):
        self.db.execute("INSERT INTO subscription_history VALUES('h2','u','s',NULL,'expired','2026-10-03T10:05:00Z',NULL,'2026-10-03T10:05:00Z','2026-10-03T10:05:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription history contains gaps'),0)
        self.assertEqual(self.count('subscription status period fields invalid'),0)
        self.db.execute("UPDATE subscription_history SET effective_start_at='2026-10-03T10:06:00Z' WHERE subscription_period_id='h2'")
        self.assertEqual(self.count('subscription history contains gaps'),1)
        self.db.execute("UPDATE subscription_history SET recorded_at='not-utc' WHERE subscription_period_id='h2'")
        self.assertEqual(self.count('subscription status period fields invalid'),1)
        self.db.execute("UPDATE subscription_history SET status='invented' WHERE subscription_period_id='h2'")
        self.assertEqual(self.count('subscription status period fields invalid'),1)

    def test_source_owner_must_match(self):
        self.assertEqual(self.count('subscription linked transaction ownership inconsistent'),0)
        self.db.execute("UPDATE transactions SET subscription_id='other' WHERE txn_id='charge'")
        self.assertEqual(self.count('subscription linked transaction ownership inconsistent'),1)

    def test_removed_statuses_are_rejected_in_history_and_snapshot(self):
        self.db.execute('CREATE TABLE users(acquisition_source TEXT,subscription_status TEXT)')
        self.db.execute("INSERT INTO users VALUES('organic','active')")
        for status in ('paused','cancelled'):
            self.db.execute("UPDATE subscription_history SET status=? WHERE subscription_period_id='h1'",(status,))
            self.assertEqual(self.count('subscription status period fields invalid'),1)
            self.db.execute('UPDATE users SET subscription_status=?',(status,))
            self.assertEqual(self.count('user value domains invalid'),1)

    def test_status_change_time_is_carried_across_renewals(self):
        self.db.execute("INSERT INTO subscription_history VALUES('h2','u','s','renewal','active','2026-10-03T10:05:00Z','2026-11-03T10:05:00Z','2026-10-01T10:00:00Z','2026-10-03T10:05:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription status change time inconsistent'),0)
        self.db.execute("UPDATE subscription_history SET subscription_status_updated_at=effective_start_at WHERE subscription_period_id='h2'")
        self.assertEqual(self.count('subscription status change time inconsistent'),1)
        self.db.execute("UPDATE subscription_history SET subscription_status_updated_at='2026-10-01T10:00:00Z' WHERE subscription_period_id='h2'")
        self.db.execute("INSERT INTO subscription_history VALUES('h3','u','s','renewal','cancel_at_period_end','2026-10-05T10:05:00Z',NULL,'2026-10-05T10:05:00Z','2026-10-05T10:05:00Z','2026-10-05T10:05:00Z','monthly_9_99')")
        self.assertEqual(self.count('subscription status change time inconsistent'),0)
        self.db.execute("UPDATE subscription_history SET subscription_status_updated_at='2026-10-01T10:00:00Z' WHERE subscription_period_id='h3'")
        self.assertEqual(self.count('subscription status change time inconsistent'),1)
        self.db.execute("UPDATE subscription_history SET subscription_status_updated_at='2026-10-05T10:05:00Z' WHERE subscription_period_id='h3'")
        self.db.execute("INSERT INTO subscription_history VALUES('h4','u','s','renewal','active','2026-10-06T10:05:00Z',NULL,'2026-10-06T10:05:00Z','2026-10-06T10:05:00Z',NULL,'monthly_9_99')")
        self.assertEqual(self.count('subscription status change time inconsistent'),0)
        self.db.execute("UPDATE subscription_history SET subscription_status_updated_at='2026-10-01T10:00:00Z' WHERE subscription_period_id='h4'")
        self.assertEqual(self.count('subscription status change time inconsistent'),1)

if __name__ == '__main__':
    unittest.main()

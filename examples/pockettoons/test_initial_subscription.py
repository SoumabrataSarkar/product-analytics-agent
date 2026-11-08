"""Initial subscription starts and periods use payment-success effective time."""
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

class InitialSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('next_calendar_month', 1, scope['next_calendar_month'])
        self.db.create_function('users_snapshot_at', 0, lambda: '2026-10-10T00:00:00Z')
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,type TEXT,transaction_subtype TEXT,status TEXT,subscription_id TEXT,transaction_at TEXT,related_txn_id TEXT,session_id TEXT);
          CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT);
          CREATE TABLE subscription_history(user_id TEXT,subscription_id TEXT,source_txn_id TEXT,status TEXT,effective_start_at TEXT,effective_end_at TEXT);
          CREATE TABLE users(user_id TEXT,subscription_status TEXT,subscription_start TEXT,subscription_end TEXT);
          CREATE TABLE user_events(session_id TEXT,event_name TEXT,event_at TEXT);
          CREATE TABLE content_views(session_id TEXT,view_type TEXT,view_started_at TEXT);
          INSERT INTO transactions VALUES('t','u','subscription','subscription_initial','pending','s','2026-10-01T10:00:00Z',NULL,'session');
          INSERT INTO payment_status_history VALUES('t','pending','2026-10-01T10:00:00Z');
        ''')

    def count(self, name):
        return self.db.execute(checks[name]).fetchone()[0]

    def succeed(self):
        self.db.execute("UPDATE transactions SET status='succeeded'")
        self.db.execute("INSERT INTO payment_status_history VALUES('t','succeeded','2026-10-01T10:05:00Z')")

    def grant(self, start='2026-10-01T10:05:00Z', end='2026-11-01T10:05:00Z'):
        self.db.execute("INSERT INTO subscription_history VALUES('u','s','t','active',?,?)", (start,end))

    def test_pending_and_failed_cannot_grant_access(self):
        for status in ('pending','failed'):
            self.db.execute('UPDATE transactions SET status=?', (status,))
            self.assertEqual(self.count('initial subscription entitlement does not start at success'),0)
            self.grant()
            self.assertEqual(self.count('initial subscription entitlement does not start at success'),1)
            self.db.execute('DELETE FROM subscription_history')

    def test_delayed_success_starts_and_ends_at_success_time(self):
        self.succeed()
        self.grant()
        self.assertEqual(self.count('initial subscription entitlement does not start at success'),0)
        self.assertEqual(self.count('monthly subscription period invalid'),0)
        self.db.execute("INSERT INTO users VALUES('u','active','2026-10-01T10:05:00Z','2026-11-01T10:05:00Z')")
        self.assertEqual(self.count('subscription snapshot boundaries inconsistent'),0)
        self.db.execute("UPDATE subscription_history SET effective_end_at='2026-11-01T10:00:00Z'")
        self.assertEqual(self.count('monthly subscription period invalid'),1)

    def test_early_or_missing_grant_fails(self):
        self.succeed()
        self.assertEqual(self.count('initial subscription entitlement does not start at success'),1)
        self.grant('2026-10-01T10:00:00Z')
        self.assertEqual(self.count('initial subscription entitlement does not start at success'),1)

    def test_initial_journey_is_not_required_for_pending_and_uses_success_time(self):
        self.assertEqual(self.count('initial subscription missing full journey'),0)
        self.succeed()
        self.db.executescript('''
          INSERT INTO user_events VALUES('session','paywall_viewed','2026-10-01T09:59:00Z'),
            ('session','checkout_started','2026-10-01T10:00:00Z'),
            ('session','subscription_started','2026-10-01T10:05:00Z');
          INSERT INTO content_views VALUES('session','sub','2026-10-01T10:05:00Z');
        ''')
        self.assertEqual(self.count('initial subscription missing full journey'),0)
        self.db.execute("DELETE FROM user_events WHERE event_name='paywall_viewed'")
        self.assertEqual(self.count('initial subscription missing full journey'),0)
        self.db.execute("UPDATE content_views SET view_started_at='2026-10-01T10:04:00Z'")
        self.assertEqual(self.count('initial subscription missing full journey'),1)

if __name__ == '__main__':
    unittest.main()

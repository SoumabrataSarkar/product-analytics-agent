"""Regression coverage for PPV entitlement start timing, purchase-episode uniqueness, single ownership and status consistency."""
import ast
import datetime as dt
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'valid_utc')
scope = {'dt': dt}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<utc>', 'exec'), scope)

class EntitlementTests(unittest.TestCase):
    def setUp(self):
        # Purchase created and pending at 10:00, succeeded effective 10:05, recorded 10:07 (UTC).
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, scope['valid_utc'])
        self.db.executescript('''
        CREATE TABLE transaction_content_attribution(txn_content_attribution_id TEXT,txn_id TEXT,content_id TEXT,episode_number INTEGER,entitlement_start_at TEXT,entitlement_end_at TEXT,refunded_at TEXT,delisted_at TEXT,attribution_status TEXT);
        CREATE TABLE transactions(txn_id TEXT,user_id TEXT,type TEXT,status TEXT);
        INSERT INTO transactions VALUES('p','u','ppv','succeeded');
        CREATE TABLE payment_status_history(payment_status_event_id TEXT,txn_id TEXT,status TEXT,effective_at TEXT,recorded_at TEXT);
        INSERT INTO payment_status_history VALUES
          ('e0','p','pending','2026-01-01T10:00:00Z','2026-01-01T10:00:00Z'),
          ('e1','p','succeeded','2026-01-01T10:05:00Z','2026-01-01T10:07:00Z');
        INSERT INTO transaction_content_attribution VALUES('a','p','c',1,'2026-01-01T10:05:00Z',NULL,NULL,NULL,'granted');
        ''')

    def violations(self, name):
        return self.db.execute(checks[name]).fetchone()[0]

class EntitlementStartTests(EntitlementTests):
    CHECK = 'PPV entitlement start differs from purchase success'

    def start_at(self, value):
        self.db.execute('UPDATE transaction_content_attribution SET entitlement_start_at=?', (value,))

    def test_start_at_success_effective_time_is_valid(self):
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_start_at_purchase_creation_while_pending_is_invalid(self):
        self.start_at('2026-01-01T10:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_start_at_success_recorded_time_is_invalid(self):
        self.start_at('2026-01-01T10:07:00Z')
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_purchase_without_success_cannot_start_entitlement(self):
        self.db.execute("UPDATE payment_status_history SET status='failed' WHERE payment_status_event_id='e1'")
        self.assertEqual(self.violations(self.CHECK), 1)

class PurchaseEpisodeUniquenessTests(EntitlementTests):
    CHECK = 'PPV attribution repeats purchase episode'

    def add(self, aid, txn, episode):
        self.db.execute("INSERT INTO transaction_content_attribution VALUES(?,?,'c',?,'2026-01-01T10:05:00Z',NULL,NULL,NULL,'granted')", (aid, txn, episode))

    def test_single_row_per_episode_is_valid(self):
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_bundle_with_distinct_episodes_is_valid(self):
        self.add('b', 'p', 2)
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_same_purchase_repeating_episode_is_invalid(self):
        self.add('b', 'p', 1)
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_separate_purchases_of_same_episode_are_not_this_rule(self):
        # Same-user repurchase (e.g. after relisting) is governed by a separate rule.
        self.add('b', 'p2', 1)
        self.assertEqual(self.violations(self.CHECK), 0)

class SingleOwnershipTests(EntitlementTests):
    CHECK = 'PPV purchase while episode already entitled'

    def repurchase(self, start, user='u', episode=1):
        self.db.execute("INSERT INTO transactions VALUES('q',?,'ppv','succeeded')", (user,))
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('b','q','c',?,?,NULL,NULL,NULL,'granted')", (episode, start))

    def end_first(self, at, refunded=False):
        self.db.execute('UPDATE transaction_content_attribution SET entitlement_end_at=?,refunded_at=? WHERE txn_content_attribution_id=?',
                        (at, at if refunded else None, 'a'))

    def test_repurchase_while_entitled_is_invalid(self):
        self.repurchase('2026-01-02T09:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_other_user_or_other_episode_is_valid(self):
        self.repurchase('2026-01-02T09:00:00Z', user='v')
        self.assertEqual(self.violations(self.CHECK), 0)
        self.db.execute("UPDATE transactions SET user_id='u' WHERE txn_id='q'")
        self.db.execute("UPDATE transaction_content_attribution SET episode_number=2 WHERE txn_content_attribution_id='b'")
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_repurchase_exactly_at_full_refund_end_is_valid(self):
        self.end_first('2026-01-02T12:00:00Z', refunded=True)
        self.repurchase('2026-01-02T12:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_repurchase_just_before_refund_end_is_invalid(self):
        self.end_first('2026-01-02T12:00:00Z', refunded=True)
        self.repurchase('2026-01-02T11:59:59Z')
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_repurchase_after_delisting_end_is_valid(self):
        self.end_first('2026-01-10T00:00:00Z')
        self.repurchase('2026-01-25T10:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 0)

class StatusConsistencyTests(EntitlementTests):
    CHECK = 'PPV attribution status and end timestamps inconsistent'

    def set_row(self, status, end=None, refunded=None, delisted=None):
        self.db.execute('UPDATE transaction_content_attribution SET attribution_status=?,entitlement_end_at=?,refunded_at=?,delisted_at=?',
                        (status, end, refunded, delisted))

    def test_valid_status_combinations(self):
        self.assertEqual(self.violations(self.CHECK), 0)
        t = '2026-01-02T10:00:00Z'
        self.set_row('refunded', t, refunded=t)
        self.assertEqual(self.violations(self.CHECK), 0)
        self.set_row('expired_delisting', t, delisted=t)
        self.assertEqual(self.violations(self.CHECK), 0)

    def test_granted_with_end_is_invalid(self):
        self.set_row('granted', '2026-01-02T10:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_status_must_match_end_reason(self):
        t = '2026-01-02T10:00:00Z'
        self.set_row('refunded', t, delisted=t)
        self.assertEqual(self.violations(self.CHECK), 1)
        self.set_row('expired_delisting', '2026-01-03T10:00:00Z', delisted=t)
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_end_without_reason_or_two_reasons_is_invalid(self):
        t = '2026-01-02T10:00:00Z'
        self.set_row('refunded', t)
        self.assertEqual(self.violations(self.CHECK), 1)
        self.set_row('refunded', t, refunded=t, delisted=t)
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_end_not_after_start_is_invalid(self):
        t = '2026-01-01T10:05:00Z'
        self.set_row('refunded', t, refunded=t)
        self.assertEqual(self.violations(self.CHECK), 1)

    def test_unsupported_or_missing_status_is_invalid(self):
        self.set_row('revoked', '2026-01-02T10:00:00Z')
        self.assertEqual(self.violations(self.CHECK), 1)
        self.set_row(None)
        self.assertEqual(self.violations(self.CHECK), 1)

class TimestampFormatTests(EntitlementTests):
    def test_non_utc_end_is_invalid(self):
        name = 'PPV attribution timestamps invalid'
        self.assertEqual(self.violations(name), 0)
        self.db.execute("UPDATE transaction_content_attribution SET entitlement_end_at='2026-01-02 10:00:00'")
        self.assertEqual(self.violations(name), 1)

if __name__ == '__main__':
    unittest.main()

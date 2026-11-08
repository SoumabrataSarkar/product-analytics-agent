"""Regression coverage for PPV entitlement start timing and purchase-episode uniqueness."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))

class EntitlementTests(unittest.TestCase):
    def setUp(self):
        # Purchase created and pending at 10:00, succeeded effective 10:05, recorded 10:07 (UTC).
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
        CREATE TABLE transaction_content_attribution(txn_content_attribution_id TEXT,txn_id TEXT,content_id TEXT,episode_number INTEGER,entitlement_start_at TEXT);
        CREATE TABLE payment_status_history(payment_status_event_id TEXT,txn_id TEXT,status TEXT,effective_at TEXT,recorded_at TEXT);
        INSERT INTO payment_status_history VALUES
          ('e0','p','pending','2026-01-01T10:00:00Z','2026-01-01T10:00:00Z'),
          ('e1','p','succeeded','2026-01-01T10:05:00Z','2026-01-01T10:07:00Z');
        INSERT INTO transaction_content_attribution VALUES('a','p','c',1,'2026-01-01T10:05:00Z');
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
        self.db.execute("INSERT INTO transaction_content_attribution VALUES(?,?,'c',?,'2026-01-01T10:05:00Z')", (aid, txn, episode))

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

if __name__ == '__main__':
    unittest.main()

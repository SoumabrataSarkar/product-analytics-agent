"""Validate checkout references on payment attempts, including retries."""
import ast
import datetime as dt
from pathlib import Path
import sqlite3
import unittest

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in n.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')==value)
    except (TypeError,ValueError):
        return 0

class CheckoutTransactionTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,type TEXT,status TEXT,session_id TEXT,transaction_at TEXT,checkout_event_id TEXT);
          CREATE TABLE user_events(event_id TEXT,event_name TEXT,user_id TEXT,session_id TEXT,event_at TEXT,event_properties_json TEXT,content_id TEXT,episode_number INTEGER);
          CREATE TABLE transaction_content_attribution(txn_id TEXT,content_id TEXT,episode_number INTEGER);
          INSERT INTO user_events VALUES('checkout','checkout_started','u','session','2026-01-01T10:00:00Z','{"product":"ppv"}','c',1);
          INSERT INTO transactions VALUES('failed','u','ppv','failed','session','2026-01-01T10:00:00Z','checkout');
          INSERT INTO transactions VALUES('success','u','ppv','succeeded','session','2026-01-01T10:01:00Z','checkout');
          INSERT INTO transaction_content_attribution VALUES('success','c',1);
        ''')

    def count(self):
        return self.db.execute(checks['transaction checkout link invalid']).fetchone()[0]

    def test_failed_and_successful_retries_share_checkout(self):
        self.assertEqual(self.count(),0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM transactions WHERE checkout_event_id='checkout'").fetchone()[0],2)

    def test_null_link_allows_off_session_or_unknown(self):
        self.db.execute("INSERT INTO transactions VALUES('renew','u','subscription','succeeded',NULL,'2026-01-01T10:00:00Z',NULL)")
        self.db.execute("UPDATE transactions SET checkout_event_id=NULL WHERE txn_id='failed'")
        self.assertEqual(self.count(),0)

    def test_invalid_parent_user_session_time_product_or_type(self):
        mutations=["checkout_event_id='missing'", "user_id='other'", "session_id='other'", "session_id=NULL", "transaction_at='2026-01-01T09:59:59Z'", "transaction_at='bad'", "type='subscription'", "type='refund'"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.db.execute('SAVEPOINT change')
                self.db.execute("UPDATE transactions SET "+mutation+" WHERE txn_id='success'")
                self.assertEqual(self.count(),1)
                self.db.execute('ROLLBACK TO change')
                self.db.execute('RELEASE change')
        self.db.execute("UPDATE user_events SET event_name='paywall_viewed' WHERE event_id='checkout'")
        self.assertEqual(self.count(),2)

    def test_episode_match_when_attribution_exists(self):
        self.db.execute("UPDATE transaction_content_attribution SET episode_number=2 WHERE txn_id='success'")
        self.assertEqual(self.count(),1)
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('success','c',1)")
        self.assertEqual(self.count(),0)
        self.assertEqual(self.db.execute("SELECT count(*) FROM transaction_content_attribution WHERE txn_id='failed'").fetchone()[0],0)

    def test_subscription_checkout_without_episode(self):
        self.db.execute("UPDATE user_events SET event_properties_json='{\"product\":\"subscription\"}',content_id=NULL,episode_number=NULL")
        self.db.execute("UPDATE transactions SET type='subscription'")
        self.assertEqual(self.count(),0)

    def test_invalid_or_missing_event_product_is_rejected(self):
        for properties in ('bad', None, '{}'):
            with self.subTest(properties=properties):
                self.db.execute('UPDATE user_events SET event_properties_json=?',(properties,))
                self.assertEqual(self.count(),2)

if __name__=='__main__':
    unittest.main()

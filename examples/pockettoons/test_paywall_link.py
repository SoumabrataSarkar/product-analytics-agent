"""Explicit checkout-to-paywall references."""
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

class PaywallLinkTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.executescript('''
          CREATE TABLE user_events(event_id TEXT,event_name TEXT,session_id TEXT,event_at TEXT,event_properties_json TEXT,content_id TEXT,episode_number INTEGER,triggering_paywall_event_id TEXT);
          INSERT INTO user_events VALUES('wall1','paywall_viewed','s','2026-01-01T10:00:00Z','{"product":"ppv"}','c',1,NULL);
          INSERT INTO user_events VALUES('wall2','paywall_viewed','s','2026-01-01T10:05:00Z','{"product":"ppv"}','c',1,NULL);
          INSERT INTO user_events VALUES('checkout','checkout_started','s','2026-01-01T10:06:00Z','{"product":"ppv"}','c',1,'wall2');
        ''')

    def count(self):
        return self.db.execute(checks['checkout paywall link invalid']).fetchone()[0]

    def test_explicit_link_disambiguates_repeated_exposures(self):
        self.assertEqual(self.count(),0)
        self.assertEqual(self.db.execute("SELECT triggering_paywall_event_id FROM user_events WHERE event_id='checkout'").fetchone()[0],'wall2')
        self.db.execute("INSERT INTO user_events VALUES('checkout2','checkout_started','s','2026-01-01T10:07:00Z','{\"product\":\"ppv\"}','c',1,'wall2')")
        self.assertEqual(self.count(),0)

    def test_null_link_for_direct_or_unknown_checkout_is_valid(self):
        self.db.execute("UPDATE user_events SET triggering_paywall_event_id=NULL WHERE event_id='checkout'")
        self.assertEqual(self.count(),0)

    def test_missing_wrong_type_session_time_product_or_episode_fails(self):
        mutations=["triggering_paywall_event_id='missing'", "event_name='paywall_viewed'", "session_id='other'", "session_id=NULL", "event_at='2026-01-01T10:05:00Z'", "event_at='bad'", "event_properties_json='{\"product\":\"subscription\"}'", "event_properties_json='bad'", "content_id='other'", "episode_number=2", "episode_number=NULL"]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.db.execute('SAVEPOINT change')
                self.db.execute("UPDATE user_events SET "+mutation+" WHERE event_id='checkout'")
                self.assertEqual(self.count(),1)
                self.db.execute('ROLLBACK TO change')
                self.db.execute('RELEASE change')
        self.db.execute("UPDATE user_events SET event_name='app_opened' WHERE event_id='wall2'")
        self.assertEqual(self.count(),1)

    def test_subscription_checkout_can_omit_episode(self):
        self.db.execute("UPDATE user_events SET event_properties_json='{\"product\":\"subscription\"}',content_id=NULL,episode_number=NULL WHERE event_id IN ('wall2','checkout')")
        self.assertEqual(self.count(),0)

if __name__=='__main__':
    unittest.main()

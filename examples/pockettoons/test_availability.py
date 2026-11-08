#!/usr/bin/env python3
"""Availability and delisting regression scenarios."""
import ast
import datetime as dt
import sqlite3
import unittest
from pathlib import Path

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in node.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')==value)
    except (TypeError,ValueError):
        return 0

class AvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.executescript('''
          CREATE TABLE content_availability_history(availability_id TEXT,content_id TEXT,episode_number INTEGER,status TEXT,available_from_at TEXT,available_until_at TEXT,recorded_at TEXT);
          CREATE TABLE content_episodes(content_id TEXT,episode_number INTEGER,episode_status TEXT,available_from_at TEXT,available_until_at TEXT);
          CREATE TABLE content_views(content_id TEXT,episode_number INTEGER,view_started_at TEXT,user_id TEXT,view_type TEXT);
          CREATE TABLE transaction_content_attribution(txn_id TEXT,content_id TEXT,episode_number INTEGER,entitlement_start_at TEXT,entitlement_end_at TEXT,refunded_at TEXT,delisted_at TEXT,attribution_status TEXT);
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,type TEXT,status TEXT);
          CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT,recorded_at TEXT,payment_status_event_id TEXT);
          CREATE TABLE user_events(user_id TEXT,event_name TEXT,content_id TEXT,episode_number INTEGER,event_at TEXT);
          CREATE TABLE dataset_metadata(metadata_key TEXT,metadata_value TEXT);
          INSERT INTO dataset_metadata VALUES('content_catalog_snapshot_at','2026-09-30T23:59:59Z');
          INSERT INTO content_availability_history VALUES
            ('a','c',1,'live','2026-01-01T00:00:00Z','2026-09-10T00:00:00Z','2026-01-01T00:00:00Z'),
            ('b','c',1,'delisted','2026-09-10T00:00:00Z','2026-09-20T00:00:00Z','2026-09-10T00:00:00Z'),
            ('c','c',1,'live','2026-09-20T00:00:00Z',NULL,'2026-09-20T00:00:00Z');
          INSERT INTO content_episodes VALUES('c',1,'live','2026-09-20T00:00:00Z',NULL);
        ''')

    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_half_open_boundaries_and_unknown_before_tracking(self):
        lookup="SELECT status FROM content_availability_history WHERE content_id='c' AND episode_number=1 AND available_from_at<=? AND (available_until_at IS NULL OR available_until_at>?)"
        for ts, expected in [('2025-12-31T23:59:59Z',[]),('2026-09-09T23:59:59Z',[('live',)]),('2026-09-10T00:00:00Z',[('delisted',)]),('2026-09-20T00:00:00Z',[('live',)])]:
            self.assertEqual(self.db.execute(lookup,(ts,ts)).fetchall(),expected)
        self.assertEqual(self.count('availability periods overlap or have gaps'),0)
        self.assertEqual(self.count('episode availability snapshot inconsistent'),0)

    def test_gaps_overlaps_and_snapshot_mismatch(self):
        self.db.execute("UPDATE content_availability_history SET available_from_at='2026-09-10T00:00:01Z' WHERE availability_id='b'")
        self.assertGreater(self.count('availability periods overlap or have gaps'),0)
        self.db.execute("UPDATE content_availability_history SET available_from_at='2026-09-09T23:59:59Z' WHERE availability_id='b'")
        self.assertGreater(self.count('availability periods overlap or have gaps'),0)
        self.db.execute("UPDATE content_episodes SET episode_status='delisted'")
        self.assertEqual(self.count('episode availability snapshot inconsistent'),1)

    def test_every_active_holder_and_notice_including_refund_exception(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('p1','u1','ppv','succeeded'),('p2','u2','ppv','succeeded'),('p3','u3','ppv','succeeded');
          INSERT INTO payment_status_history VALUES('p1','succeeded','2026-03-01T00:00:00Z','2026-03-01T00:00:00Z','s1'),('p2','succeeded','2026-03-02T00:00:00Z','2026-03-02T00:00:00Z','s2'),('p3','succeeded','2026-03-03T00:00:00Z','2026-03-03T00:00:00Z','s3');
          INSERT INTO transaction_content_attribution VALUES
            ('p1','c',1,'2026-03-01T00:00:00Z',NULL,NULL,NULL,'granted'),
            ('p2','c',1,'2026-03-02T00:00:00Z',NULL,NULL,NULL,'granted'),
            ('p3','c',1,'2026-03-03T00:00:00Z','2026-04-01T00:00:00Z','2026-04-01T00:00:00Z',NULL,'refunded');
        ''')
        self.assertEqual(self.count('ppv entitlement improperly spans delisting'),2)
        self.db.execute("UPDATE transaction_content_attribution SET entitlement_end_at='2026-09-10T00:00:00Z',delisted_at='2026-09-10T00:00:00Z',attribution_status='expired_delisting' WHERE txn_id IN ('p1','p2')")
        self.assertEqual(self.count('ppv entitlement improperly spans delisting'),0)
        self.assertEqual(self.count('delisting ended entitlement without holder notice'),2)
        self.db.execute("INSERT INTO user_events VALUES('u1','content_delisting_notice','c',1,'2026-09-01T00:00:00Z')")
        self.assertEqual(self.count('delisting ended entitlement without holder notice'),1)
        self.db.execute("INSERT INTO user_events VALUES('u2','content_delisting_notice','c',1,'2026-09-02T00:00:00Z')")
        self.assertEqual(self.count('delisting ended entitlement without holder notice'),0)
        self.assertEqual(self.db.execute("SELECT refunded_at FROM transaction_content_attribution WHERE txn_id='p3'").fetchone()[0],'2026-04-01T00:00:00Z')

    def test_purchase_while_delisted_and_after_return(self):
        self.db.execute("INSERT INTO transactions VALUES('p','u','ppv','succeeded')")
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('p','c',1,'2026-09-15T00:00:00Z',NULL,NULL,NULL,'granted')")
        self.assertEqual(self.count('ppv purchase made when episode not live'),1)
        self.db.execute("UPDATE transaction_content_attribution SET entitlement_start_at='2026-09-20T00:00:00Z'")
        self.assertEqual(self.count('ppv purchase made when episode not live'),0)

    def test_delisting_uses_payment_status_at_boundary_not_current_snapshot(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('p','u','ppv','succeeded');
          INSERT INTO payment_status_history VALUES('p','pending','2026-09-01T00:00:00Z','2026-09-01T00:00:00Z','pending'),
            ('p','succeeded','2026-09-11T00:00:00Z','2026-09-11T00:00:00Z','success');
          INSERT INTO transaction_content_attribution VALUES('p','c',1,'2026-09-01T00:00:00Z',NULL,NULL,NULL,'granted');
        ''')
        self.assertEqual(self.count('ppv entitlement improperly spans delisting'),0)

    def test_old_grant_does_not_revive_after_relisting(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('old','u','ppv','succeeded');
          INSERT INTO payment_status_history VALUES('old','succeeded','2026-03-01T00:00:00Z','2026-03-01T00:00:00Z','sold');
          INSERT INTO transaction_content_attribution VALUES('old','c',1,'2026-03-01T00:00:00Z','2026-09-10T00:00:00Z',NULL,'2026-09-10T00:00:00Z','expired_delisting');
          INSERT INTO content_views VALUES('c',1,'2026-09-20T00:00:00Z','u','ppv');
        ''')
        self.assertEqual(self.count('PPV views without entitlement'),1)
        self.db.executescript('''
          INSERT INTO transactions VALUES('new','u','ppv','succeeded');
          INSERT INTO payment_status_history VALUES('new','succeeded','2026-09-20T00:00:00Z','2026-09-20T00:00:00Z','snew');
          INSERT INTO transaction_content_attribution VALUES('new','c',1,'2026-09-20T00:00:00Z',NULL,NULL,NULL,'granted');
        ''')
        self.assertEqual(self.count('PPV views without entitlement'),0)

if __name__=='__main__':
    unittest.main()

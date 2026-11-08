#!/usr/bin/env python3
"""Episode tier, integrity and fanout regression scenarios."""
import ast
import datetime as dt
import sqlite3
import unittest
from pathlib import Path

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in node.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ') == value)
    except (TypeError, ValueError):
        return 0

class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, valid_utc)
        self.db.executescript('''
          CREATE TABLE dataset_metadata(metadata_key TEXT,metadata_value TEXT);
          INSERT INTO dataset_metadata VALUES('content_catalog_snapshot_at','2026-09-30T23:59:59Z');
          CREATE TABLE content_episodes(content_id TEXT,episode_number INTEGER,episode_duration_sec INTEGER,
            access_tier TEXT,episode_status TEXT,release_at TEXT,ppv_list_price_usd REAL,available_from_at TEXT,available_until_at TEXT);
          CREATE TABLE content_tier_history(tier_period_id TEXT,content_id TEXT,episode_number INTEGER,access_tier TEXT,
            effective_start_at TEXT,effective_end_at TEXT,recorded_at TEXT);
          CREATE TABLE content_views(content_id TEXT,episode_number INTEGER,view_type TEXT,view_started_at TEXT,watch_duration_sec INTEGER);
          CREATE TABLE transaction_content_attribution(content_id TEXT,episode_number INTEGER,txn_id TEXT,entitlement_start_at TEXT,attributed_amount_usd REAL);
          CREATE TABLE refund_content_attribution(content_id TEXT,episode_number INTEGER,allocated_refund_usd REAL);
          CREATE TABLE transactions(txn_id TEXT,type TEXT,status TEXT);
          INSERT INTO content_episodes VALUES('c1',1,1200,'free','live','2026-03-01T00:00:00Z',NULL,'2026-03-01T00:00:00Z',NULL);
          INSERT INTO content_tier_history VALUES('old','c1',1,'premium','2026-03-01T00:00:00Z','2026-07-01T00:00:00Z','2026-03-01T00:00:00Z'),
            ('new','c1',1,'free','2026-07-01T00:00:00Z',NULL,'2026-07-01T00:00:00Z');
        ''')

    def count(self, name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_tier_change_boundary_and_ppv_as_of(self):
        self.db.execute("INSERT INTO content_views VALUES('c1',1,'free','2026-07-01T00:00:00Z',100)")
        self.db.execute("INSERT INTO transactions VALUES('t1','ppv','succeeded')")
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('c1',1,'t1','2026-06-30T23:59:59Z',1.99)")
        self.assertEqual(self.count('free views without free tier at playback'),0)
        self.assertEqual(self.count('ppv purchases without premium tier at purchase'),0)
        self.db.execute("UPDATE content_views SET view_started_at='2026-06-30T23:59:59Z'")
        self.db.execute("UPDATE transaction_content_attribution SET entitlement_start_at='2026-07-01T00:00:00Z'")
        self.assertEqual(self.count('free views without free tier at playback'),1)
        self.assertEqual(self.count('ppv purchases without premium tier at purchase'),1)

    def test_gap_overlap_snapshot_and_invalid_episode(self):
        self.assertEqual(self.count('episode tier intervals overlap or have gaps'),0)
        self.assertEqual(self.count('episode tier history and current snapshot inconsistent'),0)
        self.assertEqual(self.count('episode fields invalid'),0)
        self.db.execute("UPDATE content_tier_history SET effective_start_at='2026-07-01T00:00:01Z' WHERE tier_period_id='new'")
        self.assertEqual(self.count('episode tier intervals overlap or have gaps'),1)
        self.db.execute("UPDATE content_tier_history SET effective_start_at='2026-06-30T23:59:59Z' WHERE tier_period_id='new'")
        self.assertEqual(self.count('episode tier intervals overlap or have gaps'),1)
        self.db.execute("UPDATE content_episodes SET access_tier='premium', episode_duration_sec=0")
        self.assertEqual(self.count('episode tier history and current snapshot inconsistent'),1)
        self.assertEqual(self.count('episode fields invalid'),1)

    def test_episode_summary_does_not_multiply_view_or_allocations(self):
        self.db.execute("INSERT INTO content_views VALUES('c1',1,'free','2026-07-01T00:00:00Z',100),('c1',1,'free','2026-07-02T00:00:00Z',200)")
        self.db.execute("INSERT INTO transaction_content_attribution VALUES('c1',1,'t1','2026-06-01T00:00:00Z',1.99),('c1',1,'t2','2026-06-02T00:00:00Z',1.99)")
        self.db.execute("INSERT INTO refund_content_attribution VALUES('c1',1,1.99)")
        self.assertEqual(self.db.execute('SELECT count(*) FROM content_views v JOIN transaction_content_attribution a USING(content_id,episode_number)').fetchone()[0],4)
        self.assertEqual(self.count('episode view and allocation fanout reconciliation'),0)

if __name__ == '__main__':
    unittest.main()

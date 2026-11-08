#!/usr/bin/env python3
"""Focused regression scenarios for title inventory and safe aggregation."""
import ast
import datetime as dt
import sqlite3
import unittest
from pathlib import Path

source = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in source.body if isinstance(node, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in node.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ') == value)
    except (TypeError, ValueError):
        return 0

class CatalogChecks(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, valid_utc)
        self.db.executescript('''
          CREATE TABLE content_catalog(content_id TEXT,title TEXT,genre TEXT,total_episodes INTEGER,total_duration_sec INTEGER,
            content_tier TEXT,content_status TEXT,first_release_at TEXT,release_date TEXT,last_release_at TEXT,
            available_from_at TEXT,available_until_at TEXT,created_at TEXT,updated_at TEXT);
          CREATE TABLE content_episodes(content_id TEXT,episode_number INTEGER,episode_duration_sec INTEGER,access_tier TEXT,
            episode_status TEXT,release_at TEXT);
          CREATE TABLE content_views(content_id TEXT,watch_duration_sec INTEGER);
          INSERT INTO content_catalog VALUES('c1','Example','drama',2,1800,'mixed','live',
            '2026-01-01T00:00:00Z','2026-01-01','2026-01-01T00:00:00Z',NULL,NULL,
            '2026-01-01T00:00:00Z','2026-01-01T00:00:00Z');
          INSERT INTO content_episodes VALUES ('c1',1,900,'free','live','2026-01-01T00:00:00Z'),
            ('c1',2,900,'premium','scheduled','2026-02-01T00:00:00Z');
          INSERT INTO content_views VALUES ('c1',100),('c1',200);
        ''')

    def count(self, name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_scheduled_episode_included_in_inventory_not_last_release(self):
        self.assertEqual(self.count('content inventory count or duration inconsistent'), 0)
        self.assertEqual(self.count('content episode release summary inconsistent'), 0)
        self.db.execute('UPDATE content_catalog SET total_episodes=1')
        self.assertEqual(self.count('content inventory count or duration inconsistent'), 1)
        self.db.execute("UPDATE content_catalog SET last_release_at='2026-02-01T00:00:00Z'")
        self.assertEqual(self.count('content episode release summary inconsistent'), 1)

    def test_tier_and_date_validation(self):
        self.assertEqual(self.count('content title tier inconsistent with episodes'), 0)
        self.assertEqual(self.count('content title fields and dates invalid'), 0)
        self.db.execute("UPDATE content_catalog SET content_tier='free',release_date='2026-01-02'")
        self.assertEqual(self.count('content title tier inconsistent with episodes'), 1)
        self.assertEqual(self.count('content title fields and dates invalid'), 1)

    def test_preaggregated_title_join_avoids_fanout(self):
        unsafe = self.db.execute('SELECT count(*),sum(c.total_duration_sec),sum(v.watch_duration_sec) FROM content_catalog c JOIN content_episodes e USING(content_id) JOIN content_views v USING(content_id)').fetchone()
        self.assertEqual(unsafe, (4,7200,600))
        self.assertEqual(self.count('title episode summary fanout reconciliation'), 0)

if __name__ == '__main__':
    unittest.main()

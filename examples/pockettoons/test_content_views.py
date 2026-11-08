#!/usr/bin/env python3
"""Regression tests for first views and distinct daily free quota."""
import ast
import sqlite3
import unittest
from pathlib import Path

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in node.targets))

class ViewTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript('''CREATE TABLE content_views(view_id TEXT,user_id TEXT,content_id TEXT,episode_number INTEGER,
          date TEXT,view_started_at TEXT,is_first_view_of_episode INTEGER,view_type TEXT,free_quota_consuming INTEGER,free_quota_sequence INTEGER);
          INSERT INTO content_views VALUES('v1','u','c',1,'2026-06-01','2026-06-01T09:00:00Z',1,'free',1,1),
          ('v2','u','c',1,'2026-06-01','2026-06-01T10:00:00Z',0,'free',0,NULL),
          ('v3','u','c',2,'2026-06-01','2026-06-01T11:00:00Z',1,'free',1,2);
        ''')
    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]
    def test_resume_does_not_use_new_slot_and_first_view_is_unique(self):
        for name in ['view first episode flag inconsistent','free quota sequence inconsistent','free resume without earlier counted episode','free episode consumed twice on same UTC day']:
            self.assertEqual(self.count(name),0)
        self.db.execute("UPDATE content_views SET is_first_view_of_episode=1,free_quota_consuming=1,free_quota_sequence=2 WHERE view_id='v2'")
        self.assertEqual(self.count('view first episode flag inconsistent'),1)
        self.assertEqual(self.count('free episode consumed twice on same UTC day'),1)
        self.assertGreater(self.count('free quota sequence inconsistent'),0)
    def test_uncounted_first_free_view_is_invalid(self):
        self.db.execute("UPDATE content_views SET free_quota_consuming=0,free_quota_sequence=NULL WHERE view_id='v1'")
        self.assertGreater(self.count('free resume without earlier counted episode'),0)
    def test_same_episode_on_next_utc_day_can_use_new_slot(self):
        self.db.execute("INSERT INTO content_views VALUES('v4','u','c',1,'2026-06-02','2026-06-02T00:00:00Z',0,'free',1,1)")
        self.assertEqual(self.count('free quota sequence inconsistent'),0)
        self.assertEqual(self.count('free episode consumed twice on same UTC day'),0)

if __name__=='__main__':
    unittest.main()

#!/usr/bin/env python3
"""Regression tests for segment-based watch time and unique content coverage."""
import ast
import datetime as dt
import sqlite3
import unittest
from pathlib import Path

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in node.targets))
class_node=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='UniqueCoverage')
namespace={}
exec(compile(ast.Module(body=[class_node],type_ignores=[]),'<coverage>','exec'),namespace)

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')==value)
    except (TypeError,ValueError):
        return 0

class SegmentTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.create_aggregate('unique_coverage',2,namespace['UniqueCoverage'])
        self.db.executescript('''
          CREATE TABLE content_views(view_id TEXT,user_id TEXT,content_id TEXT,episode_number INTEGER,view_started_at TEXT,view_ended_at TEXT,watch_duration_sec INTEGER,content_duration_sec INTEGER,playback_position_start_sec INTEGER,playback_position_end_sec INTEGER,completion_pct REAL);
          CREATE TABLE playback_segments(segment_id TEXT,view_id TEXT,segment_index INTEGER,segment_started_at TEXT,segment_ended_at TEXT,position_start_sec INTEGER,position_end_sec INTEGER,watch_duration_sec INTEGER);
          INSERT INTO content_views VALUES('rewind','u','c',1,'2026-01-01T10:00:00Z','2026-01-01T10:08:00Z',480,1200,0,360,0.3);
          INSERT INTO playback_segments VALUES('s1','rewind',1,'2026-01-01T10:00:00Z','2026-01-01T10:05:00Z',0,300,300),
            ('s2','rewind',2,'2026-01-01T10:05:00Z','2026-01-01T10:08:00Z',180,360,180);
        ''')
    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_rewind_unique_content_not_total_watch(self):
        self.assertEqual(self.db.execute('SELECT unique_coverage(position_start_sec,position_end_sec) FROM playback_segments').fetchone()[0],360)
        sql='''WITH ordered AS (SELECT view_id,segment_id,position_start_sec AS start_pos,position_end_sec AS end_pos,
          MAX(position_end_sec) OVER (PARTITION BY view_id ORDER BY position_start_sec,position_end_sec,segment_id ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) previous_max_end FROM playback_segments),
          grouped AS (SELECT *,SUM(CASE WHEN previous_max_end IS NULL OR start_pos>previous_max_end THEN 1 ELSE 0 END)
          OVER(PARTITION BY view_id ORDER BY start_pos,end_pos,segment_id) island FROM ordered),
          ranges AS (SELECT view_id,island,min(start_pos) start_pos,max(end_pos) end_pos FROM grouped GROUP BY view_id,island)
          SELECT view_id,sum(end_pos-start_pos) FROM ranges GROUP BY view_id'''
        self.assertEqual(self.db.execute(sql).fetchall(),[('rewind',360)])
        self.assertEqual(self.count('view segment totals or completion inconsistent'),0)
        self.db.execute("UPDATE content_views SET completion_pct=0.4")
        self.assertEqual(self.count('view segment totals or completion inconsistent'),1)

    def test_seek_gap_does_not_count_as_watched(self):
        self.db.execute("UPDATE content_views SET watch_duration_sec=600,view_ended_at='2026-01-01T10:10:00Z',playback_position_end_sec=750,completion_pct=0.5")
        self.db.execute("UPDATE playback_segments SET segment_ended_at='2026-01-01T10:10:00Z',position_start_sec=450,position_end_sec=750,watch_duration_sec=300 WHERE segment_id='s2'")
        self.assertEqual(self.db.execute('SELECT unique_coverage(position_start_sec,position_end_sec) FROM playback_segments').fetchone()[0],600)
        self.assertEqual(self.count('view segment totals or completion inconsistent'),0)
        self.assertEqual(self.count('playback segment fields or view bounds invalid'),0)

    def test_invalid_order_positions_and_missing_segments(self):
        self.db.execute("UPDATE playback_segments SET segment_started_at='2026-01-01T10:04:59Z' WHERE segment_id='s2'")
        self.assertEqual(self.count('playback segment order invalid'),1)
        self.db.execute("UPDATE playback_segments SET position_end_sec=1300 WHERE segment_id='s2'")
        self.assertEqual(self.count('playback segment fields or view bounds invalid'),1)
        self.db.execute('DELETE FROM playback_segments')
        self.assertEqual(self.count('view segment totals or completion inconsistent'),1)

    def test_union_across_attempts_does_not_double_count_rewatched_content(self):
        self.db.execute("INSERT INTO content_views VALUES('resume','u','c',1,'2026-01-02T10:00:00Z','2026-01-02T10:05:00Z',300,1200,300,600,0.25)")
        self.db.execute("INSERT INTO playback_segments VALUES('s3','resume',1,'2026-01-02T10:00:00Z','2026-01-02T10:05:00Z',300,600,300)")
        covered=self.db.execute('SELECT unique_coverage(s.position_start_sec,s.position_end_sec) FROM playback_segments s JOIN content_views v USING(view_id) WHERE v.user_id=? AND v.content_id=? AND v.episode_number=?',('u','c',1)).fetchone()[0]
        self.assertEqual(covered,600)
        self.assertEqual(self.count('view segment totals or completion inconsistent'),0)

    def test_sqlite_rounding_matches_completion_reconciliation(self):
        self.db.executescript('''
          DELETE FROM playback_segments;
          DELETE FROM content_views;
          INSERT INTO content_views VALUES('tie','u','c',1,'2026-01-01T10:00:00Z','2026-01-01T10:06:09Z',369,1312,0,369,round(1.0*369/1312,4));
          INSERT INTO playback_segments VALUES('s','tie',1,'2026-01-01T10:00:00Z','2026-01-01T10:06:09Z',0,369,369);
        ''')
        self.assertEqual(self.db.execute('SELECT completion_pct FROM content_views').fetchone()[0],0.2813)
        self.assertEqual(self.count('view segment totals or completion inconsistent'),0)

if __name__=='__main__':
    unittest.main()

"""Tests for the layer builder and the silver_resolved_sessions contract."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import build_layers


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'fixture.sqlite')
        db = sqlite3.connect(self.path)
        db.executescript('''
        CREATE TABLE sessions(session_id TEXT PRIMARY KEY, user_id TEXT, anonymous_id TEXT NOT NULL, platform TEXT NOT NULL,
          country_at_event TEXT, app_version TEXT, session_started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL,
          session_ended_at TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT PRIMARY KEY, session_id TEXT, user_id TEXT);
        INSERT INTO sessions VALUES
          ('s_user','u1','d1','ios','US','1.2.0','2026-04-10T10:00:00Z','2026-04-10T10:30:00Z','2026-04-10T10:30:00Z'),
          ('s_link',NULL,'d2','web','PH','1.2.0','2026-04-11T10:00:00Z','2026-04-11T10:10:00Z',NULL),
          ('s_none',NULL,'shared','web','PH','1.2.0','2026-04-12T10:00:00Z','2026-04-12T10:05:00Z','2026-04-12T10:05:00Z'),
          ('s_later',NULL,'shared','web','PH','1.2.0','2026-04-13T10:00:00Z','2026-04-13T10:05:00Z','2026-04-13T10:05:00Z'),
          ('s_two',NULL,'d3','android','MX','1.2.0','2026-04-14T10:00:00Z','2026-04-14T10:05:00Z','2026-04-14T10:05:00Z'),
          ('s_mismatch','u4','d4','ios','US','1.2.0','2026-04-15T10:00:00Z','2026-04-15T10:01:01Z','2026-04-15T10:01:01Z');
        INSERT INTO identity_links VALUES
          ('l1','s_user','u1'), ('l2','s_link','u2'), ('l3','s_later','u3'),
          ('l4','s_two','u5'), ('l5','s_two','u6'), ('l6','s_mismatch','u9');
        ''')
        for table in build_layers.SOURCE_ROLES:
            if table not in ('sessions', 'identity_links'):
                db.execute(f'CREATE TABLE "{table}"(id TEXT)')
        db.execute("INSERT INTO users VALUES('u1')")
        db.commit()
        db.close()

    def query(self, sql):
        db = sqlite3.connect(self.path)
        try:
            return db.execute(sql).fetchall()
        finally:
            db.close()

    def test_resolution_methods_mismatch_and_no_cross_session_attribution(self):
        result = build_layers.build(self.path)
        self.assertEqual(result['status'], 'succeeded')
        rows = {r[0]: r[1:] for r in self.query(
            'SELECT session_id, resolved_user_id, resolution_method, link_count, linked_user_count, link_user_mismatch, active_span_sec FROM silver_resolved_sessions')}
        self.assertEqual(rows['s_user'][:2], ('u1', 'session_user'))
        self.assertEqual(rows['s_link'][:2], ('u2', 'same_session_link'))
        self.assertEqual(rows['s_none'][:2], (None, 'unresolved_no_link'))  # later login on the same device does not reach back
        self.assertEqual(rows['s_later'][:2], ('u3', 'same_session_link'))
        self.assertEqual(rows['s_two'][:4], (None, 'unresolved_ambiguous', 2, 2))
        self.assertEqual(rows['s_mismatch'][:2], ('u4', 'session_user'))
        self.assertEqual(rows['s_mismatch'][4:], (1, 61))
        checks = json.loads(result['reconciliation'])['checks']
        self.assertTrue(all(checks.values()))

    def test_bronze_views_cover_every_source_table(self):
        build_layers.build(self.path)
        views = {r[0] for r in self.query("SELECT name FROM sqlite_master WHERE type='view'")}
        self.assertEqual(views, {f'bronze_{t}' for t in build_layers.SOURCE_ROLES})
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze_sessions'), [(6,)])
        self.assertEqual(self.query('SELECT id FROM bronze_users'), [('u1',)])

    def test_later_source_change_is_detectable_from_the_build_fingerprint(self):
        result = build_layers.build(self.path)
        db = sqlite3.connect(self.path)
        db.execute("INSERT INTO users VALUES('u_new')")
        db.commit()
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze_users'), [(2,)])  # a view shows current source
        recorded = json.loads(result['source_fingerprint'])['users']
        self.assertNotEqual(build_layers.fingerprint(db)['users'], recorded)
        db.close()

    def test_missing_source_table_stops_the_build(self):
        db = sqlite3.connect(self.path)
        db.execute('DROP TABLE marketing_spend')
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, 'missing table marketing_spend'):
            build_layers.build(self.path)

    def test_source_tables_are_not_modified(self):
        before = self.query('SELECT * FROM sessions ORDER BY 1') + self.query('SELECT * FROM identity_links ORDER BY 1')
        build_layers.build(self.path)
        after = self.query('SELECT * FROM sessions ORDER BY 1') + self.query('SELECT * FROM identity_links ORDER BY 1')
        self.assertEqual(before, after)

    def test_rebuild_replaces_only_owned_objects_and_logs_each_build(self):
        build_layers.build(self.path)
        db = sqlite3.connect(self.path)
        db.execute('CREATE TABLE silver_user_notes(note TEXT)')
        db.execute("INSERT INTO silver_user_notes VALUES('keep me')")
        db.commit()
        db.close()
        build_layers.build(self.path)
        self.assertEqual(self.query('SELECT note FROM silver_user_notes'), [('keep me',)])
        self.assertEqual(self.query("SELECT status, COUNT(*) FROM layer_build_log GROUP BY 1"), [('succeeded', 2)])
        self.assertEqual(self.query('SELECT COUNT(DISTINCT build_id) FROM silver_resolved_sessions'), [(1,)])

    def test_schema_mismatch_stops_the_build_and_is_recorded(self):
        db = sqlite3.connect(self.path)
        db.execute('ALTER TABLE sessions DROP COLUMN app_version')
        db.commit()
        db.close()
        with self.assertRaisesRegex(ValueError, 'sessions missing columns'):
            build_layers.build(self.path)
        self.assertEqual(self.query("SELECT status FROM layer_build_log"), [('failed',)])
        self.assertEqual(self.query("SELECT name FROM sqlite_master WHERE name='silver_resolved_sessions'"), [])

    def test_failed_build_keeps_previous_layer(self):
        first = build_layers.build(self.path)
        original = build_layers.reconcile
        build_layers.reconcile = lambda db: ({'forced_failure': False}, {})
        try:
            with self.assertRaisesRegex(AssertionError, 'forced_failure'):
                build_layers.build(self.path)
        finally:
            build_layers.reconcile = original
        self.assertEqual(self.query('SELECT DISTINCT build_id FROM silver_resolved_sessions'), [(first['build_id'],)])
        self.assertEqual(self.query('SELECT status, COUNT(*) FROM layer_build_log GROUP BY 1 ORDER BY 1'),
                         [('failed', 1), ('succeeded', 1)])
        self.assertIn('forced_failure', self.query("SELECT error FROM layer_build_log WHERE status='failed'")[0][0])


if __name__ == '__main__':
    unittest.main()

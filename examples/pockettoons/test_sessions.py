#!/usr/bin/env python3
"""Regression scenarios for the SQLite session checks, without changing the fixture."""
import ast
import datetime as dt
import sqlite3
import unittest
from pathlib import Path

source = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in source.body
              if isinstance(node, ast.Assign) and any(isinstance(x, ast.Name) and x.id == 'checks' for x in node.targets))

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ') == value)
    except (ValueError, TypeError):
        return 0

class SessionChecks(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, valid_utc)
        self.db.executescript('''
          CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, date TEXT,
            session_started_at TEXT, session_ended_at TEXT, last_activity_at TEXT, duration_sec INTEGER, platform TEXT);
          CREATE TABLE identity_links(session_id TEXT, anonymous_id TEXT, user_id TEXT, linked_at TEXT);
          CREATE TABLE transactions(session_id TEXT, user_id TEXT, transaction_at TEXT);
          CREATE TABLE content_views(session_id TEXT, anonymous_id TEXT, user_id TEXT, view_started_at TEXT, view_ended_at TEXT, view_id TEXT);
          CREATE TABLE user_events(session_id TEXT, anonymous_id TEXT, user_id TEXT, event_at TEXT, event_id TEXT, event_name TEXT, view_id TEXT);
        ''')

    def add_session(self, sid, uid, aid, start, end, last, duration):
        self.db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)',
                        (sid, uid, aid, start[:10], start, end, last, duration, 'ios'))

    def count(self, name):
        return self.db.execute(checks[name]).fetchone()[0]

    def test_overlapping_distinct_devices_and_switch_on_same_device(self):
        self.add_session('a', 'u1', 'device1', '2026-01-01T10:00:00Z', '2026-01-01T10:10:00Z', '2026-01-01T10:10:00Z', 600)
        self.add_session('b', 'u1', 'device2', '2026-01-01T10:05:00Z', '2026-01-01T10:15:00Z', '2026-01-01T10:15:00Z', 600)
        self.add_session('c', 'u2', 'device1', '2026-01-01T10:10:00Z', '2026-01-01T10:20:00Z', '2026-01-01T10:20:00Z', 600)
        self.assertEqual(self.count('overlapping sessions on the same browser identity'), 0)
        self.add_session('d', 'u2', 'device1', '2026-01-01T10:12:00Z', '2026-01-01T10:18:00Z', '2026-01-01T10:18:00Z', 360)
        self.assertGreater(self.count('overlapping sessions on the same browser identity'), 0)

    def test_anonymous_open_session_and_invalid_duration(self):
        self.add_session('a', None, 'device1', '2026-01-01T10:00:00Z', None, '2026-01-01T10:05:00Z', None)
        self.assertEqual(self.count('session timestamps and duration invalid'), 0)
        self.db.execute('UPDATE sessions SET duration_sec=300')
        self.assertEqual(self.count('session timestamps and duration invalid'), 1)

    def test_login_link_cannot_cross_user_or_device(self):
        self.add_session('a', 'u1', 'device1', '2026-01-01T10:00:00Z', '2026-01-01T10:10:00Z', '2026-01-01T10:10:00Z', 600)
        self.db.execute("INSERT INTO identity_links VALUES ('a','device1','u1','2026-01-01T10:05:00Z')")
        self.assertEqual(self.count('session identity links inconsistent'), 0)
        self.db.execute("UPDATE identity_links SET user_id='u2'")
        self.assertEqual(self.count('session identity links inconsistent'), 1)

    def test_prelogin_event_stays_anonymous(self):
        self.add_session('a', 'u1', 'device1', '2026-01-01T10:00:00Z', '2026-01-01T10:10:00Z', '2026-01-01T10:10:00Z', 600)
        self.db.execute("INSERT INTO identity_links VALUES ('a','device1','u1','2026-01-01T10:05:00Z')")
        self.db.execute("INSERT INTO user_events (session_id,anonymous_id,user_id,event_at) VALUES ('a','device1',NULL,'2026-01-01T10:02:00Z')")
        self.assertEqual(self.count('identified session event without prior login link'), 0)
        self.db.execute("UPDATE user_events SET user_id='u1'")
        self.assertEqual(self.count('identified session event without prior login link'), 1)

    def test_exact_thirty_minute_gap_requires_new_session(self):
        self.db.execute("INSERT INTO user_events (session_id,event_at,event_id,event_name) VALUES ('a','2026-01-01T10:00:00Z','1','app_opened'),('a','2026-01-01T10:29:59Z','2','session_engagement')")
        self.assertEqual(self.count('session activity gap at least 30 minutes'), 0)
        self.db.execute("UPDATE user_events SET event_at='2026-01-01T10:30:00Z' WHERE event_id='2'")
        self.assertEqual(self.count('session activity gap at least 30 minutes'), 1)

    def test_playback_heartbeats_prevent_idle_gap_and_require_valid_view(self):
        self.db.execute("INSERT INTO content_views VALUES ('a','device1','u1','2026-01-01T10:00:00Z','2026-01-01T10:10:00Z','v1')")
        self.db.execute("INSERT INTO user_events VALUES ('a','device1','u1','2026-01-01T10:05:00Z','h1','playback_heartbeat','v1'),('a','device1','u1','2026-01-01T10:10:00Z','h2','playback_heartbeat','v1')")
        self.assertEqual(self.count('playback heartbeat invalid'), 0)
        self.assertEqual(self.count('playback heartbeat missing or gap over five minutes'), 0)
        self.db.execute("DELETE FROM user_events WHERE event_id='h1'")
        self.assertGreater(self.count('playback heartbeat missing or gap over five minutes'), 0)
        self.db.execute("UPDATE user_events SET view_id='missing'")
        self.assertEqual(self.count('playback heartbeat invalid'), 1)

    def test_long_playback_without_other_interaction(self):
        start='2026-01-01T10:00:00Z'; end='2026-01-01T10:35:00Z'
        self.add_session('a', 'u1', 'device1', start, end, end, 2100)
        self.db.execute("INSERT INTO content_views VALUES ('a','device1','u1',?,?,'v1')", (start,end))
        self.db.execute("INSERT INTO user_events VALUES ('a','device1','u1',?,'open','app_opened',NULL)", (start,))
        for minute in range(5,36,5):
            self.db.execute("INSERT INTO user_events VALUES ('a','device1','u1',?,?, 'playback_heartbeat','v1')",
                            (f'2026-01-01T10:{minute:02}:00Z', f'h{minute}'))
        self.assertEqual(self.count('session activity evidence missing boundaries'), 0)
        self.assertEqual(self.count('session activity gap at least 30 minutes'), 0)
        self.assertEqual(self.count('playback heartbeat missing or gap over five minutes'), 0)

if __name__ == '__main__':
    unittest.main()

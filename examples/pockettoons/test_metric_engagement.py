"""Regression coverage for the registered engagement group."""
import sqlite3
import unittest

from metric_registry import load_sql

APRIL = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-05-01T00:00:00Z'}
APR_MAY = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-06-01T00:00:00Z'}


class EngagementTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
        CREATE TABLE content_episodes(content_id TEXT, episode_number INTEGER, episode_duration_sec INTEGER);
        CREATE TABLE content_views(view_id TEXT, user_id TEXT, session_id TEXT, content_id TEXT, episode_number INTEGER,
                                   date TEXT, view_started_at TEXT, free_quota_consuming INTEGER, free_quota_sequence INTEGER);
        CREATE TABLE playback_segments(segment_id TEXT, view_id TEXT, segment_started_at TEXT, segment_ended_at TEXT,
                                       position_start_sec INTEGER, position_end_sec INTEGER, watch_duration_sec INTEGER);
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT, country_at_event TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT, session_id TEXT, linked_at TEXT);
        CREATE TABLE user_events(event_id TEXT, user_id TEXT, session_id TEXT, event_name TEXT, event_at TEXT);
        ''')
        for ep in (1, 2, 3):
            self.db.execute("INSERT INTO content_episodes VALUES('c1',?,1000)", (ep,))
        self.n = 0

    def view(self, user, ep, start, segments=(), quota=None, title='c1'):
        """segments: (wall_start, wall_end, pos_start, pos_end, watched)."""
        self.n += 1
        vid = f'v{self.n}'
        self.db.execute('INSERT INTO content_views VALUES(?,?,?,?,?,?,?,?,?)',
                        (vid, user, None, title, ep, start[:10], start, int(quota is not None), quota))
        for k, (a, b, p, q, w) in enumerate(segments):
            self.db.execute('INSERT INTO playback_segments VALUES(?,?,?,?,?,?,?)', (f'{vid}_{k}', vid, a, b, p, q, w))
        return vid

    def session(self, user, start, sid=None):
        self.n += 1
        sid = sid or f's{self.n}'
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (sid, user, 'd', 'ios', start, start, 'US'))
        return sid

    def rows(self, name, params=APRIL):
        return self.db.execute(load_sql(name), params).fetchall()


class WatchTimeTests(EngagementTests):
    def test_watch_time_splits_across_months_and_per_engaged_user_excludes_light_viewers(self):
        self.view('u1', 1, '2026-04-30T23:58:00Z', [('2026-04-30T23:58:00Z', '2026-05-01T00:02:00Z', 0, 240, 240)])
        self.view('u2', 1, '2026-04-10T10:00:00Z', [('2026-04-10T10:00:00Z', '2026-04-10T10:00:30Z', 0, 30, 30)])
        rows = {r[0]: r[1:] for r in self.rows('watch_time_monthly', APR_MAY)}
        self.assertAlmostEqual(rows['2026-04'][0], 150)
        self.assertAlmostEqual(rows['2026-05'][0], 120)
        self.assertEqual(rows['2026-04'][2], 1)  # only u1 is engaged in April (120 s); u2 watched 30 s
        self.assertAlmostEqual(rows['2026-04'][3], 120)

    def test_views_per_viewer_counts_attempts(self):
        for ep in (1, 2, 3):
            self.view('u1', ep, '2026-04-10T10:00:00Z')
        self.view('u2', 1, '2026-04-11T10:00:00Z')
        self.assertEqual(self.rows('views_per_viewer_monthly')[0][1:3], (4, 2))
        self.assertAlmostEqual(self.rows('views_per_viewer_monthly')[0][3], 2.0)


class CompletionTests(EngagementTests):
    def completion(self, params=APRIL):
        return {(r[0], r[1], r[2]): (r[5], r[7]) for r in self.rows('user_episode_completion', params)}

    def test_resume_in_a_later_attempt_completes_but_rewinds_do_not(self):
        self.view('u1', 1, '2026-04-10T10:00:00Z', [('2026-04-10T10:00:00Z', '2026-04-10T10:08:00Z', 0, 480, 480)])
        self.view('u1', 1, '2026-04-11T10:00:00Z', [('2026-04-11T10:00:00Z', '2026-04-11T10:07:00Z', 480, 900, 420)])
        self.view('u2', 1, '2026-04-10T10:00:00Z', [('2026-04-10T10:00:00Z', '2026-04-10T10:10:00Z', 0, 600, 600),
                                                    ('2026-04-10T10:10:00Z', '2026-04-10T10:15:00Z', 300, 600, 300)])
        got = self.completion()
        self.assertEqual(got[('u1', 'c1', 1)], (900, 1))
        self.assertEqual(got[('u2', 'c1', 1)], (600, 0))

    def test_ninety_percent_threshold_and_seven_day_window(self):
        self.view('u1', 1, '2026-04-01T10:00:00Z', [('2026-04-01T10:00:00Z', '2026-04-01T10:14:59Z', 0, 899, 899)])
        self.view('u1', 2, '2026-04-01T10:00:00Z', [('2026-04-01T10:00:00Z', '2026-04-01T10:08:00Z', 0, 480, 480)])
        self.view('u1', 2, '2026-04-08T10:00:01Z', [('2026-04-08T10:00:01Z', '2026-04-08T10:08:00Z', 480, 1000, 520)])
        got = self.completion()
        self.assertEqual(got[('u1', 'c1', 1)][1], 0)  # 899 of 1000 is below 90%
        self.assertEqual(got[('u1', 'c1', 2)][1], 0)  # resume after the 7-day window is not counted

    def test_monthly_rate_requires_window_inside_coverage(self):
        self.view('u1', 1, '2026-04-10T10:00:00Z', [('2026-04-10T10:00:00Z', '2026-04-10T10:16:40Z', 0, 1000, 1000)])
        self.view('u2', 1, '2026-04-28T10:00:00Z', [('2026-04-28T10:00:00Z', '2026-04-28T10:16:40Z', 0, 1000, 1000)])
        self.assertEqual(self.rows('episode_completion_monthly')[0][1:3], (1, 1))

    def test_continuation_requires_next_episode_within_window_and_skips_last_episode(self):
        full = lambda t: [(t, t, 0, 1000, 1000)]
        self.view('u1', 1, '2026-04-01T10:00:00Z', full('2026-04-01T10:00:00Z'))
        self.view('u1', 2, '2026-04-05T10:00:00Z', full('2026-04-05T10:00:00Z'))
        self.view('u2', 1, '2026-04-01T10:00:00Z', full('2026-04-01T10:00:00Z'))
        self.view('u2', 2, '2026-04-09T10:00:00Z')
        self.view('u3', 3, '2026-04-01T10:00:00Z', full('2026-04-01T10:00:00Z'))
        month, eligible, continued, rate = self.rows('series_continuation_monthly')[0]
        # u1 ep1 continued, u1 ep2 has a next episode but no view of ep3, u2 ep1 continued too late; u3 ep3 is last.
        self.assertEqual((eligible, continued), (3, 1))


class QuotaAndPaywallTests(EngagementTests):
    def test_free_quota_hit_rate_is_per_free_viewer_day(self):
        for seq in range(1, 9):
            self.view('u1', 1, f'2026-04-10T1{seq}:00:00Z', quota=seq, title=f't{seq}')
        self.view('u2', 1, '2026-04-10T10:00:00Z', quota=1)
        self.view('u1', 1, '2026-04-11T10:00:00Z', quota=1)
        row = self.rows('free_quota_hit_monthly')[0]
        self.assertEqual(row[1:3], (3, 1))
        self.assertAlmostEqual(row[3], 1 / 3)

    def test_paywall_exposure_resolves_anonymous_events_through_session(self):
        s1 = self.session('u1', '2026-04-10T10:00:00Z')
        s2 = self.session(None, '2026-04-11T10:00:00Z')
        self.db.execute("INSERT INTO identity_links VALUES('l','d','u2',?,'2026-04-11T10:01:00Z')", (s2,))
        self.session('u3', '2026-04-12T10:00:00Z')
        self.db.execute("INSERT INTO user_events VALUES('e1','u1',?,'paywall_viewed','2026-04-10T10:02:00Z')", (s1,))
        self.db.execute("INSERT INTO user_events VALUES('e2',NULL,?,'paywall_viewed','2026-04-11T10:00:30Z')", (s2,))
        month, exposed, mau, rate = self.rows('paywall_exposure_monthly')[0]
        self.assertEqual((exposed, mau), (2, 3))

    def test_zero_denominators_report_null(self):
        self.assertIsNone(self.rows('views_per_viewer_monthly')[0][3])
        self.assertIsNone(self.rows('free_quota_hit_monthly')[0][3])
        self.assertIsNone(self.rows('paywall_exposure_monthly')[0][3])
        self.assertIsNone(self.rows('episode_completion_monthly')[0][3])


if __name__ == '__main__':
    unittest.main()

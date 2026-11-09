"""Regression coverage for the registered activity family, ratios and growth accounting."""
import sqlite3
import unittest

from metric_registry import load_sql

APRIL = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-05-01T00:00:00Z'}
APR_JUN = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-07-01T00:00:00Z'}


class ActivityTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT, country_at_event TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT,
                                    session_id TEXT, linked_at TEXT);
        CREATE TABLE users(user_id TEXT, signup_at TEXT);
        CREATE TABLE content_views(view_id TEXT, user_id TEXT, content_id TEXT);
        CREATE TABLE playback_segments(segment_id TEXT, view_id TEXT, segment_started_at TEXT,
                                       segment_ended_at TEXT, watch_duration_sec INTEGER);
        ''')
        self.n = 0
        self.addCleanup(self.db.close)

    def session(self, user, start, last=None):
        self.n += 1
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)',
                        (f's{self.n}', user, 'd1', 'ios', start, last or start, 'US'))

    def watch(self, user, start, end, seconds):
        self.n += 1
        self.db.execute('INSERT INTO content_views VALUES(?,?,?)', (f'v{self.n}', user, 'c1'))
        self.db.execute('INSERT INTO playback_segments VALUES(?,?,?,?,?)', (f'g{self.n}', f'v{self.n}', start, end, seconds))

    def user(self, user, signup):
        self.db.execute('INSERT INTO users VALUES(?,?)', (user, signup))

    def run_metric(self, name, params=APRIL):
        return self.db.execute(load_sql(name), params).fetchall()

    def values(self, name, params=APRIL):
        return {row[0]: row[1] for row in self.run_metric(name, params)}


class DailyAndWeeklyActiveTests(ActivityTests):
    def test_dau_counts_a_session_crossing_midnight_on_both_days(self):
        self.session('u1', '2026-04-10T23:50:00Z', '2026-04-11T00:10:00Z')
        dau = self.values('dau')
        self.assertEqual(len(dau), 30)
        self.assertEqual((dau['2026-04-10'], dau['2026-04-11'], dau['2026-04-12']), (1, 1, 0))

    def test_dau_counts_a_user_once_per_day(self):
        self.session('u1', '2026-04-10T08:00:00Z', '2026-04-10T08:10:00Z')
        self.session('u1', '2026-04-10T20:00:00Z', '2026-04-10T20:10:00Z')
        self.assertEqual(self.values('dau')['2026-04-10'], 1)

    def test_wau_uses_complete_monday_weeks_inside_coverage(self):
        # Coverage starts Wednesday 1 April, so the first complete ISO week starts Monday 6 April.
        self.session('u1', '2026-04-02T10:00:00Z')
        self.session('u2', '2026-04-12T23:59:00Z')  # Sunday, week of 6 April
        self.session('u3', '2026-04-13T00:00:00Z')  # Monday, week of 13 April
        wau = self.values('wau')
        self.assertEqual(sorted(wau), ['2026-04-06', '2026-04-13', '2026-04-20'])
        self.assertEqual((wau['2026-04-06'], wau['2026-04-13']), (1, 1))

    def test_family_month_block_matches_approved_mau(self):
        self.session('u1', '2026-04-30T23:50:00Z', '2026-05-01T00:20:00Z')
        self.session(None, '2026-05-03T10:00:00Z')
        self.session('u2', '2026-06-03T10:00:00Z')
        mau = [(m, v) for m, v, _ in self.run_metric('mau_monthly', APR_JUN)]
        self.assertEqual(self.run_metric('mau_from_family', APR_JUN), mau)


class EngagedTests(ActivityTests):
    def test_under_sixty_seconds_is_not_engaged(self):
        self.watch('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:00:59Z', 59)
        self.assertEqual(self.values('deu')['2026-04-10'], 0)

    def test_watch_time_adds_across_views_in_the_period(self):
        self.watch('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:00:30Z', 30)
        self.watch('u1', '2026-04-10T18:00:00Z', '2026-04-10T18:00:30Z', 30)
        self.assertEqual(self.values('deu')['2026-04-10'], 1)

    def test_segment_crossing_midnight_is_split_by_wall_clock_share(self):
        self.watch('u1', '2026-04-10T23:59:00Z', '2026-04-11T00:01:00Z', 100)  # 50 s each day
        self.watch('u2', '2026-04-10T23:59:00Z', '2026-04-11T00:01:00Z', 120)  # 60 s each day
        deu = self.values('deu')
        self.assertEqual((deu['2026-04-10'], deu['2026-04-11']), (1, 1))
        self.assertEqual(self.values('meu')['2026-04'], 2)

    def test_zero_length_segment_counts_in_its_period(self):
        self.watch('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:00:00Z', 60)
        self.assertEqual(self.values('deu')['2026-04-10'], 1)

    def test_weu_and_meu_use_the_same_threshold(self):
        self.watch('u1', '2026-04-06T10:00:00Z', '2026-04-06T10:00:40Z', 40)
        self.watch('u1', '2026-04-12T10:00:00Z', '2026-04-12T10:00:40Z', 40)
        self.assertEqual(self.values('weu')['2026-04-06'], 1)
        self.assertEqual(self.values('deu')['2026-04-06'], 0)
        self.assertEqual(self.values('meu')['2026-04'], 1)


class RatioTests(ActivityTests):
    def test_stickiness_is_average_dau_over_mau(self):
        for day in ('01', '02', '03'):
            self.session('u1', f'2026-04-{day}T10:00:00Z')
        self.session('u2', '2026-04-05T10:00:00Z')
        month, average_dau, mau, stickiness = self.run_metric('stickiness')[0]
        self.assertEqual((month, mau), ('2026-04', 2))
        self.assertAlmostEqual(average_dau, 4 / 30)
        self.assertAlmostEqual(stickiness, 4 / 60)

    def test_engaged_stickiness_and_engagement_rate(self):
        self.session('u1', '2026-04-01T10:00:00Z')
        self.session('u2', '2026-04-01T10:00:00Z')
        self.watch('u1', '2026-04-01T10:00:00Z', '2026-04-01T10:01:00Z', 60)
        self.watch('u1', '2026-04-02T10:00:00Z', '2026-04-02T10:01:00Z', 60)
        self.assertAlmostEqual(self.run_metric('engaged_stickiness')[0][3], 2 / 30)
        self.assertEqual(self.run_metric('engagement_rate')[0][:3], ('2026-04', 1, 2))
        self.assertAlmostEqual(self.run_metric('engagement_rate')[0][3], 0.5)

    def test_zero_denominator_reports_null(self):
        self.assertIsNone(self.run_metric('stickiness')[0][3])
        self.assertIsNone(self.run_metric('engagement_rate')[0][3])


class GrowthAccountingTests(ActivityTests):
    def test_buckets_and_identities(self):
        self.user('retained', '2026-03-05T00:00:00Z')
        self.user('churned', '2026-03-05T00:00:00Z')
        self.user('new', '2026-05-02T00:00:00Z')
        self.user('late_first', '2026-03-20T00:00:00Z')
        self.user('back', '2026-03-01T00:00:00Z')
        for user in ('retained', 'churned', 'back'):
            self.session(user, '2026-04-10T10:00:00Z')
        for user in ('retained', 'new', 'late_first'):
            self.session(user, '2026-05-10T10:00:00Z')
        self.session('back', '2026-06-10T10:00:00Z')
        rows = {r[0]: r[1:] for r in self.run_metric('growth_accounting_monthly', APR_JUN)}
        self.assertNotIn('2026-04', rows)
        # May: new, retained, resurrected (signed up earlier, first active in May), churned (churned and back).
        self.assertEqual(rows['2026-05'][:4], (1, 1, 1, 2))
        self.assertAlmostEqual(rows['2026-05'][4], 1.0)
        # June: back returns after an inactive month; the three May users churn.
        self.assertEqual(rows['2026-06'][:4], (0, 0, 1, 3))
        mau = {m: v for m, v, _ in self.run_metric('mau_monthly', APR_JUN)}
        for month, prev in (('2026-05', '2026-04'), ('2026-06', '2026-05')):
            new, retained, resurrected, churned, _ = rows[month]
            self.assertEqual(new + retained + resurrected, mau[month])
            self.assertEqual(mau[month] - mau[prev], new + resurrected - churned)

    def test_quick_ratio_is_null_without_churn(self):
        self.user('u1', '2026-03-01T00:00:00Z')
        self.session('u1', '2026-04-10T10:00:00Z')
        self.session('u1', '2026-05-10T10:00:00Z')
        rows = {r[0]: r[1:] for r in self.run_metric('growth_accounting_monthly', APR_JUN)}
        self.assertIsNone(rows['2026-05'][4])


if __name__ == '__main__':
    unittest.main()

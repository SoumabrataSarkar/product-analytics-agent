"""Regression coverage for the registered MAU definition (docs/metrics/metric-registry.md)."""
import sqlite3
import unittest

from metric_registry import load_sql, with_monthly

MONTHLY = load_sql('mau_monthly')
QUARTER = with_monthly(load_sql('mau_quarter_average'))
BY_PLATFORM = load_sql('mau_monthly_by_platform')
APR_JUN = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-07-01T00:00:00Z'}


class MauTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT,
                                    session_id TEXT, linked_at TEXT);
        ''')
        self.n = 0

    def session(self, user, start, last, platform='ios', anon='d1'):
        self.n += 1
        sid = f's{self.n}'
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?)', (sid, user, anon, platform, start, last))
        return sid

    def link(self, sid, user, anon='d1', at='2026-04-10T10:05:00Z'):
        self.db.execute('INSERT INTO identity_links VALUES(?,?,?,?,?)', (f'l{sid}{user}', anon, user, sid, at))

    def monthly(self, params=APR_JUN):
        return {m: (mau, unidentified) for m, mau, unidentified in self.db.execute(MONTHLY, params)}

    def test_distinct_users_per_month_regardless_of_session_count(self):
        self.session('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:20:00Z')
        self.session('u1', '2026-04-11T10:00:00Z', '2026-04-11T10:20:00Z', platform='web')
        self.session('u2', '2026-05-02T09:00:00Z', '2026-05-02T09:10:00Z')
        self.assertEqual(self.monthly(), {'2026-04': (1, 0), '2026-05': (1, 0), '2026-06': (0, 0)})

    def test_session_crossing_month_boundary_counts_in_both_months(self):
        self.session('u1', '2026-04-30T23:50:00Z', '2026-05-01T00:20:00Z')
        self.assertEqual(self.monthly(), {'2026-04': (1, 0), '2026-05': (1, 0), '2026-06': (0, 0)})

    def test_activity_ending_exactly_at_month_start_counts_in_new_month(self):
        self.session('u1', '2026-04-30T23:40:00Z', '2026-05-01T00:00:00Z')
        self.assertEqual(self.monthly()['2026-05'], (1, 0))

    def test_session_before_coverage_counts_only_where_active_inside(self):
        self.session('u1', '2026-03-31T23:50:00Z', '2026-04-01T00:10:00Z')
        self.session('u2', '2026-03-31T10:00:00Z', '2026-03-31T10:30:00Z')
        self.assertEqual(self.monthly()['2026-04'], (1, 0))

    def test_login_partway_resolves_user_from_same_session_link(self):
        sid = self.session(None, '2026-04-10T10:00:00Z', '2026-04-10T10:30:00Z')
        self.link(sid, 'u1')
        self.assertEqual(self.monthly()['2026-04'], (1, 0))

    def test_never_logged_in_session_is_excluded_and_reported(self):
        self.session(None, '2026-04-10T10:00:00Z', '2026-04-10T10:30:00Z')
        self.assertEqual(self.monthly()['2026-04'], (0, 1))

    def test_links_to_two_users_in_one_session_stay_unresolved(self):
        sid = self.session(None, '2026-04-10T10:00:00Z', '2026-04-10T10:30:00Z')
        self.link(sid, 'u1')
        self.link(sid, 'u2')
        self.assertEqual(self.monthly()['2026-04'], (0, 1))

    def test_no_attribution_across_sessions_by_device(self):
        self.session(None, '2026-04-09T10:00:00Z', '2026-04-09T10:30:00Z', anon='shared')
        later = self.session(None, '2026-05-10T10:00:00Z', '2026-05-10T10:30:00Z', anon='shared')
        self.link(later, 'u1', anon='shared', at='2026-05-10T10:05:00Z')
        self.assertEqual(self.monthly()['2026-04'], (0, 1))
        self.assertEqual(self.monthly()['2026-05'], (1, 0))

    def test_partial_month_outside_coverage_is_not_reported(self):
        self.session('u1', '2026-07-03T10:00:00Z', '2026-07-03T10:30:00Z')
        self.assertNotIn('2026-07', self.monthly())

    def test_platform_slices_overlap_and_do_not_sum_to_total(self):
        self.session('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:20:00Z', platform='ios')
        self.session('u1', '2026-04-12T10:00:00Z', '2026-04-12T10:20:00Z', platform='web')
        self.session('u2', '2026-04-12T11:00:00Z', '2026-04-12T11:20:00Z', platform='web')
        slices = {p: n for m, p, n in self.db.execute(BY_PLATFORM, APR_JUN) if m == '2026-04'}
        self.assertEqual(slices, {'ios': 1, 'web': 2})
        self.assertEqual(self.monthly()['2026-04'][0], 2)

    def test_quarter_is_average_of_three_complete_months_not_sum(self):
        self.session('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:20:00Z')
        for user in ('u1', 'u2'):
            self.session(user, '2026-05-10T10:00:00Z', '2026-05-10T10:20:00Z')
        for user in ('u1', 'u2', 'u3'):
            self.session(user, '2026-06-10T10:00:00Z', '2026-06-10T10:20:00Z')
        self.assertEqual(self.db.execute(QUARTER, APR_JUN).fetchall(), [('2026-Q2', 2.0)])

    def test_incomplete_quarter_is_not_reported(self):
        self.session('u1', '2026-04-10T10:00:00Z', '2026-04-10T10:20:00Z')
        params = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-06-01T00:00:00Z'}
        self.assertEqual(self.db.execute(QUARTER, params).fetchall(), [])


if __name__ == '__main__':
    unittest.main()

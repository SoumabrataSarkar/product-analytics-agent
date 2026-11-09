"""Regression coverage for the registered funnel and lifecycle group."""
import sqlite3
import unittest

from metric_registry import load_sql

APR_JUN = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-07-01T00:00:00Z'}
APRIL = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-05-01T00:00:00Z'}


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
        CREATE TABLE users(user_id TEXT, signup_at TEXT);
        CREATE TABLE transactions(txn_id TEXT, user_id TEXT, type TEXT, amount_usd REAL, related_txn_id TEXT,
                                  country_at_event TEXT, checkout_event_id TEXT);
        CREATE TABLE payment_status_history(payment_status_event_id TEXT, txn_id TEXT, status TEXT,
                                            effective_at TEXT, recorded_at TEXT);
        CREATE TABLE subscription_history(user_id TEXT, status TEXT, effective_start_at TEXT, effective_end_at TEXT);
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT, country_at_event TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT, session_id TEXT, linked_at TEXT);
        CREATE TABLE user_events(event_id TEXT, event_name TEXT, event_at TEXT, triggering_paywall_event_id TEXT,
                                 event_properties_json TEXT);
        CREATE TABLE marketing_spend(date TEXT, channel TEXT, impressions INTEGER, clicks INTEGER);
        ''')
        self.n = 0

    def nid(self, prefix):
        self.n += 1
        return f'{prefix}{self.n}'

    def user(self, user, signup):
        self.db.execute('INSERT INTO users VALUES(?,?)', (user, signup))

    def charge(self, user, kind, status, at, checkout=None, related=None):
        tid = self.nid('t')
        self.db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?)', (tid, user, kind, 9.99, related, 'US', checkout))
        self.db.execute('INSERT INTO payment_status_history VALUES(?,?,?,?,?)', (self.nid('p'), tid, status, at, at))
        return tid

    def period(self, user, start, end, status='active'):
        self.db.execute('INSERT INTO subscription_history VALUES(?,?,?,?)', (user, status, start, end))

    def session(self, user, start, last=None):
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (self.nid('s'), user, 'd', 'ios', start, last or start, 'US'))

    def event(self, name, at, product, paywall=None):
        eid = self.nid('e')
        self.db.execute('INSERT INTO user_events VALUES(?,?,?,?,?)', (eid, name, at, paywall, f'{{"product":"{product}"}}'))
        return eid

    def rows(self, name, params=APR_JUN):
        return self.db.execute(load_sql(name), params).fetchall()


class ConversionTests(LifecycleTests):
    def test_thirty_day_window_is_half_open_and_uses_success_time(self):
        self.user('in', '2026-04-01T00:00:00Z')
        self.charge('in', 'subscription', 'succeeded', '2026-04-30T23:59:59Z')
        self.user('edge', '2026-04-01T00:00:00Z')
        self.charge('edge', 'subscription', 'succeeded', '2026-05-01T00:00:00Z')
        self.user('failed', '2026-04-01T00:00:00Z')
        self.charge('failed', 'subscription', 'failed', '2026-04-02T00:00:00Z')
        april = {r[0]: r[1:] for r in self.rows('conversion_30d')}['2026-04']
        self.assertEqual(april[:3], (3, 1, 1))

    def test_ppv_counts_for_paid_but_not_subscription_conversion(self):
        self.user('u1', '2026-04-05T00:00:00Z')
        purchase = self.charge('u1', 'ppv', 'succeeded', '2026-04-06T10:00:00Z')
        self.charge('u1', 'refund', 'succeeded', '2026-04-07T10:00:00Z', related=purchase)
        april = {r[0]: r[1:] for r in self.rows('conversion_30d')}['2026-04']
        self.assertEqual(april[:3], (1, 0, 1))

    def test_incomplete_window_and_pre_coverage_signups_are_excluded(self):
        self.user('march', '2026-03-20T00:00:00Z')
        self.user('late', '2026-06-05T00:00:00Z')
        self.user('ok', '2026-05-31T00:00:00Z')
        self.assertEqual(self.rows('conversion_30d'), [('2026-05', 1, 0, 0, 0.0, 0.0)])


class ChurnTests(LifecycleTests):
    def test_snapshot_churn_ignores_lapse_and_resubscribe_within_month(self):
        self.period('stays', '2026-04-10T01:00:00Z', None)
        self.period('lapses', '2026-04-10T01:00:00Z', '2026-05-10T01:00:00Z')
        self.period('back', '2026-04-10T01:00:00Z', '2026-05-10T01:00:00Z')
        self.period('back', '2026-05-20T01:00:00Z', None)
        self.period('notice', '2026-04-10T01:00:00Z', '2026-06-10T01:00:00Z', 'cancel_at_period_end')
        self.period('refunded', '2026-04-10T01:00:00Z', None, 'refunded')
        rows = {r[0]: r[1:] for r in self.rows('subscriber_churn_monthly')}
        self.assertEqual(rows['2026-04'], (0, 0, None))
        self.assertEqual(rows['2026-05'][:2], (4, 1))
        self.assertAlmostEqual(rows['2026-05'][2], 0.25)
        self.assertEqual(rows['2026-06'][:2], (3, 1))

    def test_mau_by_subscriber_status_uses_status_at_session_start(self):
        self.period('u1', '2026-04-10T01:00:00Z', None)
        self.session('u1', '2026-04-05T10:00:00Z')
        self.session('u1', '2026-04-12T10:00:00Z')
        self.session('u2', '2026-04-12T10:00:00Z')
        self.assertEqual(self.rows('mau_monthly_by_subscriber_status', APRIL),
                         [('2026-04', 'non_subscriber', 2), ('2026-04', 'subscriber', 1)])


class RetentionTests(LifecycleTests):
    def test_day_n_counts_activity_on_that_utc_day_including_sessions_across_midnight(self):
        self.user('u1', '2026-04-01T00:00:00Z')
        self.session('u1', '2026-04-02T12:00:00Z')
        self.session('u1', '2026-04-07T23:50:00Z', '2026-04-08T00:10:00Z')
        self.user('u2', '2026-04-01T00:00:00Z')
        self.session('u2', '2026-05-01T10:00:00Z')
        got = {(r[0], r[1]): r[2:4] for r in self.rows('retention_day_n')}
        self.assertEqual(got[('2026-04', 1)], (2, 1))
        self.assertEqual(got[('2026-04', 7)], (2, 1))
        self.assertEqual(got[('2026-04', 30)], (2, 1))

    def test_day_n_eligibility_requires_day_inside_coverage(self):
        self.user('u1', '2026-06-25T00:00:00Z')
        self.user('march', '2026-03-31T00:00:00Z')
        got = {(r[0], r[1]): r[2] for r in self.rows('retention_day_n')}
        self.assertEqual(got, {('2026-06', 1): 1})

    def test_monthly_cohort_retention(self):
        for user in ('a', 'b', 'c', 'd'):
            self.user(user, '2026-04-10T00:00:00Z')
        self.session('a', '2026-05-03T10:00:00Z')
        self.session('b', '2026-05-03T10:00:00Z')
        self.session('a', '2026-06-03T10:00:00Z')
        got = {(r[0], r[2]): r[3:5] for r in self.rows('retention_monthly_cohort')}
        self.assertEqual(got[('2026-04', 1)], (4, 2))
        self.assertEqual(got[('2026-04', 2)], (4, 1))
        self.assertNotIn(('2026-04', 0), got)


class FunnelAndCtrTests(LifecycleTests):
    def test_funnel_counts_each_paywall_once_through_captured_links(self):
        pw = self.event('paywall_viewed', '2026-04-10T10:00:00Z', 'subscription')
        co1 = self.event('checkout_started', '2026-04-10T10:01:00Z', 'subscription', pw)
        co2 = self.event('checkout_started', '2026-04-10T10:05:00Z', 'subscription', pw)
        self.charge('u1', 'subscription', 'failed', '2026-04-10T10:02:00Z', checkout=co1)
        self.charge('u1', 'subscription', 'succeeded', '2026-04-10T10:06:00Z', checkout=co2)
        self.event('paywall_viewed', '2026-04-11T10:00:00Z', 'subscription')
        orphan = self.event('checkout_started', '2026-04-11T10:01:00Z', 'subscription')
        self.charge('u2', 'subscription', 'succeeded', '2026-04-11T10:02:00Z', checkout=orphan)
        self.event('paywall_viewed', '2026-04-12T10:00:00Z', 'ppv')
        rows = {r[1]: r[2:] for r in self.rows('paywall_funnel_monthly', APRIL)}
        self.assertEqual(rows['subscription'][:3], (2, 1, 1))
        self.assertEqual(rows['subscription'][3:], (0.5, 1.0, 0.5))
        self.assertEqual(rows['ppv'][:3], (1, 0, 0))
        self.assertIsNone(rows['ppv'][4])

    def test_ctr_is_ratio_of_sums_not_average_of_daily_rates(self):
        self.db.execute("INSERT INTO marketing_spend VALUES('2026-04-01','paid_social',100,10)")
        self.db.execute("INSERT INTO marketing_spend VALUES('2026-04-02','paid_social',900,9)")
        self.db.execute("INSERT INTO marketing_spend VALUES('2026-04-02','paid_search',1000,20)")
        rows = {r[1]: r[2:] for r in self.rows('marketing_ctr_monthly', APRIL)}
        self.assertEqual(rows['paid_social'][:2], (19, 1000))
        self.assertAlmostEqual(rows['paid_social'][2], 0.019)
        self.assertAlmostEqual(rows['all'][2], 39 / 2000)


if __name__ == '__main__':
    unittest.main()

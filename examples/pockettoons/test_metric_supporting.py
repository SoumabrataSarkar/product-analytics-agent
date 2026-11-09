"""Regression coverage for the registered supporting metrics."""
import sqlite3
import unittest

from metric_registry import load_sql

APRIL = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-05-01T00:00:00Z'}
APR_JUN = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-07-01T00:00:00Z'}


class SupportingTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
        CREATE TABLE users(user_id TEXT, signup_at TEXT, acquisition_source TEXT);
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT, country_at_event TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT, session_id TEXT, linked_at TEXT);
        CREATE TABLE content_views(view_id TEXT, user_id TEXT, content_id TEXT);
        CREATE TABLE playback_segments(segment_id TEXT, view_id TEXT, segment_started_at TEXT, segment_ended_at TEXT,
                                       watch_duration_sec INTEGER);
        CREATE TABLE transactions(txn_id TEXT, user_id TEXT, type TEXT, amount_usd REAL, related_txn_id TEXT,
                                  country_at_event TEXT, transaction_at TEXT, list_price_usd REAL);
        CREATE TABLE payment_status_history(payment_status_event_id TEXT, txn_id TEXT, status TEXT,
                                            effective_at TEXT, recorded_at TEXT);
        CREATE TABLE subscription_history(user_id TEXT, status TEXT, effective_start_at TEXT, effective_end_at TEXT,
                                          source_txn_id TEXT, cancelled_at TEXT);
        CREATE TABLE marketing_spend(date TEXT, channel TEXT, spend_usd REAL, impressions INTEGER, clicks INTEGER);
        ''')
        self.n = 0

    def nid(self, prefix):
        self.n += 1
        return f'{prefix}{self.n}'

    def user(self, user, signup, source='organic'):
        self.db.execute('INSERT INTO users VALUES(?,?,?)', (user, signup, source))

    def session(self, user, start, last=None):
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (self.nid('s'), user, 'd', 'ios', start, last or start, 'US'))

    def watch(self, user, start, end, seconds):
        vid = self.nid('v')
        self.db.execute('INSERT INTO content_views VALUES(?,?,?)', (vid, user, 'c1'))
        self.db.execute('INSERT INTO playback_segments VALUES(?,?,?,?,?)', (self.nid('g'), vid, start, end, seconds))

    def txn(self, user, kind, amount, *events, related=None, created=None, price=None):
        tid = self.nid('t')
        self.db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?)',
                        (tid, user, kind, amount, related, 'US', created or events[0][1], price))
        for status, at in events:
            self.db.execute('INSERT INTO payment_status_history VALUES(?,?,?,?,?)', (self.nid('p'), tid, status, at, at))
        return tid

    def period(self, user, start, end, status='active', source=None, cancelled=None):
        self.db.execute('INSERT INTO subscription_history VALUES(?,?,?,?,?,?)', (user, status, start, end, source, cancelled))

    def rows(self, name, params=APRIL):
        return self.db.execute(load_sql(name), params).fetchall()


class ActivityBasicsTests(SupportingTests):
    def test_signups_by_source_keep_unknown_and_total(self):
        self.user('a', '2026-04-02T00:00:00Z', 'paid_social')
        self.user('b', '2026-04-03T00:00:00Z', 'unknown')
        self.user('c', '2026-03-30T00:00:00Z', 'organic')
        self.assertEqual(self.rows('new_signups_monthly'), [('2026-04', 'all', 2), ('2026-04', 'paid_social', 1), ('2026-04', 'unknown', 1)])

    def test_activation_needs_an_engaged_day_within_days_zero_to_six(self):
        self.user('day6', '2026-04-01T09:00:00Z')
        self.watch('day6', '2026-04-07T23:59:00Z', '2026-04-08T00:01:00Z', 120)  # 60 s on day 6
        self.user('day7', '2026-04-01T09:00:00Z')
        self.watch('day7', '2026-04-08T10:00:00Z', '2026-04-08T10:05:00Z', 300)
        self.user('light', '2026-04-01T09:00:00Z')
        self.watch('light', '2026-04-02T10:00:00Z', '2026-04-02T10:00:59Z', 59)
        self.user('late', '2026-04-26T00:00:00Z')
        self.assertEqual(self.rows('activation_7d')[0][:3], ('2026-04', 3, 1))

    def test_sessions_per_active_user_and_session_duration(self):
        self.session('a', '2026-04-10T10:00:00Z', '2026-04-10T10:10:00Z')
        self.session('a', '2026-04-11T10:00:00Z', '2026-04-11T10:20:00Z')
        self.session('b', '2026-04-12T10:00:00Z', '2026-04-12T10:40:00Z')
        self.session(None, '2026-04-12T11:00:00Z', '2026-04-12T13:00:00Z')
        self.assertEqual(self.rows('sessions_per_active_user_monthly')[0][1:3], (3, 2))
        month, sessions, mean_sec, median_sec = self.rows('session_duration_monthly')[0]
        self.assertEqual((sessions, median_sec), (3, 1200))
        self.assertAlmostEqual(mean_sec, 1400)

    def test_active_days_count_each_utc_day_a_session_touches(self):
        self.session('a', '2026-04-10T23:50:00Z', '2026-04-11T00:10:00Z')
        self.session('a', '2026-04-11T12:00:00Z')
        self.session('b', '2026-04-20T12:00:00Z')
        self.assertEqual(self.rows('active_days_distribution_monthly'), [('2026-04', 1, 1), ('2026-04', 2, 1)])


class MonetisationTests(SupportingTests):
    def test_paying_users_by_product(self):
        self.txn('a', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        self.txn('a', 'ppv', 1.99, ('succeeded', '2026-04-04T01:00:00Z'))
        self.txn('b', 'ppv', 1.99, ('failed', '2026-04-04T01:00:00Z'))
        self.assertEqual(self.rows('paying_users_monthly'), [('2026-04', 1, 1, 1)])

    def test_subscriber_snapshots_net_adds_and_mrr(self):
        charge = self.txn('a', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'), price=9.99)
        self.period('a', '2026-04-03T01:00:00Z', None, source=charge)
        other = self.txn('b', 'subscription', 9.99, ('succeeded', '2026-05-03T01:00:00Z'), price=9.99)
        self.period('b', '2026-05-03T01:00:00Z', '2026-06-10T01:00:00Z', 'cancel_at_period_end', source=other)
        subs = {r[0]: r[1:] for r in self.rows('active_subscribers_monthly', APR_JUN)}
        self.assertEqual(subs, {'2026-04': (0, 1, 1), '2026-05': (1, 2, 1), '2026-06': (2, 1, -1)})
        mrr = {r[0]: r[1:] for r in self.rows('mrr_monthly', APR_JUN)}
        self.assertEqual(mrr['2026-05'], (2, 1998))

    def test_refund_rate_by_amount(self):
        charge = self.txn('a', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        self.txn('b', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        self.txn('a', 'refund', 9.99, ('succeeded', '2026-04-05T01:00:00Z'), related=charge)
        row = self.rows('refund_rate_monthly')[0]
        self.assertEqual(row[1:5], (1998, 999, 2, 1))
        self.assertAlmostEqual(row[5], 0.5)

    def test_payment_failure_uses_latest_outcome_and_creation_month(self):
        self.txn('a', 'subscription', 9.99, ('failed', '2026-04-03T00:00:00Z'))
        self.txn('a', 'subscription', 9.99, ('succeeded', '2026-04-03T06:00:00Z'))
        self.txn('b', 'subscription', 9.99, ('pending', '2026-04-04T00:00:00Z'))
        self.txn('c', 'ppv', 1.99, ('pending', '2026-04-30T23:59:00Z'), ('succeeded', '2026-05-01T00:01:00Z'))
        rows = {r[1]: r[2:] for r in self.rows('payment_failure_rate_monthly')}
        self.assertEqual(rows['subscription'][:2], (2, 1))
        self.assertAlmostEqual(rows['subscription'][2], 0.5)
        self.assertEqual(rows['ppv'][:2], (1, 0))


class LifecycleAndMarketingTests(SupportingTests):
    def test_cancellation_request_rate(self):
        self.period('a', '2026-03-10T01:00:00Z', None)
        self.period('b', '2026-03-10T01:00:00Z', '2026-04-20T01:00:00Z', 'cancel_at_period_end', cancelled='2026-04-12T00:00:00Z')
        self.assertEqual(self.rows('cancellation_request_rate_monthly')[0][1:], (1, 2, 0.5))

    def test_resubscription_within_sixty_days_and_complete_windows(self):
        self.period('back', '2026-04-01T01:00:00Z', '2026-04-05T01:00:00Z')
        self.period('back', '2026-05-20T01:00:00Z', None)
        self.period('gone', '2026-04-01T01:00:00Z', '2026-04-05T01:00:00Z')
        self.period('late', '2026-04-01T01:00:00Z', '2026-05-15T01:00:00Z')
        self.period('renewed', '2026-04-01T01:00:00Z', '2026-04-10T01:00:00Z')
        self.period('renewed', '2026-04-10T01:00:00Z', None)
        rows = {r[0]: r[1:] for r in self.rows('resubscription_60d', APR_JUN)}
        self.assertEqual(rows['2026-04'][:2], (2, 1))
        self.assertEqual(rows['2026-05'][:2], (0, 0))

    def test_marketing_cpc_cost_per_signup_and_cac(self):
        self.db.execute("INSERT INTO marketing_spend VALUES('2026-04-02','paid_social',100.0,1000,50)")
        self.db.execute("INSERT INTO marketing_spend VALUES('2026-04-03','paid_social',100.0,1000,50)")
        for user in ('a', 'b', 'c', 'd'):
            self.user(user, '2026-04-02T00:00:00Z', 'paid_social')
        self.user('e', '2026-04-02T00:00:00Z', 'unknown')
        self.txn('a', 'subscription', 9.99, ('succeeded', '2026-04-05T01:00:00Z'))
        self.txn('a', 'ppv', 1.99, ('succeeded', '2026-04-06T01:00:00Z'))
        self.txn('e', 'subscription', 9.99, ('succeeded', '2026-04-05T01:00:00Z'))
        row = self.rows('marketing_efficiency_monthly')[0]
        self.assertEqual(row[:6], ('2026-04', 'paid_social', 20000, 100, 4, 1))
        self.assertAlmostEqual(row[6], 2.0)
        self.assertAlmostEqual(row[7], 50.0)
        self.assertAlmostEqual(row[8], 200.0)

    def test_zero_denominators_report_null(self):
        self.assertIsNone(self.rows('sessions_per_active_user_monthly')[0][3])
        self.assertIsNone(self.rows('refund_rate_monthly')[0][5])
        self.assertIsNone(self.rows('cancellation_request_rate_monthly')[0][3])


if __name__ == '__main__':
    unittest.main()

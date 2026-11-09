"""Regression coverage for the registered revenue group."""
import sqlite3
import unittest

from metric_registry import load_sql

APRIL = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-05-01T00:00:00Z'}
APR_MAY = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-06-01T00:00:00Z'}
APR_JUN = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-07-01T00:00:00Z'}


class RevenueTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
        CREATE TABLE transactions(txn_id TEXT, user_id TEXT, type TEXT, amount_usd REAL,
                                  related_txn_id TEXT, country_at_event TEXT);
        CREATE TABLE payment_status_history(payment_status_event_id TEXT, txn_id TEXT, status TEXT,
                                            effective_at TEXT, recorded_at TEXT);
        CREATE TABLE sessions(session_id TEXT, user_id TEXT, anonymous_id TEXT, platform TEXT,
                              session_started_at TEXT, last_activity_at TEXT, country_at_event TEXT);
        CREATE TABLE identity_links(identity_link_id TEXT, anonymous_id TEXT, user_id TEXT,
                                    session_id TEXT, linked_at TEXT);
        ''')
        self.n = 0

    def txn(self, user, kind, amount, *statuses, related=None):
        """Add a transaction with (status, effective_at) history entries."""
        self.n += 1
        tid = f't{self.n}'
        self.db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?)', (tid, user, kind, amount, related, 'US'))
        for k, (status, at) in enumerate(statuses):
            self.db.execute('INSERT INTO payment_status_history VALUES(?,?,?,?,?)', (f'{tid}_{k}', tid, status, at, at))
        return tid

    def active(self, user, at):
        self.n += 1
        self.db.execute('INSERT INTO sessions VALUES(?,?,?,?,?,?,?)', (f's{self.n}', user, 'd', 'ios', at, at, 'US'))

    def rows(self, name, params=APRIL):
        return self.db.execute(load_sql(name), params).fetchall()

    def net(self, params=APRIL):
        return {r[0]: r[1:] for r in self.rows('net_revenue_monthly', params)}

    def test_successful_charges_minus_successful_refunds(self):
        sub = self.txn('u1', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        self.txn('u2', 'ppv', 1.99, ('succeeded', '2026-04-04T10:00:00Z'))
        self.txn('u1', 'refund', 9.99, ('succeeded', '2026-04-06T10:00:00Z'), related=sub)
        self.assertEqual(self.net()['2026-04'], (1198, 999, 199))

    def test_failed_and_never_succeeded_attempts_count_for_nothing(self):
        self.txn('u1', 'ppv', 1.99, ('failed', '2026-04-04T10:00:00Z'))
        self.txn('u1', 'ppv', 1.99, ('pending', '2026-04-04T10:00:00Z'))
        self.assertEqual(self.net()['2026-04'], (0, 0, 0))

    def test_booked_at_success_effective_time_not_creation(self):
        self.txn('u1', 'subscription', 9.99, ('pending', '2026-04-30T23:59:00Z'), ('succeeded', '2026-05-01T00:02:00Z'))
        net = self.net(APR_MAY)
        self.assertEqual((net['2026-04'][2], net['2026-05'][2]), (0, 999))

    def test_refund_counts_in_its_own_month(self):
        sub = self.txn('u1', 'subscription', 9.99, ('succeeded', '2026-04-28T01:00:00Z'))
        self.txn('u1', 'refund', 9.99, ('succeeded', '2026-05-02T10:00:00Z'), related=sub)
        net = self.net(APR_MAY)
        self.assertEqual((net['2026-04'], net['2026-05']), ((999, 0, 999), (0, 999, -999)))

    def test_exact_cents(self):
        for _ in range(10):
            self.txn('u1', 'ppv', 0.1, ('succeeded', '2026-04-04T10:00:00Z'))
        self.txn('u1', 'ppv', 0.2, ('succeeded', '2026-04-04T10:00:00Z'))
        self.assertEqual(self.net()['2026-04'][2], 120)

    def test_type_split_assigns_refunds_to_the_refunded_charge_type(self):
        sub = self.txn('u1', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        ppv = self.txn('u2', 'ppv', 1.99, ('succeeded', '2026-04-04T10:00:00Z'))
        self.txn('u2', 'refund', 1.99, ('succeeded', '2026-04-05T10:00:00Z'), related=ppv)
        split = {r[1]: r[2:] for r in self.rows('net_revenue_by_type_monthly')}
        self.assertEqual(split, {'subscription': (999, 0, 999), 'ppv': (199, 199, 0)})
        self.assertEqual(sum(v[2] for v in split.values()), self.net()['2026-04'][2])
        self.assertTrue(sub)

    def test_quarter_is_sum_of_three_complete_months(self):
        for month in ('04', '05', '06'):
            self.txn('u1', 'subscription', 9.99, ('succeeded', f'2026-{month}-03T01:00:00Z'))
        self.assertEqual(self.rows('net_revenue_quarterly', APR_JUN), [('2026-Q2', 2997, 0, 2997)])
        self.assertEqual(self.rows('net_revenue_quarterly', APR_MAY), [])

    def test_arpu_divides_net_revenue_by_mau(self):
        self.txn('u1', 'subscription', 9.99, ('succeeded', '2026-04-03T01:00:00Z'))
        for user in ('u1', 'u2', 'u3'):
            self.active(user, '2026-04-10T10:00:00Z')
        month, net, mau, arpu = self.rows('arpu')[0]
        self.assertEqual((month, net, mau), ('2026-04', 999, 3))
        self.assertAlmostEqual(arpu, 3.33)

    def test_arppu_counts_payers_once_and_keeps_refunded_payers(self):
        a = self.txn('u1', 'ppv', 1.99, ('succeeded', '2026-04-04T10:00:00Z'))
        self.txn('u1', 'ppv', 1.99, ('succeeded', '2026-04-05T10:00:00Z'))
        self.txn('u1', 'refund', 1.99, ('succeeded', '2026-04-06T10:00:00Z'), related=a)
        p = self.txn('u2', 'ppv', 1.99, ('succeeded', '2026-04-07T10:00:00Z'))
        self.txn('u2', 'refund', 1.99, ('succeeded', '2026-04-08T10:00:00Z'), related=p)
        month, net, payers, arppu = self.rows('arppu')[0]
        self.assertEqual((net, payers), (199, 2))
        self.assertAlmostEqual(arppu, 0.995)

    def test_refund_only_user_is_not_a_payer_and_zero_denominators_are_null(self):
        sub = self.txn('u1', 'subscription', 9.99, ('succeeded', '2026-04-28T01:00:00Z'))
        self.txn('u1', 'refund', 9.99, ('succeeded', '2026-05-02T10:00:00Z'), related=sub)
        may = {r[0]: r for r in self.rows('arppu', APR_MAY)}['2026-05']
        self.assertEqual(may[2], 0)
        self.assertIsNone(may[3])
        self.assertIsNone(self.rows('arpu', APR_MAY)[1][3])


if __name__ == '__main__':
    unittest.main()

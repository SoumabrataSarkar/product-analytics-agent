"""Tests for the layer builder and the Silver table contracts."""
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
          ('s_mismatch','u4','d4','ios','US','1.2.0','2026-04-15T10:00:00Z','2026-04-15T10:01:01Z','2026-04-15T10:01:01Z'),
          ('s_cross','u2','d2','web','PH','1.2.0','2026-04-11T23:50:00Z','2026-04-12T00:10:00Z','2026-04-12T00:10:00Z'),
          ('s_to_midnight','u5','d5','ios','MX','1.2.0','2026-04-14T23:00:00Z','2026-04-15T00:00:00Z','2026-04-15T00:00:00Z'),
          ('s_sub','s1','d6','ios','US','1.2.0','2026-06-04T10:00:00Z','2026-06-04T10:20:00Z','2026-06-04T10:20:00Z'),
          ('s_ghost','ghost','d7','web','US','1.2.0','2026-04-16T10:00:00Z','2026-04-16T10:05:00Z','2026-04-16T10:05:00Z');
        INSERT INTO identity_links VALUES
          ('l1','s_user','u1'), ('l2','s_link','u2'), ('l3','s_later','u3'),
          ('l4','s_two','u5'), ('l5','s_two','u6'), ('l6','s_mismatch','u9');
        ''')
        db.executescript('''
        CREATE TABLE transactions(txn_id TEXT PRIMARY KEY, user_id TEXT, type TEXT, transaction_subtype TEXT,
          amount_usd REAL, payment_method TEXT, transaction_at TEXT, session_id TEXT, related_txn_id TEXT,
          subscription_id TEXT, list_price_usd REAL, country_at_event TEXT, checkout_event_id TEXT);
        CREATE TABLE payment_status_history(payment_status_event_id TEXT PRIMARY KEY, txn_id TEXT, status TEXT,
          effective_at TEXT, recorded_at TEXT);
        ''')
        payments = [  # txn_id, user, type, amount, related, statuses (status, effective_at)
            ('t_ok', 'u1', 'subscription', 9.99, None, [('succeeded', '2026-04-03T01:00:00Z')]),
            ('t_retry_fail', 'u1', 'subscription', 9.99, None, [('failed', '2026-05-02T20:00:00Z')]),
            ('t_late', 'u2', 'ppv', 1.99, None, [('pending', '2026-04-30T23:59:00Z'), ('succeeded', '2026-05-01T00:01:00Z')]),
            ('t_bad_cents', 'u3', 'ppv', 9.995, None, [('succeeded', '2026-04-05T10:00:00Z')]),
            ('t_text', 'u3', 'ppv', 'unavailable', None, [('succeeded', '2026-04-05T10:00:00Z')]),
            ('t_double', 'u3', 'ppv', 1.99, None, [('succeeded', '2026-04-06T10:00:00Z'), ('succeeded', '2026-04-07T10:00:00Z')]),
            ('t_failed_charge', 'u4', 'ppv', 1.99, None, [('failed', '2026-04-08T10:00:00Z')]),
            ('r_of_failed', 'u4', 'refund', 1.99, 't_failed_charge', [('succeeded', '2026-04-09T10:00:00Z')]),
            ('r_missing', 'u5', 'refund', 1.99, 'nowhere', [('succeeded', '2026-04-09T10:00:00Z')]),
            ('r_ok', 'u1', 'refund', 9.99, 't_ok', [('succeeded', '2026-04-10T10:00:00Z')]),
            ('sub_paid', 's1', 'subscription', 9.99, None, [('succeeded', '2026-06-03T01:00:00Z')]),
            ('p_ppv', 'p1', 'ppv', 1.99, None, [('succeeded', '2026-04-21T10:00:00Z')]),
            ('p_sub', 'p1', 'subscription', 9.99, None, [('succeeded', '2026-04-25T10:00:00Z')]),
        ]
        for tid, user, kind, amount, related, statuses in payments:
            db.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (tid, user, kind, kind + '_x', amount, 'card', statuses[0][1], None, related, None, 9.99, 'US', None))
            for k, (status, at) in enumerate(statuses):
                db.execute('INSERT INTO payment_status_history VALUES(?,?,?,?,?)', (f'{tid}_{k}', tid, status, at, at))
        db.execute("INSERT INTO transactions VALUES('sub_badprice','s6','subscription','subscription_initial',9.99,'card','2026-06-04T01:00:00Z',NULL,NULL,NULL,9.995,'US',NULL)")
        db.execute("INSERT INTO payment_status_history VALUES('sub_badprice_0','sub_badprice','succeeded','2026-06-04T01:00:00Z','2026-06-04T01:00:00Z')")
        db.executescript('''
        CREATE TABLE subscription_history(subscription_period_id TEXT PRIMARY KEY, subscription_id TEXT, user_id TEXT,
          status TEXT, effective_start_at TEXT, effective_end_at TEXT, cancelled_at TEXT, source_txn_id TEXT, plan_code TEXT);
        CREATE TABLE dataset_metadata(metadata_key TEXT PRIMARY KEY, metadata_value TEXT);
        INSERT INTO dataset_metadata VALUES('users_snapshot_at','2026-09-30T23:59:59Z');
        INSERT INTO subscription_history VALUES
          ('renew_1','sub1','s1','active','2026-06-03T01:00:00Z','2026-07-03T01:00:00Z',NULL,'sub_paid','p'),
          ('renew_2','sub1','s1','active','2026-07-03T01:00:00Z','2026-08-03T01:00:00Z',NULL,'sub_paid','p'),
          ('notice_1','sub2','s2','active','2026-06-03T01:00:00Z','2026-06-10T00:00:00Z',NULL,'sub_paid','p'),
          ('notice_2','sub2','s2','cancel_at_period_end','2026-06-10T00:00:00Z','2026-07-03T01:00:00Z','2026-06-10T00:00:00Z','sub_paid','p'),
          ('lapse','sub3','s3','active','2026-06-03T01:00:00Z','2026-07-03T01:00:00Z',NULL,'sub_paid','p'),
          ('lapse_expired','sub3','s3','expired','2026-07-03T01:00:00Z','2026-08-10T01:00:00Z',NULL,NULL,'p'),
          ('return','sub3b','s3','active','2026-08-10T01:00:00Z','2026-09-10T01:00:00Z',NULL,'sub_paid','p'),
          ('scheduled','sub4','s4','active','2026-09-05T01:00:00Z','2026-10-05T01:00:00Z',NULL,'sub_paid','p'),
          ('overlap_a','sub5','s5','active','2026-06-03T01:00:00Z','2026-07-03T01:00:00Z',NULL,'sub_paid','p'),
          ('overlap_b','sub5','s5','active','2026-06-20T01:00:00Z','2026-07-20T01:00:00Z',NULL,'sub_paid','p'),
          ('unpaid','sub7','s7','active','2026-06-03T01:00:00Z','2026-07-03T01:00:00Z',NULL,'t_failed_charge','p'),
          ('bad_price','sub6','s6','active','2026-06-04T01:00:00Z','2026-07-04T01:00:00Z',NULL,'sub_badprice','p'),
          ('refunded','sub8','s8','refunded','2026-06-05T01:00:00Z',NULL,NULL,NULL,'p');
        ''')
        db.executescript('''
        CREATE TABLE users(user_id TEXT PRIMARY KEY, signup_at TEXT, acquisition_source TEXT, country_origin TEXT,
          country_current TEXT, subscription_status TEXT);
        INSERT INTO users VALUES
          ('u1','2026-04-01T09:00:00Z','organic','US','US','active'),
          ('u2','2026-04-11T09:00:00Z','paid_search','PH','PH','none'),
          ('u3','2026-04-20T00:00:00Z',NULL,'PH','PH','none'),
          ('u4','2026-04-15 10:00:00','organic','US','US','none'),
          ('u5','2026-04-14T09:00:00Z','paid_social','MX','MX','none'),
          ('u7','2026-05-05T09:00:00Z','tiktok','US','US','none'),
          ('p1','2026-04-20T09:00:00Z','creator','US','CA','active'),
          ('s1','2026-06-01T09:00:00Z','organic','US','US','active'),
          ('s3','2026-06-01T09:00:00Z','referral','US','US','active');
        CREATE TABLE content_views(view_id TEXT PRIMARY KEY, user_id TEXT, content_id TEXT, view_started_at TEXT);
        CREATE TABLE playback_segments(segment_id TEXT PRIMARY KEY, view_id TEXT, segment_started_at TEXT,
          segment_ended_at TEXT, watch_duration_sec INTEGER);
        INSERT INTO content_views VALUES('v_u1','u1','c1','2026-04-09T23:58:00Z'), ('v_u2','u2','c1','2026-04-11T10:00:00Z'),
          ('v_u5','u5','c2','2026-04-14T10:00:00Z');
        INSERT INTO playback_segments VALUES
          ('g_midnight','v_u1','2026-04-09T23:58:00Z','2026-04-10T00:01:00Z',180),
          ('g_u2','v_u2','2026-04-11T10:00:00Z','2026-04-11T10:01:30Z',90),
          ('g_short','v_u5','2026-04-14T10:00:00Z','2026-04-14T10:00:30Z',30);
        ''')
        for table in build_layers.SOURCE_ROLES:
            if table not in ('sessions', 'identity_links', 'transactions', 'payment_status_history',
                             'subscription_history', 'dataset_metadata', 'users', 'content_views', 'playback_segments'):
                db.execute(f'CREATE TABLE "{table}"(id TEXT)')
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
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze_sessions'), [(10,)])
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze_users'), [(9,)])

    def test_later_source_change_is_detectable_from_the_build_fingerprint(self):
        result = build_layers.build(self.path)
        db = sqlite3.connect(self.path)
        db.execute("INSERT INTO users VALUES('u_new','2026-05-01T00:00:00Z','organic','US','US','none')")
        db.commit()
        self.assertEqual(self.query('SELECT COUNT(*) FROM bronze_users'), [(10,)])  # a view shows current source
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

    def test_payment_attempts_validate_money_and_label_exceptions(self):
        result = build_layers.build(self.path)
        self.assertEqual(result['status'], 'succeeded')
        rows = {r[0]: r[1:] for r in self.query('''SELECT txn_id, outcome, revenue_type, succeeded_at, amount_cents,
            revenue_cents, exception_status, exception_reason FROM silver_payment_attempts''')}
        self.assertEqual(rows['t_ok'], ('succeeded', 'subscription', '2026-04-03T01:00:00Z', 999, 999, 'ok', None))
        self.assertEqual(rows['t_retry_fail'][:2], ('failed', 'subscription'))
        self.assertEqual(rows['t_retry_fail'][4], 0)
        self.assertEqual(rows['t_late'][2], '2026-05-01T00:01:00Z')  # booked at success, not creation
        self.assertEqual(rows['t_bad_cents'][3:], (None, 0, 'excluded', 'invalid_amount'))
        self.assertEqual(rows['t_text'][3:], (None, 0, 'excluded', 'invalid_amount'))
        self.assertEqual(rows['t_double'][2:], (None, 199, 0, 'excluded', 'multiple_success_events'))
        self.assertEqual(rows['r_of_failed'][1:], ('unattributed', '2026-04-09T10:00:00Z', 199, -199,
                                                   'suspicious_usable', 'refund_without_successful_original'))
        self.assertEqual(rows['r_missing'][1], 'unattributed')
        self.assertEqual(rows['r_ok'][1:5], ('subscription', '2026-04-10T10:00:00Z', 999, -999))
        checks = json.loads(result['reconciliation'])['checks']
        self.assertTrue(checks['silver_payment_attempts.independent_decimal_cents_recount'])
        self.assertTrue(checks['silver_payment_attempts.net_revenue_matches_registry_on_source'])
        april = self.query("SELECT SUM(revenue_cents) FROM silver_payment_attempts WHERE succeeded_at LIKE '2026-04%'")
        self.assertEqual(april, [(999 - 199 - 199 - 999 + 199 + 999,)])  # last two: p1's PPV and subscription

    def test_subscription_access_spells_losses_and_exceptions(self):
        result = build_layers.build(self.path)
        self.assertEqual(result['status'], 'succeeded')
        rows = {r[0]: r[1:] for r in self.query('''SELECT subscription_period_id, grants_access, starts_access_spell,
            ends_access_spell, access_spell_number, price_cents, exception_status, exception_reason
            FROM silver_subscription_access''')}
        self.assertEqual(rows['renew_1'][:4], (1, 1, 0, 1))       # renewal continues the spell
        self.assertEqual(rows['renew_2'][:4], (1, 0, 1, 1))       # loss only at the real end
        self.assertEqual(rows['notice_1'][2], 0)                   # cancellation notice is not a loss
        self.assertEqual(rows['notice_2'][:3], (1, 0, 1))
        self.assertEqual(rows['lapse'][2], 1)
        self.assertEqual(rows['lapse_expired'][:4], (0, 0, 0, None))
        self.assertEqual(rows['return'][:4], (1, 1, 1, 2))         # second spell
        self.assertEqual(rows['scheduled'][2], 0)                  # ends after the snapshot: scheduled, not a loss
        self.assertEqual(rows['overlap_b'][5:], ('suspicious_usable', 'overlapping_access'))
        self.assertEqual(rows['unpaid'][5:], ('suspicious_usable', 'source_charge_not_successful'))
        self.assertEqual(rows['bad_price'][4:], (None, 'suspicious_usable', 'invalid_list_price'))
        self.assertEqual(rows['refunded'][:2], (0, 0))
        self.assertEqual(rows['renew_1'][4:], (999, 'ok', None))
        checks = json.loads(result['reconciliation'])['checks']
        self.assertTrue(all(v for k, v in checks.items() if k.startswith('silver_subscription_access')))

    def test_user_profile_milestones_snapshots_and_exceptions(self):
        result = build_layers.build(self.path)
        self.assertEqual(result['status'], 'succeeded')
        rows = {r[0]: r[1:] for r in self.query('''SELECT user_id, acquisition_source, first_session_at, first_engaged_date,
            first_paid_at, first_subscription_at, first_ppv_at, subscription_spells, is_returning_subscriber,
            exception_status, exception_reason, signup_month, country_current_snapshot FROM silver_user_profile''')}
        self.assertEqual(len(rows), 9)                                   # one row per user, active or not
        self.assertEqual(rows['u1'][1:6], ('2026-04-10T10:00:00Z', '2026-04-09', '2026-04-03T01:00:00Z',
                                           '2026-04-03T01:00:00Z', None))  # refund later does not erase the milestone
        self.assertEqual(rows['u2'][2:6], ('2026-04-11', '2026-05-01T00:01:00Z', None, '2026-05-01T00:01:00Z'))
        self.assertIsNone(rows['u5'][2])                                 # 30 s is not engaged
        self.assertEqual(rows['p1'][3:6], ('2026-04-21T10:00:00Z', '2026-04-25T10:00:00Z', '2026-04-21T10:00:00Z'))
        self.assertEqual(rows['p1'][11], 'CA')                           # snapshot value, not origin
        self.assertEqual(rows['u7'][1:8], (None, None, None, None, None, 0, 0))  # no activity at all
        self.assertEqual(rows['s3'][6:8], (2, 1))                        # returning subscriber
        self.assertEqual(rows['s1'][6:8], (1, 0))
        self.assertEqual(rows['u3'][0], 'unknown')
        self.assertIsNone(rows['u3'][3])                                 # excluded charges are not a first payment
        self.assertEqual(rows['u3'][8:10], ('suspicious_usable', 'activity_before_signup'))
        self.assertEqual(rows['u4'][8:10], ('suspicious_usable', 'invalid_signup_time'))
        self.assertEqual(rows['u7'][8:10], ('suspicious_usable', 'unrecognised_acquisition_source'))
        self.assertEqual(rows['u7'][0], 'tiktok')                        # kept as given, only flagged
        self.assertEqual(rows['u1'][8:10], ('ok', None))
        checks = json.loads(result['reconciliation'])['checks']
        profile = {k: v for k, v in checks.items() if k.startswith('silver_user_profile')}
        self.assertEqual(len(profile), 7)
        self.assertTrue(all(profile.values()))

    def test_user_day_activity_days_watch_and_status(self):
        result = build_layers.build(self.path)
        self.assertEqual(result['status'], 'succeeded')
        rows = {(r[0], r[1]): r[2:] for r in self.query('''SELECT user_id, activity_date, sessions_touching, sessions_started,
            started_session_span_sec, watch_seconds, views_started, subscriber_at_day_start, exception_status,
            exception_reason FROM silver_user_day_activity''')}
        self.assertEqual(rows[('u2', '2026-04-11')][:3], (2, 2, 600 + 1200))     # span counted on the start day only
        self.assertEqual(rows[('u2', '2026-04-12')][:3], (1, 0, 0))              # crossing midnight touches both days
        self.assertEqual(rows[('u5', '2026-04-15')][:2], (1, 0))                 # last activity exactly at midnight
        self.assertEqual(rows[('u1', '2026-04-09')][:2], (0, 0))                 # watch-only day kept
        self.assertAlmostEqual(rows[('u1', '2026-04-09')][3], 120)               # 180 s split by wall-clock share
        self.assertAlmostEqual(rows[('u1', '2026-04-10')][3], 60)
        self.assertEqual(rows[('u2', '2026-04-11')][4], 1)                       # one view started
        self.assertEqual(rows[('s1', '2026-06-04')][5], 1)                       # access began 06-03 01:00
        self.assertEqual(rows[('u1', '2026-04-10')][5], 0)
        self.assertEqual(rows[('u3', '2026-04-13')][6:], ('suspicious_usable', 'activity_before_signup'))
        self.assertEqual(rows[('ghost', '2026-04-16')][6:], ('suspicious_usable', 'user_not_in_users'))
        self.assertEqual(rows[('u1', '2026-04-10')][6:], ('ok', None))
        self.assertNotIn(('u6', '2026-04-14'), rows)                             # ambiguous session is not attributed
        checks = json.loads(result['reconciliation'])['checks']
        activity = {k: v for k, v in checks.items() if k.startswith('silver_user_day_activity')}
        self.assertEqual(len(activity), 11)
        self.assertTrue(all(activity.values()))

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

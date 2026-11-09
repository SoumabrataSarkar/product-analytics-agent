"""Build PocketToons data layers inside an existing generated SQLite database.

Usage: python3 build_layers.py DATABASE

The builder implements the contracts in docs/data-layers/pockettoons-layer-contracts.md.
It reads source tables, never modifies them, and replaces only the objects it owns.
All layer objects are built and reconciled in one transaction: a failed build is
rolled back, recorded in layer_build_log, and leaves the previous layers in place.
Run it on a copy of a reviewed database first.
"""
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
import datetime as dt
import hashlib
import json
import sqlite3
import sys
import uuid

from metric_registry import REGISTRY, load_sql

HERE = Path(__file__).resolve()
# Coverage window documented in the dataset contract (README and data model).
COVERAGE = {'coverage_start': '2026-04-01T00:00:00Z', 'coverage_end': '2026-10-01T00:00:00Z'}
DEFINITIONS = {'mau': '1.1', 'activity_family': '1.0', 'stickiness_and_engagement_rate': '1.0',
               'growth_accounting': '1.0', 'revenue_group': '1.1', 'funnel_and_lifecycle_group': '1.0',
               'engagement_group': '1.0', 'supporting_metrics': '1.1'}

# Source tables exposed in Bronze, with their role (see the layer contracts).
SOURCE_ROLES = {
    'sessions': 'raw record', 'identity_links': 'raw record', 'content_views': 'raw record',
    'playback_segments': 'raw record', 'user_events': 'raw record', 'transactions': 'raw record',
    'payment_status_history': 'raw record', 'marketing_spend': 'raw record',
    'raw_payment_source': 'raw provider feed',
    'subscription_history': 'effective-dated history', 'content_availability_history': 'effective-dated history',
    'content_tier_history': 'effective-dated history',
    'users': 'current-state snapshot', 'anonymous_identities': 'current-state snapshot',
    'content_catalog': 'current-state snapshot', 'content_episodes': 'current-state snapshot',
    'transaction_content_attribution': 'derived business bridge', 'refund_content_attribution': 'derived business bridge',
    'payment_quality_review': 'review evidence', 'dataset_metadata': 'metadata',
}

# Source columns the Silver builds read; the build stops if any is missing.
REQUIRED_COLUMNS = {
    'sessions': {'session_id', 'user_id', 'anonymous_id', 'platform', 'country_at_event', 'app_version',
                 'session_started_at', 'last_activity_at', 'session_ended_at'},
    'identity_links': {'identity_link_id', 'session_id', 'user_id'},
    'transactions': {'txn_id', 'user_id', 'type', 'transaction_subtype', 'amount_usd', 'payment_method',
                     'transaction_at', 'session_id', 'related_txn_id', 'subscription_id', 'list_price_usd',
                     'country_at_event', 'checkout_event_id'},
    'payment_status_history': {'payment_status_event_id', 'txn_id', 'status', 'effective_at', 'recorded_at'},
    'dataset_metadata': {'metadata_key', 'metadata_value'},
    'users': {'user_id', 'signup_at', 'acquisition_source', 'country_origin', 'country_current', 'subscription_status'},
    'content_views': {'view_id', 'user_id', 'content_id', 'episode_number', 'date', 'view_started_at', 'view_type',
                      'is_first_view_of_episode', 'free_quota_consuming', 'free_quota_sequence'},
    'playback_segments': {'view_id', 'segment_started_at', 'segment_ended_at', 'watch_duration_sec',
                          'position_start_sec', 'position_end_sec'},
    'content_episodes': {'content_id', 'episode_number', 'episode_duration_sec'},
    'marketing_spend': {'date', 'channel', 'spend_usd', 'impressions', 'clicks', 'loaded_at'},
    'payment_quality_review': {'txn_id'},
    'user_events': {'event_id', 'user_id', 'event_at', 'event_name', 'session_id', 'content_id', 'episode_number',
                    'event_properties_json', 'triggering_paywall_event_id'},
    'subscription_history': {'subscription_period_id', 'subscription_id', 'user_id', 'status', 'effective_start_at',
                             'effective_end_at', 'cancelled_at', 'source_txn_id', 'plan_code'},
}

BUILD_LOG_DDL = '''CREATE TABLE IF NOT EXISTS layer_build_log(
  build_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL
  CHECK(status IN ('succeeded','failed')), builder_sha256 TEXT NOT NULL, registry_sha256 TEXT NOT NULL,
  definitions TEXT NOT NULL, source_fingerprint TEXT, row_counts TEXT, reconciliation TEXT, error TEXT)'''

# ---------------------------------------------------------------- silver_resolved_sessions

RESOLVED_SESSIONS_SQL = '''
CREATE TABLE silver_resolved_sessions(
  session_id TEXT PRIMARY KEY, raw_user_id TEXT, resolved_user_id TEXT,
  resolution_method TEXT NOT NULL CHECK(resolution_method IN
    ('session_user','same_session_link','unresolved_no_link','unresolved_ambiguous')),
  anonymous_id TEXT NOT NULL, platform TEXT NOT NULL, country_at_event TEXT, app_version TEXT,
  session_started_at TEXT NOT NULL, last_activity_at TEXT NOT NULL, session_ended_at TEXT,
  start_date TEXT NOT NULL, last_activity_date TEXT NOT NULL, active_span_sec INTEGER NOT NULL,
  link_count INTEGER NOT NULL, linked_user_count INTEGER NOT NULL,
  link_user_mismatch INTEGER NOT NULL CHECK(link_user_mismatch IN (0,1)), build_id TEXT NOT NULL);
INSERT INTO silver_resolved_sessions
SELECT s.session_id, s.user_id,
       CASE WHEN s.user_id IS NOT NULL THEN s.user_id WHEN l.linked_users = 1 THEN l.one_user END,
       CASE WHEN s.user_id IS NOT NULL THEN 'session_user'
            WHEN l.linked_users = 1 THEN 'same_session_link'
            WHEN l.linked_users > 1 THEN 'unresolved_ambiguous'
            ELSE 'unresolved_no_link' END,
       s.anonymous_id, s.platform, s.country_at_event, s.app_version,
       s.session_started_at, s.last_activity_at, s.session_ended_at,
       substr(s.session_started_at, 1, 10), substr(s.last_activity_at, 1, 10),
       CAST(ROUND((julianday(s.last_activity_at) - julianday(s.session_started_at)) * 86400) AS INTEGER),
       COALESCE(l.links, 0), COALESCE(l.linked_users, 0),
       CASE WHEN s.user_id IS NOT NULL AND EXISTS (SELECT 1 FROM identity_links m
            WHERE m.session_id = s.session_id AND m.user_id <> s.user_id) THEN 1 ELSE 0 END,
       :build_id
FROM sessions s
LEFT JOIN (SELECT session_id, COUNT(*) AS links, COUNT(DISTINCT user_id) AS linked_users, MIN(user_id) AS one_user
           FROM identity_links GROUP BY session_id) l ON l.session_id = s.session_id;
CREATE INDEX ix_silver_resolved_sessions_user_time ON silver_resolved_sessions(resolved_user_id, session_started_at);
CREATE INDEX ix_silver_resolved_sessions_time ON silver_resolved_sessions(session_started_at)
'''

SILVER_MAU = '''
WITH RECURSIVE months(month_start) AS (
  SELECT :coverage_start UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') FROM months
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') < :coverage_end)
SELECT substr(m.month_start, 1, 7), COUNT(DISTINCT r.resolved_user_id)
FROM months m LEFT JOIN silver_resolved_sessions r
  ON r.session_started_at < strftime('%Y-%m-%dT%H:%M:%SZ', m.month_start, '+1 month')
 AND r.last_activity_at >= m.month_start
GROUP BY m.month_start ORDER BY m.month_start'''


def independent_session_recount(db):
    """Recount resolution methods and mismatches in Python, independently of the build SQL."""
    links = {}
    for session_id, user_id in db.execute('SELECT session_id, user_id FROM identity_links'):
        links.setdefault(session_id, set()).add(user_id)
    counts = {'session_user': 0, 'same_session_link': 0, 'unresolved_no_link': 0, 'unresolved_ambiguous': 0}
    mismatches = 0
    for session_id, user_id in db.execute('SELECT session_id, user_id FROM sessions'):
        linked = links.get(session_id, set())
        if user_id is not None:
            counts['session_user'] += 1
            mismatches += bool(linked - {user_id})
        elif len(linked) == 1:
            counts['same_session_link'] += 1
        elif linked:
            counts['unresolved_ambiguous'] += 1
        else:
            counts['unresolved_no_link'] += 1
    return counts, mismatches


def reconcile_resolved_sessions(db):
    checks = {}
    source_rows = db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    silver_rows = db.execute('SELECT COUNT(*) FROM silver_resolved_sessions').fetchone()[0]
    checks['row_count_equals_source'] = silver_rows == source_rows
    checks['keys_equal_source'] = db.execute('''SELECT COUNT(*) FROM (
        SELECT session_id FROM sessions EXCEPT SELECT session_id FROM silver_resolved_sessions
        UNION ALL SELECT session_id FROM silver_resolved_sessions EXCEPT SELECT session_id FROM sessions)''').fetchone()[0] == 0
    methods = dict(db.execute('SELECT resolution_method, COUNT(*) FROM silver_resolved_sessions GROUP BY 1').fetchall())
    checks['methods_add_to_total'] = sum(methods.values()) == silver_rows
    expected, mismatches = independent_session_recount(db)
    checks['independent_method_recount'] = {k: methods.get(k, 0) for k in expected} == expected
    checks['independent_mismatch_recount'] = db.execute(
        'SELECT COUNT(*) FROM silver_resolved_sessions WHERE link_user_mismatch=1').fetchone()[0] == mismatches
    registry_mau = [(m, v) for m, v, _ in db.execute(load_sql('mau_monthly'), COVERAGE)]
    checks['mau_matches_registry_on_source'] = db.execute(SILVER_MAU, COVERAGE).fetchall() == registry_mau
    return checks, {'source_rows': source_rows, 'methods': methods, 'mismatches': mismatches}

# ---------------------------------------------------------------- silver_payment_attempts

PAYMENT_ATTEMPTS_SQL = '''
CREATE TABLE silver_payment_attempts(
  txn_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, type TEXT NOT NULL, transaction_subtype TEXT,
  revenue_type TEXT NOT NULL, related_txn_id TEXT, subscription_id TEXT, session_id TEXT, checkout_event_id TEXT,
  payment_method TEXT, country_at_event TEXT, created_at TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK(outcome IN ('succeeded','failed','no_outcome')),
  success_event_count INTEGER NOT NULL, succeeded_at TEXT, succeeded_recorded_at TEXT,
  amount_usd_source, amount_cents INTEGER, list_price_cents INTEGER,
  amount_valid INTEGER NOT NULL CHECK(amount_valid IN (0,1)), revenue_cents INTEGER NOT NULL,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','excluded','suspicious_usable')),
  exception_reason TEXT, build_id TEXT NOT NULL);
WITH success AS (
  SELECT txn_id, COUNT(*) AS n, MIN(effective_at) AS effective_at, MIN(recorded_at) AS recorded_at
  FROM payment_status_history WHERE status = 'succeeded' GROUP BY txn_id
),
latest AS (
  SELECT txn_id, (SELECT h.status FROM payment_status_history h
                  WHERE h.txn_id = t.txn_id AND h.status IN ('succeeded', 'failed')
                  ORDER BY h.effective_at DESC, h.recorded_at DESC LIMIT 1) AS outcome
  FROM transactions t
),
base AS (
  SELECT t.*, COALESCE(s.n, 0) AS success_n, s.effective_at AS success_at, s.recorded_at AS success_recorded,
         l.outcome,
         (typeof(t.amount_usd) IN ('integer', 'real') AND t.amount_usd > 0
          AND abs(t.amount_usd * 100 - ROUND(t.amount_usd * 100)) < 0.000001) AS valid,
         o.txn_id AS original_id, o.type AS original_type, COALESCE(os.n, 0) AS original_success_n
  FROM transactions t
  LEFT JOIN success s ON s.txn_id = t.txn_id
  LEFT JOIN latest l ON l.txn_id = t.txn_id
  LEFT JOIN transactions o ON o.txn_id = t.related_txn_id
  LEFT JOIN success os ON os.txn_id = o.txn_id
)
INSERT INTO silver_payment_attempts
SELECT txn_id, user_id, type, transaction_subtype,
       CASE WHEN type <> 'refund' THEN type
            WHEN original_id IS NOT NULL AND original_success_n >= 1 THEN original_type
            ELSE 'unattributed' END,
       related_txn_id, subscription_id, session_id, checkout_event_id, payment_method, country_at_event,
       transaction_at, COALESCE(outcome, 'no_outcome'), success_n,
       CASE WHEN success_n = 1 THEN success_at END, CASE WHEN success_n = 1 THEN success_recorded END,
       amount_usd, CASE WHEN valid THEN CAST(ROUND(amount_usd * 100) AS INTEGER) END,
       CASE WHEN typeof(list_price_usd) IN ('integer', 'real') THEN CAST(ROUND(list_price_usd * 100) AS INTEGER) END,
       valid,
       CASE WHEN valid AND success_n = 1
            THEN (CASE WHEN type = 'refund' THEN -1 ELSE 1 END) * CAST(ROUND(amount_usd * 100) AS INTEGER)
            ELSE 0 END,
       CASE WHEN NOT valid OR success_n > 1 THEN 'excluded'
            WHEN type = 'refund' AND success_n = 1 AND NOT (original_id IS NOT NULL AND original_success_n >= 1)
            THEN 'suspicious_usable' ELSE 'ok' END,
       CASE WHEN NOT valid THEN 'invalid_amount'
            WHEN success_n > 1 THEN 'multiple_success_events'
            WHEN type = 'refund' AND success_n = 1 AND NOT (original_id IS NOT NULL AND original_success_n >= 1)
            THEN 'refund_without_successful_original' END,
       :build_id
FROM base;
CREATE INDEX ix_silver_payment_attempts_success ON silver_payment_attempts(succeeded_at);
CREATE INDEX ix_silver_payment_attempts_user_success ON silver_payment_attempts(user_id, succeeded_at)
'''

SILVER_NET_REVENUE = '''
WITH RECURSIVE months(month_start) AS (
  SELECT :coverage_start UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') FROM months
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') < :coverage_end)
SELECT substr(m.month_start, 1, 7), COALESCE(SUM(a.revenue_cents), 0)
FROM months m LEFT JOIN silver_payment_attempts a
  ON a.succeeded_at >= m.month_start AND a.succeeded_at < strftime('%Y-%m-%dT%H:%M:%SZ', m.month_start, '+1 month')
GROUP BY m.month_start ORDER BY m.month_start'''


def exact_cents(value):
    """Return integer cents for a positive exact-cent number, else None (independent of SQL rounding)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    cents = amount * 100
    if amount <= 0 or cents != cents.to_integral_value():
        return None
    return int(cents)


def independent_payment_recount(db):
    """Recount monthly charges and refunds in Python Decimal cents, independently of the build SQL."""
    successes = {}
    for txn_id, effective_at in db.execute("SELECT txn_id, effective_at FROM payment_status_history WHERE status='succeeded'"):
        successes.setdefault(txn_id, []).append(effective_at)
    totals = {}
    for txn_id, kind, amount in db.execute('SELECT txn_id, type, amount_usd FROM transactions'):
        times = successes.get(txn_id, [])
        cents = exact_cents(amount)
        if len(times) != 1 or cents is None:
            continue
        month = times[0][:7]
        charges, refunds = totals.get(month, (0, 0))
        totals[month] = (charges, refunds + cents) if kind == 'refund' else (charges + cents, refunds)
    return totals


def reconcile_payment_attempts(db):
    checks = {}
    source_rows = db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0]
    silver_rows = db.execute('SELECT COUNT(*) FROM silver_payment_attempts').fetchone()[0]
    checks['row_count_equals_source'] = silver_rows == source_rows
    outcomes = dict(db.execute('SELECT outcome, COUNT(*) FROM silver_payment_attempts GROUP BY 1').fetchall())
    checks['outcomes_add_to_total'] = sum(outcomes.values()) == silver_rows
    silver_totals = {m: (c, r) for m, c, r in db.execute('''SELECT substr(succeeded_at, 1, 7),
        SUM(CASE WHEN revenue_cents > 0 THEN revenue_cents ELSE 0 END),
        SUM(CASE WHEN revenue_cents < 0 THEN -revenue_cents ELSE 0 END)
        FROM silver_payment_attempts WHERE revenue_cents <> 0 GROUP BY 1''')}
    checks['independent_decimal_cents_recount'] = silver_totals == independent_payment_recount(db)
    registry = [(m, net) for m, _, _, net in db.execute(load_sql('net_revenue_monthly'), COVERAGE)]
    checks['net_revenue_matches_registry_on_source'] = db.execute(SILVER_NET_REVENUE, COVERAGE).fetchall() == registry
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_payment_attempts GROUP BY 1').fetchall())
    return checks, {'source_rows': source_rows, 'outcomes': outcomes, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_subscription_access

SUBSCRIPTION_ACCESS_SQL = """
CREATE TABLE silver_subscription_access(
  subscription_period_id TEXT PRIMARY KEY, subscription_id TEXT, user_id TEXT NOT NULL, status TEXT NOT NULL,
  grants_access INTEGER NOT NULL CHECK(grants_access IN (0,1)), effective_start_at TEXT NOT NULL, effective_end_at TEXT,
  cancelled_at TEXT, source_txn_id TEXT, plan_code TEXT, price_cents INTEGER,
  starts_access_spell INTEGER NOT NULL CHECK(starts_access_spell IN (0,1)),
  ends_access_spell INTEGER NOT NULL CHECK(ends_access_spell IN (0,1)), access_spell_number INTEGER,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL);
WITH periods AS (
  SELECT h.*, h.status IN ('active', 'cancel_at_period_end') AS access FROM subscription_history h
),
flags AS (
  SELECT p.*,
    p.access AND NOT EXISTS (SELECT 1 FROM periods q WHERE q.user_id = p.user_id AND q.access
        AND q.subscription_period_id <> p.subscription_period_id AND q.effective_start_at < p.effective_start_at
        AND (q.effective_end_at IS NULL OR q.effective_end_at >= p.effective_start_at)) AS starts_spell,
    p.access AND p.effective_end_at IS NOT NULL
        AND p.effective_end_at <= (SELECT metadata_value FROM dataset_metadata WHERE metadata_key = 'users_snapshot_at')
        AND NOT EXISTS (SELECT 1 FROM periods q WHERE q.user_id = p.user_id
        AND q.access AND q.subscription_period_id <> p.subscription_period_id
        AND q.effective_start_at <= p.effective_end_at
        AND (q.effective_end_at IS NULL OR q.effective_end_at > p.effective_end_at)) AS ends_spell,
    p.access AND EXISTS (SELECT 1 FROM periods q WHERE q.user_id = p.user_id AND q.access
        AND q.subscription_period_id <> p.subscription_period_id
        AND q.effective_start_at < COALESCE(p.effective_end_at, '9999')
        AND p.effective_start_at < COALESCE(q.effective_end_at, '9999')) AS overlapping,
    p.access AND NOT EXISTS (SELECT 1 FROM payment_status_history s
        WHERE s.txn_id = p.source_txn_id AND s.status = 'succeeded') AS unpaid,
    t.list_price_usd AS list_price
  FROM periods p LEFT JOIN transactions t ON t.txn_id = p.source_txn_id
),
priced AS (
  SELECT f.*,
    CASE WHEN typeof(list_price) IN ('integer', 'real') AND list_price > 0
          AND abs(list_price * 100 - ROUND(list_price * 100)) < 0.000001
         THEN CAST(ROUND(list_price * 100) AS INTEGER) END AS price,
    CASE WHEN access THEN SUM(starts_spell) OVER (PARTITION BY user_id ORDER BY effective_start_at, subscription_period_id
                                                  ROWS UNBOUNDED PRECEDING) END AS spell
  FROM flags f
)
INSERT INTO silver_subscription_access
SELECT subscription_period_id, subscription_id, user_id, status, access, effective_start_at, effective_end_at,
       cancelled_at, source_txn_id, plan_code, CASE WHEN access THEN price END, starts_spell, ends_spell, spell,
       CASE WHEN overlapping OR unpaid OR (access AND price IS NULL) THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN overlapping THEN 'overlapping_access,' ELSE '' END)
                    || (CASE WHEN unpaid THEN 'source_charge_not_successful,' ELSE '' END)
                    || (CASE WHEN access AND price IS NULL THEN 'invalid_list_price,' ELSE '' END), ','), ''),
       :build_id
FROM priced;
CREATE INDEX ix_silver_subscription_access_user_start ON silver_subscription_access(user_id, effective_start_at)
"""

SILVER_SUBSCRIBERS = """
WITH RECURSIVE months(month_start) AS (
  SELECT :coverage_start UNION ALL
  SELECT strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') FROM months
  WHERE strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') < :coverage_end),
bounds AS (SELECT month_start, strftime('%Y-%m-%dT%H:%M:%SZ', month_start, '+1 month') AS month_end FROM months)
SELECT substr(b.month_start, 1, 7),
  (SELECT COUNT(DISTINCT a.user_id) FROM silver_subscription_access a WHERE a.grants_access = 1
     AND a.effective_start_at <= b.month_start AND (a.effective_end_at IS NULL OR a.effective_end_at > b.month_start)),
  (SELECT COUNT(DISTINCT a.user_id) FROM silver_subscription_access a WHERE a.grants_access = 1
     AND a.effective_start_at <= b.month_end AND (a.effective_end_at IS NULL OR a.effective_end_at > b.month_end)),
  (SELECT COALESCE(SUM(price), 0) FROM (SELECT a.user_id, MAX(a.price_cents) AS price FROM silver_subscription_access a
     WHERE a.grants_access = 1 AND a.effective_start_at <= b.month_end
       AND (a.effective_end_at IS NULL OR a.effective_end_at > b.month_end) GROUP BY a.user_id))
FROM bounds b ORDER BY b.month_start"""


def independent_spell_recount(db):
    """Merge each user's access intervals in Python; touching intervals are one continuous spell.
    A spell end counts as an access loss only when it is known by the users snapshot."""
    snapshot = db.execute("SELECT metadata_value FROM dataset_metadata WHERE metadata_key='users_snapshot_at'").fetchone()[0]
    intervals = {}
    for user, start, end in db.execute("""SELECT user_id, effective_start_at, effective_end_at FROM subscription_history
                                          WHERE status IN ('active','cancel_at_period_end')"""):
        intervals.setdefault(user, []).append((start, end or '9999'))
    starts = losses = 0
    for spans in intervals.values():
        spans.sort()
        merged = [list(spans[0])]
        for start, end in spans[1:]:
            if start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        starts += len(merged)
        losses += sum(1 for _, end in merged if end != '9999' and end <= snapshot)
    return starts, losses


def reconcile_subscription_access(db):
    checks = {}
    source_rows = db.execute('SELECT COUNT(*) FROM subscription_history').fetchone()[0]
    silver_rows = db.execute('SELECT COUNT(*) FROM silver_subscription_access').fetchone()[0]
    checks['row_count_equals_source'] = silver_rows == source_rows
    access = dict(db.execute('SELECT grants_access, COUNT(*) FROM silver_subscription_access GROUP BY 1').fetchall())
    checks['access_counts_add_to_total'] = sum(access.values()) == silver_rows
    starts, losses = independent_spell_recount(db)
    checks['independent_spell_start_recount'] = db.execute(
        'SELECT COUNT(*) FROM silver_subscription_access WHERE starts_access_spell = 1').fetchone()[0] == starts
    checks['independent_access_loss_recount'] = db.execute(
        'SELECT COUNT(*) FROM silver_subscription_access WHERE ends_access_spell = 1').fetchone()[0] == losses
    silver = db.execute(SILVER_SUBSCRIBERS, COVERAGE).fetchall()
    churn = db.execute(load_sql('subscriber_churn_monthly'), COVERAGE).fetchall()
    mrr = db.execute(load_sql('mrr_monthly'), COVERAGE).fetchall()
    checks['subscribers_at_start_match_registry'] = [r[1] for r in silver] == [r[1] for r in churn]
    checks['mrr_matches_registry_on_source'] = [(r[0], r[2], r[3]) for r in silver] == [tuple(r) for r in mrr]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_subscription_access GROUP BY 1').fetchall())
    return checks, {'source_rows': source_rows, 'spell_starts': starts, 'access_losses': losses, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_user_profile

ACQUISITION_SOURCES = ('organic', 'paid_search', 'paid_social', 'creator', 'referral', 'other', 'unknown')

USER_PROFILE_SQL = """
CREATE TABLE silver_user_profile(
  user_id TEXT PRIMARY KEY, signup_at TEXT, signup_date TEXT, signup_month TEXT, acquisition_source TEXT NOT NULL,
  country_origin TEXT, country_current_snapshot TEXT, subscription_status_snapshot TEXT,
  first_session_at TEXT, first_engaged_date TEXT, first_paid_at TEXT, first_subscription_at TEXT, first_ppv_at TEXT,
  subscription_spells INTEGER NOT NULL, is_returning_subscriber INTEGER NOT NULL CHECK(is_returning_subscriber IN (0,1)),
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL);
INSERT INTO silver_user_profile
WITH RECURSIVE segment_days(user_id, day, seg_start, seg_end, watched) AS (
  SELECT v.user_id, date(s.segment_started_at), s.segment_started_at, s.segment_ended_at, s.watch_duration_sec
  FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id
  UNION ALL
  SELECT user_id, date(day, '+1 day'), seg_start, seg_end, watched FROM segment_days
  WHERE date(day, '+1 day') < substr(seg_end, 1, 10)
     OR (date(day, '+1 day') = substr(seg_end, 1, 10) AND substr(seg_end, 12) <> '00:00:00Z')
),
engaged AS (
  SELECT user_id, MIN(day) AS first_day FROM (
    SELECT user_id, day FROM segment_days GROUP BY user_id, day
    HAVING SUM(watched * CASE WHEN julianday(seg_end) = julianday(seg_start) THEN 1.0
                              ELSE (MIN(julianday(seg_end), julianday(day, '+1 day')) - MAX(julianday(seg_start), julianday(day)))
                                   / (julianday(seg_end) - julianday(seg_start)) END) >= 60)
  GROUP BY user_id
),
sessions_first AS (
  SELECT resolved_user_id AS user_id, MIN(session_started_at) AS first_session_at
  FROM silver_resolved_sessions WHERE resolved_user_id IS NOT NULL GROUP BY resolved_user_id
),
payments_first AS (
  SELECT user_id, MIN(succeeded_at) AS first_paid_at,
         MIN(CASE WHEN type = 'subscription' THEN succeeded_at END) AS first_subscription_at,
         MIN(CASE WHEN type = 'ppv' THEN succeeded_at END) AS first_ppv_at
  FROM silver_payment_attempts WHERE revenue_cents > 0 GROUP BY user_id
),
spells AS (SELECT user_id, COALESCE(MAX(access_spell_number), 0) AS n FROM silver_subscription_access GROUP BY user_id),
base AS (
  SELECT u.user_id, u.signup_at, u.acquisition_source, u.country_origin, u.country_current, u.subscription_status,
         sf.first_session_at, e.first_day, pf.first_paid_at, pf.first_subscription_at, pf.first_ppv_at,
         COALESCE(sp.n, 0) AS spell_count,
         (u.signup_at IS NULL OR strftime('%Y-%m-%dT%H:%M:%SZ', u.signup_at) IS NOT u.signup_at) AS bad_signup,
         COALESCE(sf.first_session_at < u.signup_at OR pf.first_paid_at < u.signup_at
                  OR e.first_day < substr(u.signup_at, 1, 10), 0) AS before_signup,
         (COALESCE(u.acquisition_source, 'unknown') NOT IN ACQUISITION_SOURCES) AS bad_source
  FROM users u
  LEFT JOIN sessions_first sf ON sf.user_id = u.user_id
  LEFT JOIN engaged e ON e.user_id = u.user_id
  LEFT JOIN payments_first pf ON pf.user_id = u.user_id
  LEFT JOIN spells sp ON sp.user_id = u.user_id
)
SELECT user_id, signup_at, substr(signup_at, 1, 10), substr(signup_at, 1, 7), COALESCE(acquisition_source, 'unknown'),
       country_origin, country_current, subscription_status,
       first_session_at, first_day, first_paid_at, first_subscription_at, first_ppv_at,
       spell_count, spell_count > 1,
       CASE WHEN bad_signup OR before_signup OR bad_source THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN bad_signup THEN 'invalid_signup_time,' ELSE '' END)
                    || (CASE WHEN before_signup THEN 'activity_before_signup,' ELSE '' END)
                    || (CASE WHEN bad_source THEN 'unrecognised_acquisition_source,' ELSE '' END), ','), ''),
       :build_id
FROM base;
CREATE INDEX ix_silver_user_profile_signup ON silver_user_profile(signup_at);
CREATE INDEX ix_silver_user_profile_source_signup ON silver_user_profile(acquisition_source, signup_at)
""".replace('ACQUISITION_SOURCES', "(" + ",".join(f"'{v}'" for v in ACQUISITION_SOURCES) + ")", 1)


def independent_profile_recount(db):
    """First valid paid charge and first identified session per user, recomputed in Python from the source."""
    successes = {}
    for txn_id, effective_at in db.execute("SELECT txn_id, effective_at FROM payment_status_history WHERE status='succeeded'"):
        successes.setdefault(txn_id, []).append(effective_at)
    first_paid = {}
    for txn_id, user, kind, amount in db.execute('SELECT txn_id, user_id, type, amount_usd FROM transactions'):
        times = successes.get(txn_id, [])
        if kind == 'refund' or len(times) != 1 or exact_cents(amount) is None or exact_cents(amount) <= 0:
            continue
        if user not in first_paid or times[0] < first_paid[user]:
            first_paid[user] = times[0]
    links = {}
    for session_id, user in db.execute('SELECT session_id, user_id FROM identity_links'):
        links.setdefault(session_id, set()).add(user)
    first_session = {}
    for session_id, user, started in db.execute('SELECT session_id, user_id, session_started_at FROM sessions'):
        if user is None:
            linked = links.get(session_id, set())
            user = next(iter(linked)) if len(linked) == 1 else None
        if user is not None and (user not in first_session or started < first_session[user]):
            first_session[user] = started
    return first_paid, first_session


def reconcile_user_profile(db):
    checks = {}
    source_rows = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    checks['row_count_equals_source'] = db.execute('SELECT COUNT(*) FROM silver_user_profile').fetchone()[0] == source_rows
    checks['keys_equal_source'] = db.execute(
        'SELECT COUNT(*) FROM (SELECT user_id FROM users EXCEPT SELECT user_id FROM silver_user_profile '
        'UNION ALL SELECT user_id FROM silver_user_profile EXCEPT SELECT user_id FROM users)').fetchone()[0] == 0
    first_paid, first_session = independent_profile_recount(db)
    known = {r[0] for r in db.execute('SELECT user_id FROM users')}
    first_paid = {k: v for k, v in first_paid.items() if k in known}
    first_session = {k: v for k, v in first_session.items() if k in known}
    checks['independent_first_paid_recount'] = first_paid == dict(db.execute(
        'SELECT user_id, first_paid_at FROM silver_user_profile WHERE first_paid_at IS NOT NULL'))
    checks['independent_first_session_recount'] = first_session == dict(db.execute(
        'SELECT user_id, first_session_at FROM silver_user_profile WHERE first_session_at IS NOT NULL'))
    signups = db.execute(
        "WITH s AS (SELECT signup_month, acquisition_source FROM silver_user_profile "
        "  WHERE signup_at >= :coverage_start AND signup_at < :coverage_end) "
        "SELECT signup_month, acquisition_source, COUNT(*) FROM s GROUP BY 1, 2 "
        "UNION ALL SELECT signup_month, 'all', COUNT(*) FROM s GROUP BY 1 ORDER BY 1, 2", COVERAGE).fetchall()
    registry = [r for r in db.execute(load_sql('new_signups_monthly'), COVERAGE) if not (r[1] == 'all' and r[2] == 0)]
    checks['signups_match_registry_on_source'] = signups == registry
    activation = db.execute(
        "SELECT signup_month, COUNT(*), SUM(COALESCE(first_engaged_date >= signup_date "
        "  AND first_engaged_date < date(signup_date, '+7 days'), 0)) FROM silver_user_profile "
        "WHERE signup_date || 'T00:00:00Z' >= :coverage_start "
        "  AND strftime('%Y-%m-%dT%H:%M:%SZ', signup_date, '+7 days') <= :coverage_end "
        "GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['activation_matches_registry_on_source'] = activation == [
        tuple(r[:3]) for r in db.execute(load_sql('activation_7d'), COVERAGE)]
    window = "strftime('%Y-%m-%dT%H:%M:%SZ', signup_at, '+30 days')"
    conversion = db.execute(
        f"SELECT signup_month, COUNT(*), "
        f"  SUM(COALESCE(first_subscription_at >= signup_at AND first_subscription_at < {window}, 0)), "
        f"  SUM(COALESCE(first_paid_at >= signup_at AND first_paid_at < {window}, 0)) "
        f"FROM silver_user_profile WHERE signup_at >= :coverage_start AND {window} <= :coverage_end "
        f"GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['conversion_matches_registry_on_source'] = conversion == [
        tuple(r[:4]) for r in db.execute(load_sql('conversion_30d'), COVERAGE)]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_user_profile GROUP BY 1').fetchall())
    return checks, {'source_rows': source_rows, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_user_day_activity

USER_DAY_ACTIVITY_SQL = """
CREATE TABLE silver_user_day_activity(
  user_id TEXT NOT NULL, activity_date TEXT NOT NULL, activity_month TEXT NOT NULL,
  sessions_touching INTEGER NOT NULL, sessions_started INTEGER NOT NULL, started_session_span_sec INTEGER NOT NULL,
  watch_seconds REAL NOT NULL, views_started INTEGER NOT NULL, free_quota_slots_used INTEGER NOT NULL,
  subscriber_at_day_start INTEGER NOT NULL CHECK(subscriber_at_day_start IN (0,1)),
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL, PRIMARY KEY(user_id, activity_date));
INSERT INTO silver_user_day_activity
WITH RECURSIVE session_days(user_id, day, last_day, started_day, span_sec) AS (
  SELECT resolved_user_id, date(session_started_at), date(last_activity_at), date(session_started_at), active_span_sec
  FROM silver_resolved_sessions WHERE resolved_user_id IS NOT NULL
  UNION ALL
  SELECT user_id, date(day, '+1 day'), last_day, started_day, span_sec FROM session_days WHERE day < last_day
),
segment_days(user_id, day, seg_start, seg_end, watched) AS (
  SELECT v.user_id, date(s.segment_started_at), s.segment_started_at, s.segment_ended_at, s.watch_duration_sec
  FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id
  UNION ALL
  SELECT user_id, date(day, '+1 day'), seg_start, seg_end, watched FROM segment_days
  WHERE date(day, '+1 day') < substr(seg_end, 1, 10)
     OR (date(day, '+1 day') = substr(seg_end, 1, 10) AND substr(seg_end, 12) <> '00:00:00Z')
),
session_agg AS (
  SELECT user_id, day, COUNT(*) AS touching, SUM(day = started_day) AS started,
         SUM(CASE WHEN day = started_day THEN span_sec ELSE 0 END) AS span
  FROM session_days GROUP BY user_id, day
),
watch_agg AS (
  SELECT user_id, day,
         SUM(watched * CASE WHEN julianday(seg_end) = julianday(seg_start) THEN 1.0
                            ELSE (MIN(julianday(seg_end), julianday(day, '+1 day')) - MAX(julianday(seg_start), julianday(day)))
                                 / (julianday(seg_end) - julianday(seg_start)) END) AS seconds
  FROM segment_days GROUP BY user_id, day
),
view_agg AS (SELECT user_id, date(view_started_at) AS day, COUNT(*) AS n FROM content_views GROUP BY 1, 2),
quota_agg AS (
  SELECT user_id, date AS day, COALESCE(MAX(free_quota_sequence), 0) AS slots, COUNT(*) AS consuming
  FROM content_views WHERE free_quota_consuming = 1 GROUP BY 1, 2
),
keys AS (SELECT user_id, day FROM session_agg UNION SELECT user_id, day FROM watch_agg UNION SELECT user_id, day FROM view_agg
         UNION SELECT user_id, day FROM quota_agg),
base AS (
  SELECT k.user_id, k.day, COALESCE(sa.touching, 0) AS touching, COALESCE(sa.started, 0) AS started,
         COALESCE(sa.span, 0) AS span, COALESCE(w.seconds, 0.0) AS seconds, COALESCE(va.n, 0) AS views,
         COALESCE(q.slots, 0) AS slots, COALESCE(q.slots <> q.consuming, 0) AS quota_gap,
         EXISTS (SELECT 1 FROM silver_subscription_access a
                 WHERE a.user_id = k.user_id AND a.grants_access = 1
                   AND a.effective_start_at <= k.day || 'T00:00:00Z'
                   AND (a.effective_end_at IS NULL OR a.effective_end_at > k.day || 'T00:00:00Z')) AS subscriber,
         u.user_id IS NULL AS unknown_user,
         k.day < substr(u.signup_at, 1, 10) AS before_signup
  FROM keys k
  LEFT JOIN session_agg sa ON sa.user_id = k.user_id AND sa.day = k.day
  LEFT JOIN watch_agg w ON w.user_id = k.user_id AND w.day = k.day
  LEFT JOIN view_agg va ON va.user_id = k.user_id AND va.day = k.day
  LEFT JOIN quota_agg q ON q.user_id = k.user_id AND q.day = k.day
  LEFT JOIN users u ON u.user_id = k.user_id
)
SELECT user_id, day, substr(day, 1, 7), touching, started, span, seconds, views, slots, subscriber,
       CASE WHEN unknown_user OR COALESCE(before_signup, 0) OR quota_gap THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN unknown_user THEN 'user_not_in_users,' ELSE '' END)
                    || (CASE WHEN COALESCE(before_signup, 0) THEN 'activity_before_signup,' ELSE '' END)
                    || (CASE WHEN quota_gap THEN 'free_quota_sequence_gap,' ELSE '' END), ','), ''),
       :build_id
FROM base;
CREATE INDEX ix_silver_user_day_activity_date ON silver_user_day_activity(activity_date, user_id)
"""


def independent_day_activity_recount(db):
    """Session-active user-days and total watch seconds, recomputed in Python from the source."""
    links = {}
    for session_id, user in db.execute('SELECT session_id, user_id FROM identity_links'):
        links.setdefault(session_id, set()).add(user)
    active = set()
    for session_id, user, started, last in db.execute(
            'SELECT session_id, user_id, session_started_at, last_activity_at FROM sessions'):
        if user is None:
            linked = links.get(session_id, set())
            user = next(iter(linked)) if len(linked) == 1 else None
        if user is None:
            continue
        day, end = dt.date.fromisoformat(started[:10]), dt.date.fromisoformat(last[:10])
        while day <= end:
            active.add((user, day.isoformat()))
            day += dt.timedelta(days=1)
    total_watch = db.execute('SELECT COALESCE(SUM(watch_duration_sec), 0) FROM playback_segments').fetchone()[0]
    return active, total_watch


def instant(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00'))


def independent_daily_watch(db):
    """Exact watch seconds per user and UTC day, splitting each segment by its wall-clock share."""
    watch = {}
    for user, started, ended, seconds in db.execute(
            'SELECT v.user_id, s.segment_started_at, s.segment_ended_at, s.watch_duration_sec '
            'FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id'):
        start, end = instant(started), instant(ended)
        if end == start:
            key = (user, start.date().isoformat())
            watch[key] = watch.get(key, Fraction(0)) + seconds
            continue
        total = Fraction(int((end - start).total_seconds()))
        day = start.date()
        while dt.datetime.combine(day, dt.time(), dt.timezone.utc) < end:
            lo = max(start, dt.datetime.combine(day, dt.time(), dt.timezone.utc))
            hi = min(end, dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), dt.timezone.utc))
            key = (user, day.isoformat())
            watch[key] = watch.get(key, Fraction(0)) + seconds * Fraction(int((hi - lo).total_seconds())) / total
            day += dt.timedelta(days=1)
    return watch


def reconcile_user_day_activity(db):
    checks = {}
    active, total_watch = independent_day_activity_recount(db)
    silver_active = set(db.execute('SELECT user_id, activity_date FROM silver_user_day_activity WHERE sessions_touching > 0'))
    checks['independent_active_day_recount'] = silver_active == active
    silver_watch = db.execute('SELECT COALESCE(SUM(watch_seconds), 0) FROM silver_user_day_activity').fetchone()[0]
    checks['watch_seconds_equal_segments'] = abs(silver_watch - total_watch) <= 1e-6 * max(1, total_watch)
    checks['sessions_started_equal_resolved'] = db.execute(
        'SELECT COALESCE(SUM(sessions_started), 0) FROM silver_user_day_activity').fetchone()[0] == db.execute(
        'SELECT COUNT(*) FROM silver_resolved_sessions WHERE resolved_user_id IS NOT NULL').fetchone()[0]
    checks['views_started_equal_source'] = db.execute(
        'SELECT COALESCE(SUM(views_started), 0) FROM silver_user_day_activity').fetchone()[0] == db.execute(
        'SELECT COUNT(*) FROM content_views').fetchone()[0]
    days = [p for p in db.execute(load_sql('periods_day'), COVERAGE)]
    daily_active = {}
    for user, day in active:
        daily_active[day] = daily_active.get(day, 0) + 1
    checks['dau_matches_independent_recount'] = [(d, daily_active.get(d, 0)) for d, _, _ in days] == [
        (d, db.execute('SELECT COUNT(*) FROM silver_user_day_activity WHERE activity_date = ? AND sessions_touching > 0',
                       (d,)).fetchone()[0]) for d, _, _ in days]
    exact = independent_daily_watch(db)
    silver_engaged = set(db.execute('SELECT user_id, activity_date FROM silver_user_day_activity WHERE watch_seconds >= 60'))
    exact_engaged = {k for k, v in exact.items() if v >= 60}
    boundary = {k for k, v in exact.items() if abs(v - 60) <= Fraction(1, 10**6)}
    checks['deu_matches_independent_exact_recount'] = (silver_engaged ^ exact_engaged) <= boundary
    for grain in ('week', 'month'):
        periods = db.execute(load_sql(f'periods_{grain}'), COVERAGE).fetchall()
        active_counts, engaged_counts = [], []
        for label, start, end in periods:
            lo, hi = start[:10], end[:10]
            active_counts.append((label, db.execute(
                'SELECT COUNT(DISTINCT user_id) FROM silver_user_day_activity '
                'WHERE activity_date >= ? AND activity_date < ? AND sessions_touching > 0', (lo, hi)).fetchone()[0]))
            engaged_counts.append((label, db.execute(
                'SELECT COUNT(*) FROM (SELECT user_id FROM silver_user_day_activity '
                'WHERE activity_date >= ? AND activity_date < ? GROUP BY user_id HAVING SUM(watch_seconds) >= 60)',
                (lo, hi)).fetchone()[0]))
        active_name = {'day': 'dau', 'week': 'wau', 'month': 'mau_from_family'}[grain]
        engaged_name = {'day': 'deu', 'week': 'weu', 'month': 'meu'}[grain]
        checks[f'{active_name}_matches_registry_on_source'] = active_counts == [
            tuple(r) for r in db.execute(load_sql(active_name), COVERAGE)]
        checks[f'{engaged_name}_matches_registry_on_source'] = engaged_counts == [
            tuple(r) for r in db.execute(load_sql(engaged_name), COVERAGE)]
    distribution = db.execute(
        "WITH m AS (SELECT activity_month, user_id, COUNT(*) AS days FROM silver_user_day_activity "
        "  WHERE sessions_touching > 0 AND activity_date >= substr(:coverage_start, 1, 10) "
        "    AND activity_date < substr(:coverage_end, 1, 10) GROUP BY 1, 2) "
        "SELECT activity_month, days, COUNT(*) FROM m GROUP BY 1, 2 ORDER BY 1, 2", COVERAGE).fetchall()
    checks['active_days_distribution_matches_registry_on_source'] = distribution == [
        tuple(r) for r in db.execute(load_sql('active_days_distribution_monthly'), COVERAGE)]
    quota = db.execute(
        "WITH m AS (SELECT substr(period_start, 1, 7) AS month FROM (" + load_sql('periods_month') + ")) "
        "SELECT m.month, COUNT(a.user_id), COALESCE(SUM(a.free_quota_slots_used = 8), 0) FROM m "
        "LEFT JOIN silver_user_day_activity a ON a.activity_month = m.month AND a.free_quota_slots_used > 0 "
        "GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['free_quota_hits_match_registry_on_source'] = quota == [
        tuple(r[:3]) for r in db.execute(load_sql('free_quota_hit_monthly'), COVERAGE)]
    rows = db.execute('SELECT COUNT(*) FROM silver_user_day_activity').fetchone()[0]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_user_day_activity GROUP BY 1').fetchall())
    watch_only = db.execute('SELECT COUNT(*) FROM silver_user_day_activity WHERE sessions_touching = 0').fetchone()[0]
    return checks, {'rows': rows, 'watch_or_view_only_days': watch_only, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_user_day_title_watch

VIEW_TYPES = ('free', 'sub', 'ppv')

USER_DAY_TITLE_WATCH_SQL = """
CREATE TABLE silver_user_day_title_watch(
  user_id TEXT NOT NULL, activity_date TEXT NOT NULL, activity_month TEXT NOT NULL, content_id TEXT NOT NULL,
  view_type TEXT NOT NULL, views_started INTEGER NOT NULL, episodes_started INTEGER NOT NULL,
  first_views_of_episode INTEGER NOT NULL, watch_seconds REAL NOT NULL,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL, PRIMARY KEY(user_id, activity_date, content_id, view_type));
INSERT INTO silver_user_day_title_watch
WITH RECURSIVE segment_days(user_id, content_id, view_type, day, seg_start, seg_end, watched) AS (
  SELECT v.user_id, v.content_id, v.view_type, date(s.segment_started_at), s.segment_started_at, s.segment_ended_at,
         s.watch_duration_sec
  FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id
  UNION ALL
  SELECT user_id, content_id, view_type, date(day, '+1 day'), seg_start, seg_end, watched FROM segment_days
  WHERE date(day, '+1 day') < substr(seg_end, 1, 10)
     OR (date(day, '+1 day') = substr(seg_end, 1, 10) AND substr(seg_end, 12) <> '00:00:00Z')
),
watch_agg AS (
  SELECT user_id, day, content_id, view_type,
         SUM(watched * CASE WHEN julianday(seg_end) = julianday(seg_start) THEN 1.0
                            ELSE (MIN(julianday(seg_end), julianday(day, '+1 day')) - MAX(julianday(seg_start), julianday(day)))
                                 / (julianday(seg_end) - julianday(seg_start)) END) AS seconds
  FROM segment_days GROUP BY user_id, day, content_id, view_type
),
view_agg AS (
  SELECT user_id, date(view_started_at) AS day, content_id, view_type, COUNT(*) AS views,
         COUNT(DISTINCT episode_number) AS episodes, SUM(is_first_view_of_episode = 1) AS first_views
  FROM content_views GROUP BY 1, 2, 3, 4
),
keys AS (SELECT user_id, day, content_id, view_type FROM watch_agg
         UNION SELECT user_id, day, content_id, view_type FROM view_agg),
base AS (
  SELECT k.*, COALESCE(va.views, 0) AS views, COALESCE(va.episodes, 0) AS episodes,
         COALESCE(va.first_views, 0) AS first_views, COALESCE(w.seconds, 0.0) AS seconds,
         u.user_id IS NULL AS unknown_user, k.view_type NOT IN VIEW_TYPES AS bad_type
  FROM keys k
  LEFT JOIN watch_agg w ON w.user_id = k.user_id AND w.day = k.day AND w.content_id = k.content_id AND w.view_type = k.view_type
  LEFT JOIN view_agg va ON va.user_id = k.user_id AND va.day = k.day AND va.content_id = k.content_id AND va.view_type = k.view_type
  LEFT JOIN users u ON u.user_id = k.user_id
)
SELECT user_id, day, substr(day, 1, 7), content_id, view_type, views, episodes, first_views, seconds,
       CASE WHEN unknown_user OR bad_type THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN unknown_user THEN 'user_not_in_users,' ELSE '' END)
                    || (CASE WHEN bad_type THEN 'unrecognised_view_type,' ELSE '' END), ','), ''),
       :build_id
FROM base;
CREATE INDEX ix_silver_user_day_title_watch_date_title ON silver_user_day_title_watch(activity_date, content_id)
""".replace('VIEW_TYPES', "(" + ",".join(f"'{v}'" for v in VIEW_TYPES) + ")", 1)


def reconcile_user_day_title_watch(db):
    checks = {}
    title_days = {}
    for user, day, seconds, views in db.execute(
            'SELECT user_id, activity_date, SUM(watch_seconds), SUM(views_started) FROM silver_user_day_title_watch GROUP BY 1, 2'):
        title_days[(user, day)] = (seconds, views)
    activity_days = {(user, day): (seconds, views) for user, day, seconds, views in db.execute(
        'SELECT user_id, activity_date, watch_seconds, views_started FROM silver_user_day_activity '
        'WHERE watch_seconds > 0 OR views_started > 0')}
    checks['watch_seconds_equal_day_activity'] = title_days.keys() == activity_days.keys() and all(
        abs(title_days[k][0] - activity_days[k][0]) <= 1e-6 for k in title_days)
    checks['views_equal_day_activity'] = title_days.keys() == activity_days.keys() and all(
        title_days[k][1] == activity_days[k][1] for k in title_days)
    checks['views_started_equal_source'] = db.execute(
        'SELECT COALESCE(SUM(views_started), 0) FROM silver_user_day_title_watch').fetchone()[0] == db.execute(
        'SELECT COUNT(*) FROM content_views').fetchone()[0]
    window = ("activity_date >= substr(:coverage_start, 1, 10) AND activity_date < substr(:coverage_end, 1, 10)")
    reach = db.execute(
        f"SELECT activity_month, content_id, COUNT(DISTINCT user_id) FROM silver_user_day_title_watch "
        f"WHERE views_started > 0 AND {window} GROUP BY 1, 2 ORDER BY 1, 2", COVERAGE).fetchall()
    checks['title_reach_matches_registry_on_source'] = reach == [
        tuple(r) for r in db.execute(load_sql('title_reach_monthly'), COVERAGE)]
    views = db.execute(
        f"WITH m AS (SELECT substr(period_start, 1, 7) AS month FROM ({load_sql('periods_month')})) "
        f"SELECT m.month, COALESCE(SUM(t.views_started), 0), COUNT(DISTINCT CASE WHEN t.views_started > 0 THEN t.user_id END) "
        f"FROM m LEFT JOIN silver_user_day_title_watch t ON t.activity_month = m.month GROUP BY 1 ORDER BY 1",
        COVERAGE).fetchall()
    checks['views_per_viewer_matches_registry_on_source'] = views == [
        tuple(r[:3]) for r in db.execute(load_sql('views_per_viewer_monthly'), COVERAGE)]
    watch = dict(db.execute(
        f"SELECT activity_month, SUM(watch_seconds) FROM silver_user_day_title_watch WHERE {window} GROUP BY 1",
        COVERAGE).fetchall())
    registry_watch = [(r[0], r[1]) for r in db.execute(load_sql('watch_time_monthly'), COVERAGE)]
    checks['watch_time_matches_registry_on_source'] = all(
        abs(watch.get(month, 0) - seconds) <= 1e-6 * max(1, seconds) for month, seconds in registry_watch)
    rows = db.execute('SELECT COUNT(*) FROM silver_user_day_title_watch').fetchone()[0]
    by_type = dict(db.execute('SELECT view_type, COUNT(*) FROM silver_user_day_title_watch GROUP BY 1').fetchall())
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_user_day_title_watch GROUP BY 1').fetchall())
    return checks, {'rows': rows, 'by_view_type': by_type, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_user_episodes

USER_EPISODES_SQL = """
CREATE TABLE silver_user_episodes(
  user_id TEXT NOT NULL, content_id TEXT NOT NULL, episode_number INTEGER NOT NULL,
  first_start_at TEXT NOT NULL, first_start_month TEXT NOT NULL, window_end_at TEXT NOT NULL,
  window_complete INTEGER NOT NULL CHECK(window_complete IN (0,1)), first_view_type TEXT NOT NULL,
  views_in_window INTEGER NOT NULL, covered_sec INTEGER NOT NULL, episode_duration_sec INTEGER,
  has_next_episode INTEGER NOT NULL CHECK(has_next_episode IN (0,1)),
  started_next_episode_in_window INTEGER NOT NULL CHECK(started_next_episode_in_window IN (0,1)),
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL, PRIMARY KEY(user_id, content_id, episode_number));
INSERT INTO silver_user_episodes
WITH firsts AS (
  SELECT user_id, content_id, episode_number, view_started_at AS first_start_at, view_type AS first_view_type,
         strftime('%Y-%m-%dT%H:%M:%SZ', view_started_at, '+7 days') AS window_end_at
  FROM (SELECT user_id, content_id, episode_number, view_started_at, view_type,
               ROW_NUMBER() OVER (PARTITION BY user_id, content_id, episode_number ORDER BY view_started_at, view_id) AS n
        FROM content_views)
  WHERE n = 1
),
window_views AS (
  SELECT f.user_id, f.content_id, f.episode_number, v.view_id
  FROM firsts f
  JOIN content_views v ON v.user_id = f.user_id AND v.content_id = f.content_id
                      AND v.episode_number = f.episode_number AND v.view_started_at < f.window_end_at
),
view_counts AS (SELECT user_id, content_id, episode_number, COUNT(*) AS n FROM window_views GROUP BY 1, 2, 3),
segments AS (
  SELECT w.user_id, w.content_id, w.episode_number, s.position_start_sec AS a, s.position_end_sec AS b
  FROM window_views w JOIN playback_segments s ON s.view_id = w.view_id
  WHERE s.position_end_sec > s.position_start_sec
),
ordered AS (
  SELECT *, MAX(b) OVER (PARTITION BY user_id, content_id, episode_number ORDER BY a, b
                         ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS prior_end
  FROM segments
),
islands AS (
  SELECT *, SUM(CASE WHEN prior_end IS NULL OR a > prior_end THEN 1 ELSE 0 END)
              OVER (PARTITION BY user_id, content_id, episode_number ORDER BY a, b ROWS UNBOUNDED PRECEDING) AS island
  FROM ordered
),
coverage AS (
  SELECT user_id, content_id, episode_number, SUM(island_sec) AS covered_sec
  FROM (SELECT user_id, content_id, episode_number, MAX(b) - MIN(a) AS island_sec
        FROM islands GROUP BY user_id, content_id, episode_number, island)
  GROUP BY user_id, content_id, episode_number
),
next_starts AS (
  SELECT f.user_id, f.content_id, f.episode_number, 1 AS started
  FROM firsts f
  JOIN content_views n ON n.user_id = f.user_id AND n.content_id = f.content_id
                      AND n.episode_number = f.episode_number + 1
                      AND n.view_started_at >= f.first_start_at AND n.view_started_at < f.window_end_at
  GROUP BY 1, 2, 3
),
base AS (
  SELECT f.*, COALESCE(vc.n, 0) AS views, COALESCE(c.covered_sec, 0) AS covered, d.episode_duration_sec AS duration,
         nx.episode_number IS NOT NULL AS has_next, COALESCE(ns.started, 0) AS started_next,
         d.content_id IS NULL AS missing_episode, u.user_id IS NULL AS unknown_user
  FROM firsts f
  LEFT JOIN view_counts vc ON vc.user_id = f.user_id AND vc.content_id = f.content_id AND vc.episode_number = f.episode_number
  LEFT JOIN coverage c ON c.user_id = f.user_id AND c.content_id = f.content_id AND c.episode_number = f.episode_number
  LEFT JOIN content_episodes d ON d.content_id = f.content_id AND d.episode_number = f.episode_number
  LEFT JOIN content_episodes nx ON nx.content_id = f.content_id AND nx.episode_number = f.episode_number + 1
  LEFT JOIN next_starts ns ON ns.user_id = f.user_id AND ns.content_id = f.content_id AND ns.episode_number = f.episode_number
  LEFT JOIN users u ON u.user_id = f.user_id
)
SELECT user_id, content_id, episode_number, first_start_at, substr(first_start_at, 1, 7), window_end_at,
       window_end_at <= :coverage_end, first_view_type, views, covered, duration, has_next, started_next,
       CASE WHEN unknown_user OR missing_episode OR covered > COALESCE(duration, covered) THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN unknown_user THEN 'user_not_in_users,' ELSE '' END)
                    || (CASE WHEN missing_episode THEN 'episode_not_in_catalog,' ELSE '' END)
                    || (CASE WHEN covered > COALESCE(duration, covered) THEN 'coverage_exceeds_duration,' ELSE '' END), ','), ''),
       :build_id
FROM base;
CREATE INDEX ix_silver_user_episodes_start ON silver_user_episodes(first_start_at)
"""


def independent_coverage_recount(db):
    """Unique covered seconds per user-episode inside its 7-day window, merged as intervals in Python."""
    first = {}
    for user, content, episode, started in db.execute(
            'SELECT user_id, content_id, episode_number, MIN(view_started_at) FROM content_views GROUP BY 1, 2, 3'):
        first[(user, content, episode)] = instant(started) + dt.timedelta(days=7)
    intervals = {}
    for user, content, episode, started, a, b in db.execute(
            'SELECT v.user_id, v.content_id, v.episode_number, v.view_started_at, s.position_start_sec, s.position_end_sec '
            'FROM playback_segments s JOIN content_views v ON v.view_id = s.view_id'):
        key = (user, content, episode)
        if b > a and instant(started) < first[key]:
            intervals.setdefault(key, []).append((a, b))
    covered = {key: 0 for key in first}
    for key, spans in intervals.items():
        total, end = 0, None
        for a, b in sorted(spans):
            if end is None or a > end:
                total += b - a
                end = b
            elif b > end:
                total += b - end
                end = b
        covered[key] = total
    return covered


def reconcile_user_episodes(db):
    checks = {}
    source = db.execute('SELECT COUNT(*) FROM (SELECT DISTINCT user_id, content_id, episode_number FROM content_views)').fetchone()[0]
    checks['row_count_equals_source_user_episodes'] = db.execute('SELECT COUNT(*) FROM silver_user_episodes').fetchone()[0] == source
    checks['independent_coverage_recount'] = independent_coverage_recount(db) == {
        (u, c, e): s for u, c, e, s in db.execute(
            'SELECT user_id, content_id, episode_number, covered_sec FROM silver_user_episodes')}
    window = "first_start_at >= :coverage_start AND first_start_at < :coverage_end AND window_complete = 1"
    completion = db.execute(
        "WITH m AS (SELECT substr(period_start, 1, 7) AS month FROM (" + load_sql('periods_month') + ")) "
        "SELECT m.month, COUNT(e.user_id), COALESCE(SUM(e.covered_sec >= 0.9 * e.episode_duration_sec), 0) FROM m "
        "LEFT JOIN silver_user_episodes e ON e.first_start_month = m.month AND e.episode_duration_sec IS NOT NULL AND "
        + window.replace('first_start_at', 'e.first_start_at').replace('window_complete', 'e.window_complete') +
        " GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['completion_matches_registry_on_source'] = completion == [
        tuple(r[:3]) for r in db.execute(load_sql('episode_completion_monthly'), COVERAGE)]
    continuation = db.execute(
        "WITH m AS (SELECT substr(period_start, 1, 7) AS month FROM (" + load_sql('periods_month') + ")) "
        "SELECT m.month, COUNT(e.user_id), COALESCE(SUM(e.started_next_episode_in_window), 0) FROM m "
        "LEFT JOIN silver_user_episodes e ON e.first_start_month = m.month AND e.has_next_episode = 1 "
        "  AND e.covered_sec >= 0.9 * e.episode_duration_sec AND "
        + window.replace('first_start_at', 'e.first_start_at').replace('window_complete', 'e.window_complete') +
        " GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['continuation_matches_registry_on_source'] = continuation == [
        tuple(r[:3]) for r in db.execute(load_sql('series_continuation_monthly'), COVERAGE)]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_user_episodes GROUP BY 1').fetchall())
    reasons = dict(db.execute('SELECT exception_reason, COUNT(*) FROM silver_user_episodes '
                              'WHERE exception_reason IS NOT NULL GROUP BY 1').fetchall())
    return checks, {'rows': source, 'exceptions': exceptions, 'reasons': reasons}

# ---------------------------------------------------------------- silver_paywall_funnel

PAYWALL_PRODUCTS = ('subscription', 'ppv')

PAYWALL_FUNNEL_SQL = """
CREATE TABLE silver_paywall_funnel(
  paywall_event_id TEXT PRIMARY KEY, event_at TEXT NOT NULL, event_month TEXT NOT NULL, session_id TEXT, user_id TEXT,
  product TEXT, content_id TEXT, episode_number INTEGER,
  checkouts_started INTEGER NOT NULL, first_checkout_event_id TEXT, first_checkout_at TEXT,
  purchase_txn_id TEXT, purchased_at TEXT, purchase_revenue_cents INTEGER,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL);
INSERT INTO silver_paywall_funnel
WITH paywalls AS (
  SELECT e.event_id, e.event_at, e.session_id, COALESCE(e.user_id, r.resolved_user_id) AS user_id,
         json_extract(e.event_properties_json, '$.product') AS product, e.content_id, e.episode_number
  FROM user_events e LEFT JOIN silver_resolved_sessions r ON r.session_id = e.session_id
  WHERE e.event_name = 'paywall_viewed'
),
checkouts AS (
  SELECT event_id, event_at, triggering_paywall_event_id AS paywall_id,
         ROW_NUMBER() OVER (PARTITION BY triggering_paywall_event_id ORDER BY event_at, event_id) AS n
  FROM user_events WHERE event_name = 'checkout_started' AND triggering_paywall_event_id IS NOT NULL
),
purchases AS (
  SELECT c.paywall_id, a.txn_id, a.succeeded_at, a.revenue_cents,
         ROW_NUMBER() OVER (PARTITION BY c.paywall_id ORDER BY a.succeeded_at, a.txn_id) AS n
  FROM checkouts c
  JOIN transactions t ON t.checkout_event_id = c.event_id
  JOIN silver_payment_attempts a ON a.txn_id = t.txn_id AND a.revenue_cents > 0
),
base AS (
  SELECT p.*, (SELECT COUNT(*) FROM checkouts c WHERE c.paywall_id = p.event_id) AS checkout_count,
         fc.event_id AS checkout_id, fc.event_at AS checkout_at,
         pu.txn_id, pu.succeeded_at, pu.revenue_cents,
         p.user_id IS NULL AS unidentified, COALESCE(p.product NOT IN PAYWALL_PRODUCTS, 1) AS bad_product,
         COALESCE(fc.event_at < p.event_at, 0) AS checkout_first
  FROM paywalls p
  LEFT JOIN checkouts fc ON fc.paywall_id = p.event_id AND fc.n = 1
  LEFT JOIN purchases pu ON pu.paywall_id = p.event_id AND pu.n = 1
)
SELECT event_id, event_at, substr(event_at, 1, 7), session_id, user_id, product, content_id, episode_number,
       checkout_count, checkout_id, checkout_at, txn_id, succeeded_at, revenue_cents,
       CASE WHEN unidentified OR bad_product OR checkout_first THEN 'suspicious_usable' ELSE 'ok' END,
       NULLIF(rtrim((CASE WHEN unidentified THEN 'unidentified_viewer,' ELSE '' END)
                    || (CASE WHEN bad_product THEN 'unrecognised_product,' ELSE '' END)
                    || (CASE WHEN checkout_first THEN 'checkout_before_paywall,' ELSE '' END), ','), ''),
       :build_id
FROM base;
CREATE INDEX ix_silver_paywall_funnel_time ON silver_paywall_funnel(event_at);
CREATE INDEX ix_silver_paywall_funnel_user_time ON silver_paywall_funnel(user_id, event_at)
""".replace('PAYWALL_PRODUCTS', "(" + ",".join(f"'{v}'" for v in PAYWALL_PRODUCTS) + ")", 1)


def independent_paywall_recount(db):
    """Checkouts and first valid purchase per paywall, recomputed in Python from the source."""
    successes = {}
    for txn_id, effective_at in db.execute("SELECT txn_id, effective_at FROM payment_status_history WHERE status='succeeded'"):
        successes.setdefault(txn_id, []).append(effective_at)
    charges = {}
    for txn_id, kind, amount, checkout in db.execute(
            'SELECT txn_id, type, amount_usd, checkout_event_id FROM transactions WHERE checkout_event_id IS NOT NULL'):
        times = successes.get(txn_id, [])
        cents = exact_cents(amount)
        if kind != 'refund' and len(times) == 1 and cents is not None and cents > 0:
            charges.setdefault(checkout, []).append((times[0], txn_id))
    counts, purchase = {}, {}
    for event_id, paywall in db.execute(
            "SELECT event_id, triggering_paywall_event_id FROM user_events "
            "WHERE event_name='checkout_started' AND triggering_paywall_event_id IS NOT NULL"):
        counts[paywall] = counts.get(paywall, 0) + 1
        for found in charges.get(event_id, []):
            if paywall not in purchase or found < purchase[paywall]:
                purchase[paywall] = found
    return counts, {k: v[1] for k, v in purchase.items()}


def reconcile_paywall_funnel(db):
    checks = {}
    source = db.execute("SELECT COUNT(*) FROM user_events WHERE event_name='paywall_viewed'").fetchone()[0]
    checks['row_count_equals_source_paywalls'] = db.execute('SELECT COUNT(*) FROM silver_paywall_funnel').fetchone()[0] == source
    counts, purchases = independent_paywall_recount(db)
    silver = {k: (c, t) for k, c, t in db.execute(
        'SELECT paywall_event_id, checkouts_started, purchase_txn_id FROM silver_paywall_funnel')}
    checks['independent_checkout_recount'] = all(silver[k][0] == counts.get(k, 0) for k in silver) and set(counts) <= set(silver)
    checks['independent_purchase_recount'] = {k: t for k, (_, t) in silver.items() if t is not None} == purchases
    window = "event_at >= :coverage_start AND event_at < :coverage_end"
    funnel = db.execute(
        f"SELECT event_month, product, COUNT(*), SUM(checkouts_started > 0), SUM(purchase_txn_id IS NOT NULL) "
        f"FROM silver_paywall_funnel WHERE {window} GROUP BY 1, 2 ORDER BY 1, 2", COVERAGE).fetchall()
    checks['funnel_matches_registry_on_source'] = funnel == [
        tuple(r[:5]) for r in db.execute(load_sql('paywall_funnel_monthly'), COVERAGE)]
    exposure = db.execute(
        "WITH m AS (SELECT substr(period_start, 1, 7) AS month FROM (" + load_sql('periods_month') + ")) "
        "SELECT m.month, COUNT(DISTINCT f.user_id) FROM m LEFT JOIN silver_paywall_funnel f ON f.event_month = m.month "
        "GROUP BY 1 ORDER BY 1", COVERAGE).fetchall()
    checks['exposure_matches_registry_on_source'] = exposure == [
        tuple(r[:2]) for r in db.execute(load_sql('paywall_exposure_monthly'), COVERAGE)]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_paywall_funnel GROUP BY 1').fetchall())
    return checks, {'rows': source, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_marketing_daily

MARKETING_DAILY_SQL = """
CREATE TABLE silver_marketing_daily(
  date TEXT NOT NULL, month TEXT NOT NULL, channel TEXT NOT NULL, has_spend_row INTEGER NOT NULL CHECK(has_spend_row IN (0,1)),
  spend_cents INTEGER, impressions INTEGER, clicks INTEGER, signups INTEGER NOT NULL, new_paying_users INTEGER NOT NULL,
  loaded_at TEXT,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('ok','excluded','suspicious_usable')), exception_reason TEXT,
  build_id TEXT NOT NULL, PRIMARY KEY(date, channel));
INSERT INTO silver_marketing_daily
WITH spend AS (
  SELECT date, channel, spend_usd, impressions, clicks, loaded_at,
         CASE WHEN typeof(spend_usd) IN ('integer', 'real') AND spend_usd >= 0
                   AND abs(spend_usd * 100 - ROUND(spend_usd * 100)) < 0.000001
              THEN CAST(ROUND(spend_usd * 100) AS INTEGER) END AS cents
  FROM marketing_spend
),
signups AS (
  SELECT signup_date AS date, acquisition_source AS channel, COUNT(*) AS n
  FROM silver_user_profile WHERE signup_date IS NOT NULL GROUP BY 1, 2
),
payers AS (
  SELECT substr(first_paid_at, 1, 10) AS date, acquisition_source AS channel, COUNT(*) AS n
  FROM silver_user_profile WHERE first_paid_at IS NOT NULL GROUP BY 1, 2
),
keys AS (SELECT date, channel FROM spend UNION SELECT date, channel FROM signups UNION SELECT date, channel FROM payers)
SELECT k.date, substr(k.date, 1, 7), k.channel, s.date IS NOT NULL, s.cents, s.impressions, s.clicks,
       COALESCE(g.n, 0), COALESCE(p.n, 0), s.loaded_at,
       CASE WHEN s.date IS NOT NULL AND s.cents IS NULL THEN 'excluded'
            WHEN s.clicks > s.impressions OR s.clicks < 0 OR s.impressions < 0 THEN 'suspicious_usable'
            ELSE 'ok' END,
       CASE WHEN s.date IS NOT NULL AND s.cents IS NULL THEN 'invalid_spend'
            WHEN s.clicks < 0 OR s.impressions < 0 THEN 'negative_count'
            WHEN s.clicks > s.impressions THEN 'clicks_exceed_impressions' END,
       :build_id
FROM keys k
LEFT JOIN spend s ON s.date = k.date AND s.channel = k.channel
LEFT JOIN signups g ON g.date = k.date AND g.channel = k.channel
LEFT JOIN payers p ON p.date = k.date AND p.channel = k.channel;
CREATE INDEX ix_silver_marketing_daily_channel_date ON silver_marketing_daily(channel, date)
"""


def reconcile_marketing_daily(db):
    checks = {}
    source = db.execute('SELECT spend_usd FROM marketing_spend').fetchall()
    source_cents = [exact_cents(r[0]) for r in source]
    checks['spend_rows_equal_source'] = db.execute(
        'SELECT COUNT(*) FROM silver_marketing_daily WHERE has_spend_row = 1').fetchone()[0] == len(source)
    checks['independent_decimal_spend_recount'] = db.execute(
        'SELECT COALESCE(SUM(spend_cents), 0) FROM silver_marketing_daily').fetchone()[0] == sum(
        c for c in source_cents if c is not None and c >= 0)
    checks['signups_equal_profile'] = db.execute('SELECT SUM(signups) FROM silver_marketing_daily').fetchone()[0] == db.execute(
        'SELECT COUNT(*) FROM silver_user_profile WHERE signup_date IS NOT NULL').fetchone()[0]
    checks['new_payers_equal_profile'] = db.execute(
        'SELECT SUM(new_paying_users) FROM silver_marketing_daily').fetchone()[0] == db.execute(
        'SELECT COUNT(*) FROM silver_user_profile WHERE first_paid_at IS NOT NULL').fetchone()[0]
    window = "date >= substr(:coverage_start, 1, 10) AND date < substr(:coverage_end, 1, 10) AND has_spend_row = 1"
    ctr = db.execute(
        f"SELECT month, channel, SUM(clicks), SUM(impressions) FROM silver_marketing_daily WHERE {window} GROUP BY 1, 2 "
        f"UNION ALL SELECT month, 'all', SUM(clicks), SUM(impressions) FROM silver_marketing_daily WHERE {window} GROUP BY 1 "
        f"ORDER BY 1, 2", COVERAGE).fetchall()
    checks['ctr_matches_registry_on_source'] = ctr == [tuple(r[:4]) for r in db.execute(load_sql('marketing_ctr_monthly'), COVERAGE)]
    efficiency = db.execute(
        f"SELECT m.month, m.channel, CASE WHEN SUM(m.exception_status = 'excluded') = 0 THEN SUM(m.spend_cents) END, SUM(m.clicks), "
        f"  (SELECT COALESCE(SUM(x.signups), 0) FROM silver_marketing_daily x WHERE x.month = m.month AND x.channel = m.channel), "
        f"  (SELECT COALESCE(SUM(x.new_paying_users), 0) FROM silver_marketing_daily x WHERE x.month = m.month AND x.channel = m.channel) "
        f"FROM silver_marketing_daily m WHERE {window.replace('date', 'm.date').replace('has_spend_row', 'm.has_spend_row')} "
        f"GROUP BY 1, 2 ORDER BY 1, 2", COVERAGE).fetchall()
    registry = [tuple(r[:6]) for r in db.execute(load_sql('marketing_efficiency_monthly'), COVERAGE)]
    # Where a channel-month has invalid spend, the registry rounds it and Silver excludes it: compare the rest only.
    checks['efficiency_matches_registry_on_source'] = len(efficiency) == len(registry) and all(
        s[:2] == r[:2] and s[3:] == r[3:] and (s[2] is None or s[2] == r[2]) for s, r in zip(efficiency, registry))
    rows = db.execute('SELECT COUNT(*) FROM silver_marketing_daily').fetchone()[0]
    exceptions = dict(db.execute('SELECT exception_status, COUNT(*) FROM silver_marketing_daily GROUP BY 1').fetchall())
    channels = dict(db.execute('SELECT channel, COUNT(*) FROM silver_marketing_daily GROUP BY 1').fetchall())
    return checks, {'rows': rows, 'channels': channels, 'exceptions': exceptions}

# ---------------------------------------------------------------- silver_quality_exceptions

# Silver tables with exception_status/exception_reason, and the expression that renders each row's key as text.
EXCEPTION_SOURCES = [
    ('silver_payment_attempts', 'txn_id'),
    ('silver_subscription_access', 'subscription_period_id'),
    ('silver_user_profile', 'user_id'),
    ('silver_user_day_activity', "user_id || '|' || activity_date"),
    ('silver_user_day_title_watch', "user_id || '|' || activity_date || '|' || content_id || '|' || view_type"),
    ('silver_user_episodes', "user_id || '|' || content_id || '|' || episode_number"),
    ('silver_paywall_funnel', 'paywall_event_id'),
    ('silver_marketing_daily', "date || '|' || channel"),
]

# Session-resolution problems: ambiguous links and a link naming a different user. Anonymous sessions are not faults.
# Payments whose raw source amount was corrected on review: usable at the curated amount, with the review time unknown.
SESSION_EXCEPTIONS_SQL = """
SELECT 'silver_resolved_sessions', session_id, 'suspicious_usable', 'ambiguous_identity_link,'
FROM silver_resolved_sessions WHERE resolution_method = 'unresolved_ambiguous'
UNION ALL
SELECT 'silver_resolved_sessions', session_id, 'suspicious_usable', 'link_user_mismatch,'
FROM silver_resolved_sessions WHERE link_user_mismatch = 1
UNION ALL
SELECT 'silver_payment_attempts', txn_id, 'suspicious_usable', 'source_amount_corrected_on_review,'
FROM payment_quality_review"""

QUALITY_EXCEPTIONS_SQL = """
CREATE TABLE silver_quality_exceptions(
  table_name TEXT NOT NULL, row_key TEXT NOT NULL,
  exception_status TEXT NOT NULL CHECK(exception_status IN ('excluded','suspicious_usable')),
  exception_reason TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(table_name, row_key, exception_reason));
INSERT INTO silver_quality_exceptions
WITH RECURSIVE flagged(table_name, row_key, status, rest) AS (
""" + "\nUNION ALL\n".join(
    f"SELECT '{table}', {key}, exception_status, COALESCE(exception_reason, 'unspecified') || ',' "
    f"FROM {table} WHERE exception_status <> 'ok'" for table, key in EXCEPTION_SOURCES) + """
UNION ALL""" + SESSION_EXCEPTIONS_SQL + """
),
split(table_name, row_key, status, reason, rest) AS (
  SELECT table_name, row_key, status, substr(rest, 1, instr(rest, ',') - 1), substr(rest, instr(rest, ',') + 1) FROM flagged
  UNION ALL
  SELECT table_name, row_key, status, substr(rest, 1, instr(rest, ',') - 1), substr(rest, instr(rest, ',') + 1)
  FROM split WHERE rest <> ''
)
SELECT DISTINCT table_name, row_key, status, reason, :build_id FROM split;
CREATE INDEX ix_silver_quality_exceptions_reason ON silver_quality_exceptions(exception_reason, table_name)
"""


def reconcile_quality_exceptions(db):
    checks = {}
    expected = {}
    for table, _ in EXCEPTION_SOURCES:
        for status, reason, n in db.execute(
                f"SELECT exception_status, exception_reason, COUNT(*) FROM {table} WHERE exception_status <> 'ok' GROUP BY 1, 2"):
            for part in (reason or 'unspecified').split(','):
                expected[(table, status, part)] = expected.get((table, status, part), 0) + n
    session_rules = (('ambiguous_identity_link', "resolution_method = 'unresolved_ambiguous'"),
                     ('link_user_mismatch', 'link_user_mismatch = 1'))
    for reason, sql in session_rules:
        n = db.execute(f'SELECT COUNT(*) FROM silver_resolved_sessions WHERE {sql}').fetchone()[0]
        if n:
            expected[('silver_resolved_sessions', 'suspicious_usable', reason)] = n
    reviewed = db.execute('SELECT COUNT(*) FROM payment_quality_review').fetchone()[0]
    if reviewed:
        key = ('silver_payment_attempts', 'suspicious_usable', 'source_amount_corrected_on_review')
        expected[key] = expected.get(key, 0) + reviewed
    actual = {(t, s, r): n for t, s, r, n in db.execute(
        'SELECT table_name, exception_status, exception_reason, COUNT(*) FROM silver_quality_exceptions GROUP BY 1, 2, 3')}
    checks['counts_equal_each_table'] = actual == expected
    flagged = set()
    for table, key in EXCEPTION_SOURCES:
        flagged |= {(table, k) for (k,) in db.execute(f"SELECT {key} FROM {table} WHERE exception_status <> 'ok'")}
    for _, sql in session_rules:
        flagged |= {('silver_resolved_sessions', k) for (k,) in db.execute(
            f'SELECT session_id FROM silver_resolved_sessions WHERE {sql}')}
    flagged |= {('silver_payment_attempts', k) for (k,) in db.execute('SELECT txn_id FROM payment_quality_review')}
    checks['every_flagged_row_listed'] = flagged == set(db.execute(
        'SELECT DISTINCT table_name, row_key FROM silver_quality_exceptions'))
    summary = {f'{t}.{r}': n for (t, s, r), n in sorted(actual.items())}
    return checks, {'rows': sum(actual.values()), 'by_table_reason': summary}

# ================================================================ Gold
# Gold tables read Silver only, cover complete UTC months inside the coverage window,
# store counts alongside every rate, and record the definition versions they used.

GOLD_MONTHS_CTE = """months(month, period_start, period_end, days) AS (
  SELECT substr(period_start, 1, 7), period_start, period_end,
         CAST(julianday(period_end) - julianday(period_start) AS INTEGER)
  FROM (WITH RECURSIVE p(period_start) AS (
          SELECT :coverage_start UNION ALL
          SELECT strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') FROM p
          WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') < :coverage_end)
        SELECT period_start, strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') AS period_end FROM p
        WHERE strftime('%Y-%m-%dT%H:%M:%SZ', period_start, '+1 month') <= :coverage_end)
)"""

# ---------------------------------------------------------------- gold_kpi_monthly

KPI_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in (
    'mau', 'activity_family', 'stickiness_and_engagement_rate', 'revenue_group',
    'funnel_and_lifecycle_group', 'supporting_metrics')}, sort_keys=True)

KPI_MONTHLY_SQL = """
CREATE TABLE gold_kpi_monthly(
  month TEXT PRIMARY KEY, period_start TEXT NOT NULL, period_end TEXT NOT NULL, days INTEGER NOT NULL,
  mau INTEGER NOT NULL, unidentified_sessions INTEGER NOT NULL,
  dau_day_sum INTEGER NOT NULL, average_dau REAL NOT NULL, stickiness REAL,
  meu INTEGER NOT NULL, engagement_rate REAL, deu_day_sum INTEGER NOT NULL, average_deu REAL NOT NULL, engaged_stickiness REAL,
  signups INTEGER NOT NULL, unknown_source_signups INTEGER NOT NULL,
  gross_charges_cents INTEGER NOT NULL, refunds_cents INTEGER NOT NULL, net_revenue_cents INTEGER NOT NULL,
  paying_users INTEGER NOT NULL, subscription_payers INTEGER NOT NULL, ppv_payers INTEGER NOT NULL,
  arpu_usd REAL, arppu_usd REAL,
  subscribers_at_start INTEGER NOT NULL, subscribers_at_end INTEGER NOT NULL, net_adds INTEGER NOT NULL,
  churned_subscribers INTEGER NOT NULL, churn_rate REAL, mrr_cents INTEGER NOT NULL,
  cancellation_requests INTEGER NOT NULL, cancellation_request_rate REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL);
INSERT INTO gold_kpi_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
active AS (
  SELECT activity_month AS month, COUNT(DISTINCT user_id) AS mau FROM silver_user_day_activity
  WHERE sessions_touching > 0 GROUP BY 1
),
daily AS (
  SELECT activity_month AS month, SUM(sessions_touching > 0) AS dau_sum, SUM(watch_seconds >= 60) AS deu_sum
  FROM silver_user_day_activity GROUP BY 1
),
engaged AS (
  SELECT month, COUNT(*) AS meu FROM (
    SELECT activity_month AS month, user_id FROM silver_user_day_activity
    GROUP BY 1, 2 HAVING SUM(watch_seconds) >= 60)
  GROUP BY month
),
unidentified AS (
  SELECT m.month, COUNT(r.session_id) AS n FROM months m
  JOIN silver_resolved_sessions r ON r.resolved_user_id IS NULL
   AND r.session_started_at < m.period_end AND r.last_activity_at >= m.period_start
  GROUP BY m.month
),
signups AS (
  SELECT m.month, COUNT(p.user_id) AS n, COALESCE(SUM(p.acquisition_source = 'unknown'), 0) AS unknown_n FROM months m
  JOIN silver_user_profile p ON p.signup_at >= m.period_start AND p.signup_at < m.period_end
  GROUP BY m.month
),
revenue AS (
  SELECT m.month,
         COALESCE(SUM(CASE WHEN a.revenue_cents > 0 THEN a.revenue_cents END), 0) AS gross,
         COALESCE(SUM(CASE WHEN a.revenue_cents < 0 THEN -a.revenue_cents END), 0) AS refunds,
         COALESCE(SUM(a.revenue_cents), 0) AS net,
         COUNT(DISTINCT CASE WHEN a.revenue_cents > 0 THEN a.user_id END) AS payers,
         COUNT(DISTINCT CASE WHEN a.revenue_cents > 0 AND a.type = 'subscription' THEN a.user_id END) AS sub_payers,
         COUNT(DISTINCT CASE WHEN a.revenue_cents > 0 AND a.type = 'ppv' THEN a.user_id END) AS ppv_payers
  FROM months m
  LEFT JOIN silver_payment_attempts a ON a.succeeded_at >= m.period_start AND a.succeeded_at < m.period_end
  GROUP BY m.month
),
access AS (SELECT * FROM silver_subscription_access WHERE grants_access = 1),
subscribers AS (
  SELECT m.month,
         (SELECT COUNT(DISTINCT a.user_id) FROM access a WHERE a.effective_start_at <= m.period_start
            AND (a.effective_end_at IS NULL OR a.effective_end_at > m.period_start)) AS at_start,
         (SELECT COUNT(DISTINCT a.user_id) FROM access a WHERE a.effective_start_at <= m.period_end
            AND (a.effective_end_at IS NULL OR a.effective_end_at > m.period_end)) AS at_end,
         (SELECT COUNT(DISTINCT s.user_id) FROM access s WHERE s.effective_start_at <= m.period_start
            AND (s.effective_end_at IS NULL OR s.effective_end_at > m.period_start)
            AND NOT EXISTS (SELECT 1 FROM access e WHERE e.user_id = s.user_id AND e.effective_start_at <= m.period_end
                              AND (e.effective_end_at IS NULL OR e.effective_end_at > m.period_end))) AS churned,
         (SELECT COALESCE(SUM(price), 0) FROM (
            SELECT MAX(a.price_cents) AS price FROM access a WHERE a.effective_start_at <= m.period_end
              AND (a.effective_end_at IS NULL OR a.effective_end_at > m.period_end) GROUP BY a.user_id)) AS mrr,
         (SELECT COUNT(DISTINCT h.user_id) FROM silver_subscription_access h WHERE h.status = 'cancel_at_period_end'
            AND h.cancelled_at >= m.period_start AND h.cancelled_at < m.period_end) AS cancellations
  FROM months m
)
SELECT m.month, m.period_start, m.period_end, m.days,
       COALESCE(a.mau, 0), COALESCE(u.n, 0),
       COALESCE(d.dau_sum, 0), COALESCE(d.dau_sum, 0) * 1.0 / m.days, COALESCE(d.dau_sum, 0) * 1.0 / m.days / NULLIF(a.mau, 0),
       COALESCE(e.meu, 0), COALESCE(e.meu, 0) * 1.0 / NULLIF(a.mau, 0),
       COALESCE(d.deu_sum, 0), COALESCE(d.deu_sum, 0) * 1.0 / m.days, COALESCE(d.deu_sum, 0) * 1.0 / m.days / NULLIF(e.meu, 0),
       COALESCE(g.n, 0), COALESCE(g.unknown_n, 0),
       r.gross, r.refunds, r.net, r.payers, r.sub_payers, r.ppv_payers,
       r.net / 100.0 / NULLIF(a.mau, 0), r.net / 100.0 / NULLIF(r.payers, 0),
       s.at_start, s.at_end, s.at_end - s.at_start, s.churned, s.churned * 1.0 / NULLIF(s.at_start, 0), s.mrr,
       s.cancellations, s.cancellations * 1.0 / NULLIF(s.at_start, 0),
       :kpi_definitions, :build_id
FROM months m
LEFT JOIN active a ON a.month = m.month
LEFT JOIN daily d ON d.month = m.month
LEFT JOIN engaged e ON e.month = m.month
LEFT JOIN unidentified u ON u.month = m.month
LEFT JOIN signups g ON g.month = m.month
JOIN revenue r ON r.month = m.month
JOIN subscribers s ON s.month = m.month
"""


def close(a, b):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 1e-9 * max(1, abs(b)))


def reconcile_kpi_monthly(db):
    checks = {}
    gold = {r[0]: r for r in db.execute('SELECT * FROM gold_kpi_monthly ORDER BY month')}
    cols = [r[1] for r in db.execute('PRAGMA table_info(gold_kpi_monthly)')]
    g = {m: dict(zip(cols, r)) for m, r in gold.items()}
    months = [r[0] for r in db.execute(load_sql('periods_month'), COVERAGE)]
    checks['one_row_per_complete_month'] = sorted(g) == months

    def registry(name):
        cur = db.execute(load_sql(name), COVERAGE)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur]

    checks['mau_matches_registry'] = [(m, g[m]['mau'], g[m]['unidentified_sessions']) for m in months] == [
        (r['month'], r['mau'], r['unidentified_sessions']) for r in registry('mau_monthly')]
    checks['meu_matches_registry'] = [(m, g[m]['meu']) for m in months] == [(r['month'], r['meu']) for r in registry('meu')]
    # Daily DAU and DEU re-run in the registry take minutes; check the day sums against independent recounts instead.
    active, _ = independent_day_activity_recount(db)
    exact = independent_daily_watch(db)
    for m in months:
        dau = sum(1 for _, day in active if day[:7] == m)
        deu = sum(1 for (_, day), v in exact.items() if day[:7] == m and v >= 60)
        boundary = sum(1 for (_, day), v in exact.items() if day[:7] == m and abs(v - 60) <= Fraction(1, 10**6))
        checks[f'dau_day_sum_independent_{m}'] = g[m]['dau_day_sum'] == dau
        checks[f'deu_day_sum_independent_{m}'] = abs(g[m]['deu_day_sum'] - deu) <= boundary
    revenue = {r['month']: r for r in registry('net_revenue_monthly')}
    checks['revenue_matches_registry'] = all(
        (g[m]['gross_charges_cents'], g[m]['refunds_cents'], g[m]['net_revenue_cents']) ==
        (revenue[m]['gross_charges_cents'], revenue[m]['refunds_cents'], revenue[m]['net_revenue_cents']) for m in months)
    payers = {r['month']: r for r in registry('paying_users_monthly')}
    checks['paying_users_match_registry'] = all(
        (g[m]['paying_users'], g[m]['subscription_payers'], g[m]['ppv_payers']) ==
        (payers[m]['paying_users'], payers[m]['subscription_payers'], payers[m]['ppv_payers']) for m in months)
    arpu = {r['month']: r['arpu_usd'] for r in registry('arpu')}
    arppu = {r['month']: r['arppu_usd'] for r in registry('arppu')}
    checks['arpu_arppu_match_registry'] = all(close(g[m]['arpu_usd'], arpu[m]) and close(g[m]['arppu_usd'], arppu[m])
                                              for m in months)
    subs = {r['month']: r for r in registry('active_subscribers_monthly')}
    churn = {r['month']: r for r in registry('subscriber_churn_monthly')}
    mrr = {r['month']: r for r in registry('mrr_monthly')}
    cancel = {r['month']: r for r in registry('cancellation_request_rate_monthly')}
    checks['subscribers_match_registry'] = all(
        (g[m]['subscribers_at_start'], g[m]['subscribers_at_end'], g[m]['net_adds']) ==
        (subs[m]['subscribers_at_start'], subs[m]['subscribers_at_end'], subs[m]['net_adds']) for m in months)
    checks['churn_matches_registry'] = all(g[m]['churned_subscribers'] == churn[m]['churned']
                                           and close(g[m]['churn_rate'], churn[m]['churn_rate']) for m in months)
    checks['mrr_matches_registry'] = all(g[m]['mrr_cents'] == mrr[m]['mrr_cents'] for m in months)
    checks['cancellations_match_registry'] = all(g[m]['cancellation_requests'] == cancel[m]['cancellation_requests']
                                                 for m in months)
    signups = {r['month']: r['signups'] for r in registry('new_signups_monthly') if r['acquisition_source'] == 'all'}
    unknown = {r['month']: r['signups'] for r in registry('new_signups_monthly') if r['acquisition_source'] == 'unknown'}
    checks['signups_match_registry'] = all(g[m]['signups'] == signups.get(m, 0) and
                                           g[m]['unknown_source_signups'] == unknown.get(m, 0) for m in months)
    checks['rates_equal_their_counts'] = all(
        close(g[m]['stickiness'], g[m]['average_dau'] / g[m]['mau'] if g[m]['mau'] else None)
        and close(g[m]['engagement_rate'], g[m]['meu'] / g[m]['mau'] if g[m]['mau'] else None) for m in months)
    return checks, {'months': len(g)}

# ---------------------------------------------------------------- gold_activity_segments_monthly

SEGMENT_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in (
    'mau', 'activity_family', 'funnel_and_lifecycle_group')}, sort_keys=True)

ACTIVITY_SEGMENTS_SQL = """
CREATE TABLE gold_activity_segments_monthly(
  month TEXT NOT NULL, dimension TEXT NOT NULL CHECK(dimension IN
    ('all','platform','country','acquisition_source','subscriber_status')),
  value TEXT NOT NULL, active_users INTEGER NOT NULL, engaged_users INTEGER, mau INTEGER NOT NULL, active_share REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(month, dimension, value));
INSERT INTO gold_activity_segments_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
touching AS (
  SELECT m.month, r.session_id, r.resolved_user_id AS user_id, r.platform,
         COALESCE(r.country_at_event, 'unknown') AS country, r.session_started_at
  FROM months m JOIN silver_resolved_sessions r
    ON r.resolved_user_id IS NOT NULL AND r.session_started_at < m.period_end AND r.last_activity_at >= m.period_start
),
user_month AS (
  SELECT d.activity_month AS month, d.user_id, SUM(d.watch_seconds) AS watched,
         COALESCE(p.acquisition_source, 'missing_user_record') AS source
  FROM silver_user_day_activity d LEFT JOIN silver_user_profile p ON p.user_id = d.user_id
  WHERE d.sessions_touching > 0 OR d.watch_seconds > 0
  GROUP BY 1, 2
),
rows AS (
  SELECT month, 'all' AS dimension, 'all' AS value, COUNT(DISTINCT user_id) AS active, NULL AS engaged
  FROM touching GROUP BY month
  UNION ALL
  SELECT month, 'platform', platform, COUNT(DISTINCT user_id), NULL FROM touching GROUP BY month, platform
  UNION ALL
  SELECT month, 'country', country, COUNT(DISTINCT user_id), NULL FROM touching GROUP BY month, country
  UNION ALL
  SELECT t.month, 'acquisition_source', u.source, COUNT(DISTINCT t.user_id),
         (SELECT COUNT(*) FROM user_month e WHERE e.month = t.month AND e.source = u.source AND e.watched >= 60)
  FROM touching t JOIN user_month u ON u.month = t.month AND u.user_id = t.user_id
  GROUP BY t.month, u.source
  UNION ALL
  SELECT month, 'subscriber_status', status, COUNT(DISTINCT user_id), NULL FROM (
    SELECT t.month, t.user_id,
           CASE WHEN EXISTS (SELECT 1 FROM silver_subscription_access a
                             WHERE a.user_id = t.user_id AND a.grants_access = 1
                               AND a.effective_start_at <= t.session_started_at
                               AND (a.effective_end_at IS NULL OR a.effective_end_at > t.session_started_at))
                THEN 'subscriber' ELSE 'non_subscriber' END AS status
    FROM touching t)
  GROUP BY month, status
)
SELECT r.month, r.dimension, r.value, r.active, r.engaged, k.mau, r.active * 1.0 / NULLIF(k.mau, 0),
       :segment_definitions, :build_id
FROM rows r JOIN gold_kpi_monthly k ON k.month = r.month;
CREATE INDEX ix_gold_activity_segments_dimension ON gold_activity_segments_monthly(dimension, value, month)
"""


def independent_segment_recount(db):
    """Active users per month by session country and by acquisition source, recomputed in Python from the source."""
    months = [(m, s, e) for m, s, e in db.execute(load_sql('periods_month'), COVERAGE)]
    links = {}
    for session_id, user in db.execute('SELECT session_id, user_id FROM identity_links'):
        links.setdefault(session_id, set()).add(user)
    source = {u: s or 'unknown' for u, s in db.execute('SELECT user_id, acquisition_source FROM users')}
    country, by_source = {}, {}
    for session_id, user, started, last, where in db.execute(
            'SELECT session_id, user_id, session_started_at, last_activity_at, country_at_event FROM sessions'):
        if user is None:
            linked = links.get(session_id, set())
            user = next(iter(linked)) if len(linked) == 1 else None
        if user is None:
            continue
        for m, start, end in months:
            if started < end and last >= start:
                country.setdefault((m, where or 'unknown'), set()).add(user)
                by_source.setdefault((m, source.get(user, 'missing_user_record')), set()).add(user)
    return ({k: len(v) for k, v in country.items()}, {k: len(v) for k, v in by_source.items()})


def reconcile_activity_segments(db):
    checks = {}
    rows = {(m, d, v): (a, e, t) for m, d, v, a, e, t in db.execute(
        'SELECT month, dimension, value, active_users, engaged_users, mau FROM gold_activity_segments_monthly')}
    kpi = dict(db.execute('SELECT month, mau FROM gold_kpi_monthly'))
    checks['all_equals_kpi_mau'] = all(rows.get((m, 'all', 'all'), (0,))[0] == n for m, n in kpi.items() if n)
    platform = {(m, v): a for (m, d, v), (a, _, _) in rows.items() if d == 'platform'}
    checks['platform_matches_registry'] = platform == {
        (m, p): n for m, p, n in db.execute(load_sql('mau_monthly_by_platform'), COVERAGE)}
    status = {(m, v): a for (m, d, v), (a, _, _) in rows.items() if d == 'subscriber_status'}
    checks['subscriber_status_matches_registry'] = status == {
        (m, s): n for m, s, n in db.execute(load_sql('mau_monthly_by_subscriber_status'), COVERAGE)}
    country, by_source = independent_segment_recount(db)
    checks['country_independent_recount'] = {(m, v): a for (m, d, v), (a, _, _) in rows.items() if d == 'country'} == country
    checks['acquisition_source_independent_recount'] = {
        (m, v): a for (m, d, v), (a, _, _) in rows.items() if d == 'acquisition_source'} == by_source
    sources = {}
    for (m, d, v), (a, _, _) in rows.items():
        if d == 'acquisition_source':
            sources[m] = sources.get(m, 0) + a
    checks['acquisition_sources_partition_mau'] = all(sources.get(m, 0) == n for m, n in kpi.items())  # one source per user
    exact = independent_daily_watch(db)
    profile = dict(db.execute('SELECT user_id, acquisition_source FROM silver_user_profile'))
    monthly = {}
    for (user, day), seconds in exact.items():
        monthly[(day[:7], user)] = monthly.get((day[:7], user), Fraction(0)) + seconds
    engaged, boundary = {}, {}
    for (m, user), seconds in monthly.items():
        key = (m, profile.get(user, 'missing_user_record'))
        if seconds >= 60:
            engaged[key] = engaged.get(key, 0) + 1
        if abs(seconds - 60) <= Fraction(1, 10**6):
            boundary[key] = boundary.get(key, 0) + 1
    checks['engaged_by_source_independent_recount'] = all(
        abs((e or 0) - engaged.get((m, v), 0)) <= boundary.get((m, v), 0)
        for (m, d, v), (_, e, _) in rows.items() if d == 'acquisition_source')
    meu = dict(db.execute('SELECT month, meu FROM gold_kpi_monthly'))
    engaged_total = {}
    for (m, d, v), (_, e, _) in rows.items():
        if d == 'acquisition_source':
            engaged_total[m] = engaged_total.get(m, 0) + (e or 0)
    checks['engaged_by_source_partitions_meu'] = all(engaged_total.get(m, 0) == n for m, n in meu.items())
    checks['engaged_only_where_supported'] = all(
        (e is None) == (d != 'acquisition_source') for (_, d, _), (_, e, _) in rows.items())
    return checks, {'rows': len(rows)}

# ---------------------------------------------------------------- gold_growth_accounting_monthly

GROWTH_ACCOUNTING_SQL = """
CREATE TABLE gold_growth_accounting_monthly(
  month TEXT PRIMARY KEY, previous_month TEXT NOT NULL, mau INTEGER NOT NULL, previous_mau INTEGER NOT NULL,
  new_users INTEGER NOT NULL, retained_users INTEGER NOT NULL, resurrected_users INTEGER NOT NULL,
  churned_users INTEGER NOT NULL, quick_ratio REAL, definitions TEXT NOT NULL, build_id TEXT NOT NULL);
INSERT INTO gold_growth_accounting_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
active AS (
  SELECT DISTINCT activity_month AS month, user_id FROM silver_user_day_activity WHERE sessions_touching > 0
),
pairs AS (SELECT cur.month, cur.period_start, prev.month AS prev FROM months cur JOIN months prev ON prev.period_end = cur.period_start),
buckets AS (
  SELECT pr.month, pr.prev,
    (SELECT COUNT(*) FROM active a JOIN silver_user_profile u ON u.user_id = a.user_id
      WHERE a.month = pr.month AND u.signup_at >= pr.period_start) AS new_users,
    (SELECT COUNT(*) FROM active a WHERE a.month = pr.month
      AND EXISTS (SELECT 1 FROM active b WHERE b.user_id = a.user_id AND b.month = pr.prev)) AS retained_users,
    (SELECT COUNT(*) FROM active a JOIN silver_user_profile u ON u.user_id = a.user_id
      WHERE a.month = pr.month AND u.signup_at < pr.period_start
        AND NOT EXISTS (SELECT 1 FROM active b WHERE b.user_id = a.user_id AND b.month = pr.prev)) AS resurrected_users,
    (SELECT COUNT(*) FROM active b WHERE b.month = pr.prev
      AND NOT EXISTS (SELECT 1 FROM active a WHERE a.user_id = b.user_id AND a.month = pr.month)) AS churned_users
  FROM pairs pr
)
SELECT b.month, b.prev, k.mau, p.mau, b.new_users, b.retained_users, b.resurrected_users, b.churned_users,
       (b.new_users + b.resurrected_users) * 1.0 / NULLIF(b.churned_users, 0), :growth_definitions, :build_id
FROM buckets b JOIN gold_kpi_monthly k ON k.month = b.month JOIN gold_kpi_monthly p ON p.month = b.prev
"""

GROWTH_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in ('mau', 'growth_accounting')}, sort_keys=True)


def reconcile_growth_accounting(db):
    checks = {}
    gold = [tuple(r) for r in db.execute(
        'SELECT month, new_users, retained_users, resurrected_users, churned_users, quick_ratio, mau, previous_mau '
        'FROM gold_growth_accounting_monthly ORDER BY month')]
    registry = [tuple(r) for r in db.execute(load_sql('growth_accounting_monthly'), COVERAGE)]
    checks['buckets_match_registry'] = [g[:5] for g in gold] == [r[:5] for r in registry] and all(
        close(g[5], r[5]) for g, r in zip(gold, registry))
    # Active users without a users row are in no bucket (as in the registry); count them so the identities stay exact.
    missing = dict(db.execute(
        "SELECT a.activity_month, COUNT(DISTINCT a.user_id) FROM silver_user_day_activity a "
        "WHERE a.sessions_touching > 0 AND NOT EXISTS (SELECT 1 FROM silver_user_profile p WHERE p.user_id = a.user_id) "
        "AND NOT EXISTS (SELECT 1 FROM silver_user_day_activity b, gold_growth_accounting_monthly g "
        "  WHERE g.month = a.activity_month AND b.activity_month = g.previous_month AND b.user_id = a.user_id "
        "    AND b.sessions_touching > 0) GROUP BY 1"))
    checks['buckets_add_to_mau'] = all(g[1] + g[2] + g[3] + missing.get(g[0], 0) == g[6] for g in gold)
    checks['mau_change_identity'] = all(g[6] - g[7] == g[1] + g[3] + missing.get(g[0], 0) - g[4] for g in gold)
    months = [r[0] for r in db.execute(load_sql('periods_month'), COVERAGE)]
    checks['every_month_after_the_first'] = [g[0] for g in gold] == months[1:]
    return checks, {'rows': len(gold)}

# ---------------------------------------------------------------- gold_cohorts

COHORT_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in (
    'mau', 'funnel_and_lifecycle_group', 'engagement_group', 'supporting_metrics')}, sort_keys=True)

COHORTS_SQL = """
CREATE TABLE gold_cohorts(
  signup_month TEXT NOT NULL, month TEXT NOT NULL, months_since_signup INTEGER NOT NULL,
  cohort_users INTEGER NOT NULL, retained_users INTEGER, retention_rate REAL,
  day1_eligible INTEGER NOT NULL, day1_retained INTEGER NOT NULL, day1_retention_rate REAL,
  day7_eligible INTEGER NOT NULL, day7_retained INTEGER NOT NULL, day7_retention_rate REAL,
  day30_eligible INTEGER NOT NULL, day30_retained INTEGER NOT NULL, day30_retention_rate REAL,
  activation_eligible INTEGER NOT NULL, activated_users INTEGER NOT NULL, activation_rate REAL,
  conversion_eligible INTEGER NOT NULL, subscription_converted INTEGER NOT NULL, paid_converted INTEGER NOT NULL,
  subscription_conversion_rate REAL, paid_conversion_rate REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(signup_month, months_since_signup));
INSERT INTO gold_cohorts
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
cohort AS (
  SELECT m.month AS signup_month, m.period_start, p.user_id, p.signup_at, p.signup_date,
         p.first_subscription_at, p.first_paid_at
  FROM months m JOIN silver_user_profile p ON p.signup_at >= m.period_start AND p.signup_at < m.period_end
),
active_days AS (SELECT user_id, activity_date FROM silver_user_day_activity WHERE sessions_touching > 0),
engaged_days AS (SELECT user_id, activity_date FROM silver_user_day_activity WHERE watch_seconds >= 60),
levels AS (
  SELECT c.signup_month, COUNT(*) AS cohort_users,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+2 days') <= :coverage_end) AS d1_e,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+2 days') <= :coverage_end
        AND EXISTS (SELECT 1 FROM active_days a WHERE a.user_id = c.user_id AND a.activity_date = date(c.signup_date, '+1 days'))) AS d1_r,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+8 days') <= :coverage_end) AS d7_e,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+8 days') <= :coverage_end
        AND EXISTS (SELECT 1 FROM active_days a WHERE a.user_id = c.user_id AND a.activity_date = date(c.signup_date, '+7 days'))) AS d7_r,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+31 days') <= :coverage_end) AS d30_e,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+31 days') <= :coverage_end
        AND EXISTS (SELECT 1 FROM active_days a WHERE a.user_id = c.user_id AND a.activity_date = date(c.signup_date, '+30 days'))) AS d30_r,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+7 days') <= :coverage_end) AS act_e,
    SUM(c.signup_date || 'T00:00:00Z' >= :coverage_start AND strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_date, '+7 days') <= :coverage_end
        AND EXISTS (SELECT 1 FROM engaged_days e WHERE e.user_id = c.user_id
                    AND e.activity_date >= c.signup_date AND e.activity_date < date(c.signup_date, '+7 days'))) AS act_r,
    SUM(strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days') <= :coverage_end) AS conv_e,
    SUM(strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days') <= :coverage_end
        AND COALESCE(c.first_subscription_at >= c.signup_at
                     AND c.first_subscription_at < strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days'), 0)) AS sub_c,
    SUM(strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days') <= :coverage_end
        AND COALESCE(c.first_paid_at >= c.signup_at
                     AND c.first_paid_at < strftime('%Y-%m-%dT%H:%M:%SZ', c.signup_at, '+30 days'), 0)) AS paid_c
  FROM cohort c GROUP BY c.signup_month
),
offsets AS (
  SELECT l.signup_month, m.month,
         (CAST(substr(m.month, 1, 4) AS INTEGER) * 12 + CAST(substr(m.month, 6, 2) AS INTEGER))
         - (CAST(substr(l.signup_month, 1, 4) AS INTEGER) * 12 + CAST(substr(l.signup_month, 6, 2) AS INTEGER)) AS k
  FROM levels l JOIN months m ON m.month >= l.signup_month
),
retained AS (
  SELECT o.signup_month, o.month, COUNT(DISTINCT a.user_id) AS n
  FROM offsets o JOIN cohort c ON c.signup_month = o.signup_month
  JOIN silver_user_day_activity a ON a.user_id = c.user_id AND a.activity_month = o.month AND a.sessions_touching > 0
  WHERE o.k > 0 GROUP BY 1, 2
)
SELECT o.signup_month, o.month, o.k, l.cohort_users,
       CASE WHEN o.k > 0 THEN COALESCE(r.n, 0) END, CASE WHEN o.k > 0 THEN COALESCE(r.n, 0) * 1.0 / l.cohort_users END,
       l.d1_e, l.d1_r, l.d1_r * 1.0 / NULLIF(l.d1_e, 0), l.d7_e, l.d7_r, l.d7_r * 1.0 / NULLIF(l.d7_e, 0),
       l.d30_e, l.d30_r, l.d30_r * 1.0 / NULLIF(l.d30_e, 0),
       l.act_e, l.act_r, l.act_r * 1.0 / NULLIF(l.act_e, 0),
       l.conv_e, l.sub_c, l.paid_c, l.sub_c * 1.0 / NULLIF(l.conv_e, 0), l.paid_c * 1.0 / NULLIF(l.conv_e, 0),
       :cohort_definitions, :build_id
FROM offsets o JOIN levels l ON l.signup_month = o.signup_month
LEFT JOIN retained r ON r.signup_month = o.signup_month AND r.month = o.month
"""


def reconcile_cohorts(db):
    checks = {}
    cur = db.execute('SELECT * FROM gold_cohorts ORDER BY signup_month, months_since_signup')
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur]
    retention = [(r['signup_month'], r['month'], r['months_since_signup'], r['cohort_users'], r['retained_users'])
                 for r in rows if r['months_since_signup'] > 0]
    checks['monthly_retention_matches_registry'] = retention == [
        tuple(r[:5]) for r in db.execute(load_sql('retention_monthly_cohort'), COVERAGE)]
    level = {r['signup_month']: r for r in rows if r['months_since_signup'] == 0}
    day_n = {}
    for m, n, eligible, kept, _ in db.execute(load_sql('retention_day_n'), COVERAGE):
        day_n[(m, n)] = (eligible, kept)
    checks['day_n_retention_matches_registry'] = all(
        (level[m][f'day{n}_eligible'], level[m][f'day{n}_retained']) == v for (m, n), v in day_n.items()) and all(
        level[m][f'day{n}_eligible'] == 0 for m in level for n in (1, 7, 30) if (m, n) not in day_n)
    activation = {r[0]: tuple(r[1:3]) for r in db.execute(load_sql('activation_7d'), COVERAGE)}
    checks['activation_matches_registry'] = all(
        (level[m]['activation_eligible'], level[m]['activated_users']) == activation.get(m, (0, 0)) for m in level)
    conversion = {r[0]: tuple(r[1:4]) for r in db.execute(load_sql('conversion_30d'), COVERAGE)}
    checks['conversion_matches_registry'] = all(
        (level[m]['conversion_eligible'], level[m]['subscription_converted'], level[m]['paid_converted'])
        == conversion.get(m, (0, 0, 0)) for m in level)
    checks['cohort_level_values_repeat_per_row'] = all(
        all(r[c] == level[r['signup_month']][c] for c in cols if c.startswith(('cohort_users', 'day', 'activ', 'conversion',
                                                                                 'subscription_', 'paid_')))
        for r in rows)
    signups = dict(db.execute('SELECT month, signups FROM gold_kpi_monthly'))
    checks['cohort_size_equals_signups'] = all(level[m]['cohort_users'] == signups[m] for m in level) and all(
        m in level for m, n in signups.items() if n)
    return checks, {'rows': len(rows), 'cohorts': len(level)}

# ---------------------------------------------------------------- gold_revenue_monthly

REVENUE_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in ('revenue_group', 'supporting_metrics')}, sort_keys=True)

REVENUE_MONTHLY_SQL = """
CREATE TABLE gold_revenue_monthly(
  month TEXT NOT NULL, revenue_type TEXT NOT NULL CHECK(revenue_type IN ('subscription','ppv','unattributed')),
  gross_charges_cents INTEGER NOT NULL, refunds_cents INTEGER NOT NULL, net_revenue_cents INTEGER NOT NULL,
  charges INTEGER NOT NULL, refunds INTEGER NOT NULL, payers INTEGER NOT NULL, refund_rate REAL,
  attempts INTEGER NOT NULL, failed_attempts INTEGER NOT NULL, payment_failure_rate REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(month, revenue_type));
INSERT INTO gold_revenue_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
types(revenue_type) AS (VALUES ('subscription'), ('ppv'), ('unattributed')),
booked AS (
  SELECT m.month, t.revenue_type,
         COALESCE(SUM(CASE WHEN a.revenue_cents > 0 THEN a.revenue_cents END), 0) AS gross,
         COALESCE(SUM(CASE WHEN a.revenue_cents < 0 THEN -a.revenue_cents END), 0) AS refunds_cents,
         COUNT(CASE WHEN a.revenue_cents > 0 THEN 1 END) AS charges,
         COUNT(CASE WHEN a.revenue_cents < 0 THEN 1 END) AS refunds,
         COUNT(DISTINCT CASE WHEN a.revenue_cents > 0 THEN a.user_id END) AS payers
  FROM months m CROSS JOIN types t
  LEFT JOIN silver_payment_attempts a ON a.revenue_type = t.revenue_type
   AND a.succeeded_at >= m.period_start AND a.succeeded_at < m.period_end
  GROUP BY m.month, t.revenue_type
),
attempts AS (
  SELECT m.month, a.type AS revenue_type, COUNT(*) AS attempts, SUM(a.outcome = 'failed') AS failed
  FROM months m JOIN silver_payment_attempts a ON a.type <> 'refund' AND a.outcome IN ('succeeded', 'failed')
   AND a.created_at >= m.period_start AND a.created_at < m.period_end
  GROUP BY m.month, a.type
)
SELECT b.month, b.revenue_type, b.gross, b.refunds_cents, b.gross - b.refunds_cents, b.charges, b.refunds, b.payers,
       b.refunds_cents * 1.0 / NULLIF(b.gross, 0), COALESCE(t.attempts, 0), COALESCE(t.failed, 0),
       t.failed * 1.0 / NULLIF(t.attempts, 0), :revenue_definitions, :build_id
FROM booked b LEFT JOIN attempts t ON t.month = b.month AND t.revenue_type = b.revenue_type
"""


def reconcile_revenue_monthly(db):
    checks = {}
    rows = {(m, t): (g, r, n, c, rc, a, f) for m, t, g, r, n, c, rc, a, f in db.execute(
        'SELECT month, revenue_type, gross_charges_cents, refunds_cents, net_revenue_cents, charges, refunds, '
        'attempts, failed_attempts FROM gold_revenue_monthly')}
    by_type = {(m, t): (g, r, n) for m, t, g, r, n in db.execute(load_sql('net_revenue_by_type_monthly'), COVERAGE)}
    checks['by_type_matches_registry'] = {k: v[:3] for k, v in rows.items()} == by_type
    kpi = {m: (g, r, n) for m, g, r, n in db.execute(
        'SELECT month, gross_charges_cents, refunds_cents, net_revenue_cents FROM gold_kpi_monthly')}
    totals = {}
    for (m, _), v in rows.items():
        totals[m] = tuple(a + b for a, b in zip(totals.get(m, (0, 0, 0)), v[:3]))
    checks['types_add_to_kpi_revenue'] = totals == kpi
    refund = {m: (g, r, c, n) for m, g, r, c, n, _ in db.execute(load_sql('refund_rate_monthly'), COVERAGE)}
    counts = {}
    for (m, _), v in rows.items():
        counts[m] = tuple(a + b for a, b in zip(counts.get(m, (0, 0, 0, 0)), (v[0], v[1], v[3], v[4])))
    checks['refund_counts_match_registry'] = counts == refund
    failures = {(m, p): (a, f) for m, p, a, f, _ in db.execute(load_sql('payment_failure_rate_monthly'), COVERAGE)}
    checks['failures_match_registry'] = {k: v[5:7] for k, v in rows.items() if v[5]} == failures
    checks['net_equals_gross_minus_refunds'] = all(v[2] == v[0] - v[1] for v in rows.values())
    return checks, {'rows': len(rows)}

# ---------------------------------------------------------------- gold_funnel_monthly

FUNNEL_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in ('engagement_group', 'mau')}, sort_keys=True)

FUNNEL_MONTHLY_SQL = """
CREATE TABLE gold_funnel_monthly(
  month TEXT NOT NULL, product TEXT NOT NULL,
  paywalls INTEGER NOT NULL, paywalls_with_checkout INTEGER NOT NULL, paywalls_with_purchase INTEGER NOT NULL,
  paywall_to_checkout_rate REAL, checkout_to_purchase_rate REAL, paywall_to_purchase_rate REAL,
  exposed_users INTEGER NOT NULL, mau INTEGER, exposure_rate REAL,
  checkouts_without_paywall_link INTEGER NOT NULL, in_app_purchases INTEGER NOT NULL,
  in_app_purchases_without_checkout_link INTEGER NOT NULL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(month, product));
INSERT INTO gold_funnel_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
walls AS (
  SELECT m.month, COALESCE(f.product, 'unknown') AS product, f.paywall_event_id, f.user_id,
         f.checkouts_started > 0 AS checked_out, f.purchase_txn_id IS NOT NULL AS purchased
  FROM months m JOIN silver_paywall_funnel f ON f.event_at >= m.period_start AND f.event_at < m.period_end
),
-- Checkouts without a paywall link are not in Silver (its grain is the paywall view): read the Bronze event view.
orphan_checkouts AS (
  SELECT m.month, COALESCE(json_extract(e.event_properties_json, '$.product'), 'unknown') AS product, COUNT(*) AS n
  FROM months m JOIN bronze_user_events e ON e.event_name = 'checkout_started' AND e.triggering_paywall_event_id IS NULL
   AND e.event_at >= m.period_start AND e.event_at < m.period_end
  GROUP BY 1, 2
),
in_app AS (
  SELECT m.month, a.type AS product, COUNT(*) AS n, SUM(a.checkout_event_id IS NULL) AS unlinked
  FROM months m JOIN silver_payment_attempts a ON a.revenue_cents > 0 AND a.session_id IS NOT NULL
   AND a.succeeded_at >= m.period_start AND a.succeeded_at < m.period_end
  GROUP BY 1, 2
),
keys AS (
  SELECT month, product FROM walls UNION SELECT month, product FROM orphan_checkouts UNION SELECT month, product FROM in_app
  UNION SELECT month, 'all' FROM months
),
counts AS (
  SELECT k.month, k.product,
         (SELECT COUNT(*) FROM walls w WHERE w.month = k.month AND (k.product = 'all' OR w.product = k.product)) AS paywalls,
         (SELECT COALESCE(SUM(w.checked_out), 0) FROM walls w WHERE w.month = k.month AND (k.product = 'all' OR w.product = k.product)) AS chk,
         (SELECT COALESCE(SUM(w.purchased), 0) FROM walls w WHERE w.month = k.month AND (k.product = 'all' OR w.product = k.product)) AS buy,
         (SELECT COUNT(DISTINCT w.user_id) FROM walls w WHERE w.month = k.month AND (k.product = 'all' OR w.product = k.product)) AS exposed,
         (SELECT COALESCE(SUM(o.n), 0) FROM orphan_checkouts o WHERE o.month = k.month AND (k.product = 'all' OR o.product = k.product)) AS orphans,
         (SELECT COALESCE(SUM(i.n), 0) FROM in_app i WHERE i.month = k.month AND (k.product = 'all' OR i.product = k.product)) AS in_app,
         (SELECT COALESCE(SUM(i.unlinked), 0) FROM in_app i WHERE i.month = k.month AND (k.product = 'all' OR i.product = k.product)) AS unlinked
  FROM keys k
)
SELECT c.month, c.product, c.paywalls, c.chk, c.buy, c.chk * 1.0 / NULLIF(c.paywalls, 0), c.buy * 1.0 / NULLIF(c.chk, 0),
       c.buy * 1.0 / NULLIF(c.paywalls, 0), c.exposed,
       CASE WHEN c.product = 'all' THEN k.mau END, CASE WHEN c.product = 'all' THEN c.exposed * 1.0 / NULLIF(k.mau, 0) END,
       c.orphans, c.in_app, c.unlinked, :funnel_definitions, :build_id
FROM counts c JOIN gold_kpi_monthly k ON k.month = c.month
"""


def reconcile_funnel_monthly(db):
    checks = {}
    rows = {(m, p): r for m, p, *r in db.execute(
        'SELECT month, product, paywalls, paywalls_with_checkout, paywalls_with_purchase, exposed_users, mau, '
        'checkouts_without_paywall_link, in_app_purchases, in_app_purchases_without_checkout_link FROM gold_funnel_monthly')}
    registry = {(m, p if p is not None else 'unknown'): (a, b, c) for m, p, a, b, c, *_ in
                db.execute(load_sql('paywall_funnel_monthly'), COVERAGE)}
    checks['funnel_matches_registry'] = {k: tuple(v[:3]) for k, v in rows.items()
                                         if k[1] != 'all' and v[0]} == registry
    exposure = {m: (e, n) for m, e, n, _ in db.execute(load_sql('paywall_exposure_monthly'), COVERAGE)}
    checks['exposure_matches_registry'] = all(
        (rows[(m, 'all')][3], rows[(m, 'all')][4]) == v for m, v in exposure.items())
    products = {}
    for (m, p), v in rows.items():
        if p != 'all':
            products[m] = tuple(a + b for a, b in zip(products.get(m, (0,) * 3 + (0,) * 3), v[:3] + v[5:8]))
    checks['products_add_to_all'] = all(products.get(m, (0,) * 6) == tuple(v[:3] + v[5:8])
                                        for (m, p), v in rows.items() if p == 'all')
    orphans = db.execute("SELECT COUNT(*) FROM user_events WHERE event_name='checkout_started' "
                         "AND triggering_paywall_event_id IS NULL AND event_at >= :coverage_start "
                         "AND event_at < :coverage_end", COVERAGE).fetchone()[0]
    checks['unlinked_checkouts_equal_source'] = sum(v[5] for (m, p), v in rows.items() if p == 'all') == orphans
    return checks, {'rows': len(rows)}

# ---------------------------------------------------------------- gold_content_monthly

CONTENT_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in ('engagement_group',)}, sort_keys=True)

CONTENT_MONTHLY_SQL = """
CREATE TABLE gold_content_monthly(
  month TEXT NOT NULL, content_id TEXT NOT NULL, viewers INTEGER NOT NULL, views INTEGER NOT NULL,
  watch_seconds REAL NOT NULL, watch_hours REAL NOT NULL,
  user_episodes_started INTEGER NOT NULL, user_episodes_completed INTEGER NOT NULL, episode_completion_rate REAL,
  completed_with_next_episode INTEGER NOT NULL, continued INTEGER NOT NULL, series_continuation_rate REAL,
  free_viewer_days INTEGER, quota_hit_days INTEGER, free_quota_hit_rate REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(month, content_id));
INSERT INTO gold_content_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
watch AS (
  SELECT m.month, t.content_id, t.user_id, t.views_started, t.watch_seconds
  FROM months m JOIN silver_user_day_title_watch t ON t.activity_month = m.month
),
episodes AS (
  SELECT m.month, e.content_id, e.covered_sec >= 0.9 * e.episode_duration_sec AS completed, e.has_next_episode,
         e.started_next_episode_in_window
  FROM months m JOIN silver_user_episodes e ON e.first_start_at >= m.period_start AND e.first_start_at < m.period_end
   AND e.window_complete = 1 AND e.episode_duration_sec IS NOT NULL
),
quota AS (
  SELECT activity_month AS month, COUNT(*) AS free_days, SUM(free_quota_slots_used = 8) AS hits
  FROM silver_user_day_activity WHERE free_quota_slots_used > 0 GROUP BY 1
),
by_title_watch AS (
  SELECT month, content_id, COUNT(DISTINCT CASE WHEN views_started > 0 THEN user_id END) AS viewers,
         SUM(views_started) AS views, SUM(watch_seconds) AS seconds FROM watch GROUP BY 1, 2
  UNION ALL
  SELECT month, 'all', COUNT(DISTINCT CASE WHEN views_started > 0 THEN user_id END), SUM(views_started), SUM(watch_seconds)
  FROM watch GROUP BY 1
),
by_title_episodes AS (
  SELECT month, content_id, COUNT(*) AS started, SUM(completed) AS completed,
         SUM(completed AND has_next_episode = 1) AS with_next,
         SUM(CASE WHEN completed AND has_next_episode = 1 THEN started_next_episode_in_window ELSE 0 END) AS continued
  FROM episodes GROUP BY 1, 2
  UNION ALL
  SELECT month, 'all', COUNT(*), SUM(completed), SUM(completed AND has_next_episode = 1),
         SUM(CASE WHEN completed AND has_next_episode = 1 THEN started_next_episode_in_window ELSE 0 END)
  FROM episodes GROUP BY 1
),
keys AS (SELECT month, content_id FROM by_title_watch UNION SELECT month, content_id FROM by_title_episodes
         UNION SELECT month, 'all' FROM months),
counts AS (
  SELECT k.month, k.content_id, COALESCE(w.viewers, 0) AS viewers, COALESCE(w.views, 0) AS views,
         COALESCE(w.seconds, 0.0) AS seconds, COALESCE(e.started, 0) AS started, COALESCE(e.completed, 0) AS completed,
         COALESCE(e.with_next, 0) AS with_next, COALESCE(e.continued, 0) AS continued
  FROM keys k
  LEFT JOIN by_title_watch w ON w.month = k.month AND w.content_id = k.content_id
  LEFT JOIN by_title_episodes e ON e.month = k.month AND e.content_id = k.content_id
)
SELECT c.month, c.content_id, c.viewers, c.views, c.seconds, c.seconds / 3600.0,
       c.started, c.completed, c.completed * 1.0 / NULLIF(c.started, 0),
       c.with_next, c.continued, c.continued * 1.0 / NULLIF(c.with_next, 0),
       CASE WHEN c.content_id = 'all' THEN COALESCE(q.free_days, 0) END,
       CASE WHEN c.content_id = 'all' THEN COALESCE(q.hits, 0) END,
       CASE WHEN c.content_id = 'all' THEN q.hits * 1.0 / NULLIF(q.free_days, 0) END,
       :content_definitions, :build_id
FROM counts c LEFT JOIN quota q ON q.month = c.month
"""


def reconcile_content_monthly(db):
    checks = {}
    rows = {(m, c): r for m, c, *r in db.execute(
        'SELECT month, content_id, viewers, views, watch_seconds, user_episodes_started, user_episodes_completed, '
        'completed_with_next_episode, continued, free_viewer_days, quota_hit_days FROM gold_content_monthly')}
    alls = {m: v for (m, c), v in rows.items() if c == 'all'}
    reach = {(m, c): n for m, c, n in db.execute(load_sql('title_reach_monthly'), COVERAGE)}
    checks['title_reach_matches_registry'] = {k: v[0] for k, v in rows.items() if k[1] != 'all' and v[0]} == reach
    views = {m: (v, u) for m, v, u, _ in db.execute(load_sql('views_per_viewer_monthly'), COVERAGE)}
    checks['views_and_viewers_match_registry'] = all((alls[m][1], alls[m][0]) == v for m, v in views.items())
    watch = {m: s for m, s, *_ in db.execute(load_sql('watch_time_monthly'), COVERAGE)}
    checks['watch_time_matches_registry'] = all(abs(alls[m][2] - s) <= 1e-6 * max(1, s) for m, s in watch.items())
    completion = {m: (s, c) for m, s, c, _ in db.execute(load_sql('episode_completion_monthly'), COVERAGE)}
    checks['completion_matches_registry'] = all(tuple(alls[m][3:5]) == v for m, v in completion.items())
    continuation = {m: (w, c) for m, w, c, _ in db.execute(load_sql('series_continuation_monthly'), COVERAGE)}
    checks['continuation_matches_registry'] = all(tuple(alls[m][5:7]) == v for m, v in continuation.items())
    quota = {m: (d, h) for m, d, h, _ in db.execute(load_sql('free_quota_hit_monthly'), COVERAGE)}
    checks['free_quota_matches_registry'] = all(tuple(alls[m][7:9]) == v for m, v in quota.items())
    titles = {}
    for (m, c), v in rows.items():
        if c != 'all':
            titles[m] = [a + b for a, b in zip(titles.get(m, [0] * 6), v[1:7])]
    checks['titles_add_to_all'] = all(
        abs(titles.get(m, [0] * 6)[1] - v[2]) <= 1e-6 * max(1, v[2]) and
        [titles.get(m, [0] * 6)[0]] + titles.get(m, [0] * 6)[2:] == [v[1]] + list(v[3:7]) for m, v in alls.items())
    checks['quota_only_on_all_rows'] = all((v[7] is None) == (c != 'all') for (m, c), v in rows.items())
    return checks, {'rows': len(rows)}

# ---------------------------------------------------------------- gold_marketing_monthly

MARKETING_DEFINITIONS = json.dumps({k: DEFINITIONS[k] for k in ('supporting_metrics',)}, sort_keys=True)

MARKETING_MONTHLY_SQL = """
CREATE TABLE gold_marketing_monthly(
  month TEXT NOT NULL, channel TEXT NOT NULL, spend_days INTEGER NOT NULL, excluded_spend_days INTEGER NOT NULL,
  spend_cents INTEGER, impressions INTEGER, clicks INTEGER, ctr REAL, cpc_usd REAL,
  signups INTEGER NOT NULL, new_paying_users INTEGER NOT NULL, cost_per_signup_usd REAL, cac_usd REAL,
  definitions TEXT NOT NULL, build_id TEXT NOT NULL, PRIMARY KEY(month, channel));
INSERT INTO gold_marketing_monthly
WITH RECURSIVE """ + GOLD_MONTHS_CTE + """,
agg AS (
  SELECT d.month, d.channel, SUM(d.has_spend_row) AS spend_days, SUM(d.exception_status = 'excluded') AS excluded_days,
         CASE WHEN SUM(d.has_spend_row) > 0 THEN SUM(d.spend_cents) END AS spend,
         CASE WHEN SUM(d.has_spend_row) > 0 THEN SUM(d.impressions) END AS impressions,
         CASE WHEN SUM(d.has_spend_row) > 0 THEN SUM(d.clicks) END AS clicks,
         SUM(d.signups) AS signups, SUM(d.new_paying_users) AS payers
  FROM months m JOIN silver_marketing_daily d ON d.month = m.month
  GROUP BY 1, 2
)
SELECT month, channel, spend_days, excluded_days, spend, impressions, clicks, clicks * 1.0 / NULLIF(impressions, 0),
       CASE WHEN excluded_days = 0 THEN spend / 100.0 / NULLIF(clicks, 0) END, signups, payers,
       CASE WHEN excluded_days = 0 THEN spend / 100.0 / NULLIF(signups, 0) END,
       CASE WHEN excluded_days = 0 THEN spend / 100.0 / NULLIF(payers, 0) END, :marketing_definitions, :build_id
FROM agg
"""


def reconcile_marketing_monthly(db):
    checks = {}
    rows = {(m, c): r for m, c, *r in db.execute(
        'SELECT month, channel, spend_cents, impressions, clicks, signups, new_paying_users, excluded_spend_days '
        'FROM gold_marketing_monthly')}
    ctr = {(m, c): (k, i) for m, c, k, i, _ in db.execute(load_sql('marketing_ctr_monthly'), COVERAGE) if c != 'all'}
    checks['ctr_matches_registry'] = {k: (v[2], v[1]) for k, v in rows.items() if v[1] is not None} == ctr
    efficiency = {(m, c): (s, k, g, p) for m, c, s, k, g, p, *_ in db.execute(load_sql('marketing_efficiency_monthly'), COVERAGE)}
    checks['efficiency_matches_registry'] = all(
        (rows[k][2], rows[k][3], rows[k][4]) == v[1:] and (rows[k][0] == v[0] or rows[k][5] > 0)
        for k, v in efficiency.items())
    kpi = dict(db.execute('SELECT month, signups FROM gold_kpi_monthly'))
    totals = {}
    for (m, _), v in rows.items():
        totals[m] = totals.get(m, 0) + v[3]
    checks['channel_signups_add_to_kpi'] = all(totals.get(m, 0) == n for m, n in kpi.items())
    return checks, {'rows': len(rows)}

# ---------------------------------------------------------------- build orchestration

SILVER = [
    ('silver_resolved_sessions', RESOLVED_SESSIONS_SQL,
     ['ix_silver_resolved_sessions_user_time', 'ix_silver_resolved_sessions_time'], reconcile_resolved_sessions),
    ('silver_payment_attempts', PAYMENT_ATTEMPTS_SQL,
     ['ix_silver_payment_attempts_success', 'ix_silver_payment_attempts_user_success'], reconcile_payment_attempts),
    ('silver_subscription_access', SUBSCRIPTION_ACCESS_SQL,
     ['ix_silver_subscription_access_user_start'], reconcile_subscription_access),
    ('silver_user_profile', USER_PROFILE_SQL,
     ['ix_silver_user_profile_signup', 'ix_silver_user_profile_source_signup'], reconcile_user_profile),
    ('silver_user_day_activity', USER_DAY_ACTIVITY_SQL,
     ['ix_silver_user_day_activity_date'], reconcile_user_day_activity),
    ('silver_user_day_title_watch', USER_DAY_TITLE_WATCH_SQL,
     ['ix_silver_user_day_title_watch_date_title'], reconcile_user_day_title_watch),
    ('silver_user_episodes', USER_EPISODES_SQL, ['ix_silver_user_episodes_start'], reconcile_user_episodes),
    ('silver_paywall_funnel', PAYWALL_FUNNEL_SQL,
     ['ix_silver_paywall_funnel_time', 'ix_silver_paywall_funnel_user_time'], reconcile_paywall_funnel),
    ('silver_marketing_daily', MARKETING_DAILY_SQL,
     ['ix_silver_marketing_daily_channel_date'], reconcile_marketing_daily),
    ('silver_quality_exceptions', QUALITY_EXCEPTIONS_SQL,          # last: reads every other Silver table
     ['ix_silver_quality_exceptions_reason'], reconcile_quality_exceptions),
]

GOLD = [
    ('gold_kpi_monthly', KPI_MONTHLY_SQL, [], reconcile_kpi_monthly),
    ('gold_activity_segments_monthly', ACTIVITY_SEGMENTS_SQL, ['ix_gold_activity_segments_dimension'],
     reconcile_activity_segments),
    ('gold_growth_accounting_monthly', GROWTH_ACCOUNTING_SQL, [], reconcile_growth_accounting),
    ('gold_cohorts', COHORTS_SQL, [], reconcile_cohorts),
    ('gold_revenue_monthly', REVENUE_MONTHLY_SQL, [], reconcile_revenue_monthly),
    ('gold_funnel_monthly', FUNNEL_MONTHLY_SQL, [], reconcile_funnel_monthly),
    ('gold_content_monthly', CONTENT_MONTHLY_SQL, [], reconcile_content_monthly),
    ('gold_marketing_monthly', MARKETING_MONTHLY_SQL, [], reconcile_marketing_monthly),
]

# Named parameters available to every layer script, besides :build_id and the coverage window.
SCRIPT_PARAMS = {'kpi_definitions': KPI_DEFINITIONS, 'segment_definitions': SEGMENT_DEFINITIONS,
                 'growth_definitions': GROWTH_DEFINITIONS, 'cohort_definitions': COHORT_DEFINITIONS,
                 'revenue_definitions': REVENUE_DEFINITIONS, 'funnel_definitions': FUNNEL_DEFINITIONS,
                 'content_definitions': CONTENT_DEFINITIONS, 'marketing_definitions': MARKETING_DEFINITIONS}

# Objects owned by this builder. Only these are dropped and recreated.
LAYERS = SILVER + GOLD
OWNED_VIEWS = [f'bronze_{table}' for table in SOURCE_ROLES]
OWNED_TABLES = [name for name, *_ in LAYERS]
OWNED_INDEXES = [index for _, _, indexes, _ in LAYERS for index in indexes]


def now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_schema(db):
    problems = []
    for table in SOURCE_ROLES:
        present = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
        if not present:
            problems.append(f'missing table {table}')
        elif REQUIRED_COLUMNS.get(table, set()) - present:
            problems.append(f'{table} missing columns {sorted(REQUIRED_COLUMNS[table] - present)}')
    if problems:
        raise ValueError('source schema mismatch: ' + '; '.join(problems))


def fingerprint(db):
    result = {}
    for table in SOURCE_ROLES:
        rows = db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
        result[table] = {'rows': len(rows), 'sha256': hashlib.sha256(repr(rows).encode()).hexdigest()}
    return result


def reconcile(db):
    """Run every layer's reconciliation; returns (flat checks, details by object)."""
    checks = {'bronze_views_match_source': all(
        db.execute(f'SELECT COUNT(*) FROM bronze_{t}').fetchone()[0] == db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        for t in SOURCE_ROLES)}
    details = {}
    for name, _, _, reconcile_table in LAYERS:
        table_checks, table_details = reconcile_table(db)
        checks.update({f'{name}.{key}': ok for key, ok in table_checks.items()})
        details[name] = table_details
    return checks, details


def run_script(db, script, build_id):
    for statement in script.strip().split(';\n'):
        if statement.strip():
            db.execute(statement, {'build_id': build_id, **COVERAGE, **SCRIPT_PARAMS})


def write_log(db, record):
    keys = ('build_id', 'started_at', 'finished_at', 'status', 'builder_sha256', 'registry_sha256', 'definitions',
            'source_fingerprint', 'row_counts', 'reconciliation', 'error')
    db.execute(f'INSERT INTO layer_build_log VALUES ({",".join(":" + k for k in keys)})', {k: record.get(k) for k in keys})


def build(path):
    db = sqlite3.connect(path, isolation_level=None)
    db.execute(BUILD_LOG_DDL)
    build_id = uuid.uuid4().hex
    record = {'build_id': build_id, 'started_at': now(), 'builder_sha256': sha256(HERE),
              'registry_sha256': sha256(REGISTRY), 'definitions': json.dumps(DEFINITIONS)}
    try:
        check_schema(db)
        record['source_fingerprint'] = json.dumps(fingerprint(db))
        db.execute('BEGIN IMMEDIATE')
        for index in OWNED_INDEXES:
            db.execute(f'DROP INDEX IF EXISTS {index}')
        for table in OWNED_TABLES:
            db.execute(f'DROP TABLE IF EXISTS {table}')
        for view in OWNED_VIEWS:
            db.execute(f'DROP VIEW IF EXISTS {view}')
            db.execute(f'CREATE VIEW {view} AS SELECT * FROM "{view[len("bronze_"):]}"')
        for _, script, _, _ in LAYERS:
            run_script(db, script, build_id)
        checks, details = reconcile(db)
        record['reconciliation'] = json.dumps({'checks': checks, 'details': details})
        record['row_counts'] = json.dumps({t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
                                           for t in OWNED_VIEWS + OWNED_TABLES})
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise AssertionError('reconciliation failed: ' + ', '.join(failed))
        record.update(status='succeeded', finished_at=now(), error=None)
        write_log(db, record)
        db.execute('COMMIT')
        return record
    except Exception as error:
        if db.in_transaction:
            db.execute('ROLLBACK')
        record.update(status='failed', finished_at=now(), error=f'{type(error).__name__}: {error}')
        write_log(db, record)
        raise
    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python3 build_layers.py DATABASE')
    result = build(sys.argv[1])
    print('Build', result['build_id'], result['status'])
    print('Row counts:', result['row_counts'])
    print('Reconciliation:', result['reconciliation'])

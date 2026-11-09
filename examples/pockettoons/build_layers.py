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
DEFINITIONS = {'mau': '1.1', 'revenue_group': '1.1', 'funnel_and_lifecycle_group': '1.0', 'supporting_metrics': '1.1'}

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
SESSION_EXCEPTIONS_SQL = """
SELECT 'silver_resolved_sessions', session_id, 'suspicious_usable', 'ambiguous_identity_link,'
FROM silver_resolved_sessions WHERE resolution_method = 'unresolved_ambiguous'
UNION ALL
SELECT 'silver_resolved_sessions', session_id, 'suspicious_usable', 'link_user_mismatch,'
FROM silver_resolved_sessions WHERE link_user_mismatch = 1"""

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
    for reason, sql in (('ambiguous_identity_link', "resolution_method = 'unresolved_ambiguous'"),
                        ('link_user_mismatch', 'link_user_mismatch = 1')):
        n = db.execute(f'SELECT COUNT(*) FROM silver_resolved_sessions WHERE {sql}').fetchone()[0]
        if n:
            expected[('silver_resolved_sessions', 'suspicious_usable', reason)] = n
    actual = {(t, s, r): n for t, s, r, n in db.execute(
        'SELECT table_name, exception_status, exception_reason, COUNT(*) FROM silver_quality_exceptions GROUP BY 1, 2, 3')}
    checks['counts_equal_each_table'] = actual == expected
    checks['every_flagged_row_listed'] = db.execute(
        'SELECT COUNT(DISTINCT table_name || char(31) || row_key) FROM silver_quality_exceptions').fetchone()[0] == sum(
        db.execute(f"SELECT COUNT(*) FROM {table} WHERE exception_status <> 'ok'").fetchone()[0]
        for table, _ in EXCEPTION_SOURCES) + db.execute(
        "SELECT COUNT(*) FROM silver_resolved_sessions WHERE resolution_method = 'unresolved_ambiguous' "
        "OR link_user_mismatch = 1").fetchone()[0]
    summary = {f'{t}.{r}': n for (t, s, r), n in sorted(actual.items())}
    return checks, {'rows': sum(actual.values()), 'by_table_reason': summary}

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

# Objects owned by this builder. Only these are dropped and recreated.
OWNED_VIEWS = [f'bronze_{table}' for table in SOURCE_ROLES]
OWNED_TABLES = [name for name, *_ in SILVER]
OWNED_INDEXES = [index for _, _, indexes, _ in SILVER for index in indexes]


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
    for name, _, _, reconcile_table in SILVER:
        table_checks, table_details = reconcile_table(db)
        checks.update({f'{name}.{key}': ok for key, ok in table_checks.items()})
        details[name] = table_details
    return checks, details


def run_script(db, script, build_id):
    for statement in script.strip().split(';\n'):
        if statement.strip():
            db.execute(statement, {'build_id': build_id, **COVERAGE})


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
        for _, script, _, _ in SILVER:
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

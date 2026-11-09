"""Build PocketToons data layers inside an existing generated SQLite database.

Usage: python3 build_layers.py DATABASE

The builder implements the contracts in docs/data-layers/pockettoons-layer-contracts.md.
It reads source tables, never modifies them, and replaces only the objects it owns.
All layer objects are built and reconciled in one transaction: a failed build is
rolled back, recorded in layer_build_log, and leaves the previous layers in place.
Run it on a copy of a reviewed database first.
"""
from decimal import Decimal, InvalidOperation
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
DEFINITIONS = {'mau': '1.1', 'revenue_group': '1.1'}

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

# ---------------------------------------------------------------- build orchestration

SILVER = [
    ('silver_resolved_sessions', RESOLVED_SESSIONS_SQL,
     ['ix_silver_resolved_sessions_user_time', 'ix_silver_resolved_sessions_time'], reconcile_resolved_sessions),
    ('silver_payment_attempts', PAYMENT_ATTEMPTS_SQL,
     ['ix_silver_payment_attempts_success', 'ix_silver_payment_attempts_user_success'], reconcile_payment_attempts),
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
            db.execute(statement, {'build_id': build_id} if ':build_id' in statement else {})


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

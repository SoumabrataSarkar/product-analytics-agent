"""Build PocketToons data layers inside an existing generated SQLite database.

Usage: python3 build_layers.py DATABASE

The builder implements the contracts in docs/data-layers/pockettoons-layer-contracts.md.
It reads source tables, never modifies them, and replaces only the objects it owns.
All layer objects are built and reconciled in one transaction: a failed build is
rolled back, recorded in layer_build_log, and leaves the previous layers in place.
Run it on a copy of a reviewed database first.
"""
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
DEFINITIONS = {'mau': '1.1'}

# Source tables and columns the build reads; the build stops if any is missing.
REQUIRED_SOURCE = {
    'sessions': {'session_id', 'user_id', 'anonymous_id', 'platform', 'country_at_event', 'app_version',
                 'session_started_at', 'last_activity_at', 'session_ended_at'},
    'identity_links': {'identity_link_id', 'session_id', 'user_id'},
}

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

# Objects owned by this builder. Only these are dropped and recreated.
OWNED_VIEWS = [f'bronze_{table}' for table in SOURCE_ROLES]
OWNED_TABLES = ['silver_resolved_sessions']
OWNED_INDEXES = ['ix_silver_resolved_sessions_user_time', 'ix_silver_resolved_sessions_time']

BUILD_LOG_DDL = '''CREATE TABLE IF NOT EXISTS layer_build_log(
  build_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL
  CHECK(status IN ('succeeded','failed')), builder_sha256 TEXT NOT NULL, registry_sha256 TEXT NOT NULL,
  definitions TEXT NOT NULL, source_fingerprint TEXT, row_counts TEXT, reconciliation TEXT, error TEXT)'''

SILVER_RESOLVED_SESSIONS = '''
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
CREATE INDEX ix_silver_resolved_sessions_time ON silver_resolved_sessions(session_started_at);
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


def now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_schema(db):
    problems = []
    for table, columns in REQUIRED_SOURCE.items():
        present = {row[1] for row in db.execute(f'PRAGMA table_info("{table}")')}
        if not present:
            problems.append(f'missing table {table}')
        elif columns - present:
            problems.append(f'{table} missing columns {sorted(columns - present)}')
    for table in SOURCE_ROLES:
        if table not in REQUIRED_SOURCE and not db.execute(f'PRAGMA table_info("{table}")').fetchall():
            problems.append(f'missing table {table}')
    if problems:
        raise ValueError('source schema mismatch: ' + '; '.join(problems))


def fingerprint(db):
    result = {}
    for table in SOURCE_ROLES:
        rows = db.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
        result[table] = {'rows': len(rows), 'sha256': hashlib.sha256(repr(rows).encode()).hexdigest()}
    return result


def independent_recount(db):
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


def reconcile(db):
    checks = {}
    checks['bronze_views_match_source'] = all(
        db.execute(f'SELECT COUNT(*) FROM bronze_{t}').fetchone()[0] == db.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        for t in SOURCE_ROLES)
    source_rows = db.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
    silver_rows = db.execute('SELECT COUNT(*) FROM silver_resolved_sessions').fetchone()[0]
    checks['row_count_equals_source'] = silver_rows == source_rows
    checks['keys_equal_source'] = db.execute('''SELECT COUNT(*) FROM (
        SELECT session_id FROM sessions EXCEPT SELECT session_id FROM silver_resolved_sessions
        UNION ALL SELECT session_id FROM silver_resolved_sessions EXCEPT SELECT session_id FROM sessions)''').fetchone()[0] == 0
    methods = dict(db.execute('SELECT resolution_method, COUNT(*) FROM silver_resolved_sessions GROUP BY 1').fetchall())
    checks['methods_add_to_total'] = sum(methods.values()) == silver_rows
    expected, mismatches = independent_recount(db)
    checks['independent_method_recount'] = {k: methods.get(k, 0) for k in expected} == expected
    checks['independent_mismatch_recount'] = db.execute(
        'SELECT COUNT(*) FROM silver_resolved_sessions WHERE link_user_mismatch=1').fetchone()[0] == mismatches
    registry_mau = [(m, v) for m, v, _ in db.execute(load_sql('mau_monthly'), COVERAGE)]
    checks['mau_matches_registry_on_source'] = db.execute(SILVER_MAU, COVERAGE).fetchall() == registry_mau
    details = {'source_rows': source_rows, 'methods': methods, 'mismatches': mismatches}
    return checks, details


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
        for statement in SILVER_RESOLVED_SESSIONS.strip().split(';\n'):
            if statement.strip():
                db.execute(statement, {'build_id': build_id} if ':build_id' in statement else {})
        checks, details = reconcile(db)
        record['reconciliation'] = json.dumps({'checks': checks, 'details': details})
        record['row_counts'] = json.dumps({t: db.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in OWNED_VIEWS + OWNED_TABLES})
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise AssertionError('reconciliation failed: ' + ', '.join(failed))
        record.update(status='succeeded', finished_at=now(), error=None)
        db.execute('INSERT INTO layer_build_log VALUES (:build_id,:started_at,:finished_at,:status,:builder_sha256,'
                   ':registry_sha256,:definitions,:source_fingerprint,:row_counts,:reconciliation,:error)',
                   {k: record.get(k) for k in ('build_id', 'started_at', 'finished_at', 'status', 'builder_sha256',
                    'registry_sha256', 'definitions', 'source_fingerprint', 'row_counts', 'reconciliation', 'error')})
        db.execute('COMMIT')
        return record
    except Exception as error:
        if db.in_transaction:
            db.execute('ROLLBACK')
        record.update(status='failed', finished_at=now(), error=f'{type(error).__name__}: {error}')
        db.execute('INSERT INTO layer_build_log VALUES (:build_id,:started_at,:finished_at,:status,:builder_sha256,'
                   ':registry_sha256,:definitions,:source_fingerprint,:row_counts,:reconciliation,:error)',
                   {k: record.get(k) for k in ('build_id', 'started_at', 'finished_at', 'status', 'builder_sha256',
                    'registry_sha256', 'definitions', 'source_fingerprint', 'row_counts', 'reconciliation', 'error')})
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

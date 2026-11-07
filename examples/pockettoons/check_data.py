#!/usr/bin/env python3
"""Check essential invariants in the PocketToons prototype SQLite database."""
import argparse
import sqlite3

p=argparse.ArgumentParser()
p.add_argument('database')
args=p.parse_args()
db=sqlite3.connect(f'file:{args.database}?mode=ro', uri=True)
checks={
 'foreign keys': 'SELECT count(*) FROM pragma_foreign_key_check',
 'views before signup': 'SELECT count(*) FROM content_views v JOIN users u USING(user_id) WHERE v.view_started_at<u.signup_at',
 'views outside sessions': 'SELECT count(*) FROM content_views v JOIN sessions s USING(session_id) WHERE v.user_id!=s.user_id OR v.view_started_at<s.session_started_at OR v.view_ended_at>s.session_ended_at',
 'free premium views': "SELECT count(*) FROM content_views v JOIN content_episodes e USING(content_id,episode_number) WHERE v.view_type='free' AND e.access_tier!='free'",
 'subscription views without entitlement': "SELECT count(*) FROM content_views v WHERE v.view_type='sub' AND NOT EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=v.user_id AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=v.view_started_at AND (h.effective_end_at IS NULL OR h.effective_end_at>v.view_started_at))",
 'free daily quota exceeded': "SELECT count(*) FROM (SELECT user_id,date,count(*) n FROM content_views WHERE free_quota_consuming=1 GROUP BY user_id,date HAVING n>8)",
 'refunds without original': "SELECT count(*) FROM transactions r LEFT JOIN transactions t ON t.txn_id=r.related_txn_id WHERE r.type='refund' AND (t.txn_id IS NULL OR t.user_id!=r.user_id OR r.amount_usd<=0 OR t.status!='succeeded' OR t.transaction_at>r.transaction_at OR (r.transaction_subtype='ppv_refund' AND t.type!='ppv') OR (r.transaction_subtype='subscription_refund' AND t.type!='subscription'))",
 'over-refunded charges': "SELECT count(*) FROM (SELECT r.related_txn_id,sum(r.amount_usd) refunded,max(t.amount_usd) paid FROM transactions r JOIN transactions t ON t.txn_id=r.related_txn_id WHERE r.type='refund' AND r.status='succeeded' GROUP BY r.related_txn_id HAVING refunded>paid+0.001)",
 'refunds without reason': "SELECT count(*) FROM transactions WHERE (type='refund' AND (refund_reason IS NULL OR refund_reason='')) OR (type!='refund' AND refund_reason IS NOT NULL)",
 'subscription refunds without revoked access': "SELECT count(*) FROM transactions r WHERE r.transaction_subtype='subscription_refund' AND r.status='succeeded' AND (NOT EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=r.user_id AND h.source_txn_id=r.txn_id AND h.status='refunded' AND h.effective_start_at=r.transaction_at) OR EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=r.user_id AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=r.transaction_at AND (h.effective_end_at IS NULL OR h.effective_end_at>r.transaction_at)))",
 'refund allocation mismatch': "SELECT count(*) FROM transactions r WHERE r.type='refund' AND r.transaction_subtype='ppv_refund' AND abs(r.amount_usd-(SELECT coalesce(sum(a.allocated_refund_usd),0) FROM refund_content_attribution a WHERE a.refund_txn_id=r.txn_id))>0.001",
 'PPV views without entitlement': "SELECT count(*) FROM content_views v WHERE v.view_type='ppv' AND NOT EXISTS(SELECT 1 FROM transaction_content_attribution a JOIN transactions t USING(txn_id) JOIN payment_status_history p USING(txn_id) WHERE t.user_id=v.user_id AND a.content_id=v.content_id AND a.episode_number=v.episode_number AND p.status='succeeded' AND p.effective_at<=v.view_started_at AND a.entitlement_start_at<=v.view_started_at AND (a.entitlement_end_at IS NULL OR a.entitlement_end_at>v.view_started_at))",
 'views outside live availability': "SELECT count(*) FROM content_views v WHERE NOT EXISTS(SELECT 1 FROM content_availability_history h WHERE h.content_id=v.content_id AND h.episode_number=v.episode_number AND h.status='live' AND h.available_from_at<=v.view_started_at AND (h.available_until_at IS NULL OR h.available_until_at>v.view_started_at))",
 'anonymous playback': 'SELECT count(*) FROM content_views WHERE user_id IS NULL',
 'views before login': 'SELECT count(*) FROM content_views v WHERE NOT EXISTS(SELECT 1 FROM identity_links l WHERE l.session_id=v.session_id AND l.user_id=v.user_id AND l.linked_at<=v.view_started_at)',
 'transactions before signup': 'SELECT count(*) FROM transactions t JOIN users u USING(user_id) WHERE t.transaction_at<u.signup_at',
 'subscription history overlap': "SELECT count(*) FROM subscription_history a JOIN subscription_history b ON a.user_id=b.user_id AND a.subscription_period_id<b.subscription_period_id AND a.effective_start_at<coalesce(b.effective_end_at,'9999') AND b.effective_start_at<coalesce(a.effective_end_at,'9999')",
 'overlapping or too-close sessions': "SELECT count(*) FROM (SELECT user_id,session_started_at,LAG(session_ended_at) OVER (PARTITION BY user_id ORDER BY session_started_at) prev_end FROM sessions) WHERE (julianday(session_started_at)-julianday(prev_end))*86400 < 1799",
 'unreconciled raw data issues': "SELECT count(*) FROM payment_quality_review q JOIN transactions t USING(txn_id) WHERE abs(q.corrected_amount_usd-t.amount_usd)>0.001",
 'failed payments with entitlements': "SELECT count(*) FROM transactions t JOIN transaction_content_attribution a USING(txn_id) WHERE t.status!='succeeded'",
 'blocked active subscribers': "SELECT count(*) FROM user_events e JOIN subscription_history h ON h.user_id=e.user_id AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=e.event_at AND (h.effective_end_at IS NULL OR h.effective_end_at>e.event_at) WHERE e.event_name='playback_blocked'",
 'blocked valid PPV entitlements': "SELECT count(*) FROM user_events e JOIN transactions t ON t.user_id=e.user_id AND t.type='ppv' AND t.status='succeeded' JOIN transaction_content_attribution a ON a.txn_id=t.txn_id AND a.content_id=e.content_id AND a.episode_number=e.episode_number AND a.entitlement_start_at<=e.event_at AND (a.entitlement_end_at IS NULL OR a.entitlement_end_at>e.event_at) WHERE e.event_name='playback_blocked'",
 'subscriber charged PPV': "SELECT count(*) FROM transactions t JOIN subscription_history h ON h.user_id=t.user_id AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=t.transaction_at AND (h.effective_end_at IS NULL OR h.effective_end_at>t.transaction_at) WHERE t.type='ppv' AND t.status='succeeded'",
 'user events outside session': "SELECT count(*) FROM user_events e JOIN sessions s USING(session_id) WHERE e.event_at<s.session_started_at OR e.event_at>s.session_ended_at OR (e.user_id IS NOT NULL AND e.user_id!=s.user_id)",
 'refund request points to future transaction': "SELECT count(*) FROM user_events e JOIN transactions t USING(txn_id) WHERE e.event_name='refund_requested' AND e.event_at<t.transaction_at",
 'refund without prior linked request': "SELECT count(*) FROM transactions r WHERE r.type='refund' AND NOT EXISTS(SELECT 1 FROM user_events e WHERE e.event_name='refund_requested' AND e.txn_id=r.related_txn_id AND e.event_at<=r.transaction_at AND e.event_at>=(SELECT transaction_at FROM transactions t WHERE t.txn_id=r.related_txn_id))",
 'successful PPV without checkout': "WITH x AS (SELECT session_id,min(event_at) ts FROM user_events WHERE event_name='checkout_started' AND session_id IS NOT NULL GROUP BY session_id) SELECT count(*) FROM transactions t LEFT JOIN x ON x.session_id=t.session_id AND x.ts<=t.transaction_at WHERE t.type='ppv' AND t.status='succeeded' AND x.session_id IS NULL",
 'session without app open': "WITH x AS (SELECT DISTINCT session_id FROM user_events WHERE event_name='app_opened' AND session_id IS NOT NULL) SELECT count(*) FROM sessions s LEFT JOIN x ON x.session_id=s.session_id WHERE x.session_id IS NULL",
 'views without timezone': "SELECT count(*) FROM content_views WHERE event_timezone IS NULL",
}
failed=0
for name,sql in checks.items():
    n=db.execute(sql).fetchone()[0]
    print(('PASS' if n==0 else 'FAIL'),name,n)
    failed+=bool(n)
rows=db.execute("SELECT substr(session_started_at,1,7),count(DISTINCT user_id) FROM sessions GROUP BY 1 ORDER BY 1").fetchall()
q1=sum(v for _,v in rows[:3])/3; q2=sum(v for _,v in rows[3:])/3
print('Quarter-average MAU change:',round((q2/q1-1)*100,2),'%')
if len(rows)!=6 or abs(q2/q1-1.2)>0.0005: failed+=1
revenue=db.execute("SELECT substr(p.effective_at,1,7),round(sum(CASE WHEN t.type='refund' THEN -t.amount_usd ELSE t.amount_usd END),2) FROM transactions t JOIN payment_status_history p USING(txn_id) WHERE p.status='succeeded' GROUP BY 1 ORDER BY 1").fetchall()
print('Monthly net revenue:',revenue)
if len(revenue)!=6 or abs(sum(v for _,v in revenue[3:])/sum(v for _,v in revenue[:3])-1)>0.02: failed+=1
monthly=db.execute("SELECT substr(s.session_started_at,1,7),count(DISTINCT CASE WHEN u.acquisition_source='paid_social' THEN s.user_id END),count(DISTINCT CASE WHEN u.acquisition_source='unknown' THEN s.user_id END) FROM sessions s JOIN users u USING(user_id) GROUP BY 1 ORDER BY 1").fetchall()
print('Monthly paid-social active users and unknown-source users:',monthly)
# Even the adversarial assignment of every unknown Q1 user to paid social and
# no unknown Q2 user to paid social cannot erase the paid-social MAU increase.
lower_q2=sum(x[1] for x in monthly[3:]); upper_q1=sum(x[1]+x[2] for x in monthly[:3])
print('Worst-case paid-social growth:', 'PASS' if lower_q2>upper_q1 else 'FAIL')
if lower_q2<=upper_q1: failed+=1
days=db.execute('SELECT count(DISTINCT date) FROM sessions').fetchone()[0]
print('Days with sessions:',days,'of 183')
if days!=183: failed+=1
boundary=db.execute("SELECT COUNT(*) FROM user_events e WHERE e.event_name='playback_blocked' AND e.event_properties_json LIKE '%daily_free_quota_exhausted%' AND (SELECT COUNT(DISTINCT v.content_id||':'||v.episode_number) FROM content_views v WHERE v.user_id=e.user_id AND v.date=substr(e.event_at,1,10) AND v.view_type='free' AND v.view_started_at<e.event_at)=8").fetchone()[0]
print('Verified quota boundary journeys:',boundary)
if boundary<1: failed+=1
nonbuyer=db.execute("SELECT count(*) FROM user_events e WHERE e.event_name='paywall_viewed' AND NOT EXISTS(SELECT 1 FROM transactions t WHERE t.session_id=e.session_id AND t.type='ppv' AND t.status='succeeded')").fetchone()[0]
print('Paywall views without a successful PPV in session:',nonbuyer)
if nonbuyer<1: failed+=1
print('30-day cohort comparison (complete observation windows):')
cohorts=db.execute("""SELECT CASE WHEN substr(u.signup_at,1,7) IN ('2026-05','2026-06') THEN 'May-June' ELSE 'July-August' END cohort,
count(*) users,sum(EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.user_id
AND t.transaction_subtype='subscription_initial' AND t.status='succeeded'
AND julianday(t.transaction_at)>=julianday(u.signup_at) AND julianday(t.transaction_at)<julianday(u.signup_at)+30)) payers
FROM users u WHERE substr(u.signup_at,1,7) IN ('2026-05','2026-06','2026-07','2026-08')
AND julianday(u.signup_at)+30<=julianday('2026-10-01') GROUP BY 1""").fetchall()
for name,users,payers in cohorts: print(name,users,payers,round(payers/users*100,2),'%')
if len(cohorts)!=2: failed+=1
else:
    rates={name:payers/users for name,users,payers in cohorts}
    if rates['May-June']<=rates['July-August']+0.003: failed+=1
browse=db.execute("WITH v AS (SELECT DISTINCT session_id FROM content_views) SELECT count(*) FROM sessions s LEFT JOIN v USING(session_id) WHERE v.session_id IS NULL").fetchone()[0]
print('Browsing-only sessions:',browse)
if browse<1: failed+=1
raise SystemExit(1 if failed else 0)

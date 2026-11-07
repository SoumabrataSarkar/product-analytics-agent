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
raise SystemExit(1 if failed else 0)

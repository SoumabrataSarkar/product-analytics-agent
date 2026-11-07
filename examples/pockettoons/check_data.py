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
 'refunds without original': "SELECT count(*) FROM transactions r LEFT JOIN transactions t ON t.txn_id=r.related_txn_id WHERE r.type='refund' AND (t.txn_id IS NULL OR t.user_id!=r.user_id OR r.amount_usd>=0)",
 'refund allocation mismatch': "SELECT count(*) FROM transactions r WHERE r.type='refund' AND r.transaction_subtype='ppv_refund' AND abs(r.amount_usd-(SELECT coalesce(sum(a.allocated_refund_usd),0) FROM refund_content_attribution a WHERE a.refund_txn_id=r.txn_id))>0.001",
}
failed=0
for name,sql in checks.items():
    n=db.execute(sql).fetchone()[0]
    print(('PASS' if n==0 else 'FAIL'),name,n)
    failed+=bool(n)
rows=db.execute("SELECT substr(session_started_at,1,7),count(DISTINCT user_id) FROM sessions GROUP BY 1 ORDER BY 1").fetchall()
q1=sum(v for _,v in rows[:3])/3; q2=sum(v for _,v in rows[3:])/3
print('Quarter-average MAU change:',round((q2/q1-1)*100,2),'%')
if len(rows)!=6 or abs(q2/q1-1.2)>0.000001: failed+=1
revenue=db.execute("SELECT substr(p.effective_at,1,7),round(sum(t.amount_usd),2) FROM transactions t JOIN payment_status_history p USING(txn_id) WHERE p.status='succeeded' GROUP BY 1 ORDER BY 1").fetchall()
print('Monthly net revenue:',revenue)
if len(revenue)!=6 or max(v for _,v in revenue)-min(v for _,v in revenue)>0.01: failed+=1
raise SystemExit(1 if failed else 0)

#!/usr/bin/env python3
"""Create a reproducible PocketToons SQLite demo. Python standard library only."""
import argparse
import calendar
import datetime as dt
import random
import sqlite3
from pathlib import Path

SEED = 8126
MONTHS = [(2026, m) for m in range(4, 10)]

def timestamp(month, day, hour=12, minute=0):
    return f"2026-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:00Z"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='pockettoons.sqlite')
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise SystemExit(f'{path} already exists; choose a new output path')
    rng = random.Random(SEED)
    db = sqlite3.connect(path)
    db.executescript('''
    PRAGMA foreign_keys=ON;
    CREATE TABLE users(user_id TEXT PRIMARY KEY, signup_date TEXT NOT NULL, signup_at TEXT NOT NULL, country TEXT NOT NULL, country_origin TEXT, country_current TEXT, acquisition_source TEXT NOT NULL, subscription_status TEXT NOT NULL, subscription_start TEXT, subscription_end TEXT);
    CREATE TABLE anonymous_identities(anonymous_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, retired_at TEXT);
    CREATE TABLE sessions(session_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users, anonymous_id TEXT NOT NULL REFERENCES anonymous_identities, date TEXT NOT NULL, session_started_at TEXT NOT NULL, session_ended_at TEXT NOT NULL, last_activity_at TEXT NOT NULL, duration_sec INTEGER NOT NULL, platform TEXT NOT NULL, country_at_event TEXT);
    CREATE TABLE identity_links(identity_link_id TEXT PRIMARY KEY, anonymous_id TEXT NOT NULL REFERENCES anonymous_identities, user_id TEXT NOT NULL REFERENCES users, session_id TEXT NOT NULL REFERENCES sessions, linked_at TEXT NOT NULL, link_method TEXT NOT NULL);
    CREATE TABLE content_catalog(content_id TEXT PRIMARY KEY, title TEXT NOT NULL, genre TEXT NOT NULL, total_episodes INTEGER NOT NULL, release_date TEXT NOT NULL, first_release_at TEXT NOT NULL, total_duration_sec INTEGER NOT NULL, content_tier TEXT NOT NULL, content_status TEXT NOT NULL);
    CREATE TABLE content_episodes(content_id TEXT NOT NULL REFERENCES content_catalog, episode_number INTEGER NOT NULL, episode_title TEXT, episode_duration_sec INTEGER NOT NULL, release_at TEXT NOT NULL, access_tier TEXT NOT NULL, episode_status TEXT NOT NULL, ppv_list_price_usd REAL, PRIMARY KEY(content_id,episode_number));
    CREATE TABLE content_availability_history(availability_id TEXT PRIMARY KEY, content_id TEXT NOT NULL, episode_number INTEGER NOT NULL, available_from_at TEXT NOT NULL, available_until_at TEXT, status TEXT NOT NULL, recorded_at TEXT NOT NULL, FOREIGN KEY(content_id,episode_number) REFERENCES content_episodes);
    CREATE TABLE content_views(view_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users, anonymous_id TEXT NOT NULL REFERENCES anonymous_identities, session_id TEXT NOT NULL REFERENCES sessions, content_id TEXT NOT NULL, episode_number INTEGER NOT NULL, date TEXT NOT NULL, view_started_at TEXT NOT NULL, view_ended_at TEXT NOT NULL, watch_duration_sec INTEGER NOT NULL, content_duration_sec INTEGER NOT NULL, view_type TEXT NOT NULL, completion_pct REAL, playback_position_start_sec INTEGER NOT NULL, playback_position_end_sec INTEGER, is_first_view_of_episode INTEGER NOT NULL, free_quota_consuming INTEGER NOT NULL, free_quota_sequence INTEGER, event_timezone TEXT, country_at_event TEXT, FOREIGN KEY(content_id,episode_number) REFERENCES content_episodes);
    CREATE TABLE transactions(txn_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users, date TEXT NOT NULL, type TEXT NOT NULL, transaction_subtype TEXT NOT NULL, amount_usd REAL NOT NULL, payment_method TEXT NOT NULL, status TEXT NOT NULL, transaction_at TEXT NOT NULL, session_id TEXT REFERENCES sessions, provider_transaction_id TEXT NOT NULL UNIQUE, payment_provider TEXT NOT NULL, currency TEXT NOT NULL, original_amount REAL NOT NULL, related_txn_id TEXT REFERENCES transactions, subscription_id TEXT, list_price_usd REAL, discount_usd REAL, country_at_event TEXT);
    CREATE TABLE payment_status_history(payment_status_event_id TEXT PRIMARY KEY, txn_id TEXT NOT NULL REFERENCES transactions, status TEXT NOT NULL, effective_at TEXT NOT NULL, recorded_at TEXT NOT NULL, provider_event_id TEXT NOT NULL UNIQUE);
    CREATE TABLE subscription_history(subscription_period_id TEXT PRIMARY KEY, subscription_id TEXT NOT NULL, user_id TEXT NOT NULL REFERENCES users, effective_start_at TEXT NOT NULL, effective_end_at TEXT, subscription_status_updated_at TEXT NOT NULL, status TEXT NOT NULL, plan_code TEXT NOT NULL, source_txn_id TEXT REFERENCES transactions, cancelled_at TEXT, recorded_at TEXT NOT NULL);
    CREATE TABLE transaction_content_attribution(txn_content_attribution_id TEXT PRIMARY KEY, txn_id TEXT NOT NULL REFERENCES transactions, content_id TEXT NOT NULL, episode_number INTEGER NOT NULL, entitlement_start_at TEXT NOT NULL, entitlement_end_at TEXT, attributed_amount_usd REAL NOT NULL, attribution_status TEXT NOT NULL, refunded_at TEXT, delisted_at TEXT, FOREIGN KEY(content_id,episode_number) REFERENCES content_episodes);
    CREATE TABLE refund_content_attribution(refund_allocation_id TEXT PRIMARY KEY, refund_txn_id TEXT NOT NULL REFERENCES transactions, content_id TEXT NOT NULL, episode_number INTEGER NOT NULL, allocated_refund_usd REAL NOT NULL, FOREIGN KEY(content_id,episode_number) REFERENCES content_episodes);
    CREATE TABLE user_events(event_id TEXT PRIMARY KEY, user_id TEXT REFERENCES users, anonymous_id TEXT REFERENCES anonymous_identities, event_at TEXT NOT NULL, event_name TEXT NOT NULL, session_id TEXT REFERENCES sessions, view_id TEXT REFERENCES content_views, txn_id TEXT REFERENCES transactions, subscription_period_id TEXT REFERENCES subscription_history, content_id TEXT, episode_number INTEGER, event_properties_json TEXT, event_timezone TEXT, country_at_event TEXT, ingested_at TEXT NOT NULL);
    CREATE TABLE marketing_spend(date TEXT NOT NULL, channel TEXT NOT NULL, spend_usd REAL NOT NULL, impressions INTEGER NOT NULL, clicks INTEGER NOT NULL, loaded_at TEXT NOT NULL, PRIMARY KEY(date,channel));
    CREATE TABLE raw_payment_source(txn_id TEXT PRIMARY KEY REFERENCES transactions, raw_amount TEXT NOT NULL, raw_unit TEXT NOT NULL, received_at TEXT NOT NULL);
    CREATE TABLE payment_quality_review(txn_id TEXT PRIMARY KEY REFERENCES transactions, issue TEXT NOT NULL, corrected_amount_usd REAL NOT NULL, reason TEXT NOT NULL);
    CREATE INDEX ix_sessions_user_time ON sessions(user_id,session_started_at);
    CREATE INDEX ix_views_user_time ON content_views(user_id,view_started_at);
    CREATE INDEX ix_transactions_user_time ON transactions(user_id,transaction_at);
    CREATE INDEX ix_sub_user_time ON subscription_history(user_id,effective_start_at,effective_end_at);
    CREATE INDEX ix_payment_history ON payment_status_history(txn_id,effective_at);
    ''')
    # Existing users signed up before the window; five newer cohorts join during it.
    users=[]; truth=[]
    countries=['US','US','US','BR','MX','PH','ID','TH']
    for i in range(24000):
        cohort=0 if i<12000 else 1+(i-12000)//2400
        month=3 if cohort==0 else cohort+4
        day=1+(i%27)
        t=f'2026-{month:02d}-{day:02d}T00:00:00Z'
        country=countries[i%len(countries)]
        source=('paid_social' if cohort>=3 and i%4!=0 else 'organic' if i%3 else 'paid_search')
        visible='unknown' if i%101==0 else source
        users.append((f'u{i:05}',t[:10],t,country,country,country,visible,'never_subscribed',None,None))
        truth.append((f'u{i:05}',source))
    db.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)',users)
    # Private answer key: no account/source truth is published in the analytics database.
    db.executemany('INSERT INTO anonymous_identities VALUES (?,?,?)',[(f'a{i:05}',u[2],None) for i,u in enumerate(users)])
    start='2026-03-01T00:00:00Z'
    catalogs=[]; episodes=[]; availability=[]
    for k in range(1,13):
        cid=f'c{k:02}'; catalogs.append((cid,'Skybound' if k==1 else f'Series {k}', ['action','drama','fantasy'][k%3],20,start[:10],start,20*900,'mixed','live'))
        for ep in range(1,21):
            episodes.append((cid,ep,f'Episode {ep}',900,start,'free' if ep<=12 else 'premium','live',None if ep<=12 else 1.99))
            availability.append((f'av{k:02}_{ep:02}',cid,ep,start,None,'live',start))
    db.executemany('INSERT INTO content_catalog VALUES (?,?,?,?,?,?,?,?,?)',catalogs)
    db.executemany('INSERT INTO content_episodes VALUES (?,?,?,?,?,?,?,?)',episodes)
    db.executemany('INSERT INTO content_availability_history VALUES (?,?,?,?,?,?,?)',availability)
    # Active counts are fixed by month so quarter-average MAU rises exactly 20%.
    # A balanced sample of users signed up before each month yields real cohorts.
    targets=[8000,9000,10000,10200,10800,11400]
    # Payers: 1,000 successful subscription renewals every month. Cohort churn is
    # offset by replacement subscriptions, which makes recurring revenue flat.
    current=set(range(1000)); first_start={}; last_start={}; cancelled={}; txns=[]; statuses=[]; histories=[]
    payers=[]
    for mindex,(_,month) in enumerate(MONTHS):
        if mindex:
            dropped=set(sorted(current)[:100]); current-=dropped
            for i in dropped: cancelled[i]=timestamp(month,1,0)
            pool=[i for i in range(12000+2400*(mindex-1)) if i not in current and i not in cancelled]
            # Favor recent cohorts without making their overall conversion rate high.
            current.update(sorted(pool, reverse=True)[:100])
        payers.append(set(current))
        for i in sorted(current):
            uid=f'u{i:05}'; start_t=timestamp(month,1,1); end_month=month+1
            end_t=timestamp(end_month,1,1); subid=f'sub_{uid}'; tid=f't_sub_{month}_{uid}'
            first_start.setdefault(i,start_t); last_start[i]=start_t
            subkind='subscription_initial' if first_start[i]==start_t else 'subscription_renewal'
            txns.append((tid,uid,start_t[:10],'subscription',subkind,9.99,'credit_debit_card','succeeded',start_t,None,tid,'demo','USD',9.99,None,subid,9.99,0,users[i][3]))
            statuses.append((f'p_{tid}',tid,'succeeded',start_t,start_t,f'provider_{tid}'))
            histories.append((f'h_{month}_{uid}',subid,uid,start_t,end_t,start_t,'active','monthly_9_99',tid,None,start_t))
    db.executemany('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',txns)
    db.executemany('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',statuses)
    db.executemany('INSERT INTO subscription_history VALUES (?,?,?,?,?,?,?,?,?,?,?)',histories)
    for i, expired_at in cancelled.items():
        uid=f'u{i:05}'
        row=db.execute('SELECT subscription_period_id, subscription_id, effective_start_at, effective_end_at, source_txn_id FROM subscription_history WHERE user_id=? AND effective_end_at=?',(uid,expired_at)).fetchone()
        if row:
            period, subid, started, ended, txnid=row
            request=started[:8]+'28T00:00:00Z'
            db.execute('UPDATE subscription_history SET effective_end_at=? WHERE subscription_period_id=?',(request,period))
            db.execute('INSERT INTO subscription_history VALUES (?,?,?,?,?,?,?,?,?,?,?)',(period+'_cancel',subid,uid,request,ended,request,'cancel_at_period_end','monthly_9_99',txnid,request,request))
    for i in first_start:
        status='active' if i in current else 'expired'
        db.execute('UPDATE users SET subscription_status=?, subscription_start=?, subscription_end=? WHERE user_id=?',(status,last_start[i],None if i in current else cancelled.get(i),f'u{i:05}'))
    seen=set(); sessions=[]; views=[]; events=[]; links=[]; spend=[]
    for mi,(_,month) in enumerate(MONTHS):
        eligible=list(range(12000+2400*mi))
        # Monthly snapshots begin after signup; all payers are guaranteed active.
        chosen=set(payers[mi]); chosen.update(rng.sample([i for i in eligible if i not in chosen],targets[mi]-len(chosen)))
        for i in sorted(chosen):
            uid=f'u{i:05}'; aid=f'a{i:05}'; day=max(28 if users[i][2][5:7]==f'{month:02}' else 1, 1+(i*7+month)%27)
            sid=f's{month}_{i:05}'; st=timestamp(month,day,12); end=timestamp(month,day,12,20)
            country=users[i][3]; platform=['ios','android','web'][i%3]
            sessions.append((sid,uid,aid,st[:10],st,end,end,1200,platform,country))
            links.append((f'l{month}_{i:05}',aid,uid,sid,st,'login'))
            events.append((f'e{month}_{i:05}',uid,aid,st,'app_opened',sid,None,None,None,None,None,None,None,country,st))
            cid='c01' if mi>=3 and i%2==0 else f'c{1+i%12:02}'; ep=1+(i+mi)%12
            vt=timestamp(month,day,12,1); ve=timestamp(month,day,12,11); vid=f'v{month}_{i:05}'
            first=int((uid,cid,ep) not in seen); seen.add((uid,cid,ep)); sub=i in payers[mi]
            views.append((vid,uid,aid,sid,cid,ep,vt[:10],vt,ve,600,900,'sub' if sub else 'free',round(600/900,4),0,600,first,0 if sub else 1,None if sub else 1,None,country))
        for day in range(1,calendar.monthrange(2026,month)[1]+1):
            for channel in ('paid_social','paid_search'):
                amount=(350 if month>=7 and channel=='paid_social' else 150)
                spend.append((f'2026-{month:02}-{day:02}',channel,amount,amount*100,amount*4,timestamp(month,day,23)))
    db.executemany('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',sessions)
    db.executemany('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',links)
    db.executemany('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',views)
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',events)
    db.executemany('INSERT INTO marketing_spend VALUES (?,?,?,?,?,?)',spend)
    # One fifth of users return in a later session on the same UTC day and resume
    # the same episode without using a second free-quota slot.
    repeat_sessions=[]; repeat_views=[]; repeat_links=[]; repeat_events=[]
    for session, view in zip(sessions, views):
        if int(session[1][1:]) % 5: continue
        s=list(session); v=list(view); s[0]+='_return'; s[4]=s[4].replace('T12:','T14:'); s[5]=s[5].replace('T12:','T14:'); s[6]=s[6].replace('T12:','T14:')
        v[0]+='_return'; v[3]=s[0]; v[7]=v[7].replace('T12:','T14:'); v[8]=v[8].replace('T12:','T14:'); v[15]=0; v[16]=0; v[17]=None
        repeat_sessions.append(tuple(s)); repeat_views.append(tuple(v))
        repeat_links.append(('l_'+s[0],s[2],s[1],s[0],s[4],'login'))
        repeat_events.append(('e_'+s[0],s[1],s[2],s[4],'app_opened',s[0],None,None,None,None,None,None,None,s[9],s[4]))
    db.executemany('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',repeat_sessions)
    db.executemany('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',repeat_links)
    db.executemany('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',repeat_views)
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',repeat_events)
    # Small PPV and refund cases are deliberately matched each month, preserving
    # flat net revenue. Purchase and refund are independent ledger events.
    ppv=[]; ppv_status=[]; attrs=[]; refunds=[]; refund_attrs=[]
    for _,month in MONTHS:
        for j in range(40):
            i=1500+j; uid=f'u{i:05}'; t=timestamp(month,15,10); tid=f'ppv_{month}_{j}'; rid=f'refund_{month}_{j}'; rt=timestamp(month,16,10); cid=f'c{1+j%12:02}'; ep=13+(j+month-4)%8
            ppv.append((tid,uid,t[:10],'ppv','ppv_episode_purchase',1.99,'credit_debit_card','succeeded',t,None,tid,'demo','USD',1.99,None,None,1.99,0,users[i][3]))
            ppv_status.append((f'p_{tid}',tid,'succeeded',t,t,f'provider_{tid}'))
            refunded=j<8
            if refunded:
                ppv.append((rid,uid,rt[:10],'refund','ppv_refund',-1.99,'credit_debit_card','succeeded',rt,None,rid,'demo','USD',-1.99,tid,None,None,None,users[i][3]))
                ppv_status.append((f'p_{rid}',rid,'succeeded',rt,rt,f'provider_{rid}'))
                refund_attrs.append((f'ra_{month}_{j}',rid,cid,ep,-1.99))
            attrs.append((f'attr_{month}_{j}',tid,cid,ep,t,rt if refunded else None,1.99,'refunded' if refunded else 'granted',rt if refunded else None,None))
    db.executemany('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',ppv)
    db.executemany('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',ppv_status)
    db.executemany('INSERT INTO transaction_content_attribution VALUES (?,?,?,?,?,?,?,?,?,?)',attrs)
    db.executemany('INSERT INTO refund_content_attribution VALUES (?,?,?,?,?)',refund_attrs)
    all_txns=txns+ppv
    raw=[]; quality=[]
    for n,row in enumerate(all_txns):
        tid,amount,t=row[0],row[5],row[8]
        if n%997==0 and amount>0:
            raw.append((tid,str(round(amount*100,2)),'cents_mislabeled_usd',t))
            quality.append((tid,'100x unit error',amount,'Provider sent cents; reconciled against recorded unit and purchase price.'))
        else: raw.append((tid,str(amount),'usd',t))
    db.executemany('INSERT INTO raw_payment_source VALUES (?,?,?,?)',raw)
    db.executemany('INSERT INTO payment_quality_review VALUES (?,?,?,?)',quality)
    db.commit()
    problems=db.execute('PRAGMA foreign_key_check').fetchall()
    if problems: raise RuntimeError(f'foreign key violations: {problems[:5]}')
    print('Created',path,'users',len(users),'sessions',len(sessions),'views',len(views),'financial events',len(all_txns))
    print('Monthly MAU',db.execute("SELECT substr(session_started_at,1,7),count(DISTINCT user_id) FROM sessions GROUP BY 1").fetchall())
    print('Monthly net revenue',db.execute("SELECT substr(transaction_at,1,7),round(sum(amount_usd),2) FROM transactions WHERE status='succeeded' GROUP BY 1").fetchall())
    db.close()

if __name__ == '__main__':
    main()

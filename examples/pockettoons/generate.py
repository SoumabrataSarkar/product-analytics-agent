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

def offset(ts, seconds):
    return (dt.datetime.strptime(ts, '%Y-%m-%dT%H:%M:%SZ') + dt.timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%SZ')

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
    CREATE TABLE raw_payment_source(txn_id TEXT PRIMARY KEY REFERENCES transactions, raw_amount NOT NULL, raw_unit TEXT NOT NULL, received_at TEXT NOT NULL);
    CREATE TABLE payment_quality_review(txn_id TEXT PRIMARY KEY REFERENCES transactions, issue TEXT NOT NULL, corrected_amount_usd REAL NOT NULL, reason TEXT NOT NULL);
    CREATE INDEX ix_sessions_user_time ON sessions(user_id,session_started_at);
    CREATE INDEX ix_views_user_time ON content_views(user_id,view_started_at);
    CREATE INDEX ix_transactions_user_time ON transactions(user_id,transaction_at);
    CREATE INDEX ix_sub_user_time ON subscription_history(user_id,effective_start_at,effective_end_at);
    CREATE INDEX ix_payment_history ON payment_status_history(txn_id,effective_at);
    CREATE INDEX ix_identity_session ON identity_links(session_id,user_id,linked_at);
    ''')
    # Existing users signed up before the window; five newer cohorts join during it.
    users=[]; truth=[]
    cohort_sizes=[12000,2201,2653,2477,2949,1720]
    cohort_ends=[]
    for size in cohort_sizes: cohort_ends.append((cohort_ends[-1] if cohort_ends else 0)+size)
    countries=['US','US','US','BR','MX','PH','ID','TH']
    for i in range(24000):
        cohort=next(k for k,end in enumerate(cohort_ends) if i<end)
        month=3 if cohort==0 else cohort+4
        day=1+(i%27)
        t=f'2026-{month:02d}-{day:02d}T00:00:00Z'
        country=rng.choice(countries)
        source=rng.choices(['organic','paid_search','paid_social'],weights=([50,27,23] if cohort<3 else [18,17,65]))[0]
        visible='unknown' if i%101==0 else source
        users.append((f'u{i:05}',t[:10],t,country,country,country,visible,'never_subscribed',None,None))
        truth.append((f'u{i:05}',source))
    db.executemany('INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?)',users)
    # Private answer key: no account/source truth is published in the analytics database.
    db.executemany('INSERT INTO anonymous_identities VALUES (?,?,?)',[(f'a{i:05}',u[2],None) for i,u in enumerate(users)])
    start='2026-03-01T00:00:00Z'
    catalogs=[]; episodes=[]; availability=[]
    episode_counts=[24,32,21,37,28,34,22,39,26,31,23,20]
    for k in range(1,13):
        count=episode_counts[k-1]
        cid=f'c{k:02}'; catalogs.append((cid,'Skybound' if k==1 else f'Series {k}', ['action','drama','fantasy'][k%3],count,start[:10],start,count*900,'mixed','live'))
        for ep in range(1,count+1):
            episodes.append((cid,ep,f'Episode {ep}',900,start,'free' if ep<=12 else 'premium','live',None if ep<=12 else 1.99))
            availability.append((f'av{k:02}_{ep:02}',cid,ep,start,None,'live',start))
    db.executemany('INSERT INTO content_catalog VALUES (?,?,?,?,?,?,?,?,?)',catalogs)
    db.executemany('INSERT INTO content_episodes VALUES (?,?,?,?,?,?,?,?)',episodes)
    db.executemany('INSERT INTO content_availability_history VALUES (?,?,?,?,?,?,?)',availability)
    # Non-rounded targets retain approximately 20% quarter-average MAU growth.
    # A balanced sample of users signed up before each month yields real cohorts.
    targets=[7937,9134,9976,10138,10871,11447]
    # Monthly paying counts vary, while cohort churn is largely offset by new subscribers.
    payer_targets=[981,1024,995,1012,978,1011]
    current=set(range(payer_targets[0])); first_start={}; last_start={}; cancelled={}; txns=[]; statuses=[]; histories=[]
    payers=[]
    for mindex,(_,month) in enumerate(MONTHS):
        if mindex:
            dropped=set(sorted(current)[:100]); current-=dropped
            for i in dropped: cancelled[i]=timestamp(month,1+(i*7)%25,1)
            pool=[i for i in range(cohort_ends[mindex-1]) if i not in current and i not in cancelled]
            # Later cohorts convert less, with replacements also drawn from older users.
            need=payer_targets[mindex]-len(current)
            if mindex>=4:
                recent=sorted(pool,reverse=True)[:max(1,int(need*0.30))]
                old=[i for i in pool if i<cohort_ends[0] and i not in recent]
                current.update(recent+old[:need-len(recent)])
            else:
                current.update(sorted(pool, reverse=True)[:need])
        payers.append(set(current))
        for i in sorted(current):
            uid=f'u{i:05}'; bill_day=1+(i*7)%25; start_t=timestamp(month,bill_day,1); end_month=month+1
            end_t=timestamp(end_month,bill_day,1); subid=f'sub_{uid}'; tid=f't_sub_{month}_{uid}'
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
            request=offset(started,24*3600)
            db.execute('UPDATE subscription_history SET effective_end_at=? WHERE subscription_period_id=?',(request,period))
            db.execute('INSERT INTO subscription_history VALUES (?,?,?,?,?,?,?,?,?,?,?)',(period+'_cancel',subid,uid,request,ended,request,'cancel_at_period_end','monthly_9_99',txnid,request,request))
    for i in first_start:
        status='active' if i in current else 'expired'
        db.execute('UPDATE users SET subscription_status=?, subscription_start=?, subscription_end=? WHERE user_id=?',(status,last_start[i],None if i in current else cancelled.get(i),f'u{i:05}'))
    seen=set(); sessions=[]; views=[]; view_pairs=[]; events=[]; links=[]; spend=[]
    zones={'US':'America/New_York','BR':'America/Sao_Paulo','MX':'America/Mexico_City','PH':'Asia/Manila','ID':'Asia/Jakarta','TH':'Asia/Bangkok'}
    for mi,(_,month) in enumerate(MONTHS):
        eligible=list(range(cohort_ends[mi]))
        # Monthly snapshots begin after signup; all payers are guaranteed active.
        chosen=set(payers[mi]); chosen.update(rng.sample([i for i in eligible if i not in chosen],targets[mi]-len(chosen)))
        for i in sorted(chosen):
            uid=f'u{i:05}'; aid=f'a{i:05}'
            first_day=int(users[i][2][8:10]) if users[i][2][5:7]==f'{month:02}' else 1
            day=rng.randint(first_day,calendar.monthrange(2026,month)[1])
            sid=f's{month}_{i:05}'; st=timestamp(month,day,rng.randint(8,18),rng.randint(0,59)); duration=rng.randint(1200,2280); end=offset(st,duration)
            country=users[i][3]; platform=['ios','android','web'][i%3]
            sessions.append((sid,uid,aid,st[:10],st,end,end,duration,platform,country))
            links.append((f'l{month}_{i:05}',aid,uid,sid,st,'login'))
            events.append((f'e{month}_{i:05}',uid,aid,st,'app_opened',sid,None,None,None,None,None,None,None,country,st))
            # A real app visit can stop at browsing, without any playback.
            if rng.random()<0.09:
                browse_at=offset(st,40)
                events.append((f'browse_only_{sid}',uid,aid,browse_at,'episode_detail_viewed',sid,None,None,None,'c01',1,None,zones[country],country,browse_at))
                continue
            cid='c01' if mi>=3 and i%2==0 else f'c{1+i%12:02}'; ep=1+(i+mi)%12
            vt=offset(st,60); watched=rng.randint(240,600); ve=offset(vt,watched); vid=f'v{month}_{i:05}'
            first=int((uid,cid,ep) not in seen); seen.add((uid,cid,ep))
            sub=bool(db.execute("SELECT 1 FROM subscription_history WHERE user_id=? AND status IN ('active','cancel_at_period_end') AND effective_start_at<=? AND effective_end_at>? LIMIT 1",(uid,vt,vt)).fetchone())
            view=(vid,uid,aid,sid,cid,ep,vt[:10],vt,ve,watched,900,'sub' if sub else 'free',round(watched/900,4),0,watched,first,0 if sub else 1,None if sub else 1,zones[country],country)
            views.append(view); view_pairs.append((sessions[-1],view))
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
    for session, view in view_pairs:
        if int(session[1][1:]) % 5: continue
        s=list(session); v=list(view); s[0]+='_return'; s[4]=offset(s[4],7200); s[5]=offset(s[5],7200); s[6]=offset(s[6],7200)
        v[0]+='_return'; v[3]=s[0]; v[7]=offset(v[7],7200); v[13]=v[14]; v[9]=min(900-v[13],rng.randint(120,300)); v[14]=v[13]+v[9]; v[8]=offset(v[7],v[9]); v[12]=round(v[9]/900,4); v[15]=0; v[16]=0; v[17]=None
        repeat_sessions.append(tuple(s)); repeat_views.append(tuple(v))
        repeat_links.append(('l_'+s[0],s[2],s[1],s[0],s[4],'login'))
        repeat_events.append(('e_'+s[0],s[1],s[2],s[4],'app_opened',s[0],None,None,None,None,None,None,None,s[9],s[4]))
    db.executemany('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',repeat_sessions)
    db.executemany('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',repeat_links)
    db.executemany('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',repeat_views)
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',repeat_events)
    # Half of sessions continue into another free-tier episode in the same visit.
    # The original view list stays aligned with sessions for the repeat logic.
    extra_views=[]
    for s,v in view_pairs:
        if int(s[1][1:])%2: continue
        w=list(v); w[0]+='_next'; w[5]=(v[5]%12)+1
        w[7]=offset(v[8],60); w[9]=rng.randint(180,480); w[8]=offset(w[7],w[9])
        w[12]=round(w[9]/900,4); w[14]=w[9]
        w[15]=int((w[1],w[4],w[5]) not in seen); seen.add((w[1],w[4],w[5]))
        w[16]=0 if w[11]=='sub' else 1; w[17]=None if w[11]=='sub' else 2
        extra_views.append(tuple(w))
    db.executemany('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',extra_views)
    # Purchase and refund volumes vary each month, preserving near-flat quarterly net revenue.
    purchase_targets=[43,46,37,43,38,43]
    refund_targets=[6,9,8,7,8,6]
    ppv=[]; ppv_status=[]; attrs=[]; refund_attrs=[]; ppv_sessions=[]; ppv_views=[]; ppv_links=[]; ppv_events=[]; ppv_refund_events=[]
    for month_index,(_,month) in enumerate(MONTHS):
        candidates=db.execute("""SELECT DISTINCT s.user_id FROM sessions s JOIN users u USING(user_id)
          WHERE substr(s.session_started_at,6,2)=? AND u.signup_at<? AND NOT EXISTS
          (SELECT 1 FROM subscription_history h WHERE h.user_id=s.user_id
           AND h.status IN ('active','cancel_at_period_end')
           AND h.effective_start_at<? AND h.effective_end_at>?) ORDER BY s.user_id LIMIT 50""",
          (f'{month:02}',timestamp(month,1,0),timestamp(month+1,1,0),timestamp(month,1,0))).fetchall()
        if month==4:
            # Keep one purchaser active again in September for a delist/relist journey.
            both=db.execute("""SELECT DISTINCT s.user_id FROM sessions s JOIN users u USING(user_id)
              WHERE substr(s.session_started_at,6,2)='04' AND EXISTS
              (SELECT 1 FROM sessions later WHERE later.user_id=s.user_id AND substr(later.session_started_at,6,2)='09')
              AND NOT EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=s.user_id
              AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<? AND h.effective_end_at>?)
              AND NOT EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=s.user_id
              AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=? AND h.effective_end_at>?)
              ORDER BY s.user_id LIMIT 1""",(timestamp(5,1,0),timestamp(4,1,0),timestamp(9,25,10),timestamp(9,25,10))).fetchone()
            assert both
            candidates=[x for x in candidates if x!=both]
            candidates.insert(39,both)
        assert len(candidates)>=purchase_targets[month_index]
        for j in range(purchase_targets[month_index]):
            uid=candidates[j][0]; i=int(uid[1:]); aid=f'a{i:05}'; t=timestamp(month,rng.randint(2,24),rng.randint(8,20),rng.randint(0,35)); tid=f'ppv_{month}_{j}'; rid=f'refund_{month}_{j}'; rt=offset(t,rng.randint(1,4)*86400); cid=f'c{1+j%12:02}'; ep=13+(j+month-4)%8
            while db.execute('SELECT 1 FROM sessions WHERE user_id=? AND session_started_at<? AND session_ended_at>? LIMIT 1',
                             (uid,offset(t,1200+1800),offset(t,-1920))).fetchone():
                t=timestamp(month,rng.randint(2,24),rng.randint(8,20),rng.randint(0,35))
                rt=offset(t,rng.randint(1,4)*86400)
            if month==4 and j==39: cid,ep='c12',20
            sid=f's_ppv_{month}_{j}'; start_session=offset(t,-120); end=offset(t,1200); vt=offset(t,120); ve=offset(vt,600); vid=f'v_ppv_{month}_{j}'
            country=users[i][3]; wall=offset(t,-90); checkout=offset(t,-30)
            ppv_sessions.append((sid,uid,aid,t[:10],start_session,end,end,1320,['ios','android','web'][i%3],country))
            ppv_links.append((f'l_{sid}',aid,uid,sid,start_session,'login'))
            ppv_views.append((vid,uid,aid,sid,cid,ep,vt[:10],vt,ve,600,900,'ppv',round(600/900,4),0,600,1,0,None,zones[country],country))
            ppv_events.append((f'open_{sid}',uid,aid,start_session,'app_opened',sid,None,None,None,None,None,None,zones[country],country,start_session))
            ppv_events.append((f'paywall_{sid}',uid,aid,wall,'paywall_viewed',sid,None,None,None,cid,ep,None,zones[country],country,wall))
            ppv_events.append((f'checkout_{sid}',uid,aid,checkout,'checkout_started',sid,None,None,None,cid,ep,None,zones[country],country,checkout))
            ppv.append((tid,uid,t[:10],'ppv','ppv_episode_purchase',1.99,'credit_debit_card','succeeded',t,sid,tid,'demo','USD',1.99,None,None,1.99,0,users[i][3]))
            ppv_status.append((f'p_{tid}',tid,'succeeded',t,t,f'provider_{tid}'))
            refunded=j<refund_targets[month_index]
            if refunded:
                ppv.append((rid,uid,rt[:10],'refund','ppv_refund',1.99,'credit_debit_card','succeeded',rt,None,rid,'demo','USD',1.99,tid,None,None,None,users[i][3]))
                ppv_status.append((f'p_{rid}',rid,'succeeded',rt,rt,f'provider_{rid}'))
                request_at=offset(rt,-3600)
                ppv_refund_events.append((f'request_{rid}',uid,None,request_at,'refund_requested',None,None,tid,None,cid,ep,None,None,country,request_at))
                refund_attrs.append((f'ra_{month}_{j}',rid,cid,ep,1.99))
            attrs.append((f'attr_{month}_{j}',tid,cid,ep,t,rt if refunded else None,1.99,'refunded' if refunded else 'granted',rt if refunded else None,None))
    db.executemany('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',ppv_sessions)
    db.executemany('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',ppv_links)
    db.executemany('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',ppv_views)
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',ppv_events)
    db.executemany('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',ppv)
    db.executemany('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',ppv_status)
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',ppv_refund_events)
    db.executemany('INSERT INTO transaction_content_attribution VALUES (?,?,?,?,?,?,?,?,?,?)',attrs)
    db.executemany('INSERT INTO refund_content_attribution VALUES (?,?,?,?,?)',refund_attrs)
    # One episode is removed and later returns. Delisting closes the old PPV;
    # the original buyer purchases it again before playing it after relisting.
    original=next(row for row in attrs if row[1]=='ppv_4_39')
    original_txn=next(row for row in ppv if row[0]=='ppv_4_39')
    uid=original_txn[1]; i=int(uid[1:]); aid=f'a{i:05}'
    removed=timestamp(9,10,0); returned=timestamp(9,20,0); purchase=timestamp(9,25,10); end=timestamp(9,25,10,20); sid='s_relist'; tid='ppv_relist'
    db.execute('UPDATE content_availability_history SET available_until_at=? WHERE content_id=? AND episode_number=?',(removed,'c12',20))
    db.execute('INSERT INTO content_availability_history VALUES (?,?,?,?,?,?,?)',('av_c12_20_gap','c12',20,removed,returned,'delisted',removed))
    db.execute('INSERT INTO content_availability_history VALUES (?,?,?,?,?,?,?)',('av_c12_20_return','c12',20,returned,None,'live',returned))
    db.execute("UPDATE transaction_content_attribution SET entitlement_end_at=?,delisted_at=?,attribution_status='expired_delisting' WHERE txn_id='ppv_4_39'",(removed,removed))
    start_session=offset(purchase,-120)
    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',(sid,uid,aid,purchase[:10],start_session,end,end,1320,'web',users[i][3]))
    db.execute('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',('l_relist',aid,uid,sid,start_session,'login'))
    for name,when in [('app_opened',start_session),('paywall_viewed',offset(purchase,-90)),('checkout_started',offset(purchase,-30))]:
        db.execute('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',('relist_'+name,uid,aid,when,name,sid,None,None,None,'c12',20,None,zones[users[i][3]],users[i][3],when))
    repurchase=(tid,uid,purchase[:10],'ppv','ppv_episode_purchase',1.99,'credit_debit_card','succeeded',purchase,sid,tid,'demo','USD',1.99,None,None,1.99,0,users[i][3])
    db.execute('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',repurchase)
    db.execute('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',('p_relist',tid,'succeeded',purchase,purchase,'provider_relist'))
    db.execute('INSERT INTO transaction_content_attribution VALUES (?,?,?,?,?,?,?,?,?,?)',('attr_relist',tid,'c12',20,purchase,None,1.99,'granted',None,None))
    db.execute('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',('v_relist',uid,aid,sid,'c12',20,purchase[:10],timestamp(9,25,10,2),timestamp(9,25,10,12),600,900,'ppv',round(600/900,4),0,600,0,0,None,zones[users[i][3]],users[i][3]))
    ppv.append(repurchase)
    # Anonymous browsing happens before login; no anonymous content view is made.
    browsing=[]
    for s in sessions[:500]:
        login=s[4].replace(':00Z',':30Z')
        db.execute('UPDATE identity_links SET linked_at=? WHERE session_id=?',(login,s[0]))
        db.execute("UPDATE user_events SET user_id=NULL WHERE session_id=? AND event_name='app_opened'",(s[0],))
        browsing.append(('browse_'+s[0],None,s[2],s[4],'episode_detail_viewed',s[0],None,None,None,'c01',1,None,None,s[9],s[4]))
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',browsing)
    # Cancellation is an account action and keeps paid access until period end.
    cancel_events=[]
    for period,uid,requested in db.execute("SELECT subscription_period_id,user_id,cancelled_at FROM subscription_history WHERE status='cancel_at_period_end'"):
        cancel_events.append(('cancel_'+period,uid,None,requested,'subscription_cancel_requested',None,None,None,period,None,None,None,None,None,requested))
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',cancel_events)
    # Record genuine non-purchaser funnel observations in existing free sessions.
    funnel=[]
    for s,v in view_pairs:
        if len(funnel)>=1600: break
        if v[11]!='free' or int(s[1][1:])%17: continue
        observed=offset(s[4],30); cid='c01'; episode=13
        funnel.append((f'nonbuyer_wall_{s[0]}',s[1],s[2],observed,'paywall_viewed',s[0],None,None,None,cid,episode,None,None,s[9],observed))
        funnel.append((f'nonbuyer_block_{s[0]}',s[1],s[2],observed,'playback_blocked',s[0],None,None,None,cid,episode,'{"reason":"premium_requires_payment"}',None,s[9],observed))
        if int(s[1][1:])%3==0:
            checkout=offset(observed,10)
            funnel.append((f'nonbuyer_checkout_{s[0]}',s[1],s[2],checkout,'checkout_started',s[0],None,None,None,cid,episode,None,None,s[9],checkout))
    db.executemany('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',funnel)
    # An explicit account-level quota boundary: eight distinct free episodes,
    # then an attempted ninth that is blocked, not recorded as a view.
    quota=db.execute("""SELECT v.user_id,v.anonymous_id,v.date,v.country_at_event
      FROM content_views v WHERE v.view_type='free' AND substr(v.date,1,7)='2026-06'
      AND NOT EXISTS(SELECT 1 FROM subscription_history h WHERE h.user_id=v.user_id
        AND h.status IN ('active','cancel_at_period_end') AND h.effective_start_at<=v.date||'T22:00:00Z' AND h.effective_end_at>v.date||'T22:00:00Z')
      GROUP BY v.user_id,v.date HAVING count(DISTINCT v.content_id||':'||v.episode_number)=1
      ORDER BY v.user_id LIMIT 1""").fetchone()
    assert quota
    uid,aid,day,country=quota; st=day+'T22:00:00Z'; end=day+'T22:35:00Z'; sid='s_quota_boundary'
    existing=set(db.execute("SELECT content_id,episode_number FROM content_views WHERE user_id=? AND date=? AND view_type='free'",(uid,day)).fetchall())
    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?,?)',(sid,uid,aid,day,st,end,end,2100,'android',country))
    db.execute('INSERT INTO identity_links VALUES (?,?,?,?,?,?)',('l_quota',aid,uid,sid,st,'login'))
    db.execute('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',('open_quota',uid,aid,st,'app_opened',sid,None,None,None,None,None,None,zones[country],country,st))
    choices=[('c02',ep) for ep in range(1,13) if ('c02',ep) not in existing]
    for n,(cid,ep) in enumerate(choices[:7],start=2):
        vt=offset(st,(n-1)*120); ve=offset(vt,60)
        db.execute('INSERT INTO content_views VALUES ('+','.join('?'*20)+')',
          (f'v_quota_{n}',uid,aid,sid,cid,ep,day,vt,ve,60,900,'free',round(60/900,4),0,60,0,1,n,zones[country],country))
    blocked=offset(st,1800); blocked_content,blocked_ep=choices[7]
    db.execute('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',
      ('event_quota_block',uid,aid,blocked,'playback_blocked',sid,None,None,None,blocked_content,blocked_ep,'{"reason":"daily_free_quota_exhausted"}',None,country,blocked))
    # Some checkout attempts fail; they are not revenue and grant no entitlement.
    failed_txns=[]
    checkouts=db.execute("SELECT event_id,user_id,session_id,event_at,country_at_event FROM user_events WHERE event_name='checkout_started' ORDER BY event_id LIMIT 30").fetchall()
    for event_id,uid,sid,created,country in checkouts:
        tid='failed_'+event_id
        row=(tid,uid,created[:10],'ppv','ppv_episode_purchase',1.99,'credit_debit_card','failed',created,sid,tid,'demo','USD',1.99,None,None,1.99,0,country)
        db.execute('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',row)
        db.execute('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',('p_'+tid,tid,'failed',created,created,'provider_'+tid))
        db.execute('UPDATE user_events SET txn_id=? WHERE event_id=?',(tid,event_id))
        failed_txns.append(row)
    # Refund one previously cancelled subscription per month (April–August).
    # The entitlement ends when the approved refund succeeds, not at request.
    sub_refunds=[]
    for month in range(4,9):
        row=db.execute("""SELECT h.subscription_period_id,h.subscription_id,h.user_id,
          h.effective_end_at,h.source_txn_id,h.cancelled_at FROM subscription_history h
          WHERE h.status='cancel_at_period_end' AND substr(h.effective_start_at,6,2)=?
          ORDER BY h.user_id LIMIT 1""",(f'{month:02}',)).fetchone()
        assert row, f'No cancellation available in month {month}'
        period,subid,uid,old_end,charge,cancelled_at=row
        approved=timestamp(month,calendar.monthrange(2026,month)[1],23,50); requested=offset(approved,-600)
        tid=f'sub_refund_{month}'; country=users[int(uid[1:])][3]
        refund=(tid,uid,approved[:10],'refund','subscription_refund',9.99,
                'credit_debit_card','succeeded',approved,None,tid,'demo','USD',9.99,
                charge,subid,None,None,country)
        db.execute('INSERT INTO transactions VALUES ('+','.join('?'*19)+')',refund)
        db.execute('INSERT INTO payment_status_history VALUES (?,?,?,?,?,?)',
                   (f'p_{tid}',tid,'succeeded',approved,approved,f'provider_{tid}'))
        db.execute('UPDATE subscription_history SET effective_end_at=? WHERE subscription_period_id=?',(approved,period))
        db.execute('INSERT INTO subscription_history VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                   (f'h_refund_{month}',subid,uid,approved,old_end,approved,'refunded',
                    'monthly_9_99',tid,cancelled_at,approved))
        db.execute('UPDATE users SET subscription_status=?,subscription_end=? WHERE user_id=?',('refunded',approved,uid))
        db.execute('INSERT INTO user_events VALUES ('+','.join('?'*15)+')',
                   (f'event_request_{tid}',uid,None,requested,'refund_requested',None,None,charge,None,None,None,None,None,country,requested))
        sub_refunds.append(refund)
    db.execute('ALTER TABLE transactions ADD COLUMN refund_reason TEXT')
    reasons=['did_not_like_content','accidental_purchase','poor_playback_quality']
    refund_ids=[r[0] for r in ppv+sub_refunds if r[3]=='refund']
    for index,tid in enumerate(refund_ids):
        db.execute('UPDATE transactions SET refund_reason=? WHERE txn_id=?',(reasons[index%len(reasons)],tid))
    all_txns=txns+ppv+sub_refunds+failed_txns
    raw=[]; quality=[]
    for n,row in enumerate(all_txns):
        tid,amount,t=row[0],row[5],row[8]
        if n%997==0 and amount>0:
            raw.append((tid,str(round(amount*100,2)),'USD',t))
            quality.append((tid,'100x unit error',amount,'Provider sent cents; reconciled against recorded unit and purchase price.'))
        elif n%1211==1:
            raw.append((tid,'unavailable','USD',t))
            quality.append((tid,'non-numeric source amount',amount,'Recovered from confirmed provider payment.'))
        else: raw.append((tid,str(amount) if n%7==0 else amount,'USD',t))
    db.executemany('INSERT INTO raw_payment_source VALUES (?,?,?,?)',raw)
    db.executemany('INSERT INTO payment_quality_review VALUES (?,?,?,?)',quality)
    # Recompute after all sessions and late-inserted episode views are present.
    db.execute('''UPDATE content_views SET is_first_view_of_episode = CASE WHEN view_id IN
      (SELECT view_id FROM (SELECT view_id,ROW_NUMBER() OVER
       (PARTITION BY user_id,content_id,episode_number ORDER BY view_started_at,view_id) n
       FROM content_views) WHERE n=1) THEN 1 ELSE 0 END''')
    db.commit()
    problems=db.execute('PRAGMA foreign_key_check').fetchall()
    if problems: raise RuntimeError(f'foreign key violations: {problems[:5]}')
    print('Created',path,'users',len(users),'sessions',db.execute('SELECT count(*) FROM sessions').fetchone()[0], 'views',db.execute('SELECT count(*) FROM content_views').fetchone()[0], 'financial events',len(all_txns))
    print('Monthly MAU',db.execute("SELECT substr(session_started_at,1,7),count(DISTINCT user_id) FROM sessions GROUP BY 1").fetchall())
    print('Monthly net revenue',db.execute("SELECT substr(transaction_at,1,7),round(sum(CASE WHEN type='refund' THEN -amount_usd ELSE amount_usd END),2) FROM transactions WHERE status='succeeded' GROUP BY 1").fetchall())
    db.close()

if __name__ == '__main__':
    main()

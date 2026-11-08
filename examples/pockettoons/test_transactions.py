#!/usr/bin/env python3
"""Focused transaction, exact-cent and status-history regression tests."""
import ast
import datetime as dt
from decimal import Decimal, InvalidOperation
import sqlite3
import unittest
from pathlib import Path

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in node.targets))
fn=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='usd_cents')
namespace={'Decimal':Decimal,'InvalidOperation':InvalidOperation}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'<money>','exec'),namespace)

def valid_utc(value):
    try:
        return int(dt.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%dT%H:%M:%SZ')==value)
    except (TypeError,ValueError):
        return 0

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.create_function('usd_cents',1,namespace['usd_cents'])
        self.db.create_function('valid_utc',1,valid_utc)
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT,user_id TEXT,date TEXT,type TEXT,transaction_subtype TEXT,amount_usd REAL,
            payment_method TEXT,status TEXT,transaction_at TEXT,session_id TEXT,provider_transaction_id TEXT,payment_provider TEXT,
            currency TEXT,original_amount REAL,related_txn_id TEXT,subscription_id TEXT,list_price_usd REAL,discount_usd REAL,refund_reason TEXT);
          CREATE TABLE payment_status_history(payment_status_event_id TEXT,txn_id TEXT,status TEXT,effective_at TEXT,recorded_at TEXT,provider_event_id TEXT);
          CREATE TABLE transaction_content_attribution(txn_id TEXT,attributed_amount_usd REAL,content_id TEXT,episode_number INTEGER);
          CREATE TABLE refund_content_attribution(refund_txn_id TEXT,allocated_refund_usd REAL,content_id TEXT,episode_number INTEGER);
          CREATE TABLE raw_payment_source(txn_id TEXT,raw_amount,raw_unit TEXT);
          CREATE TABLE payment_quality_review(txn_id TEXT,corrected_amount_usd REAL);
          CREATE TABLE subscription_history(source_txn_id TEXT,user_id TEXT,subscription_id TEXT);
          CREATE TABLE sessions(session_id TEXT,user_id TEXT,session_started_at TEXT,session_ended_at TEXT);
          INSERT INTO transactions VALUES('p','u','2026-01-01','ppv','ppv_episode_purchase',0.30,'credit_debit_card','succeeded',
            '2026-01-01T10:00:00Z',NULL,'provider-p','demo','USD',0.30,NULL,NULL,0.30,0,NULL);
          INSERT INTO payment_status_history VALUES('e0','p','pending','2026-01-01T10:00:00Z','2026-01-01T10:00:00Z','provider-e0'),
            ('e1','p','succeeded','2026-01-01T10:03:00Z','2026-01-01T10:03:00Z','provider-e1');
        ''')
    def count(self,name):
        return self.db.execute(checks[name]).fetchone()[0]
    def test_decimal_cents_and_invalid_precision(self):
        cents=namespace['usd_cents']
        self.assertEqual(cents('0.10')+cents('0.20'),30)
        self.assertIsNone(cents('0.001'))
        self.assertIsNone(cents('unavailable'))
        self.assertEqual(self.count('transaction USD amount or pricing invalid'),0)
        self.db.execute("UPDATE transactions SET amount_usd=0.301")
        self.assertEqual(self.count('transaction USD amount or pricing invalid'),1)
    def test_delayed_success_and_duplicate_success_history(self):
        self.assertEqual(self.count('transaction status snapshot differs from latest transition'),0)
        self.assertEqual(self.count('transaction payment history invalid'),0)
        self.db.execute("INSERT INTO payment_status_history VALUES('e2','p','succeeded','2026-01-01T10:04:00Z','2026-01-01T10:04:00Z','provider-e2')")
        self.assertGreater(self.count('transaction status history ambiguous or duplicated'),0)
        self.db.execute("UPDATE transactions SET status='pending'")
        self.assertEqual(self.count('transaction status snapshot differs from latest transition'),1)
    def test_refund_exact_cent_cap_and_original_success_time(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('r1','u','2026-01-01','refund','ppv_refund',0.10,'credit_debit_card','succeeded','2026-01-01T10:02:00Z',NULL,'provider-r1','demo','USD',0.10,'p',NULL,NULL,NULL,'accidental_purchase'),
            ('r2','u','2026-01-01','refund','ppv_refund',0.20,'credit_debit_card','succeeded','2026-01-01T10:05:00Z',NULL,'provider-r2','demo','USD',0.20,'p',NULL,NULL,NULL,'poor_playback_quality');
        ''')
        self.assertEqual(self.count('refund values exceed original in exact cents'),0)
        self.assertEqual(self.count('refund original was not successful by refund attempt'),1)
        self.db.execute("INSERT INTO payment_status_history VALUES('e2','p','voided','2026-01-01T10:04:00Z','2026-01-01T10:04:00Z','provider-e2')")
        self.assertEqual(self.count('payment voided after success'),1)
        self.assertEqual(self.count('refund original was not successful by refund attempt'),2)
        self.db.execute("UPDATE transactions SET amount_usd=0.21,original_amount=0.21 WHERE txn_id='r2'")
        self.assertEqual(self.count('refund values exceed original in exact cents'),1)
    def test_source_discrepancies_require_evidence(self):
        self.db.execute("INSERT INTO raw_payment_source VALUES('p','30.00','USD')")
        self.assertEqual(self.count('raw USD discrepancies missing review evidence'),1)
        self.db.execute("INSERT INTO payment_quality_review VALUES('p',0.30)")
        self.assertEqual(self.count('raw USD discrepancies missing review evidence'),0)
        self.assertEqual(self.count('review corrections differ in exact cents'),0)
        self.db.execute("UPDATE raw_payment_source SET raw_amount='unavailable'")
        self.assertEqual(self.count('raw USD discrepancies missing review evidence'),0)
        self.db.execute("UPDATE payment_quality_review SET corrected_amount_usd=1.00")
        self.assertEqual(self.count('review corrections differ in exact cents'),1)
    def test_ppv_purchase_and_refund_allocations_in_cents(self):
        self.db.execute("INSERT INTO transaction_content_attribution(txn_id,attributed_amount_usd) VALUES('p',0.10),('p',0.20)")
        self.assertEqual(self.count('PPV purchase allocations differ in exact cents'),0)
        self.db.execute("UPDATE transaction_content_attribution SET attributed_amount_usd=0.21 WHERE attributed_amount_usd=0.20")
        self.assertEqual(self.count('PPV purchase allocations differ in exact cents'),1)

    def test_failed_attempt_cannot_grant_entitlement(self):
        self.db.execute("UPDATE transactions SET status='failed'")
        self.db.execute("INSERT INTO transaction_content_attribution(txn_id,attributed_amount_usd) VALUES('p',0.30)")
        self.assertEqual(self.count('failed payments with entitlements'),1)

    def test_post_success_void_is_invalid_and_off_session_is_permitted(self):
        self.db.execute("UPDATE transactions SET status='voided'")
        self.db.execute("INSERT INTO payment_status_history VALUES('e2','p','voided','2026-01-01T11:00:00Z','2026-01-01T11:00:00Z','provider-e2')")
        self.assertEqual(self.count('transaction status snapshot differs from latest transition'),0)
        self.assertEqual(self.count('payment voided after success'),1)
        self.assertEqual(self.count('in-app transaction session inconsistent'),0)

    def test_pending_to_void_is_permitted(self):
        self.db.execute("DELETE FROM payment_status_history WHERE status='succeeded'")
        self.db.execute("INSERT INTO payment_status_history VALUES('e2','p','voided','2026-01-01T11:00:00Z','2026-01-01T11:00:00Z','provider-e2')")
        self.assertEqual(self.count('payment voided after success'),0)

    def test_subscription_charge_and_refund_reference_same_subscription(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('sub','u','2026-01-01','subscription','subscription_initial',9.99,'credit_debit_card','succeeded',
            '2026-01-01T10:00:00Z',NULL,'provider-sub','demo','USD',9.99,NULL,'sub-u',9.99,0,NULL);
          INSERT INTO transactions VALUES('ref','u','2026-01-02','refund','subscription_refund',9.99,'credit_debit_card','succeeded',
            '2026-01-02T10:00:00Z',NULL,'provider-ref','demo','USD',9.99,'sub','sub-u',NULL,NULL,'accidental_purchase');
          INSERT INTO subscription_history VALUES('sub','u','sub-u'),('ref','u','sub-u');
        ''')
        self.assertEqual(self.count('subscription financial reference inconsistent'),0)
        self.db.execute("UPDATE transactions SET subscription_id='other' WHERE txn_id='ref'")
        self.assertEqual(self.count('subscription financial reference inconsistent'),1)

    def test_refund_allocation_must_match_original_episode(self):
        self.db.executescript('''
          INSERT INTO transactions VALUES('r','u','2026-01-01','refund','ppv_refund',0.30,'credit_debit_card','succeeded',
            '2026-01-01T11:00:00Z',NULL,'provider-r','demo','USD',0.30,'p',NULL,NULL,NULL,'accidental_purchase');
          INSERT INTO transaction_content_attribution VALUES('p',0.30,'c',1);
          INSERT INTO refund_content_attribution VALUES('r',0.30,'c',1);
        ''')
        self.assertEqual(self.count('PPV refund allocated to unpurchased episode'),0)
        self.db.execute('UPDATE refund_content_attribution SET episode_number=2')
        self.assertEqual(self.count('PPV refund allocated to unpurchased episode'),1)

if __name__=='__main__':
    unittest.main()

"""PPV refund allocation reconciliation and success-time recognition."""
import ast
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(x, ast.Name) and x.id == 'checks' for x in n.targets))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'usd_cents')
scope = {'Decimal': Decimal, 'InvalidOperation': InvalidOperation}
exec(compile(ast.Module(body=[fn], type_ignores=[]), '<money>', 'exec'), scope)

REFUND_AS_OF = '''SELECT COALESCE(SUM(usd_cents(a.allocated_refund_usd)),0)
FROM refund_content_attribution a
JOIN transactions r ON r.txn_id=a.refund_txn_id
JOIN payment_status_history p ON p.txn_id=r.txn_id AND p.status='succeeded'
WHERE r.type='refund' AND r.transaction_subtype='ppv_refund'
  AND a.content_id=:content_id AND a.episode_number=:episode_number
  AND p.effective_at<=:as_of'''

class RefundLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('usd_cents', 1, scope['usd_cents'])
        self.db.executescript('''
          CREATE TABLE transactions(txn_id TEXT, type TEXT,transaction_subtype TEXT,status TEXT,amount_usd REAL,related_txn_id TEXT);
          CREATE TABLE refund_content_attribution(refund_txn_id TEXT,content_id TEXT,episode_number INTEGER,allocated_refund_usd REAL);
          CREATE TABLE payment_status_history(txn_id TEXT,status TEXT,effective_at TEXT);
          INSERT INTO transactions VALUES('r','refund','ppv_refund','pending',0.75,'p');
          INSERT INTO refund_content_attribution VALUES('r','c1',1,0.75);
          INSERT INTO payment_status_history VALUES('r','pending','2026-01-01T10:00:00Z');
        ''')

    def allocations_invalid(self):
        return self.db.execute(checks['refund allocation mismatch']).fetchone()[0]

    def recognised(self, at):
        return self.db.execute(REFUND_AS_OF, {'content_id':'c1','episode_number':1,'as_of':at}).fetchone()[0]

    def test_pending_then_succeeded_is_recognised_only_at_success(self):
        self.assertEqual(self.allocations_invalid(), 0)
        self.assertEqual(self.recognised('2026-01-01T10:04:00Z'), 0)
        self.db.execute("UPDATE transactions SET status='succeeded' WHERE txn_id='r'")
        self.db.execute("INSERT INTO payment_status_history VALUES('r','succeeded','2026-01-01T10:05:00Z')")
        self.assertEqual(self.allocations_invalid(), 0)
        self.assertEqual(self.recognised('2026-01-01T10:04:00Z'), 0)
        self.assertEqual(self.recognised('2026-01-01T10:05:00Z'), 75)

    def test_failed_and_voided_intentions_never_count(self):
        for status in ('failed','voided'):
            self.db.execute('UPDATE transactions SET status=? WHERE txn_id=?', (status,'r'))
            self.assertEqual(self.allocations_invalid(), 0)
            self.assertEqual(self.recognised('2026-01-02T00:00:00Z'), 0)

    def test_all_statuses_require_correct_allocation_in_cents(self):
        for status in ('pending','failed','voided','succeeded'):
            self.db.execute('UPDATE transactions SET status=? WHERE txn_id=?', (status,'r'))
            self.db.execute("UPDATE refund_content_attribution SET allocated_refund_usd=0.74 WHERE refund_txn_id='r'")
            self.assertEqual(self.allocations_invalid(), 1)
            self.db.execute("UPDATE refund_content_attribution SET allocated_refund_usd=0.75 WHERE refund_txn_id='r'")
            self.assertEqual(self.allocations_invalid(), 0)
            self.db.execute("DELETE FROM refund_content_attribution WHERE refund_txn_id='r'")
            self.assertEqual(self.allocations_invalid(), 1)
            self.db.execute("INSERT INTO refund_content_attribution VALUES('r','c1',1,0.75)")

if __name__ == '__main__':
    unittest.main()

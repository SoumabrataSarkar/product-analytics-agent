"""Raw payment source arrival timestamps use the fixture UTC format."""
import ast
import datetime as dt
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))
valid_node = next(node for node in tree.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'valid_utc')
namespace = {'dt': dt}
exec(compile(ast.Module(body=[valid_node], type_ignores=[]), '<valid_utc>', 'exec'), namespace)


class RawPaymentTimestampTests(unittest.TestCase):
    def test_received_at_utc(self):
        db = sqlite3.connect(':memory:')
        db.create_function('valid_utc', 1, namespace['valid_utc'])
        db.execute('CREATE TABLE raw_payment_source(received_at TEXT)')
        for timestamp, expected in [
            ('2026-05-02T12:00:00Z', 0), (None, 1), ('2026-05-02', 1),
            ('2026-02-30T12:00:00Z', 1), ('2026-05-02T12:00:00+05:30', 1),
            ('2026-05-02T12:00:00.123Z', 1), ('broken', 1),
        ]:
            with self.subTest(timestamp=timestamp):
                db.execute('DELETE FROM raw_payment_source')
                db.execute('INSERT INTO raw_payment_source VALUES (?)', (timestamp,))
                self.assertEqual(db.execute(checks['raw payment source UTC timestamp invalid']).fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()

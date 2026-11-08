"""Payment review completion time is optional and valid UTC when supplied."""
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
function = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == 'valid_utc')
namespace = {'dt': dt}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<valid_utc>', 'exec'), namespace)


class ReviewTimestampTests(unittest.TestCase):
    def test_optional_utc_timestamp(self):
        db = sqlite3.connect(':memory:')
        db.create_function('valid_utc', 1, namespace['valid_utc'])
        db.execute('CREATE TABLE payment_quality_review(reviewed_at TEXT)')
        query = checks['payment review UTC timestamp invalid']
        for value, expected in [(None, 0), ('2026-05-02T12:00:00Z', 0),
                                ('2026-05-02', 1), ('2026-02-30T12:00:00Z', 1),
                                ('2026-05-02T12:00:00+05:30', 1), ('broken', 1)]:
            with self.subTest(value=value):
                db.execute('DELETE FROM payment_quality_review')
                db.execute('INSERT INTO payment_quality_review VALUES (?)', (value,))
                self.assertEqual(db.execute(query).fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()

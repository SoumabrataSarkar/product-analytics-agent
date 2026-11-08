"""Daily marketing dates and ingestion timestamps use the fixture UTC contract."""
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


class MarketingTimeTests(unittest.TestCase):
    def test_date_and_load_time(self):
        db = sqlite3.connect(':memory:')
        db.create_function('valid_utc', 1, namespace['valid_utc'])
        db.execute('CREATE TABLE marketing_spend(date TEXT, loaded_at TEXT)')
        check = checks['marketing reporting date or load timestamp invalid']
        for date, loaded, expected in [
            ('2026-04-01', '2026-04-01T23:00:00Z', 0),
            ('2026-04-01', '2026-03-31T23:00:00Z', 0),
            (None, '2026-04-01T23:00:00Z', 1),
            ('2026-02-30', '2026-04-01T23:00:00Z', 1),
            ('2026-04-01T00:00:00Z', '2026-04-01T23:00:00Z', 1),
            ('2026-04-01', None, 1),
            ('2026-04-01', '2026-04-01T23:00:00+05:30', 1),
        ]:
            with self.subTest(date=date, loaded=loaded):
                db.execute('DELETE FROM marketing_spend')
                db.execute('INSERT INTO marketing_spend VALUES (?,?)', (date, loaded))
                self.assertEqual(db.execute(check).fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()

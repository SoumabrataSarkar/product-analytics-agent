"""Marketing spend and delivery counts must be valid non-negative values."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class MarketingValueTests(unittest.TestCase):
    def test_values_and_clicks_above_impressions(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE marketing_spend(spend_usd, impressions, clicks)')
        check = checks['marketing spend or count values invalid']
        cases = [
            (0, 0, 0, 0), (150.5, 10, 20, 0),
            (-1, 10, 5, 1), (1, -1, 0, 1), (1, 1, -1, 1),
            (1, 1.5, 1, 1), (1, 1, 1.5, 1),
            ('bad', 1, 1, 1), (1, 'bad', 1, 1), (1, 1, 'bad', 1),
            (None, 1, 1, 1), (1, None, 1, 1), (1, 1, None, 1),
            (float('inf'), 1, 1, 1),
        ]
        for spend, impressions, clicks, expected in cases:
            with self.subTest(spend=spend, impressions=impressions, clicks=clicks):
                db.execute('DELETE FROM marketing_spend')
                db.execute('INSERT INTO marketing_spend VALUES (?,?,?)', (spend, impressions, clicks))
                self.assertEqual(db.execute(check).fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()

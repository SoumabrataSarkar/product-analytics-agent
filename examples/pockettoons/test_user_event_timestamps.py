"""Every event has valid UTC occurrence and arrival timestamps."""
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


class UserEventTimestampTests(unittest.TestCase):
    def test_utc_timestamps_and_clock_order(self):
        db = sqlite3.connect(':memory:')
        db.create_function('valid_utc', 1, namespace['valid_utc'])
        db.execute('CREATE TABLE user_events(event_at TEXT, ingested_at TEXT)')
        good = '2026-05-02T12:00:00Z'
        cases = [
            (good, '2026-05-02T12:01:00Z', 0),
            (good, '2026-05-02T11:59:00Z', 0),
            (None, good, 1), (good, None, 1),
            ('2026-05-02', good, 1),
            ('2026-05-02T12:00:00+05:30', good, 1),
            ('2026-02-30T12:00:00Z', good, 1),
            (good, 'broken', 1),
            (good, '2026-05-02T12:00:00.123Z', 1),
        ]
        for occurred, ingested, expected in cases:
            with self.subTest(occurred=occurred, ingested=ingested):
                db.execute('DELETE FROM user_events')
                db.execute('INSERT INTO user_events VALUES (?,?)', (occurred, ingested))
                actual = db.execute(checks['user event UTC timestamps invalid']).fetchone()[0]
                self.assertEqual(actual, expected)


if __name__ == '__main__':
    unittest.main()

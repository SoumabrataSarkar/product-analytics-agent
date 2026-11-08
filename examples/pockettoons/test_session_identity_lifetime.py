"""A session's observed activity must fall inside its identity lifetime."""
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


class SessionIdentityLifetimeTests(unittest.TestCase):
    def test_open_and_closed_session_activity(self):
        db = sqlite3.connect(':memory:')
        db.create_function('valid_utc', 1, namespace['valid_utc'])
        db.execute('CREATE TABLE anonymous_identities(anonymous_id TEXT, created_at TEXT, retired_at TEXT)')
        db.execute('CREATE TABLE sessions(anonymous_id TEXT, session_started_at TEXT, last_activity_at TEXT, session_ended_at TEXT)')
        db.execute("INSERT INTO anonymous_identities VALUES ('a','2026-05-01T10:00:00Z','2026-05-01T11:00:00Z')")
        query = checks['session activity outside identity lifetime']
        cases = [
            ('2026-05-01T10:00:00Z', '2026-05-01T10:59:59Z', None, 0),
            ('2026-05-01T10:00:00Z', '2026-05-01T10:59:59Z', '2026-05-01T10:59:59Z', 0),
            ('2026-05-01T09:59:59Z', '2026-05-01T10:30:00Z', None, 1),
            ('2026-05-01T10:00:00Z', '2026-05-01T11:00:00Z', None, 1),
            ('2026-05-01T11:00:00Z', '2026-05-01T11:01:00Z', '2026-05-01T11:01:00Z', 1),
        ]
        for start, last, end, expected in cases:
            with self.subTest(start=start, last=last, end=end):
                db.execute('DELETE FROM sessions')
                db.execute('INSERT INTO sessions VALUES (?,?,?,?)', ('a', start, last, end))
                self.assertEqual(db.execute(query).fetchone()[0], expected)
        db.execute('UPDATE anonymous_identities SET retired_at=NULL')
        self.assertEqual(db.execute(query).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()

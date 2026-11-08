"""Shared devices can have different users in separate sessions."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class SharedDeviceSessionTests(unittest.TestCase):
    def test_same_device_distinct_sessions_and_conflicts(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE sessions(session_id TEXT, anonymous_id TEXT, user_id TEXT, session_started_at TEXT, session_ended_at TEXT)')
        db.execute('CREATE TABLE identity_links(session_id TEXT, anonymous_id TEXT, user_id TEXT, linked_at TEXT)')
        db.executemany('INSERT INTO sessions VALUES (?,?,?,?,?)', [
            ('s1', 'device', 'u1', '2026-05-01T10:00:00Z', '2026-05-01T10:10:00Z'),
            ('s2', 'device', 'u2', '2026-05-01T10:11:00Z', '2026-05-01T10:20:00Z')])
        db.executemany('INSERT INTO identity_links VALUES (?,?,?,?)', [
            ('s1', 'device', 'u1', '2026-05-01T10:01:00Z'),
            ('s2', 'device', 'u2', '2026-05-01T10:11:00Z')])
        check = checks['session identity links inconsistent']
        self.assertEqual(db.execute(check).fetchone()[0], 0)
        db.execute("INSERT INTO identity_links VALUES ('s1','device','u2','2026-05-01T10:05:00Z')")
        self.assertEqual(db.execute(check).fetchone()[0], 1)
        db.execute("INSERT INTO identity_links VALUES ('s2','other_device','u2','2026-05-01T10:12:00Z')")
        self.assertEqual(db.execute(check).fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()

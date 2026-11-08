"""Identity lifetimes and observed login links use UTC half-open intervals."""
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


class IdentityLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.create_function('valid_utc', 1, namespace['valid_utc'])
        self.db.execute('CREATE TABLE anonymous_identities(anonymous_id TEXT, created_at TEXT, retired_at TEXT)')
        self.db.execute('CREATE TABLE identity_links(anonymous_id TEXT, linked_at TEXT)')

    def test_lifetime(self):
        start, end = '2026-05-01T10:00:00Z', '2026-05-01T11:00:00Z'
        for created, retired, expected in [(start, None, 0), (start, end, 0),
                                            (start, start, 1), (end, start, 1),
                                            ('bad', end, 1), (start, 'bad', 1),
                                            (None, None, 1)]:
            with self.subTest(created=created, retired=retired):
                self.db.execute('DELETE FROM anonymous_identities')
                self.db.execute('INSERT INTO anonymous_identities VALUES (?,?,?)', ('a', created, retired))
                self.assertEqual(self.db.execute(checks['anonymous identity lifetime invalid']).fetchone()[0], expected)

    def test_link_in_half_open_lifetime(self):
        self.db.execute("INSERT INTO anonymous_identities VALUES ('a','2026-05-01T10:00:00Z','2026-05-01T11:00:00Z')")
        for linked, expected in [('2026-05-01T09:59:59Z', 1),
                                 ('2026-05-01T10:00:00Z', 0),
                                 ('2026-05-01T10:59:59Z', 0),
                                 ('2026-05-01T11:00:00Z', 1),
                                 ('2026-05-01T11:00:01Z', 1)]:
            with self.subTest(linked=linked):
                self.db.execute('DELETE FROM identity_links')
                self.db.execute('INSERT INTO identity_links VALUES (?,?)', ('a', linked))
                self.assertEqual(self.db.execute(checks['identity link outside identity lifetime']).fetchone()[0], expected)
        self.db.execute('UPDATE anonymous_identities SET retired_at=NULL')
        self.assertEqual(self.db.execute(checks['identity link outside identity lifetime']).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()

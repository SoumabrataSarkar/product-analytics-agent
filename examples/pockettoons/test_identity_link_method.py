"""Identity link methods have the agreed fixture values."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class IdentityLinkMethodTests(unittest.TestCase):
    def test_allowed_and_invalid_methods(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE identity_links(link_method TEXT)')
        query = checks['identity link method invalid']
        for method, expected in [('login', 0), ('signup', 0), ('logn', 1),
                                 ('LOGIN', 1), ('', 1), (None, 1)]:
            with self.subTest(method=method):
                db.execute('DELETE FROM identity_links')
                db.execute('INSERT INTO identity_links VALUES (?)', (method,))
                self.assertEqual(db.execute(query).fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()

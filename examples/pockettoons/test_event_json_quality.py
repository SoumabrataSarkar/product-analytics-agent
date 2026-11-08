"""Malformed event properties are reported without breaking product checks."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class EventJsonQualityTests(unittest.TestCase):
    def test_invalid_null_and_valid_payloads(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE user_events(event_name TEXT, event_properties_json TEXT)')
        rows = [
            ('paywall_viewed', '{broken'),
            ('checkout_started', ''),
            ('app_opened', '[bad'),
            ('app_opened', None),
            ('checkout_started', '{"product":"ppv"}'),
            ('paywall_viewed', '{"product":"subscription"}'),
            ('checkout_started', '42'),
        ]
        db.executemany('INSERT INTO user_events VALUES (?, ?)', rows)
        self.assertEqual(db.execute(checks['malformed event properties JSON']).fetchone()[0], 3)
        self.assertEqual(db.execute(checks['unlabelled paywall or checkout']).fetchone()[0], 3)
        self.assertEqual(db.execute('SELECT event_name, event_properties_json FROM user_events').fetchall(), rows)


if __name__ == '__main__':
    unittest.main()

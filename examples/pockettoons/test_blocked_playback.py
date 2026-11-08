"""Blocked playback events identify an episode and explain the block."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class BlockedPlaybackTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE user_events(event_name TEXT, content_id TEXT, episode_number, event_properties_json TEXT)')
        self.db.execute('CREATE TABLE content_episodes(content_id TEXT, episode_number INTEGER)')
        self.db.execute("INSERT INTO content_episodes VALUES ('show', 1)")

    def count(self, check, event):
        self.db.execute('DELETE FROM user_events')
        self.db.execute('INSERT INTO user_events VALUES (?,?,?,?)', event)
        return self.db.execute(checks[check]).fetchone()[0]

    def test_episode_link(self):
        for title, episode, expected in [('show', 1, 0), (None, 1, 1),
                                          ('', 1, 1), ('show', None, 1),
                                          ('show', 0, 1), ('show', 2, 1),
                                          ('missing', 1, 1), ('show', '1', 1)]:
            with self.subTest(title=title, episode=episode):
                self.assertEqual(self.count('blocked playback episode invalid',
                    ('playback_blocked', title, episode, '{"reason":"premium_requires_payment"}')), expected)
        self.assertEqual(self.count('blocked playback episode invalid',
            ('other_event', None, None, None)), 0)

    def test_reason(self):
        for payload, expected in [('{"reason":"premium_requires_payment"}', 0),
                                  ('{"reason":"daily_free_quota_exhausted"}', 0),
                                  ('{"reason":"some_future_reason"}', 0),
                                  (None, 1), ('{broken', 1), ('{}', 1),
                                  ('{"reason":""}', 1), ('{"reason":"   "}', 1),
                                  ('{"reason":null}', 1), ('{"reason":42}', 1),
                                  ('{"reason":[]}', 1), ('42', 1)]:
            with self.subTest(payload=payload):
                self.assertEqual(self.count('blocked playback reason missing',
                    ('playback_blocked', 'show', 1, payload)), expected)
        self.assertEqual(self.count('blocked playback reason missing',
            ('other_event', None, None, '{broken')), 0)


if __name__ == '__main__':
    unittest.main()

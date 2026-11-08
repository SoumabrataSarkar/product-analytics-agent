"""Episode detail browsing must identify a known episode."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree = ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks = next(ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == 'checks'
                      for target in node.targets))


class EpisodeDetailEventTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE user_events(event_name TEXT, user_id TEXT, content_id TEXT, episode_number)')
        self.db.execute('CREATE TABLE content_episodes(content_id TEXT, episode_number INTEGER)')
        self.db.execute("INSERT INTO content_episodes VALUES ('show', 1)")

    def test_episode_link(self):
        cases = [
            ('episode_detail_viewed', 'u1', 'show', 1, 0),
            ('episode_detail_viewed', None, 'show', 1, 0),
            ('episode_detail_viewed', 'u1', None, 1, 1),
            ('episode_detail_viewed', 'u1', '', 1, 1),
            ('episode_detail_viewed', 'u1', 'show', None, 1),
            ('episode_detail_viewed', 'u1', 'show', 0, 1),
            ('episode_detail_viewed', 'u1', 'show', '1', 1),
            ('episode_detail_viewed', 'u1', 'show', 2, 1),
            ('episode_detail_viewed', 'u1', 'missing', 1, 1),
            ('other_event', None, None, None, 0),
        ]
        for event, user, title, episode, expected in cases:
            with self.subTest(event=event, user=user, title=title, episode=episode):
                self.db.execute('DELETE FROM user_events')
                self.db.execute('INSERT INTO user_events VALUES (?,?,?,?)', (event, user, title, episode))
                result = self.db.execute(checks['episode detail event episode invalid']).fetchone()[0]
                self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()

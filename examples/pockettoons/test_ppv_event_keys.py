"""PPV paywall and checkout events require a complete episode key."""
import ast
from pathlib import Path
import sqlite3
import unittest

tree=ast.parse(Path(__file__).with_name('check_data.py').read_text())
checks=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
            and any(isinstance(x,ast.Name) and x.id=='checks' for x in n.targets))

class PPVEventKeyTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE user_events(event_name TEXT,event_properties_json TEXT,content_id TEXT,episode_number INTEGER)')

    def count(self):
        return self.db.execute(checks['PPV paywall or checkout missing episode key']).fetchone()[0]

    def test_ppv_event_requires_title_and_episode(self):
        for event in ('paywall_viewed','checkout_started'):
            for content,episode,expected in ((None,None,1),('c1',None,1),(None,1,1),('',1,1),('c1',0,1),('c1',1,0)):
                self.db.execute('DELETE FROM user_events')
                self.db.execute('INSERT INTO user_events VALUES(?,?,?,?)',(event,'{"product":"ppv"}',content,episode))
                self.assertEqual(self.count(),expected,(event,content,episode))

    def test_subscription_product_does_not_require_episode(self):
        self.db.executemany('INSERT INTO user_events VALUES(?,?,?,?)',[(event,'{"product":"subscription"}',None,None) for event in ('paywall_viewed','checkout_started')])
        self.assertEqual(self.count(),0)

    def test_other_event_and_invalid_json_not_misclassified(self):
        self.db.execute('INSERT INTO user_events VALUES(?,?,?,?)',('app_opened','{"product":"ppv"}',None,None))
        self.db.execute('INSERT INTO user_events VALUES(?,?,?,?)',('paywall_viewed','not-json',None,None))
        self.assertEqual(self.count(),0)

if __name__=='__main__':
    unittest.main()

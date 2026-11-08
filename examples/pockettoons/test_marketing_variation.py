"""Synthetic marketing delivery is varied and reproducible."""
import ast
import calendar
from pathlib import Path
import random
import unittest

tree = ast.parse(Path(__file__).with_name('generate.py').read_text())
function = next(node for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == 'marketing_metrics')
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<marketing_metrics>', 'exec'), namespace)
generate = namespace['marketing_metrics']


def records(seed):
    rng = random.Random(seed)
    return [(month, day, channel, *generate(rng, month, channel))
            for month in range(4, 10)
            for day in range(1, calendar.monthrange(2026, month)[1] + 1)
            for channel in ('paid_social', 'paid_search')]


class MarketingVariationTests(unittest.TestCase):
    def test_determinism_realism_and_story(self):
        rows = records(10844)
        self.assertEqual(rows, records(10844))
        self.assertNotEqual(rows, records(10845))
        self.assertEqual(len(rows), 366)
        for channel in ('paid_social', 'paid_search'):
            channel_rows = [r for r in rows if r[2] == channel]
            for position in (3, 4, 5):
                self.assertGreater(len({r[position] for r in channel_rows}), 30)
            self.assertTrue(all(r[3] >= 0 and isinstance(r[4], int) and r[4] >= 0
                                and isinstance(r[5], int) and r[5] >= 0 for r in channel_rows))
        social = [r for r in rows if r[2] == 'paid_social']
        first = [r[3] for r in social if r[0] < 7]
        later = [r[3] for r in social if r[0] >= 7]
        self.assertGreater(sum(later) / len(later), sum(first) / len(first))
        self.assertGreater(len({round(sum(r[3] for r in social if r[0] == month), 2)
                                for month in range(4, 10)}), 5)


if __name__ == '__main__':
    unittest.main()

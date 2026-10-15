import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from cache_budget import choose


class CacheBudgetTests(unittest.TestCase):
    def test_optional_module_cache_preserves_space_for_existing_downloads(self):
        self.assertEqual(choose(800, {'native': 100}, limit=1000, reserve=50), {'native': True})
        for used in (900, 950, 1100):
            self.assertEqual(choose(used, {'native': 100}, limit=1000, reserve=50), {'native': False})
        self.assertEqual(choose(0, {'native': 0}), {'native': False})

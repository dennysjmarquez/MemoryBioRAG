import sqlite3
import unittest
from ledger import Claim, Ledger
from selector import Query
from search_adapter import wrap_search


class SearchAdapterTests(unittest.TestCase):
    def test_shadow_apply_passthrough_and_error(self):
        db = sqlite3.connect(':memory:')
        try:
            ledger = Ledger(db)
            for cid, value, at in [('old', 'A', 1), ('new', 'B', 2)]:
                ledger.add(Claim(cid, cid, 'entity', 'attribute', 'scope', value, 'fixture', at, confirmed=True))
            ledger.supersede('new', 'old', 'fixture')
            rows = [('old', 'preserve', 7, None, .9), ('neighbor', 'noise', 9, None, .8), ('new', 'preserve', 8, None, .2)]
            events = []
            original = lambda *a, **kw: (rows, 12)
            resolver = lambda a, kw: Query('entity', 'attribute', 'scope', 3)
            shadow = wrap_search(original, ledger, resolver, events.append)
            self.assertEqual(shadow('question'), (rows, 12))
            self.assertEqual(events[-1]['proposed_winner'], 'new')
            applied = wrap_search(original, ledger, resolver, events.append, shadow=False)
            self.assertEqual(applied('question'), ([rows[2], rows[0], rows[1]], 12))
            passthrough = wrap_search(original, ledger, lambda a, kw: None, events.append, shadow=False)
            self.assertEqual(passthrough('question'), (rows, 12))
            broken = wrap_search(original, ledger, lambda a, kw: 1/0, events.append, shadow=False)
            self.assertEqual(broken('question'), (rows, 12))
            self.assertEqual(events[-1]['status'], 'fallback_error:ZeroDivisionError')
        finally:
            db.close()

import random
import sqlite3
import unittest
from dataclasses import replace
from ledger import Claim, Ledger
from selector import Candidate, Query, select


class CompetitionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.ledger = Ledger(self.db)
        self.q = Query('entity', 'attribute', 'scope', 10)
        self.old = Claim('a', 'old', 'entity', 'attribute', 'scope', 'A', 'source-A', 1, confirmed=True)
        self.new = Claim('b', 'new', 'entity', 'attribute', 'scope', 'B', 'source-B', 2, confirmed=True)
        self.rows = (Candidate('old', .99), Candidate('neighbor', .8), Candidate('new', .1))

    def tearDown(self):
        self.db.close()

    def seed(self):
        self.ledger.add(self.old)
        self.ledger.add(self.new)
        self.ledger.supersede('b', 'a', 'explicit correction')

    def test_current_promotes_evidenced_candidate(self):
        self.seed()
        d = select(self.ledger, self.q, self.rows)
        self.assertEqual((d.status, d.winner), ('resolved', 'new'))
        self.assertEqual(set(d.candidates), set(self.rows))
        self.assertEqual(d.candidates[1:], self.rows[:2])

    def test_historical_identifier_generic_are_exact_passthrough(self):
        self.seed()
        for intent in ('historical', 'identifier', 'generic'):
            d = select(self.ledger, replace(self.q, intent=intent), self.rows)
            self.assertEqual(d.candidates, self.rows)
            self.assertIsNone(d.winner)

    def test_no_metadata_does_not_infer_truth_from_score(self):
        d = select(self.ledger, self.q, self.rows)
        self.assertEqual((d.status, d.candidates), ('unknown', self.rows))

    def test_incompatible_without_revision_reports_conflict(self):
        self.ledger.add(self.old)
        self.ledger.add(self.new)
        d = select(self.ledger, self.q, self.rows)
        self.assertEqual((d.status, d.winner, d.candidates), ('conflict', None, self.rows))

    def test_missing_successor_is_retrieval_gap_not_old_winner(self):
        self.seed()
        d = select(self.ledger, self.q, self.rows[:2])
        self.assertEqual((d.status, d.winner, d.missing_nodes), ('retrieval_gap', None, ('new',)))
        self.assertEqual(d.candidates, self.rows[:2])

    def test_can_promote_from_seventh_without_dropping_neighbors(self):
        self.seed()
        rows = self.rows[:2] + tuple(Candidate('n'+str(i), .5) for i in range(4)) + self.rows[2:]
        d = select(self.ledger, self.q, rows)
        self.assertEqual(d.candidates[0].node, 'new')
        self.assertEqual(len(d.candidates), 7)

    def test_reads_never_change_db_or_strengthen_claims(self):
        self.seed()
        changes = self.db.total_changes
        before = '\n'.join(self.db.iterdump())
        for _ in range(100):
            self.assertEqual(select(self.ledger, self.q, self.rows).winner, 'new')
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual('\n'.join(self.db.iterdump()), before)

    def test_future_revision_not_effective_early(self):
        self.seed()
        self.assertEqual(select(self.ledger, replace(self.q, at=1), self.rows).winner, 'old')
        self.assertEqual(select(self.ledger, replace(self.q, at=2), self.rows).winner, 'new')

    def test_expired_successor_does_not_resurrect_predecessor(self):
        self.ledger.add(self.old)
        self.ledger.add(replace(self.new, valid_until=5))
        self.ledger.supersede('b', 'a', 'source')
        self.assertEqual(select(self.ledger, self.q, self.rows).status, 'unknown')

    def test_chain_and_return_to_previous_value(self):
        self.seed()
        self.ledger.add(replace(self.old, id='c', node='return', valid_from=4))
        self.ledger.supersede('c', 'b', 'return confirmed')
        d = select(self.ledger, self.q, self.rows + (Candidate('return', 0),))
        self.assertEqual(d.winner, 'return')
        self.assertEqual(d.superseded, ('a', 'b'))

    def test_unconfirmed_cannot_supersede(self):
        self.ledger.add(self.old)
        self.ledger.add(replace(self.new, confirmed=False))
        with self.assertRaises(ValueError):
            self.ledger.supersede('b', 'a', 'source')
        self.assertEqual(select(self.ledger, self.q, self.rows).winner, 'old')

    def test_reject_cycle_same_time_and_self_edge(self):
        self.ledger.add(self.old)
        self.ledger.add(replace(self.new, valid_from=1))
        self.ledger.supersede('b', 'a', 'source')
        for new, old in [('a', 'b'), ('a', 'a')]:
            with self.assertRaises(ValueError):
                self.ledger.supersede(new, old, 'source')

    def test_reject_cross_scope_attribute_entity(self):
        self.ledger.add(self.old)
        for i, field in enumerate(('scope', 'attribute', 'entity')):
            c = replace(self.new, id=str(i), **{field: 'different'})
            self.ledger.add(c)
            with self.assertRaises(ValueError):
                self.ledger.supersede(c.id, 'a', 'source')

    def test_reject_missing_source_or_endpoint(self):
        self.seed()
        for new, old, src in [('b', 'missing', 'source'), ('b', 'a', '')]:
            with self.assertRaises(ValueError):
                self.ledger.supersede(new, old, src)

    def test_scope_is_not_global_current(self):
        self.seed()
        self.assertEqual(select(self.ledger, replace(self.q, scope='elsewhere'), self.rows).status, 'unknown')

    def test_agreement_is_not_conflict(self):
        self.ledger.add(self.old)
        self.ledger.add(replace(self.new, value='A'))
        self.assertEqual(select(self.ledger, self.q, self.rows).winner, 'old')

    def test_reject_nonfinite_time_score_bad_interval_and_duplicates(self):
        self.seed()
        for value in (float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                select(self.ledger, replace(self.q, at=value), self.rows)
            with self.assertRaises(ValueError):
                select(self.ledger, self.q, (Candidate('x', value),))
        with self.assertRaises(ValueError):
            self.ledger.add(replace(self.new, id='bad', valid_until=1))
        with self.assertRaises(ValueError):
            select(self.ledger, self.q, (self.rows[0], self.rows[0]))

    def test_new_claim_does_not_self_confirm(self):
        claim = Claim('unconfirmed', 'node', 'entity', 'attribute', 'scope', 'X', 'source', 1)
        self.assertFalse(claim.confirmed)
        self.ledger.add(claim)
        self.assertEqual(select(self.ledger, self.q, self.rows).status, 'unknown')

    def test_never_initialize_on_cortex(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE largo_plazo(x)')
        with self.assertRaises(ValueError):
            Ledger(db)
        db.close()

    def test_growth_invariance_tolerance_zero_10000_irrelevant(self):
        self.seed()
        before = select(self.ledger, self.q, self.rows)
        data = [Claim(str(i), 'noise'+str(i), 'other'+str(i), 'attribute', 'scope', 'X', 'source', 1)
                for i in range(10000)]
        random.Random(42).shuffle(data)
        for c in data:
            self.ledger.add(c)
        self.assertEqual(select(self.ledger, self.q, self.rows), before)
        augmented = self.rows + tuple(Candidate('noise'+str(i), 100) for i in range(100))
        d = select(self.ledger, self.q, augmented)
        self.assertEqual((d.status, d.winner, d.claims, d.superseded),
                         (before.status, before.winner, before.claims, before.superseded))
        self.assertEqual(tuple(c for c in d.candidates if c in self.rows), before.candidates)

    def test_budget_failure_is_visible(self):
        self.seed()
        with self.assertRaises(ValueError):
            self.ledger.context('entity', 'attribute', 'scope', 10, limit=1)

    def test_partial_update_does_not_supersede_other_attribute(self):
        self.seed()
        other = replace(self.old, id='path', attribute='path', value='/data')
        self.ledger.add(other)
        d = select(self.ledger, replace(self.q, attribute='path'), self.rows)
        self.assertEqual((d.winner, d.superseded), ('old', ()))

    def test_storage_order_independent_for_distinct_values(self):
        self.seed()
        other = Ledger(sqlite3.connect(':memory:'))
        other.add(self.new)
        other.add(self.old)
        other.supersede('b', 'a', 'explicit correction')
        self.assertEqual(select(other, self.q, self.rows), select(self.ledger, self.q, self.rows))
        other.db.close()


if __name__ == '__main__':
    unittest.main()

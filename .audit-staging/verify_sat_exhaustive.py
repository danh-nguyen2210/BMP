"""Exhaustive validation of the four SAT solvers on nonempty graphs of n <= 5.

Run from repository root: python -B path/to/verify_sat_exhaustive.py
Disables bounds and decomposition to exercise the actual encodings/search.
"""
import itertools
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.graph import GraphData
from src.solvers import (PairwiseIterativeSolver, PairwiseIncrementalSolver,
                        OrderIterativeSolver, OrderIncrementalSolver)
classes = [PairwiseIterativeSolver, PairwiseIncrementalSolver,
           OrderIterativeSolver, OrderIncrementalSolver]
graphs = checks = 0
for n in range(2, 6):
    pairs = list(itertools.combinations(range(1, n + 1), 2))
    for mask in range(1, 1 << len(pairs)):
        edges = [e for i, e in enumerate(pairs) if mask >> i & 1]
        graph = GraphData(n, edges)
        optimum = min(max(abs(p[u-1]-p[v-1]) for u,v in edges)
                      for p in itertools.permutations(range(1,n+1)))
        graphs += 1
        for cls in classes:
            for strategy in ('linear','binary'):
                r = cls(graph).solve(use_heuristics=False, use_components=False,
                                     strategy=strategy)
                valid, actual = graph.verify_labeling(r.labeling, r.bandwidth)
                assert set(r.labeling) == set(range(1,n+1))
                assert r.bandwidth == optimum and valid and actual == optimum, (
                    n, edges, cls.__name__, strategy, optimum,
                    r.bandwidth, r.labeling)
                checks += 1
print('PASS', graphs, 'graphs;', checks, 'solver/strategy cases')
g = GraphData(6, [(1,v) for v in range(2,6)])
for cls in classes:
    solver = cls(g)
    for components in (False, True, False, True):
        for strategy in ('binary','linear'):
            r = solver.solve(use_heuristics=False, use_components=components,
                             strategy=strategy)
            assert r.bandwidth == 2
            assert g.verify_labeling(r.labeling, 2) == (True, 2)
print('PASS 32 repeated solves')

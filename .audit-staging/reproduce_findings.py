"""Run from the BMP repository root with python -B; reproduces audit findings."""
import itertools
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from src.graph import GraphData
from src.solvers import (BaseBMPSolver, SolverResult, PairwiseIterativeSolver,
    PairwiseIncrementalSolver, OrderIterativeSolver, OrderIncrementalSolver)
from src.baselines import CPSATSolver
from scipy.io import mmread

classes = [PairwiseIterativeSolver, PairwiseIncrementalSolver,
           OrderIterativeSolver, OrderIncrementalSolver]
g = GraphData(6, [(1, v) for v in range(2, 6)])
witness = {1:3, 2:1, 3:2, 4:4, 5:5, 6:6}
out = {'disconnected_bound': {'n': g.n, 'edges': sorted(g.edges),
    'computed_lb': g.compute_lb(), 'computed_ub': g.compute_rcm_ub(),
    'optimum': 2, 'witness': witness,
    'witness_check': g.verify_labeling(witness, 2), 'solvers': []}}
for cls in classes + [CPSATSolver]:
    for components in (False, True):
        r = cls(g).solve(use_heuristics=True, use_components=components)
        out['disconnected_bound']['solvers'].append({
            'solver': cls.__name__, 'components': components,
            'bandwidth': r.bandwidth, 'iterations': r.iterations})
out['empty_edge_labelings'] = []
for n, components in ((1, True), (3, False)):
    empty = GraphData(n, [])
    for cls in classes:
        r = cls(empty).solve(use_components=components)
        out['empty_edge_labelings'].append({'n': n, 'components': components,
            'solver': cls.__name__, 'bandwidth': r.bandwidth,
            'labeling': r.labeling,
            'valid': empty.verify_labeling(r.labeling, r.bandwidth)[0]})
out['wrong_vertex_accepted'] = GraphData(3, [(1,2)]).verify_labeling(
    {1:1, 2:2, 999:3}, 1)
class SimulatedFailure(BaseBMPSolver):
    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        return SolverResult(-1, 0, 0)
r = SimulatedFailure(GraphData(4, [(1,2),(2,3)])).solve()
out['simulated_component_failure'] = {
    'note': 'Injected failure, not an observed commercial-solver termination.',
    'bandwidth': r.bandwidth, 'labeling': r.labeling}
perms = list(itertools.permutations((1,2,3)))
def bw(p):
    return max(abs(p[0]-p[1]), abs(p[1]-p[2]))
out['odd_n_symmetry_counterexample'] = {'graph': 'P3, center vertex 2',
    'unrestricted': min(map(bw, perms)),
    'center_at_most_floor_n_over_2': min(bw(p) for p in perms if p[1] <= 1),
    'center_at_most_ceil_n_over_2': min(bw(p) for p in perms if p[1] <= 2)}
c4 = GraphData(4, [(1,2),(2,3),(3,4),(4,1)])
out['existing_test_shortcut'] = {'graph': 'C4', 'lb': c4.compute_lb(),
    'ub': c4.compute_rcm_ub(), 'sat_iterations': {
        cls.__name__: cls(c4).solve(strategy='linear').iterations
        for cls in classes}}
a = mmread('data/steam3.mtx').tocoo()
numeric = GraphData(a.shape[0], [(int(u)+1,int(v)+1)
    for u,v,x in zip(a.row,a.col,a.data) if u != v and x != 0])
stored = GraphData.from_mtx('data/steam3.mtx')
out['steam3_conventions'] = {'note': 'Two graph definitions, not automatically a bug.',
    'stored_entries': int(a.nnz), 'explicit_zeros': int((a.data == 0).sum()),
    'stored_edges': stored.m, 'nonzero_edges': numeric.m,
    'stored_rcm_ub': stored.compute_rcm_ub(), 'numeric_rcm_ub': numeric.compute_rcm_ub()}
print(json.dumps(out, ensure_ascii=True, indent=2))

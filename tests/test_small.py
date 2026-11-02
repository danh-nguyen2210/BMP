import sys
import time
sys.path.insert(0, ".")
from src.graph import GraphData
from src.solvers import (
    OrderIncrementalSolver,
    OrderIterativeSolver,
    PairwiseIncrementalSolver,
    PairwiseIterativeSolver,
)

# Test đồ thị 2 thành phần liên thông: C4 (1-2-3-4-1, bw=2) và P3 (5-6-7, bw=1) -> Băng thông tổng = max(2, 1) = 2
edges = [(1, 2), (2, 3), (3, 4), (4, 1), (5, 6), (6, 7)]
g = GraphData.from_edge_list(n=7, edges=edges, name="disconnected_7")


print(
    f"Test {g.name}: n={g.n}, m={g.m}, LB={g.compute_lb()},"
    f" UB={g.compute_rcm_ub()}",
    flush=True,
)

solvers = [
    ("Pairwise + Iterative SAT", PairwiseIterativeSolver(g)),
    ("Pairwise + Incremental SAT", PairwiseIncrementalSolver(g)),
    ("Order + Iterative SAT", OrderIterativeSolver(g)),
    ("Order + Incremental SAT", OrderIncrementalSolver(g)),
]

for name, s in solvers:
    t0 = time.time()
    res = s.solve(use_heuristics=False, use_components=True, verbose=True)
    dt = time.time() - t0
    print(
        f"{name} -> Bandwidth={res.bandwidth}, Time={dt:.3f}s,"
        f" Iters={res.iterations}, Clauses={res.clauses_count}",
        flush=True,
    )


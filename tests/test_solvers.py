import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
import time
from src.graph import GraphData
from src.solvers import (
    OrderIncrementalSolver,
    OrderIterativeSolver,
    PairwiseIncrementalSolver,
    PairwiseIterativeSolver,
)


def run_test():
    mtx_path = "data/bcspwr01.mtx"
    g = GraphData.from_mtx(mtx_path)
    print("\n========================================================")
    print(f"BENCHMARK: {g.name} (n={g.n}, m={g.m})")
    print(
        f"Optimization 4.4.2 -> LB: {g.compute_lb()}, RCM UB:"
        f" {g.compute_rcm_ub()}"
    )
    print(
        f"Optimization 4.4.3 -> Components: {len(g.get_connected_components())}"
    )
    print("Paper Target: Best = 5, LB = 5")
    print("========================================================\n")

    solvers = [
        ("Pairwise + Iterative SAT", PairwiseIterativeSolver(g)),
        ("Pairwise + Incremental SAT", PairwiseIncrementalSolver(g)),
        ("Order + Iterative SAT", OrderIterativeSolver(g)),
        ("Order + Incremental SAT", OrderIncrementalSolver(g)),
    ]

    for name, solver in solvers:
        print(f"--- Running: {name} ---")
        t0 = time.time()
        res = solver.solve(
            use_heuristics=True, use_components=True, verbose=True
        )
        dt = time.time() - t0
        print(
            f"==> RESULT: Bandwidth = {res.bandwidth} (Found in {dt:.3f}s,"
            f" {res.iterations} iters, {res.clauses_count} clauses)\n"
        )


if __name__ == "__main__":
    run_test()


"""Real PySAT and worker-process tests for resumable benchmark sessions."""

import multiprocessing as mp
import json
from pathlib import Path
import tempfile
import time
import unittest

from src.graph import GraphData
from src.solvers import (
    BaseBMPSolver, SolverResult, OrderIncrementalSolver, OrderIterativeSolver,
    PairwiseIncrementalSolver, PairwiseIterativeSolver,
)


class SlowSolver(BaseBMPSolver):
    def _solve_single_graph(self, **kwargs):
        time.sleep(30)
        return SolverResult(1, 0, 0)


class BrokenSolver(BaseBMPSolver):
    def _solve_single_graph(self, **kwargs):
        raise RuntimeError("worker failure for test")


class LocalProgressSolver(BaseBMPSolver):
    def _solve_single_graph(self, **kwargs):
        self._queue.put(("PROGRESS", 0, 99, {1: 1}, 1, 1))
        time.sleep(30)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.graph = GraphData.from_edge_list(4, [(1, 2), (2, 3), (3, 4), (4, 1)])

    def assert_no_worker_left(self):
        self.assertEqual(mp.active_children(), [])

    def test_absolute_unicode_dataset_path(self):
        with tempfile.TemporaryDirectory(prefix="đồ_thị_") as folder:
            path = Path(folder) / "ma_trận.mtx"
            path.write_text("%%MatrixMarket matrix coordinate pattern symmetric\n4 4 4\n1 2\n2 3\n3 4\n4 1\n", encoding="ascii")
            graph = GraphData.from_mtx(str(path.resolve()))
            self.assertEqual((graph.n, graph.m), (4, 4))

    def test_small_graph_obeys_timeout(self):
        started = time.monotonic()
        result = SlowSolver(self.graph, timeout=0.2).solve(use_components=False)
        self.assertEqual(result.status, "TIMEOUT")
        self.assertLess(time.monotonic() - started, 8)
        self.assertEqual(len(result.labeling), 4)
        self.assertEqual(len(json.loads(json.dumps(result.labeling))), 4)
        self.assert_no_worker_left()

    def test_worker_error_reaches_parent_and_is_not_timeout(self):
        with self.assertRaisesRegex(RuntimeError, "worker failure for test"):
            BrokenSolver(self.graph, timeout=15).solve(use_components=False)
        self.assert_no_worker_left()

    def test_component_progress_never_replaces_full_labeling(self):
        result = LocalProgressSolver(self.graph, timeout=3).solve(use_components=False)
        self.assertEqual(result.status, "TIMEOUT")
        self.assertEqual(len(result.labeling), 4)
        self.assert_no_worker_left()

    def test_real_sat_result_survives_worker_queue(self):
        result = OrderIncrementalSolver(self.graph, timeout=15).solve(
            use_heuristics=False, use_components=False,
        )
        self.assertEqual((result.status, result.bandwidth), ("OPTIMAL", 2))
        self.assertTrue(self.graph.verify_labeling(result.labeling, 2)[0])
        self.assertGreater(result.iterations, 0)
        self.assert_no_worker_left()

    def test_real_sat_encodings_still_solve_for_both_search_strategies(self):
        for solver_cls in (OrderIncrementalSolver, OrderIterativeSolver,
                           PairwiseIncrementalSolver, PairwiseIterativeSolver):
            for strategy in ("linear", "binary"):
                with self.subTest(solver=solver_cls.__name__, strategy=strategy):
                    result = solver_cls(self.graph, amo_method="sequential", timeout=0).solve(
                        use_heuristics=False, use_components=False, strategy=strategy,
                    )
                    self.assertEqual(result.bandwidth, 2)
                    self.assertTrue(self.graph.verify_labeling(result.labeling, 2)[0])


if __name__ == "__main__":
    unittest.main()

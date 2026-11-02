"""Bộ kiểm thử đơn vị tự động (Automated Unit Tests)

Kiểm tra tính đúng đắn toán học 100% của:
1. GraphData: nạp dữ liệu, tính bậc lớn nhất, đường kính, cận dưới LB, cận trên RCM UB.
2. Tối ưu 4.4.3: Phân rã thành phần liên thông (Connected Components).
3. Chứng chỉ lời giải (Solution Certificate): Kiểm tra song ánh và độ lệch cạnh.
4. Cả 4 bộ giải SAT:
   - PairwiseIterativeSolver
   - PairwiseIncrementalSolver
   - OrderIterativeSolver
   - OrderIncrementalSolver
"""

import sys
import unittest

sys.path.insert(0, ".")
from src.graph import GraphData
from src.solvers import (
    OrderIncrementalSolver,
    OrderIterativeSolver,
    PairwiseIncrementalSolver,
    PairwiseIterativeSolver,
)
from src.baselines import (
    CPSATSolver,
    CplexCPSolver,
    GurobiMIPSolver,
    CplexMIPSolver,
)


class TestGraphData(unittest.TestCase):

    def test_path_graph_p4(self):
        # Đồ thị đường đi P4: 1 - 2 - 3 - 4 (n=4, m=3, Bw=1)
        edges = [(1, 2), (2, 3), (3, 4)]
        g = GraphData.from_edge_list(n=4, edges=edges, name="P4")
        self.assertEqual(g.n, 4)
        self.assertEqual(g.m, 3)
        self.assertEqual(g.get_max_degree(), 2)
        self.assertEqual(g.get_diameter(), 3)
        self.assertEqual(g.compute_lb(), 1)
        self.assertEqual(g.compute_rcm_ub(), 1)

    def test_cycle_graph_c4(self):
        # Đồ thị chu trình C4: 1 - 2 - 3 - 4 - 1 (n=4, m=4, Bw=2)
        edges = [(1, 2), (2, 3), (3, 4), (4, 1)]
        g = GraphData.from_edge_list(n=4, edges=edges, name="C4")
        self.assertEqual(g.n, 4)
        self.assertEqual(g.m, 4)
        self.assertEqual(g.get_max_degree(), 2)
        self.assertEqual(g.get_diameter(), 2)
        self.assertEqual(g.compute_lb(), 2)
        self.assertEqual(g.compute_rcm_ub(), 2)

    def test_disconnected_components(self):
        # Đồ thị 2 thành phần liên thông: C4 và P3
        edges = [(1, 2), (2, 3), (3, 4), (4, 1), (5, 6), (6, 7)]
        g = GraphData.from_edge_list(n=7, edges=edges, name="C4_P3")
        comps = g.get_connected_components()
        self.assertEqual(len(comps), 2)
        self.assertEqual({comps[0].n, comps[1].n}, {4, 3})


class TestSolversCorrectness(unittest.TestCase):

    def setUp(self):
        # C4 (Bw = 2)
        self.c4_edges = [(1, 2), (2, 3), (3, 4), (4, 1)]
        self.g_c4 = GraphData.from_edge_list(4, self.c4_edges, name="C4")

        # Disconnected C4 + P3 (Bw = 2)
        self.disc_edges = [(1, 2), (2, 3), (3, 4), (4, 1), (5, 6), (6, 7)]
        self.g_disc = GraphData.from_edge_list(7, self.disc_edges, name="C4_P3")

    def _test_solver_on_graph(self, solver_cls, graph, expected_bw, use_heuristics=True, use_components=True):
        solver = solver_cls(graph)
        res = solver.solve(
            use_heuristics=use_heuristics,
            use_components=use_components,
            strategy="linear",
            verbose=False,
        )
        self.assertEqual(res.bandwidth, expected_bw)
        valid, actual_bw = graph.verify_labeling(res.labeling, expected_bw)
        self.assertTrue(valid, f"Phép gán nhãn không hợp lệ: {actual_bw}")
        self.assertEqual(actual_bw, expected_bw)

    def test_pairwise_iterative(self):
        self._test_solver_on_graph(PairwiseIterativeSolver, self.g_c4, 2)
        self._test_solver_on_graph(PairwiseIterativeSolver, self.g_disc, 2)

    def test_pairwise_incremental(self):
        self._test_solver_on_graph(PairwiseIncrementalSolver, self.g_c4, 2)
        self._test_solver_on_graph(PairwiseIncrementalSolver, self.g_disc, 2)

    def test_order_iterative(self):
        self._test_solver_on_graph(OrderIterativeSolver, self.g_c4, 2)
        self._test_solver_on_graph(OrderIterativeSolver, self.g_disc, 2)

    def test_order_incremental(self):
        self._test_solver_on_graph(OrderIncrementalSolver, self.g_c4, 2)
        self._test_solver_on_graph(OrderIncrementalSolver, self.g_disc, 2)

    def test_cp_sat_baseline(self):
        self._test_solver_on_graph(CPSATSolver, self.g_c4, 2)
        self._test_solver_on_graph(CPSATSolver, self.g_disc, 2)

    def test_cplex_cp_baseline(self):
        self._test_solver_on_graph(CplexCPSolver, self.g_c4, 2)
        self._test_solver_on_graph(CplexCPSolver, self.g_disc, 2)

    def test_gurobi_mip_baseline(self):
        self._test_solver_on_graph(GurobiMIPSolver, self.g_c4, 2)
        self._test_solver_on_graph(GurobiMIPSolver, self.g_disc, 2)

    def test_cplex_mip_baseline(self):
        self._test_solver_on_graph(CplexMIPSolver, self.g_c4, 2)
        self._test_solver_on_graph(CplexMIPSolver, self.g_disc, 2)


if __name__ == "__main__":
    unittest.main()

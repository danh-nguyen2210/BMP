"""Module triển khai đầy đủ 4 bộ giải đối chuẩn (Exact Baselines) theo yêu cầu của Giảng viên:
1. CPSATSolver: Lập trình ràng buộc (Constraint Programming) sử dụng Google OR-Tools CP-SAT
2. CplexCPSolver: Lập trình ràng buộc (Constraint Programming) sử dụng IBM ILOG CPLEX CP Optimizer
3. GurobiMIPSolver: Quy hoạch tuyến tính nguyên (ILP/MIP) sử dụng Gurobi Optimizer
4. CplexMIPSolver: Quy hoạch tuyến tính nguyên (ILP/MIP) sử dụng IBM ILOG CPLEX MIP Optimizer

Tất cả các lớp kế thừa từ BaseBMPSolver để tích hợp liền mạch vào hệ thống.
"""

import time
from src.solvers import BaseBMPSolver, SolverResult

# 1. Google OR-Tools CP-SAT
from ortools.sat.python import cp_model

# 2. Gurobi Optimizer
try:
    import gurobipy as gp
    from gurobipy import GRB
    HAS_GUROBI = True
except ImportError:
    HAS_GUROBI = False

# 3. IBM ILOG CPLEX CP & MIP
try:
    import docplex.mp.model as cpx_mp
    from docplex.cp.model import CpoModel
    HAS_CPLEX = True
except ImportError:
    HAS_CPLEX = False


# ==============================================================================
# 1. GOOGLE OR-TOOLS CP-SAT
# ==============================================================================
class CPSATSolver(BaseBMPSolver):
    """Bộ giải đối chuẩn bằng Constraint Programming (Google OR-Tools CP-SAT)."""

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, labeling={u: u for u in range(1, n + 1)})

        low = self.graph.compute_lb() if use_heuristics else 1
        high = self.graph.compute_rcm_ub() if use_heuristics else n - 1

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        t0 = time.time()
        model = cp_model.CpModel()

        # 1. Biến nguyên miền rời rạc: f[u] in [1, n]
        f = {u: model.NewIntVar(1, n, f"f_{u}") for u in range(1, n + 1)}
        bw = model.NewIntVar(low, high, "bw")

        # 2. Ràng buộc toàn cục AllDifferent (Song ánh cực mạnh)
        model.AddAllDifferent([f[u] for u in range(1, n + 1)])

        # 3. Ràng buộc khoảng cách cạnh: |f[u] - f[v]| <= bw
        for u, v in self.edges:
            diff = model.NewIntVar(0, n - 1, f"diff_{u}_{v}")
            model.AddAbsEquality(diff, f[u] - f[v])
            model.Add(diff <= bw)

        # 4. Hàm mục tiêu: Cực tiểu hóa băng thông
        model.Minimize(bw)

        solver = cp_model.CpSolver()
        if not verbose:
            solver.parameters.log_search_progress = False

        status = solver.Solve(model)
        elapsed = time.time() - t0

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            best_bw = int(solver.Value(bw))
            labeling = {u: int(solver.Value(f[u])) for u in range(1, n + 1)}
            return SolverResult(
                bandwidth=best_bw,
                runtime=elapsed,
                iterations=int(solver.NumBranches()),
                clauses_count=0,
                vars_count=n + len(self.edges) + 1,
                labeling=labeling,
            )
        else:
            return SolverResult(bandwidth=-1, runtime=elapsed, iterations=0)


# ==============================================================================
# 2. IBM ILOG CPLEX CP OPTIMIZER
# ==============================================================================
class CplexCPSolver(BaseBMPSolver):
    """Bộ giải đối chuẩn bằng Constraint Programming sử dụng IBM ILOG CPLEX CP Optimizer."""

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        if not HAS_CPLEX:
            raise RuntimeError("Thư viện docplex chưa được cài đặt!")

        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, labeling={u: u for u in range(1, n + 1)})

        low = self.graph.compute_lb() if use_heuristics else 1
        high = self.graph.compute_rcm_ub() if use_heuristics else n - 1

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        t0 = time.time()
        mdl = CpoModel(name="BMP_CplexCP")

        # 1. Biến nguyên miền rời rạc
        f = {u: mdl.integer_var(1, n, name=f"f_{u}") for u in range(1, n + 1)}
        B = mdl.integer_var(low, high, name="B")

        # 2. Ràng buộc song ánh toàn cục AllDifferent
        mdl.add(mdl.all_diff([f[u] for u in range(1, n + 1)]))

        # 3. Ràng buộc băng thông cạnh: |f[u] - f[v]| <= B
        for u, v in self.edges:
            mdl.add(mdl.abs(f[u] - f[v]) <= B)

        # 4. Hàm mục tiêu
        mdl.minimize(B)

        msol = mdl.solve(log_output=None)
        elapsed = time.time() - t0

        if msol and msol.is_solution():
            best_bw = int(msol.get_value(B))
            labeling = {u: int(msol.get_value(f[u])) for u in range(1, n + 1)}
            return SolverResult(
                bandwidth=best_bw,
                runtime=elapsed,
                iterations=1,
                clauses_count=0,
                vars_count=n + 1,
                labeling=labeling,
            )
        else:
            return SolverResult(bandwidth=-1, runtime=elapsed, iterations=0)


# ==============================================================================
# 3. GUROBI MIP OPTIMIZER
# ==============================================================================
class GurobiMIPSolver(BaseBMPSolver):
    """Bộ giải đối chuẩn bằng Integer Linear Programming (ILP/MIP) sử dụng Gurobi Optimizer."""

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        if not HAS_GUROBI:
            raise RuntimeError("Thư viện gurobipy chưa được cài đặt!")

        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, labeling={u: u for u in range(1, n + 1)})

        low = self.graph.compute_lb() if use_heuristics else 1
        high = self.graph.compute_rcm_ub() if use_heuristics else n - 1

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        t0 = time.time()
        model = gp.Model("BMP_Gurobi")
        if not verbose:
            model.setParam("OutputFlag", 0)

        # 1. Biến nhị phân gán nhãn X[u, i] và biến nguyên mục tiêu B
        X = model.addVars(range(1, n + 1), range(1, n + 1), vtype=GRB.BINARY, name="X")
        B = model.addVar(lb=low, ub=high, vtype=GRB.INTEGER, name="B")

        # 2. Hàm mục tiêu
        model.setObjective(B, GRB.MINIMIZE)

        # 3. Ràng buộc song ánh:
        # Mỗi đỉnh nhận đúng 1 nhãn
        model.addConstrs((X.sum(u, "*") == 1 for u in range(1, n + 1)), name="one_label_per_node")
        # Mỗi nhãn gán cho đúng 1 đỉnh
        model.addConstrs((X.sum("*", i) == 1 for i in range(1, n + 1)), name="one_node_per_label")

        # 4. Tuyến tính hóa khoảng cách cạnh: |pos_u - pos_v| <= B
        for u, v in self.edges:
            pos_u = gp.quicksum(i * X[u, i] for i in range(1, n + 1))
            pos_v = gp.quicksum(i * X[v, i] for i in range(1, n + 1))
            model.addConstr(pos_u - pos_v <= B)
            model.addConstr(pos_v - pos_u <= B)

        model.optimize()
        elapsed = time.time() - t0

        if model.status in (GRB.OPTIMAL, GRB.SUBOPTIMAL):
            best_bw = int(round(B.X))
            labeling = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if X[u, i].X > 0.5:
                        labeling[u] = i
                        break
            return SolverResult(
                bandwidth=best_bw,
                runtime=elapsed,
                iterations=int(model.NodeCount),
                clauses_count=2 * n + 2 * len(self.edges),
                vars_count=n * n + 1,
                labeling=labeling,
            )
        else:
            return SolverResult(bandwidth=-1, runtime=elapsed, iterations=0)


# ==============================================================================
# 4. IBM ILOG CPLEX MIP OPTIMIZER
# ==============================================================================
class CplexMIPSolver(BaseBMPSolver):
    """Bộ giải đối chuẩn bằng Integer Linear Programming (ILP/MIP) sử dụng IBM ILOG CPLEX MIP."""

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        if not HAS_CPLEX:
            raise RuntimeError("Thư viện docplex chưa được cài đặt!")

        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, labeling={u: u for u in range(1, n + 1)})

        low = self.graph.compute_lb() if use_heuristics else 1
        high = self.graph.compute_rcm_ub() if use_heuristics else n - 1

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        t0 = time.time()
        mdl = cpx_mp.Model(name="BMP_CplexMIP")

        # 1. Biến nhị phân gán nhãn X[u, i] và biến nguyên mục tiêu B
        X = mdl.binary_var_matrix(range(1, n + 1), range(1, n + 1), name="X")
        B = mdl.integer_var(lb=low, ub=high, name="B")

        # 2. Hàm mục tiêu
        mdl.minimize(B)

        # 3. Ràng buộc song ánh:
        for u in range(1, n + 1):
            mdl.add_constraint(mdl.sum(X[u, i] for i in range(1, n + 1)) == 1)
        for i in range(1, n + 1):
            mdl.add_constraint(mdl.sum(X[u, i] for u in range(1, n + 1)) == 1)

        # 4. Tuyến tính hóa khoảng cách cạnh: |pos_u - pos_v| <= B
        for u, v in self.edges:
            pos_u = mdl.sum(i * X[u, i] for i in range(1, n + 1))
            pos_v = mdl.sum(i * X[v, i] for i in range(1, n + 1))
            mdl.add_constraint(pos_u - pos_v <= B)
            mdl.add_constraint(pos_v - pos_u <= B)

        msol = mdl.solve(log_output=verbose)
        elapsed = time.time() - t0

        if msol is not None:
            best_bw = int(round(msol.get_value(B)))
            labeling = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if msol.get_value(X[u, i]) > 0.5:
                        labeling[u] = i
                        break
            return SolverResult(
                bandwidth=best_bw,
                runtime=elapsed,
                iterations=1,
                clauses_count=2 * n + 2 * len(self.edges),
                vars_count=n * n + 1,
                labeling=labeling,
            )
        else:
            return SolverResult(bandwidth=-1, runtime=elapsed, iterations=0)

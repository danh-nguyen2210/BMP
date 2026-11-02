"""Module triển khai 4 bộ giải SAT cho bài toán BMP:
1. PairwiseIterativeSolver: Pairwise Encoding + SAT nhiều lần
2. PairwiseIncrementalSolver: Pairwise Encoding + Incremental SAT
3. OrderIterativeSolver: Order Encoding (Biến phụ G của Thầy) + SAT nhiều lần
4. OrderIncrementalSolver: Order Encoding (Biến phụ G của Thầy) + Incremental SAT

Tích hợp:
- Tối ưu 4.4.2: Thu hẹp khoảng tìm kiếm [LB, UB] bằng Heuristic RCM và lý thuyết đồ thị.
- Tối ưu 4.4.3: Phân rã thành phần liên thông (Connected Components).
"""

import time
from pysat.solvers import Cadical153


class SolverResult:

    def __init__(
        self,
        bandwidth,
        runtime,
        iterations,
        clauses_count=0,
        vars_count=0,
        labeling=None,
    ):
        self.bandwidth = bandwidth
        self.runtime = runtime
        self.iterations = iterations
        self.clauses_count = clauses_count
        self.vars_count = vars_count
        self.labeling = labeling or {}

    def __repr__(self):
        return (
            f"SolverResult(bw={self.bandwidth}, time={self.runtime:.3f}s,"
            f" iters={self.iterations}, clauses={self.clauses_count},"
            f" vars={self.vars_count})"
        )


class BaseBMPSolver:

    def __init__(self, graph):
        self.graph = graph
        self.n = graph.n
        self.edges = graph.edges

    def solve(
        self,
        use_heuristics=True,
        use_components=True,
        strategy="binary",
        verbose=False,
    ):
        """Phương thức giải chính điều phối tối ưu 4.4.2 và 4.4.3.

        strategy: 'binary' (tìm kiếm nhị phân) hoặc 'linear' (tìm kiếm tuyến
        tính giảm dần từ UB).
        """
        start_time = time.time()

        # Tối ưu 4.4.3: Phân rã thành phần liên thông
        if use_components:
            components = self.graph.get_connected_components()
            if len(components) > 1:
                if verbose:
                    print(
                        f"[{self.__class__.__name__}] Decomposed into"
                        f" {len(components)} connected components."
                    )
                max_bw = 0
                total_iters = 0
                total_clauses = 0
                total_vars = 0
                global_labeling = {}
                total_offset = 0

                for comp in components:
                    if comp.n <= 1:
                        comp_bw = 0
                        comp_labeling = {1: 1}
                    elif comp.n == 2:
                        comp_bw = 1 if comp.m > 0 else 0
                        comp_labeling = {1: 1, 2: 2}
                    else:
                        sub_solver = self.__class__(comp)
                        res = sub_solver._solve_single_graph(
                            use_heuristics=use_heuristics,
                            strategy=strategy,
                            verbose=verbose,
                        )
                        comp_bw = res.bandwidth
                        comp_labeling = res.labeling
                        total_iters += res.iterations
                        total_clauses += res.clauses_count
                        total_vars += res.vars_count

                    if comp_bw > max_bw:
                        max_bw = comp_bw

                    orig_nodes = getattr(comp, "original_nodes", list(range(1, comp.n + 1)))
                    for sub_u, lbl in comp_labeling.items():
                        orig_u = orig_nodes[sub_u - 1]
                        global_labeling[orig_u] = lbl + total_offset
                    total_offset += comp.n

                elapsed = time.time() - start_time
                return SolverResult(
                    bandwidth=max_bw,
                    runtime=elapsed,
                    iterations=total_iters,
                    clauses_count=total_clauses,
                    vars_count=total_vars,
                    labeling=global_labeling,
                )

        # Nếu đồ thị liên thông hoặc không dùng phân rã
        res = self._solve_single_graph(
            use_heuristics=use_heuristics, strategy=strategy, verbose=verbose
        )
        res.runtime = time.time() - start_time
        return res

    def _solve_single_graph(self, use_heuristics, verbose):
        raise NotImplementedError


# ==============================================================================
# 1. PAIRWISE + ITERATIVE SAT (SAT NHIỀU LẦN)
# ==============================================================================
class PairwiseIterativeSolver(BaseBMPSolver):

    def _get_var_x(self, u, i):
        # Biến X[u, i] đánh số 1-indexed: 1 .. n^2
        return (u - 1) * self.n + i

    def _build_base_clauses(self):
        clauses = []
        n = self.n

        # 1. ALO: Mỗi đỉnh nhận ít nhất 1 nhãn
        for u in range(1, n + 1):
            clauses.append([self._get_var_x(u, i) for i in range(1, n + 1)])

        # 2. AMO: Mỗi đỉnh nhận tối đa 1 nhãn
        for u in range(1, n + 1):
            for i in range(1, n + 1):
                for j in range(i + 1, n + 1):
                    clauses.append(
                        [-self._get_var_x(u, i), -self._get_var_x(u, j)]
                    )

        # 3. Đơn ánh (Injective): Không 2 đỉnh nào cùng nhãn
        for i in range(1, n + 1):
            for u in range(1, n + 1):
                for v in range(u + 1, n + 1):
                    clauses.append(
                        [-self._get_var_x(u, i), -self._get_var_x(v, i)]
                    )

        return clauses

    def _get_bandwidth_clauses(self, k):
        # Ràng buộc băng thông <= k: cấm |i - j| > k cho mọi cạnh (u, v)
        clauses = []
        n = self.n
        for u, v in self.edges:
            for i in range(1, n + 1):
                for j in range(1, n + 1):
                    if abs(i - j) > k:
                        clauses.append(
                            [-self._get_var_x(u, i), -self._get_var_x(v, j)]
                        )
        return clauses

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0)

        # Tối ưu 4.4.2: Xác định khoảng [low, high]
        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Pairwise-Iterative] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        base_clauses = self._build_base_clauses()
        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        last_clauses_count = len(base_clauses)
        vars_count = n * n

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._get_var_x(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        if strategy == "linear":
            for k in range(high - 1, low - 1, -1):
                iterations += 1
                with Cadical153() as solver:
                    for cl in base_clauses:
                        solver.add_clause(cl)
                    bw_clauses = self._get_bandwidth_clauses(k)
                    for cl in bw_clauses:
                        solver.add_clause(cl)

                    last_clauses_count = len(base_clauses) + len(bw_clauses)
                    is_sat = solver.solve()
                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(f"  Iter {iterations}: Test k={k} -> {status}")
                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                    else:
                        break
        else:  # binary search
            while low <= high:
                mid = (low + high) // 2
                iterations += 1

                with Cadical153() as solver:
                    for cl in base_clauses:
                        solver.add_clause(cl)
                    bw_clauses = self._get_bandwidth_clauses(mid)
                    for cl in bw_clauses:
                        solver.add_clause(cl)

                    last_clauses_count = len(base_clauses) + len(bw_clauses)
                    is_sat = solver.solve()

                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  Iter {iterations}: Test k={mid} -> {status}"
                            f" ({last_clauses_count} clauses)"
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw,
            runtime=0,
            iterations=iterations,
            clauses_count=last_clauses_count,
            vars_count=vars_count,
            labeling=best_labeling,
        )


# ==============================================================================
# 2. PAIRWISE + INCREMENTAL SAT (SAT GIA TĂNG)
# ==============================================================================
class PairwiseIncrementalSolver(PairwiseIterativeSolver):

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0)

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Pairwise-Incremental] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        vars_count = n * n
        total_clauses = 0

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._get_var_x(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        # Tái sử dụng hàm _build_base_clauses() từ PairwiseIterativeSolver
        base_clauses = self._build_base_clauses()

        # Khởi tạo solver một lần duy nhất trong toàn bộ tiến trình
        with Cadical153() as solver:
            for cl in base_clauses:
                solver.add_clause(cl)
                total_clauses += 1

            act_var_counter = vars_count

            if strategy == "linear":
                for k in range(high - 1, low - 1, -1):
                    iterations += 1
                    act_var_counter += 1
                    act_lit = act_var_counter

                    # Tái sử dụng hàm _get_bandwidth_clauses(k) gắn kèm phủ định act_lit
                    for cl in self._get_bandwidth_clauses(k):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    is_sat = solver.solve(assumptions=[act_lit])
                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(f"  [Inc] Iter {iterations}: Test k={k} -> {status}")

                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                    else:
                        break
            else:  # binary search
                while low <= high:
                    mid = (low + high) // 2
                    iterations += 1

                    act_var_counter += 1
                    act_lit = act_var_counter

                    for cl in self._get_bandwidth_clauses(mid):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    is_sat = solver.solve(assumptions=[act_lit])

                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  [Inc] Iter {iterations}: Test k={mid} ->"
                            f" {status}"
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw,
            runtime=0,
            iterations=iterations,
            clauses_count=total_clauses,
            vars_count=act_var_counter,
            labeling=best_labeling,
        )


# ==============================================================================
# 3. ORDER + ITERATIVE SAT (ORDER ENCODING VỚI BIẾN PHỤ G CỦA THẦY)
# ==============================================================================
class OrderIterativeSolver(BaseBMPSolver):

    def __init__(self, graph):
        super().__init__(graph)
        self.var_map = {}
        self.var_counter = 0

    def _get_var(self, name):
        if name not in self.var_map:
            self.var_counter += 1
            self.var_map[name] = self.var_counter
        return self.var_map[name]

    def _X(self, u, i):
        return self._get_var(f"X_{u}_{i}")

    def _G(self, u, i):
        return self._get_var(f"G_{u}_{i}")

    def _build_base_clauses(self):
        clauses = []
        n = self.n

        # 1. ALO và AMO trên X
        for u in range(1, n + 1):
            clauses.append([self._X(u, i) for i in range(1, n + 1)])
            for i in range(1, n + 1):
                for j in range(i + 1, n + 1):
                    clauses.append([-self._X(u, i), -self._X(u, j)])

        # 2. Đơn ánh trên X
        for i in range(1, n + 1):
            for u in range(1, n + 1):
                for v in range(u + 1, n + 1):
                    clauses.append([-self._X(u, i), -self._X(v, i)])

        # 3. Tính chất thứ tự của G: G(u, i) -> G(u, i-1)
        for u in range(1, n + 1):
            for i in range(3, n + 1):
                clauses.append([-self._G(u, i), self._G(u, i - 1)])

        # 4. Cầu nối 2 chiều giữa X và G: X(u, i) <=> G(u, i) ^ ~G(u, i+1)
        for u in range(1, n + 1):
            for i in range(1, n + 1):
                # X -> G
                if i >= 2:
                    clauses.append([-self._X(u, i), self._G(u, i)])
                if i <= n - 1:
                    clauses.append([-self._X(u, i), -self._G(u, i + 1)])

                # G -> X: (G(u, i) ^ ~G(u, i+1)) -> X(u, i)
                if i == 1:
                    clauses.append([self._G(u, 2), self._X(u, 1)])
                elif i == n:
                    clauses.append([-self._G(u, n), self._X(u, n)])
                else:
                    clauses.append(
                        [-self._G(u, i), self._G(u, i + 1), self._X(u, i)]
                    )

        return clauses

    def _get_bandwidth_clauses(self, k):
        """Ràng buộc Băng thông <= k (tương ứng b = k + 1) theo biến G của

        Thầy:

        X(u, i) -> ~G(v, i + k + 1) ^ G(v, i - k)
        """
        clauses = []
        n = self.n

        for u, v in self.edges:
            for src, dst in [(u, v), (v, u)]:
                for i in range(1, n + 1):
                    # Chặn trên: f(dst) < i + k + 1 <=> ~G(dst, i + k + 1)
                    if i + k + 1 <= n:
                        clauses.append(
                            [-self._X(src, i), -self._G(dst, i + k + 1)]
                        )
                    # Chặn dưới: f(dst) >= i - k <=> G(dst, i - k)
                    if i - k >= 2:
                        clauses.append([-self._X(src, i), self._G(dst, i - k)])

        return clauses

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0)

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Order-Iterative] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        self.var_map.clear()
        self.var_counter = 0
        base_clauses = self._build_base_clauses()
        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        last_clauses_count = len(base_clauses)

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._X(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        if strategy == "linear":
            for k in range(high - 1, low - 1, -1):
                iterations += 1
                with Cadical153() as solver:
                    for cl in base_clauses:
                        solver.add_clause(cl)
                    bw_clauses = self._get_bandwidth_clauses(k)
                    for cl in bw_clauses:
                        solver.add_clause(cl)

                    last_clauses_count = len(base_clauses) + len(bw_clauses)
                    is_sat = solver.solve()
                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(f"  [Order] Iter {iterations}: Test k={k} -> {status}")
                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                    else:
                        break
        else:  # binary search
            while low <= high:
                mid = (low + high) // 2
                iterations += 1

                with Cadical153() as solver:
                    for cl in base_clauses:
                        solver.add_clause(cl)
                    bw_clauses = self._get_bandwidth_clauses(mid)
                    for cl in bw_clauses:
                        solver.add_clause(cl)

                    last_clauses_count = len(base_clauses) + len(bw_clauses)
                    is_sat = solver.solve()

                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  [Order] Iter {iterations}: Test k={mid} ->"
                            f" {status} ({last_clauses_count} clauses)"
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw,
            runtime=0,
            iterations=iterations,
            clauses_count=last_clauses_count,
            vars_count=self.var_counter,
            labeling=best_labeling,
        )


# ==============================================================================
# 4. ORDER + INCREMENTAL SAT (ORDER ENCODING GIA TĂNG)
# ==============================================================================
class OrderIncrementalSolver(OrderIterativeSolver):

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        n = self.n
        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0)

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Order-Incremental] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(bandwidth=high, runtime=0, iterations=0, labeling=self.graph.get_rcm_labeling())

        self.var_map.clear()
        self.var_counter = 0
        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        total_clauses = 0

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._X(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        # Tái sử dụng hàm _build_base_clauses() từ OrderIterativeSolver
        base_clauses = self._build_base_clauses()

        with Cadical153() as solver:
            for cl in base_clauses:
                solver.add_clause(cl)
                total_clauses += 1

            if strategy == "linear":
                for k in range(high - 1, low - 1, -1):
                    iterations += 1
                    act_lit = self._get_var(f"ACT_{k}")

                    # Tái sử dụng hàm _get_bandwidth_clauses(k) gắn kèm phủ định act_lit
                    for cl in self._get_bandwidth_clauses(k):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    is_sat = solver.solve(assumptions=[act_lit])
                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(f"  [Order-Inc] Iter {iterations}: Test k={k} -> {status}")

                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                    else:
                        break
            else:  # binary search
                while low <= high:
                    mid = (low + high) // 2
                    iterations += 1

                    act_lit = self._get_var(f"ACT_{mid}")

                    for cl in self._get_bandwidth_clauses(mid):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    is_sat = solver.solve(assumptions=[act_lit])

                    if verbose:
                        status = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  [Order-Inc] Iter {iterations}: Test k={mid} ->"
                            f" {status}"
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw,
            runtime=0,
            iterations=iterations,
            clauses_count=total_clauses,
            vars_count=self.var_counter,
            labeling=best_labeling,
        )

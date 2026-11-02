"""Module triển khai 4 bộ giải SAT cho bài toán BMP:
1. PairwiseIterativeSolver: Pairwise Encoding + SAT nhiều lần
2. PairwiseIncrementalSolver: Pairwise Encoding + Incremental SAT
3. OrderIterativeSolver: Order Encoding (Biến phụ G của Thầy) + SAT nhiều lần
4. OrderIncrementalSolver: Order Encoding (Biến phụ G của Thầy) + Incremental SAT

Tích hợp:
- BƯỚC 1: Ràng buộc Song ánh cho biến X (Bijective Assignment):
  (1.1) ALO: Mỗi đỉnh nhận ít nhất 1 nhãn.
  (1.2) AMO: Mỗi đỉnh nhận tối đa 1 nhãn.
  (1.3) Injective: Không 2 đỉnh nào trùng nhãn.
  Hỗ trợ các phương pháp mã hóa AMO/ALO nâng cao: pairwise, sequential, binary, commander, product.
- Giới hạn kích thước đồ thị: Đồ thị n > 400 sẽ tự động trả về MEM_EXCEED (Memory Exceeded).
- Giới hạn thời gian (Timeout): Mỗi bài toán tối đa 10 phút (600 giây).
- Tối ưu 4.4.2: Thu hẹp khoảng tìm kiếm [LB, UB] bằng Heuristic RCM và lý thuyết đồ thị.
- Tối ưu 4.4.3: Phân rã thành phần liên thông (Connected Components).
"""

import multiprocessing as mp
import sys
import time
from pysat.solvers import Cadical153
from src.cardinality import encode_bijective_assignment

sys.stdout.reconfigure(encoding="utf-8")


def _worker_solve_entry(solver_instance, use_heuristics, use_components, strategy, verbose, queue):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        solver_instance._queue = queue
        res = solver_instance._solve_direct(
            use_heuristics=use_heuristics,
            use_components=use_components,
            strategy=strategy,
            verbose=verbose,
        )
        queue.put(("RESULT", res))
    except Exception as e:
        import traceback
        queue.put(("ERROR", traceback.format_exc()))


class SolverResult:

    def __init__(
        self,
        bandwidth,
        runtime,
        iterations,
        clauses_count=0,
        vars_count=0,
        labeling=None,
        status="OPTIMAL",
    ):
        self.bandwidth = bandwidth
        self.runtime = runtime
        self.iterations = iterations
        self.clauses_count = clauses_count
        self.vars_count = vars_count
        self.labeling = labeling or {}
        self.status = status

    def __repr__(self):
        return (
            f"SolverResult(bw={self.bandwidth}, status={self.status},"
            f" time={self.runtime:.3f}s, iters={self.iterations},"
            f" clauses={self.clauses_count}, vars={self.vars_count})"
        )


class BaseBMPSolver:

    def __init__(self, graph, amo_method="pairwise", timeout=600.0):
        self.graph = graph
        self.n = graph.n
        self.edges = graph.edges
        self.amo_method = amo_method.lower().replace("-", "_").replace(" ", "")
        self.timeout = timeout

    def solve(
        self,
        use_heuristics=True,
        use_components=True,
        strategy="binary",
        verbose=False,
    ):
        """Phương thức giải chính điều phối tối ưu 4.4.2, 4.4.3 và quản lý Timeout cứng qua Process Watchdog."""
        start_time = time.time()
        self.start_time = start_time

        # Kiểm tra giới hạn bộ nhớ theo yêu cầu: n > 400 không cần chạy, trả về MEM_EXCEED
        if self.n > 400:
            if verbose:
                print(
                    f"[{self.__class__.__name__}] n = {self.n} > 400 ->"
                    " Memory Exceeded (MEM_EXCEED). Bỏ qua giải toán.",
                    flush=True,
                )
            return SolverResult(
                bandwidth="MEM_EXCEED",
                runtime=0.0,
                iterations=0,
                clauses_count=0,
                vars_count=0,
                status="MEM_EXCEED",
            )

        # Chạy trong tiến trình con (Process Watchdog) cho đồ thị n > 30 để ngắt cứng 100% khi hết timeout
        if getattr(self, "timeout", None) and self.timeout > 0 and self.n > 30:
            q = mp.Queue()
            p = mp.Process(
                target=_worker_solve_entry,
                args=(self, use_heuristics, use_components, strategy, verbose, q),
            )
            t0 = time.time()
            p.start()

            best_bw = self.graph.compute_rcm_ub() if use_heuristics else self.n - 1
            best_lbl = self.graph.get_rcm_labeling()
            total_iters = 0
            total_clauses = 0
            total_vars = 0

            while time.time() - t0 < self.timeout:
                if not p.is_alive():
                    break
                while not q.empty():
                    try:
                        msg = q.get_nowait()
                        if msg[0] == "PROGRESS":
                            best_bw = msg[1]
                            total_iters = msg[2]
                            best_lbl = msg[3]
                            total_clauses = msg[4]
                            total_vars = msg[5]
                        elif msg[0] == "RESULT":
                            p.join(timeout=1)
                            return msg[1]
                        elif msg[0] == "ERROR":
                            p.join(timeout=1)
                            raise RuntimeError(msg[1])
                    except Exception:
                        break
                time.sleep(0.1)

            init_ub = self.graph.compute_rcm_ub() if use_heuristics else self.n - 1
            if p.is_alive():
                if verbose:
                    print(
                        f"\n  [Timeout] Quá thời gian quy định ({self.timeout}s). Dừng tiến trình solver...",
                        flush=True,
                    )
                p.terminate()
                p.join(timeout=2)
                if p.is_alive():
                    p.kill()
                    p.join()
                reported_bw = best_bw if (total_iters > 0 and best_bw != init_ub) else "TIMEOUT"
                return SolverResult(
                    bandwidth=reported_bw,
                    runtime=time.time() - t0,
                    iterations=total_iters,
                    clauses_count=total_clauses,
                    vars_count=total_vars,
                    labeling=best_lbl,
                    status="TIMEOUT",
                )
            else:
                p.join()
                while not q.empty():
                    msg = q.get_nowait()
                    if msg[0] == "RESULT":
                        return msg[1]
                    elif msg[0] == "ERROR":
                        raise RuntimeError(msg[1])
                reported_bw = best_bw if (total_iters > 0 and best_bw != init_ub) else "TIMEOUT"
                return SolverResult(
                    bandwidth=reported_bw,
                    runtime=time.time() - t0,
                    iterations=total_iters,
                    clauses_count=total_clauses,
                    vars_count=total_vars,
                    labeling=best_lbl,
                    status="TIMEOUT",
                )

        return self._solve_direct(
            use_heuristics=use_heuristics,
            use_components=use_components,
            strategy=strategy,
            verbose=verbose,
        )

    def _solve_direct(
        self,
        use_heuristics=True,
        use_components=True,
        strategy="binary",
        verbose=False,
    ):
        start_time = getattr(self, "start_time", None) or time.time()

        # Tối ưu 4.4.3: Phân rã thành phần liên thông
        if use_components:
            components = self.graph.get_connected_components()
            if len(components) > 1:
                if verbose:
                    print(
                        f"[{self.__class__.__name__}] Decomposed into"
                        f" {len(components)} connected components.",
                        flush=True,
                    )
                max_bw = 0
                total_iters = 0
                total_clauses = 0
                total_vars = 0
                global_labeling = {}
                total_offset = 0

                for comp in components:
                    rem_time = max(0.1, self.timeout - (time.time() - start_time))
                    if self.timeout and time.time() - start_time >= self.timeout:
                        return SolverResult(
                            bandwidth="TIMEOUT",
                            runtime=time.time() - start_time,
                            iterations=total_iters,
                            clauses_count=total_clauses,
                            vars_count=total_vars,
                            status="TIMEOUT",
                        )

                    if comp.n <= 1:
                        comp_bw = 0
                        comp_labeling = {1: 1}
                    elif comp.n == 2:
                        comp_bw = 1 if comp.m > 0 else 0
                        comp_labeling = {1: 1, 2: 2}
                    else:
                        sub_solver = self.__class__(
                            comp, amo_method=self.amo_method, timeout=0.0
                        )
                        sub_solver.start_time = self.start_time
                        sub_solver._queue = getattr(self, "_queue", None)
                        res = sub_solver._solve_single_graph(
                            use_heuristics=use_heuristics,
                            strategy=strategy,
                            verbose=verbose,
                        )
                        if res.status in ("MEM_EXCEED", "TIMEOUT"):
                            return res
                        comp_bw = res.bandwidth
                        comp_labeling = res.labeling
                        total_iters += res.iterations
                        total_clauses += res.clauses_count
                        total_vars += res.vars_count

                    if isinstance(comp_bw, int) and comp_bw > max_bw:
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
                    status="OPTIMAL",
                )

        # Nếu đồ thị liên thông hoặc không dùng phân rã
        res = self._solve_single_graph(
            use_heuristics=use_heuristics,
            strategy=strategy,
            verbose=verbose,
        )
        res.runtime = time.time() - start_time
        return res

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        raise NotImplementedError


# ==============================================================================
# 1. PAIRWISE + ITERATIVE SAT (SAT NHIỀU LẦN)
# ==============================================================================
class PairwiseIterativeSolver(BaseBMPSolver):

    def _get_var_x(self, u, i):
        # Biến X[u, i] đánh số 1-indexed: 1 .. n^2
        return (u - 1) * self.n + i

    def _build_base_clauses(self):
        """BƯỚC 1: Ràng buộc Song ánh cho biến X (Bijective Assignment)

        (1.1) ALO: Mỗi đỉnh nhận ít nhất 1 nhãn.
        (1.2) AMO: Mỗi đỉnh nhận tối đa 1 nhãn (qua phương pháp amo_method).
        (1.3) Đơn ánh: Mỗi nhãn gán cho tối đa 1 đỉnh (qua phương pháp amo_method).
        """
        clauses, self.top_var = encode_bijective_assignment(
            self.n,
            self._get_var_x,
            top_id=self.n * self.n,
            amo_method=self.amo_method,
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
        start_time = getattr(self, "start_time", None) or time.time()

        n = self.n
        if n > 400:
            return SolverResult(
                bandwidth="MEM_EXCEED", runtime=0.0, iterations=0, status="MEM_EXCEED"
            )

        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, status="OPTIMAL")

        # Tối ưu 4.4.2: Xác định khoảng [low, high]
        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Pairwise-Iterative ({self.amo_method})] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(
                bandwidth=high,
                runtime=0,
                iterations=0,
                labeling=self.graph.get_rcm_labeling(),
                status="OPTIMAL",
            )

        if verbose:
            print(f"  [Pairwise-Iter] Đang khởi tạo Base Clauses (AMO={self.amo_method})...", flush=True)
        base_clauses = self._build_base_clauses()
        if verbose:
            print(f"  [Pairwise-Iter] Base Clauses xong: {len(base_clauses):,} clauses.", flush=True)

        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        last_clauses_count = len(base_clauses)
        vars_count = getattr(self, "top_var", n * n)
        status = "OPTIMAL"

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
                    if verbose:
                        print(f"  [Pairwise-Iter] Iter {iterations}: Đang kiểm tra k={k} (LB={low}, UB={best_bw} | Clauses: {last_clauses_count:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve()
                    dt_k = time.time() - t_k
                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Pairwise-Iter] Iter {iterations}: Test k={k} -> {s_str} ({dt_k:.2f}s)", flush=True)
                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, last_clauses_count, vars_count))
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
                    if verbose:
                        print(f"  [Pairwise-Iter] Iter {iterations}: Đang kiểm tra k={mid} (Phạm vi: [{low}, {high}] | Clauses: {last_clauses_count:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve()
                    dt_k = time.time() - t_k

                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  [Pairwise-Iter] Iter {iterations}: Test k={mid} -> {s_str} ({dt_k:.2f}s)",
                            flush=True,
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, last_clauses_count, vars_count))
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw if status != "TIMEOUT" or best_bw != high else "TIMEOUT",
            runtime=0,
            iterations=iterations,
            clauses_count=last_clauses_count,
            vars_count=vars_count,
            labeling=best_labeling,
            status=status,
        )


# ==============================================================================
# 2. PAIRWISE + INCREMENTAL SAT (SAT GIA TĂNG)
# ==============================================================================
class PairwiseIncrementalSolver(PairwiseIterativeSolver):

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        start_time = getattr(self, "start_time", None) or time.time()

        n = self.n
        if n > 400:
            return SolverResult(
                bandwidth="MEM_EXCEED", runtime=0.0, iterations=0, status="MEM_EXCEED"
            )

        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, status="OPTIMAL")

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Pairwise-Incremental ({self.amo_method})] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(
                bandwidth=high,
                runtime=0,
                iterations=0,
                labeling=self.graph.get_rcm_labeling(),
                status="OPTIMAL",
            )

        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        status = "OPTIMAL"

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._get_var_x(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        if verbose:
            print(f"  [Pairwise-Inc] Đang khởi tạo Base Clauses (AMO={self.amo_method})...", flush=True)
        base_clauses = self._build_base_clauses()
        vars_count = getattr(self, "top_var", n * n)
        if verbose:
            print(f"  [Pairwise-Inc] Base Clauses xong: {len(base_clauses):,} clauses.", flush=True)
        total_clauses = 0

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

                    for cl in self._get_bandwidth_clauses(k):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    if verbose:
                        print(f"  [Pairwise-Inc] Iter {iterations}: Đang kiểm tra k={k} (LB={low}, UB={best_bw} | Clauses: {total_clauses:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve(assumptions=[act_lit])
                    dt_k = time.time() - t_k
                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Pairwise-Inc] Iter {iterations}: Test k={k} -> {s_str} ({dt_k:.2f}s)", flush=True)

                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, total_clauses, act_var_counter))
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

                    if verbose:
                        print(f"  [Pairwise-Inc] Iter {iterations}: Đang kiểm tra k={mid} (Phạm vi: [{low}, {high}] | Clauses: {total_clauses:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve(assumptions=[act_lit])
                    dt_k = time.time() - t_k

                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Pairwise-Inc] Iter {iterations}: Test k={mid} -> {s_str} ({dt_k:.2f}s)", flush=True)

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, total_clauses, act_var_counter))
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw if status != "TIMEOUT" or best_bw != high else "TIMEOUT",
            runtime=0,
            iterations=iterations,
            clauses_count=total_clauses,
            vars_count=act_var_counter,
            labeling=best_labeling,
            status=status,
        )


# ==============================================================================
# 3. ORDER + ITERATIVE SAT (ORDER ENCODING VỚI BIẾN PHỤ G CỦA THẦY)
# ==============================================================================
class OrderIterativeSolver(BaseBMPSolver):

    def __init__(self, graph, amo_method="pairwise", timeout=600.0):
        super().__init__(graph, amo_method=amo_method, timeout=timeout)
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
        n = self.n

        # Cấp phát toàn bộ biến X và G trước để giữ ID cố định
        for u in range(1, n + 1):
            for i in range(1, n + 1):
                self._X(u, i)
            for i in range(2, n + 1):
                self._G(u, i)

        # 1. BƯỚC 1: Ràng buộc Song ánh cho biến X (Bijective Assignment)
        # ALO, AMO, Injective AMO qua amo_method
        x_clauses, self.var_counter = encode_bijective_assignment(
            n, self._X, top_id=self.var_counter, amo_method=self.amo_method
        )
        clauses = list(x_clauses)

        # 2. Tính chất thứ tự của G: G(u, i) -> G(u, i-1)
        for u in range(1, n + 1):
            for i in range(3, n + 1):
                clauses.append([-self._G(u, i), self._G(u, i - 1)])

        # 3. Cầu nối 2 chiều giữa X và G: X(u, i) <=> G(u, i) ^ ~G(u, i+1)
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
        start_time = getattr(self, "start_time", None) or time.time()

        n = self.n
        if n > 400:
            return SolverResult(
                bandwidth="MEM_EXCEED", runtime=0.0, iterations=0, status="MEM_EXCEED"
            )

        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, status="OPTIMAL")

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Order-Iterative ({self.amo_method})] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(
                bandwidth=high,
                runtime=0,
                iterations=0,
                labeling=self.graph.get_rcm_labeling(),
                status="OPTIMAL",
            )

        self.var_map.clear()
        self.var_counter = 0
        if verbose:
            print(f"  [Order-Iter] Đang khởi tạo Base Clauses (AMO={self.amo_method})...", flush=True)
        base_clauses = self._build_base_clauses()
        if verbose:
            print(f"  [Order-Iter] Base Clauses xong: {len(base_clauses):,} clauses, {self.var_counter:,} biến.", flush=True)
        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        last_clauses_count = len(base_clauses)
        status = "OPTIMAL"

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
                    if verbose:
                        print(f"  [Order-Iter] Iter {iterations}: Đang kiểm tra k={k} (LB={low}, UB={best_bw} | Clauses: {last_clauses_count:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve()
                    dt_k = time.time() - t_k
                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Order-Iter] Iter {iterations}: Test k={k} -> {s_str} ({dt_k:.2f}s)", flush=True)
                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, last_clauses_count, self.var_counter))
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
                    if verbose:
                        print(f"  [Order-Iter] Iter {iterations}: Đang kiểm tra k={mid} (Phạm vi: [{low}, {high}] | Clauses: {last_clauses_count:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve()
                    dt_k = time.time() - t_k

                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(
                            f"  [Order-Iter] Iter {iterations}: Test k={mid} ->"
                            f" {s_str} ({dt_k:.2f}s)"
                        )

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, last_clauses_count, self.var_counter))
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw if status != "TIMEOUT" or best_bw != high else "TIMEOUT",
            runtime=0,
            iterations=iterations,
            clauses_count=last_clauses_count,
            vars_count=self.var_counter,
            labeling=best_labeling,
            status=status,
        )


# ==============================================================================
# 4. ORDER + INCREMENTAL SAT (ORDER ENCODING GIA TĂNG)
# ==============================================================================
class OrderIncrementalSolver(OrderIterativeSolver):

    def _solve_single_graph(self, use_heuristics, strategy, verbose):
        start_time = getattr(self, "start_time", None) or time.time()

        n = self.n
        if n > 400:
            return SolverResult(
                bandwidth="MEM_EXCEED", runtime=0.0, iterations=0, status="MEM_EXCEED"
            )

        if n <= 1 or not self.edges:
            return SolverResult(0, 0, 0, status="OPTIMAL")

        if use_heuristics:
            low = self.graph.compute_lb()
            high = self.graph.compute_rcm_ub()
        else:
            low = 1
            high = n - 1

        if verbose:
            print(
                f"[Order-Incremental ({self.amo_method})] Strategy: {strategy}, Search range:"
                f" [{low}, {high}]"
            )

        if low >= high:
            return SolverResult(
                bandwidth=high,
                runtime=0,
                iterations=0,
                labeling=self.graph.get_rcm_labeling(),
                status="OPTIMAL",
            )

        self.var_map.clear()
        self.var_counter = 0
        if verbose:
            print(f"  [Order-Inc] Đang khởi tạo Base Clauses (AMO={self.amo_method})...", flush=True)
        base_clauses = self._build_base_clauses()
        if verbose:
            print(f"  [Order-Inc] Base Clauses xong: {len(base_clauses):,} clauses, {self.var_counter:,} biến.", flush=True)
        best_bw = high
        best_labeling = self.graph.get_rcm_labeling()
        iterations = 0
        total_clauses = 0
        status = "OPTIMAL"

        def _extract_x_labeling(solver_inst):
            model_set = set(solver_inst.get_model())
            lbl = {}
            for u in range(1, n + 1):
                for i in range(1, n + 1):
                    if self._X(u, i) in model_set:
                        lbl[u] = i
                        break
            return lbl

        with Cadical153() as solver:
            for cl in base_clauses:
                solver.add_clause(cl)
                total_clauses += 1

            if strategy == "linear":
                for k in range(high - 1, low - 1, -1):
                    iterations += 1
                    act_lit = self._get_var(f"ACT_{k}")

                    for cl in self._get_bandwidth_clauses(k):
                        solver.add_clause([-act_lit] + cl)
                        total_clauses += 1

                    if verbose:
                        print(f"  [Order-Inc] Iter {iterations}: Đang kiểm tra k={k} (LB={low}, UB={best_bw} | Clauses: {total_clauses:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve(assumptions=[act_lit])
                    dt_k = time.time() - t_k
                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Order-Inc] Iter {iterations}: Test k={k} -> {s_str} ({dt_k:.2f}s)", flush=True)

                    if is_sat:
                        best_bw = k
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, total_clauses, self.var_counter))
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

                    if verbose:
                        print(f"  [Order-Inc] Iter {iterations}: Đang kiểm tra k={mid} (Phạm vi: [{low}, {high}] | Clauses: {total_clauses:,})...", flush=True)
                    t_k = time.time()
                    is_sat = solver.solve(assumptions=[act_lit])
                    dt_k = time.time() - t_k

                    if verbose:
                        s_str = "SAT" if is_sat else "UNSAT"
                        print(f"  [Order-Inc] Iter {iterations}: Test k={mid} -> {s_str} ({dt_k:.2f}s)", flush=True)

                    if is_sat:
                        best_bw = mid
                        best_labeling = _extract_x_labeling(solver)
                        if getattr(self, "_queue", None):
                            self._queue.put(("PROGRESS", best_bw, iterations, best_labeling, total_clauses, self.var_counter))
                        high = mid - 1
                    else:
                        low = mid + 1

        return SolverResult(
            bandwidth=best_bw if status != "TIMEOUT" or best_bw != high else "TIMEOUT",
            runtime=0,
            iterations=iterations,
            clauses_count=total_clauses,
            vars_count=self.var_counter,
            labeling=best_labeling,
            status=status,
        )

"""Chương trình điều phối chính (Main CLI Entrypoint) cho Đề tài BMP.

Cho phép chạy độc lập hoặc đối chuẩn 4 bộ giải SAT:
- Order + Incremental SAT (Khuyến nghị)
- Order + Iterative SAT
- Pairwise + Incremental SAT
- Pairwise + Iterative SAT

Hỗ trợ kiểm tra toán học 100% chứng chỉ lời giải (Solution Certificate Verification).
"""

import argparse
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
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
from src.visualizer import generate_plots

SOLVER_MAP = {
    # 4 bộ giải SAT
    "order-inc": ("Order + Incremental SAT", OrderIncrementalSolver),
    "order-iter": ("Order + Iterative SAT", OrderIterativeSolver),
    "pairwise-inc": ("Pairwise + Incremental SAT", PairwiseIncrementalSolver),
    "pairwise-iter": ("Pairwise + Iterative SAT", PairwiseIterativeSolver),
    # 4 bộ giải đối chuẩn (Exact Baselines) theo đề bài của Thầy
    "cp-sat": ("Google OR-Tools CP-SAT", CPSATSolver),
    "cp": ("Google OR-Tools CP-SAT", CPSATSolver),
    "cplex-cp": ("IBM ILOG CPLEX CP Optimizer", CplexCPSolver),
    "gurobi": ("Gurobi Optimizer MIP", GurobiMIPSolver),
    "cplex-mip": ("IBM ILOG CPLEX MIP", CplexMIPSolver),
}


def solve_instance(
    instance_path,
    solver_key="order-inc",
    strategy="linear",
    use_heuristics=True,
    use_components=True,
    verify=True,
    verbose=True,
):
    if not os.path.exists(instance_path):
        # Thử tìm trong thư mục data/
        candidate = os.path.join("data", instance_path)
        if os.path.exists(candidate):
            instance_path = candidate
        elif os.path.exists(candidate + ".mtx"):
            instance_path = candidate + ".mtx"
        else:
            print(f"[Lỗi] Không tìm thấy file đồ thị: {instance_path}")
            return None

    graph = GraphData.from_mtx(instance_path)
    lb = graph.compute_lb() if use_heuristics else 1
    ub = graph.compute_rcm_ub() if use_heuristics else graph.n - 1
    comps = len(graph.get_connected_components())

    print("=" * 75)
    print(f"BÀI TOÁN BĂNG THÔNG ĐỒ THỊ (BMP) - ĐỒ THỊ: {graph.name}")
    print(f"Số đỉnh: n = {graph.n} | Số cạnh: m = {graph.m} | Thành phần liên thông: {comps}")
    if use_heuristics:
        print(f"Tối ưu 4.4.2 -> Khoảng tìm kiếm Heuristic [LB, UB]: [{lb}, {ub}]")
    else:
        print(f"Tìm kiếm toàn dải [1, {graph.n - 1}]")
    print(f"Chiến lược tìm kiếm: {strategy.upper()} SEARCH")
    print("=" * 75)

    solvers_to_run = (
        SOLVER_MAP.items()
        if solver_key == "all"
        else [(solver_key, SOLVER_MAP[solver_key])]
    )

    results = {}
    for key, (display_name, solver_cls) in solvers_to_run:
        print(f"\n>>> Đang thực thi: {display_name} ...")
        solver = solver_cls(graph)
        t0 = time.time()
        res = solver.solve(
            use_heuristics=use_heuristics,
            use_components=use_components,
            strategy=strategy,
            verbose=verbose,
        )
        dt = time.time() - t0

        print(f"  + Băng thông tối ưu tìm được: B(G) = {res.bandwidth}")
        print(f"  + Thời gian chạy: {dt:.3f} giây ({res.iterations} lần gọi SAT)")
        print(f"  + Số mệnh đề CNF sinh ra: {res.clauses_count:,}")

        # Kiểm chứng chứng chỉ lời giải
        if verify and res.labeling:
            valid, max_diff = graph.verify_labeling(res.labeling, res.bandwidth)
            if valid:
                print(f"  [Xác thực toán học OK] Song ánh hợp lệ 100%! Băng thông thực tế = {max_diff}")
            else:
                print(f"  [CẢNH BÁO XÁC THỰC] {max_diff}")

        results[key] = res

    return results


def main():
    parser = argparse.ArgumentParser(
        description="BMP Exact SAT Solver (Harwell-Boeing Benchmark)"
    )
    parser.add_argument(
        "-i", "--instance", default="data/pores_1.mtx", help="Đường dẫn file .mtx"
    )
    parser.add_argument(
        "-s",
        "--solver",
        choices=[
            "order-inc", "order-iter", "pairwise-inc", "pairwise-iter",
            "cp-sat", "cp", "cplex-cp", "gurobi", "cplex-mip", "all"
        ],
        default="order-inc",
        help="Lựa chọn bộ giải (order-inc, order-iter, pairwise-inc, pairwise-iter, cp-sat, cplex-cp, gurobi, cplex-mip, all)",
    )
    parser.add_argument(
        "--strategy",
        choices=["linear", "binary"],
        default="linear",
        help="Chiến lược tìm kiếm (linear giảm dần từ UB hoặc binary search)",
    )
    parser.add_argument(
        "--no-heuristics",
        action="store_true",
        help="Tắt tối ưu 4.4.2 (Heuristic Bounds RCM & lý thuyết)",
    )
    parser.add_argument(
        "--no-components",
        action="store_true",
        help="Tắt tối ưu 4.4.3 (Phân rã thành phần liên thông)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Tắt xác thực chứng chỉ lời giải toán học",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Vẽ lại biểu đồ trực quan hóa từ results/benchmark_summary.csv",
    )

    args = parser.parse_args()

    if args.plot:
        generate_plots()
        return

    solve_instance(
        instance_path=args.instance,
        solver_key=args.solver,
        strategy=args.strategy,
        use_heuristics=not args.no_heuristics,
        use_components=not args.no_components,
        verify=not args.no_verify,
        verbose=True,
    )


if __name__ == "__main__":
    main()

"""Kịch bản chạy thực nghiệm tự động (Automated Benchmark Runner)

Đánh giá 4 bộ giải SAT trên các ma trận benchmark nhỏ từ Bảng 6 (Table 6) của bộ
Harwell-Boeing:
- Pairwise + Iterative SAT
- Pairwise + Incremental SAT
- Order + Iterative SAT
- Order + Incremental SAT

Tích hợp:
- Tối ưu 4.4.2: Heuristic Bounds [LB, UB] bằng RCM và lý thuyết đồ thị
- Tối ưu 4.4.3: Phân rã thành phần liên thông (Connected Components)
"""

import csv
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

# Danh sách các ma trận nhỏ từ Bảng 6 kèm theo thông tin trong bài báo để đối chiếu
BENCHMARK_SUITE = [
    {
        "name": "pores_1",
        "file": "data/pores_1.mtx",
        "paper_n": 30,
        "paper_lb": 7,
        "paper_best": 7,
    },
    {
        "name": "bcspwr01",
        "file": "data/bcspwr01.mtx",
        "paper_n": 39,
        "paper_lb": 5,
        "paper_best": 5,
    },
]


def run_benchmark(strategy="linear", output_csv="results/benchmark_summary.csv"):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    print("=" * 80)
    print("BẮT ĐẦU CHẠY THỰC NGHIỆM ĐỐI CHUẨN 4 BỘ GIẢI SAT TRÊN HARWELL-BOEING")
    print(f"Chiến lược tìm kiếm: {strategy.upper()} SEARCH")
    print(
        "Tối ưu kích hoạt: 4.4.2 (Heuristic Bounds RCM) & 4.4.3 (Connected"
        " Components)"
    )
    print("=" * 80)

    results_table = []

    for item in BENCHMARK_SUITE:
        name = item["name"]
        file_path = item["file"]

        if not os.path.exists(file_path):
            print(f"[Skip] File {file_path} không tồn tại.")
            continue

        graph = GraphData.from_mtx(file_path, name=name)
        lb = graph.compute_lb()
        rcm_ub = graph.compute_rcm_ub()
        comps = len(graph.get_connected_components())

        print(f"\n>>> INSTANCE: {name} | n={graph.n}, m={graph.m} | Comps={comps}")
        print(
            f"    Cận tính toán: LB={lb}, RCM UB={rcm_ub} | Bài báo: LB={item['paper_lb']},"
            f" Best={item['paper_best']}"
        )

        solvers = [
            ("Order_Inc", OrderIncrementalSolver(graph)),
            ("Order_Iter", OrderIterativeSolver(graph)),
            ("Pairwise_Inc", PairwiseIncrementalSolver(graph)),
            ("Pairwise_Iter", PairwiseIterativeSolver(graph)),
        ]

        row = {
            "Instance": name,
            "n": graph.n,
            "m": graph.m,
            "LB_Heuristic": lb,
            "UB_RCM": rcm_ub,
            "Paper_Best": item["paper_best"],
        }

        for solver_name, solver in solvers:
            print(f"    -> Đang chạy {solver_name} ...", end=" ", flush=True)
            t0 = time.time()
            try:
                res = solver.solve(
                    use_heuristics=True,
                    use_components=True,
                    strategy=strategy,
                    verbose=False,
                )
                dt = time.time() - t0
                print(
                    f"Xong! Bw={res.bandwidth} ({dt:.2f}s, {res.iterations}"
                    " iters)"
                )

                row[f"{solver_name}_Bw"] = res.bandwidth
                row[f"{solver_name}_Time"] = round(dt, 3)
                row[f"{solver_name}_Iters"] = res.iterations
                row[f"{solver_name}_Clauses"] = res.clauses_count
            except Exception as e:
                print(f"Lỗi: {e}")
                row[f"{solver_name}_Bw"] = "ERROR"
                row[f"{solver_name}_Time"] = "N/A"
                row[f"{solver_name}_Iters"] = "N/A"
                row[f"{solver_name}_Clauses"] = "N/A"

        results_table.append(row)

        # Lưu ngay dòng này vào file CSV để đảm bảo không bị mất dữ liệu
        file_exists = os.path.exists(output_csv)
        fieldnames = list(row.keys())
        with open(output_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)
        print(f"    [Saved] Đã ghi kết quả {name} vào {output_csv}")

    # In bảng tổng kết Markdown chuẩn báo cáo
    print("\n" + "=" * 80)
    print("BẢNG TỔNG KẾT KẾT QUẢ THỰC NGHIỆM (SO SÁNH 4 BỘ GIẢI SAT)")
    print("=" * 80)
    print(
        f"{'Instance':<10} | {'n':<4} | {'Best':<4} | {'Order_Inc':<15} |"
        f" {'Order_Iter':<15} | {'Pair_Inc':<15} | {'Pair_Iter':<15}"
    )
    print(
        f"{'':<10} | {'':<4} | {'':<4} | {'Bw (s)':<15} | {'Bw (s)':<15} |"
        f" {'Bw (s)':<15} | {'Bw (s)':<15}"
    )
    print("-" * 88)
    for r in results_table:
        o_inc = f"{r.get('Order_Inc_Bw', '-') } ({r.get('Order_Inc_Time', '-') }s)"
        o_iter = (
            f"{r.get('Order_Iter_Bw', '-') } ({r.get('Order_Iter_Time', '-') }s)"
        )
        p_inc = (
            f"{r.get('Pairwise_Inc_Bw', '-') } ({r.get('Pairwise_Inc_Time', '-') }s)"
        )
        p_iter = f"{r.get('Pairwise_Iter_Bw', '-') } ({r.get('Pairwise_Iter_Time', '-') }s)"
        print(
            f"{r['Instance']:<10} | {r['n']:<4} | {r['Paper_Best']:<4} |"
            f" {o_inc:<15} | {o_iter:<15} | {p_inc:<15} | {p_iter:<15}"
        )
    print("=" * 80)


if __name__ == "__main__":
    run_benchmark(strategy="linear")

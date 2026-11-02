"""Kịch bản thực nghiệm Bóc tách Thành phần (Ablation Study Runner) cho BTL 2.

Thực hiện 3 nghiên cứu bóc tách thành phần chính chuẩn báo cáo khoa học (Elsevier):
1. Ablation Study 1 (AMO Encodings):
   So sánh 5 phương pháp mã hóa ALO/AMO:
   - Pairwise AMO
   - Sequential Counter (Sinz, 2005)
   - Binary / Bitwise
   - Commander Encoding (Klieber & Kwon, 2007)
   - 2-Product Encoding (Chen, 2010)
   Đo đạc: Số biến, Số mệnh đề, Tỷ lệ giảm mệnh đề (%), Thời gian giải (s), Trạng thái.
   Xuất file: results/ablation_amo.csv

2. Ablation Study 2 (Heuristic Bounds RCM):
   So sánh hiệu quả của việc thu hẹp khoảng tìm kiếm [LB, UB] bằng RCM và lý thuyết:
   - Có Heuristic: Khoảng [LB, UB] chặt, số lần lặp SAT ít (2-4 lần)
   - Không có Heuristic: Toàn dải [1, n-1], số lần lặp SAT nhiều (8-15 lần)
   Xuất file: results/ablation_heuristics.csv

3. Ablation Study 3 (Connected Components Decomposition):
   So sánh khi bật và tắt phân rã thành phần liên thông trên các đồ thị không liên thông.
   Xuất file: results/ablation_components.csv
"""

import argparse
import csv
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from src.graph import GraphData
from src.solvers import OrderIncrementalSolver, PairwiseIncrementalSolver
from src.downloader import download_hb_matrix


def run_amo_ablation(instances=None, timeout=300.0, output_csv="results/ablation_amo.csv"):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    if instances is None:
        instances = ["pores_1", "ibm32", "bcspwr01", "curtis54"]

    print("=" * 85)
    print("ABLATION STUDY 1: SO SÁNH 5 KỸ THUẬT MÃ HÓA ALO / AMO TRÊN CÙNG INSTANCE")
    print("=" * 85)

    methods = ["pairwise", "sequential", "binary", "commander", "product"]
    rows = []

    for name in instances:
        file_path = os.path.join("data", f"{name}.mtx")
        if not os.path.exists(file_path):
            download_hb_matrix(name, target_dir="data")
        if not os.path.exists(file_path):
            continue

        g = GraphData.from_mtx(file_path, name=name)
        print(f"\n>>> Đồ thị: {name} (n={g.n}, m={g.m})")

        # Lấy baseline pairwise để tính tỷ lệ giảm mệnh đề
        baseline_clauses = None

        for m in methods:
            print(f"  -> Đang chạy AMO={m:<12} ...", end=" ", flush=True)
            solver = OrderIncrementalSolver(g, amo_method=m, timeout=timeout)
            t0 = time.time()
            try:
                res = solver.solve(use_heuristics=True, strategy="linear", verbose=False)
                dt = time.time() - t0
                if m == "pairwise":
                    baseline_clauses = res.clauses_count
                    reduction_pct = 0.0
                else:
                    reduction_pct = (
                        round((1.0 - res.clauses_count / baseline_clauses) * 100, 1)
                        if baseline_clauses
                        else 0.0
                    )

                print(
                    f"Bw={res.bandwidth}, Clauses={res.clauses_count:,} ({reduction_pct:+.1f}%),"
                    f" Vars={res.vars_count:,}, Time={dt:.2f}s [{res.status}]"
                )

                row = {
                    "Instance": name,
                    "n": g.n,
                    "m": g.m,
                    "AMO_Method": m,
                    "Bandwidth": res.bandwidth,
                    "Clauses": res.clauses_count,
                    "Clause_Reduction_Pct": reduction_pct,
                    "Vars": res.vars_count,
                    "Runtime_s": round(dt, 3),
                    "Iterations": res.iterations,
                    "Status": res.status,
                }
                rows.append(row)
            except Exception as e:
                print(f"Lỗi: {e}")

    # Ghi ra file CSV
    if rows:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[Saved] Đã ghi toàn bộ kết quả Ablation AMO vào: {output_csv}")


def run_heuristics_ablation(instances=None, timeout=300.0, output_csv="results/ablation_heuristics.csv"):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    if instances is None:
        instances = ["pores_1", "ibm32", "bcspwr01"]

    print("\n" + "=" * 85)
    print("ABLATION STUDY 2: ĐÁNH GIÁ TỐI ƯU 4.4.2 (HEURISTIC RCM BOUNDS [LB, UB])")
    print("=" * 85)

    rows = []
    for name in instances:
        file_path = os.path.join("data", f"{name}.mtx")
        if not os.path.exists(file_path):
            download_hb_matrix(name, target_dir="data")
        if not os.path.exists(file_path):
            continue

        g = GraphData.from_mtx(file_path, name=name)
        lb = g.compute_lb()
        ub = g.compute_rcm_ub()
        print(f"\n>>> Đồ thị: {name} (n={g.n}, m={g.m}) | Heuristic RCM: [{lb}, {ub}] vs Full: [1, {g.n-1}]")

        # 1. Có Heuristic
        s_with = OrderIncrementalSolver(g, amo_method="sequential", timeout=timeout)
        t0 = time.time()
        res_with = s_with.solve(use_heuristics=True, strategy="binary", verbose=False)
        dt_with = time.time() - t0

        # 2. Không có Heuristic
        s_without = OrderIncrementalSolver(g, amo_method="sequential", timeout=timeout)
        t0 = time.time()
        res_without = s_without.solve(use_heuristics=False, strategy="binary", verbose=False)
        dt_without = time.time() - t0

        speedup = round(dt_without / dt_with, 2) if dt_with > 0 else 1.0
        iter_saved = res_without.iterations - res_with.iterations

        print(f"  + Với Heuristic RCM   : Bw={res_with.bandwidth}, Iters={res_with.iterations}, Time={dt_with:.2f}s")
        print(f"  + Không dùng Heuristic: Bw={res_without.bandwidth}, Iters={res_without.iterations}, Time={dt_without:.2f}s")
        print(f"  ==> Tốc độ tăng {speedup}x, Tiết kiệm {iter_saved} lần gọi SAT!")

        rows.append({
            "Instance": name,
            "n": g.n,
            "LB_Heuristic": lb,
            "UB_RCM": ub,
            "With_Heuristic_Time": round(dt_with, 3),
            "With_Heuristic_Iters": res_with.iterations,
            "Without_Heuristic_Time": round(dt_without, 3),
            "Without_Heuristic_Iters": res_without.iterations,
            "Speedup_Ratio": speedup,
            "Iterations_Saved": iter_saved,
        })

    if rows:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[Saved] Đã ghi kết quả Ablation Heuristic vào: {output_csv}")


def run_components_ablation(instances=None, timeout=300.0, output_csv="results/ablation_components.csv"):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    if instances is None:
        instances = ["bcspwr01", "bcspwr02"]

    print("\n" + "=" * 85)
    print("ABLATION STUDY 3: ĐÁNH GIÁ TỐI ƯU 4.4.3 (CONNECTED COMPONENTS DECOMPOSITION)")
    print("=" * 85)

    rows = []
    for name in instances:
        file_path = os.path.join("data", f"{name}.mtx")
        if not os.path.exists(file_path):
            download_hb_matrix(name, target_dir="data")
        if not os.path.exists(file_path):
            continue

        g = GraphData.from_mtx(file_path, name=name)
        comps = len(g.get_connected_components())
        print(f"\n>>> Đồ thị: {name} (n={g.n}, m={g.m}, Comps={comps})")

        # Có phân rã
        s_with = OrderIncrementalSolver(g, amo_method="sequential", timeout=timeout)
        t0 = time.time()
        res_with = s_with.solve(use_heuristics=True, use_components=True, strategy="binary", verbose=False)
        dt_with = time.time() - t0

        # Không phân rã
        s_without = OrderIncrementalSolver(g, amo_method="sequential", timeout=timeout)
        t0 = time.time()
        res_without = s_without.solve(use_heuristics=True, use_components=False, strategy="binary", verbose=False)
        dt_without = time.time() - t0

        speedup = round(dt_without / dt_with, 2) if dt_with > 0 else 1.0
        print(f"  + Có phân rã liên thông : Bw={res_with.bandwidth}, Time={dt_with:.2f}s, Clauses={res_with.clauses_count:,}")
        print(f"  + Không phân rã         : Bw={res_without.bandwidth}, Time={dt_without:.2f}s, Clauses={res_without.clauses_count:,}")
        print(f"  ==> Tốc độ tăng {speedup}x!")

        rows.append({
            "Instance": name,
            "n": g.n,
            "m": g.m,
            "Components": comps,
            "With_Components_Time": round(dt_with, 3),
            "With_Components_Clauses": res_with.clauses_count,
            "Without_Components_Time": round(dt_without, 3),
            "Without_Components_Clauses": res_without.clauses_count,
            "Speedup_Ratio": speedup,
        })

    if rows:
        with open(output_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[Saved] Đã ghi kết quả Ablation Components vào: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy thực nghiệm bóc tách thành phần (Ablation Study)")
    parser.add_argument("--study", choices=["amo", "heuristics", "components", "all"], default="all")
    parser.add_argument("--instances", nargs="*", default=None)
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    if args.study in ("amo", "all"):
        run_amo_ablation(instances=args.instances, timeout=args.timeout)
    if args.study in ("heuristics", "all"):
        run_heuristics_ablation(instances=args.instances, timeout=args.timeout)
    if args.study in ("components", "all"):
        run_components_ablation(instances=args.instances, timeout=args.timeout)

"""Module trực quan hóa kết quả thực nghiệm bằng thư viện cnsplots và

matplotlib.

Xuất ra các đồ thị chuẩn xuất bản:
1. runtime_comparison.png: So sánh thời gian chạy giữa các bộ giải SAT.
2. clauses_comparison.png: So sánh số lượng mệnh đề giữa Pairwise và Order Encoding.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
import cnsplots
import matplotlib.pyplot as plt
import pandas as pd


def generate_plots(
    csv_path="results/benchmark_summary.csv", output_dir="results"
):
    if not os.path.exists(csv_path):
        print(f"[Error] Results file not found: {csv_path}")
        return

    os.makedirs(output_dir, exist_ok=True)
    df = pd.read_csv(csv_path)

    # 1. Chuyển đổi dữ liệu sang định dạng dài (Long Format) cho Runtime
    runtime_records = []
    for _, row in df.iterrows():
        inst = row["Instance"]
        for solver in [
            "Order_Inc",
            "Order_Iter",
            "Pairwise_Inc",
            "Pairwise_Iter",
        ]:
            col_t = f"{solver}_Time"
            col_c = f"{solver}_Clauses"
            if col_t in row and pd.notna(row[col_t]):
                try:
                    t_val = float(row[col_t])
                    c_val = float(row[col_c])
                    runtime_records.append({
                        "Instance": inst,
                        "Solver": solver,
                        "Runtime (s)": t_val,
                        "Clauses": c_val,
                        "Encoding": (
                            "Order" if "Order" in solver else "Pairwise"
                        ),
                        "Mode": (
                            "Incremental"
                            if "Inc" in solver
                            else "Iterative (Nhiều lần)"
                        ),
                    })
                except ValueError:
                    pass

    df_plot = pd.DataFrame(runtime_records)
    if df_plot.empty:
        print("[Warning] No valid data found for plotting.")
        return

    # =========================================================================
    # BIỂU ĐỒ 1: SO SÁNH THỜI GIAN GIẢI (RUNTIME) BẰNG CNSPLOTS
    # =========================================================================
    plt.figure(figsize=(10, 6))
    ax = cnsplots.barplot(
        data=df_plot,
        x="Instance",
        y="Runtime (s)",
        hue="Solver",
        palette="Set2",
    )
    plt.title(
        "Comparison of BMP Solving Runtime (Harwell-Boeing)",
        fontsize=14,
        fontweight="bold",
    )
    plt.ylabel("Runtime (seconds) - Lower is better", fontsize=12)
    plt.xlabel("Benchmark Instance", fontsize=12)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    runtime_fig_path = os.path.join(output_dir, "runtime_comparison.png")
    plt.savefig(runtime_fig_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[Generated] Saved Runtime plot: {runtime_fig_path}")

    # =========================================================================
    # BIỂU ĐỒ 2: SO SÁNH SỐ LƯỢNG MỆNH ĐỀ (CLAUSES COUNT)
    # =========================================================================
    plt.figure(figsize=(10, 6))
    ax2 = cnsplots.barplot(
        data=df_plot,
        x="Instance",
        y="Clauses",
        hue="Encoding",
        palette="pastel",
    )
    plt.title(
        "Comparison of CNF Clauses Count (Pairwise vs Order Encoding)",
        fontsize=14,
        fontweight="bold",
    )
    plt.ylabel("Number of CNF Clauses", fontsize=12)
    plt.xlabel("Benchmark Instance", fontsize=12)
    plt.grid(axis="y", linestyle="--", alpha=0.5)

    clauses_fig_path = os.path.join(output_dir, "clauses_comparison.png")
    plt.savefig(clauses_fig_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[Generated] Saved Clauses plot: {clauses_fig_path}")


if __name__ == "__main__":
    generate_plots()

"""Kịch bản chạy thực nghiệm tự động (Automated Benchmark Runner)

Đánh giá 4 bộ giải SAT trên toàn bộ ma trận thuộc Bảng 6 và Bảng 7 (Harwell-Boeing Collection):
- Pairwise + Iterative SAT
- Pairwise + Incremental SAT
- Order + Iterative SAT
- Order + Incremental SAT

Hỗ trợ:
- Đầy đủ 72 ma trận từ Bảng 6 và Bảng 7 (Part I) kèm link tải NIST chính thức.
- Tự động tải dataset nếu chưa có trong thư mục data/.
- Cấu hình ALO/AMO: pairwise, sequential, binary, commander, product.
- Giới hạn kích thước ma trận: n > 400 tự động đánh dấu MEM_EXCEED (Memory Exceeded), không chạy solver.
- Giới hạn thời gian (Timeout): Mỗi bài toán tối đa 10 phút (600 giây).
- Tối ưu 4.4.2 (Heuristic Bounds RCM) & 4.4.3 (Connected Components).
"""

import argparse
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
from src.downloader import download_hb_matrix, get_matrix_url

# Toàn bộ danh mục 72 ma trận benchmark theo Table 6 và Table 7
BENCHMARK_SUITE = [
    # ==========================================================================
    # BẢNG 6 (TABLE 6): 31 ma trận nhỏ (Torres-Jimenez et al., 2015)
    # ==========================================================================
    {"name": "arc130", "table": 6, "file": "data/arc130.mtx", "paper_n": 130, "paper_lb": 63, "paper_best": 63},
    {"name": "ash85", "table": 6, "file": "data/ash85.mtx", "paper_n": 85, "paper_lb": 9, "paper_best": 9},
    {"name": "bcspwr01", "table": 6, "file": "data/bcspwr01.mtx", "paper_n": 39, "paper_lb": 5, "paper_best": 5},
    {"name": "bcspwr02", "table": 6, "file": "data/bcspwr02.mtx", "paper_n": 49, "paper_lb": 7, "paper_best": 7},
    {"name": "bcspwr03", "table": 6, "file": "data/bcspwr03.mtx", "paper_n": 118, "paper_lb": 9, "paper_best": 10},
    {"name": "bcsstk01", "table": 6, "file": "data/bcsstk01.mtx", "paper_n": 48, "paper_lb": 16, "paper_best": 16},
    {"name": "bcsstk04", "table": 6, "file": "data/bcsstk04.mtx", "paper_n": 132, "paper_lb": 36, "paper_best": 37},
    {"name": "bcsstk05", "table": 6, "file": "data/bcsstk05.mtx", "paper_n": 153, "paper_lb": 19, "paper_best": 20},
    {"name": "bcsstk22", "table": 6, "file": "data/bcsstk22.mtx", "paper_n": 138, "paper_lb": 9, "paper_best": 10},
    {"name": "can_144", "table": 6, "file": "data/can_144.mtx", "paper_n": 144, "paper_lb": 13, "paper_best": 13},
    {"name": "can_161", "table": 6, "file": "data/can_161.mtx", "paper_n": 161, "paper_lb": 18, "paper_best": 18},
    {"name": "curtis54", "table": 6, "file": "data/curtis54.mtx", "paper_n": 54, "paper_lb": 10, "paper_best": 10},
    {"name": "fs_183_1", "table": 6, "file": "data/fs_183_1.mtx", "paper_n": 183, "paper_lb": 52, "paper_best": 60},
    {"name": "gent113", "table": 6, "file": "data/gent113.mtx", "paper_n": 113, "paper_lb": 25, "paper_best": 27},
    {"name": "gre_115", "table": 6, "file": "data/gre_115.mtx", "paper_n": 115, "paper_lb": 20, "paper_best": 23},
    {"name": "gre_185", "table": 6, "file": "data/gre_185.mtx", "paper_n": 185, "paper_lb": 17, "paper_best": 21},
    {"name": "ibm32", "table": 6, "file": "data/ibm32.mtx", "paper_n": 32, "paper_lb": 11, "paper_best": 11},
    {"name": "impcol_b", "table": 6, "file": "data/impcol_b.mtx", "paper_n": 59, "paper_lb": 19, "paper_best": 20},
    {"name": "impcol_c", "table": 6, "file": "data/impcol_c.mtx", "paper_n": 137, "paper_lb": 23, "paper_best": 30},
    {"name": "lns_131", "table": 6, "file": "data/lns_131.mtx", "paper_n": 131, "paper_lb": 18, "paper_best": 20},
    {"name": "lund_a", "table": 6, "file": "data/lund_a.mtx", "paper_n": 147, "paper_lb": 19, "paper_best": 23},
    {"name": "lund_b", "table": 6, "file": "data/lund_b.mtx", "paper_n": 147, "paper_lb": 19, "paper_best": 23},
    {"name": "mcca", "table": 6, "file": "data/mcca.mtx", "paper_n": 180, "paper_lb": 32, "paper_best": 37},
    {"name": "nos4", "table": 6, "file": "data/nos4.mtx", "paper_n": 100, "paper_lb": 10, "paper_best": 10},
    {"name": "pores_1", "table": 6, "file": "data/pores_1.mtx", "paper_n": 30, "paper_lb": 7, "paper_best": 7},
    {"name": "steam3", "table": 6, "file": "data/steam3.mtx", "paper_n": 80, "paper_lb": 7, "paper_best": 7},
    {"name": "west0132", "table": 6, "file": "data/west0132.mtx", "paper_n": 132, "paper_lb": 23, "paper_best": 32},
    {"name": "west0156", "table": 6, "file": "data/west0156.mtx", "paper_n": 156, "paper_lb": 33, "paper_best": 36},
    {"name": "west0167", "table": 6, "file": "data/west0167.mtx", "paper_n": 167, "paper_lb": 31, "paper_best": 34},
    {"name": "will199", "table": 6, "file": "data/will199.mtx", "paper_n": 199, "paper_lb": 55, "paper_best": 64},
    {"name": "will57", "table": 6, "file": "data/will57.mtx", "paper_n": 57, "paper_lb": 6, "paper_best": 6},

    # ==========================================================================
    # BẢNG 7 (TABLE 7 - PART I): 41 ma trận kích thước lớn
    # ==========================================================================
    {"name": "494_bus", "table": 7, "file": "data/494_bus.mtx", "paper_n": 494, "paper_lb": 25, "paper_best": 28},
    {"name": "662_bus", "table": 7, "file": "data/662_bus.mtx", "paper_n": 662, "paper_lb": 36, "paper_best": 39},
    {"name": "685_bus", "table": 7, "file": "data/685_bus.mtx", "paper_n": 685, "paper_lb": 30, "paper_best": 32},
    {"name": "ash292", "table": 7, "file": "data/ash292.mtx", "paper_n": 292, "paper_lb": 16, "paper_best": 19},
    {"name": "bcspwr04", "table": 7, "file": "data/bcspwr04.mtx", "paper_n": 274, "paper_lb": 23, "paper_best": 24},
    {"name": "bcspwr05", "table": 7, "file": "data/bcspwr05.mtx", "paper_n": 443, "paper_lb": 25, "paper_best": 27},
    {"name": "bcsstk06", "table": 7, "file": "data/bcsstk06.mtx", "paper_n": 420, "paper_lb": 38, "paper_best": 45},
    {"name": "bcsstk19", "table": 7, "file": "data/bcsstk19.mtx", "paper_n": 817, "paper_lb": 13, "paper_best": 14},
    {"name": "bcsstk20", "table": 7, "file": "data/bcsstk20.mtx", "paper_n": 485, "paper_lb": 8, "paper_best": 13},
    {"name": "bcsstm07", "table": 7, "file": "data/bcsstm07.mtx", "paper_n": 420, "paper_lb": 37, "paper_best": 45},
    {"name": "bp_0", "table": 7, "file": "data/bp_0.mtx", "paper_n": 822, "paper_lb": 174, "paper_best": 234},
    {"name": "bp_1000", "table": 7, "file": "data/bp_1000.mtx", "paper_n": 822, "paper_lb": 197, "paper_best": 283},
    {"name": "bp_1200", "table": 7, "file": "data/bp_1200.mtx", "paper_n": 822, "paper_lb": 197, "paper_best": 287},
    {"name": "bp_1400", "table": 7, "file": "data/bp_1400.mtx", "paper_n": 822, "paper_lb": 199, "paper_best": 291},
    {"name": "bp_1600", "table": 7, "file": "data/bp_1600.mtx", "paper_n": 822, "paper_lb": 199, "paper_best": 292},
    {"name": "bp_200", "table": 7, "file": "data/bp_200.mtx", "paper_n": 822, "paper_lb": 186, "paper_best": 257},
    {"name": "bp_400", "table": 7, "file": "data/bp_400.mtx", "paper_n": 822, "paper_lb": 188, "paper_best": 267},
    {"name": "bp_600", "table": 7, "file": "data/bp_600.mtx", "paper_n": 822, "paper_lb": 190, "paper_best": 272},
    {"name": "bp_800", "table": 7, "file": "data/bp_800.mtx", "paper_n": 822, "paper_lb": 197, "paper_best": 278},
    {"name": "can_292", "table": 7, "file": "data/can_292.mtx", "paper_n": 292, "paper_lb": 34, "paper_best": 38},
    {"name": "can_445", "table": 7, "file": "data/can_445.mtx", "paper_n": 445, "paper_lb": 46, "paper_best": 52},
    {"name": "can_715", "table": 7, "file": "data/can_715.mtx", "paper_n": 715, "paper_lb": 54, "paper_best": 71},
    {"name": "can_838", "table": 7, "file": "data/can_838.mtx", "paper_n": 838, "paper_lb": 75, "paper_best": 86},
    {"name": "dwt_209", "table": 7, "file": "data/dwt_209.mtx", "paper_n": 209, "paper_lb": 21, "paper_best": 23},
    {"name": "dwt_221", "table": 7, "file": "data/dwt_221.mtx", "paper_n": 221, "paper_lb": 12, "paper_best": 13},
    {"name": "dwt_234", "table": 7, "file": "data/dwt_234.mtx", "paper_n": 234, "paper_lb": 11, "paper_best": 11},
    {"name": "dwt_245", "table": 7, "file": "data/dwt_245.mtx", "paper_n": 245, "paper_lb": 21, "paper_best": 21},
    {"name": "dwt_310", "table": 7, "file": "data/dwt_310.mtx", "paper_n": 310, "paper_lb": 11, "paper_best": 12},
    {"name": "dwt_361", "table": 7, "file": "data/dwt_361.mtx", "paper_n": 361, "paper_lb": 14, "paper_best": 14},
    {"name": "dwt_419", "table": 7, "file": "data/dwt_419.mtx", "paper_n": 419, "paper_lb": 23, "paper_best": 25},
    {"name": "dwt_503", "table": 7, "file": "data/dwt_503.mtx", "paper_n": 503, "paper_lb": 29, "paper_best": 41},
    {"name": "dwt_592", "table": 7, "file": "data/dwt_592.mtx", "paper_n": 592, "paper_lb": 22, "paper_best": 29},
    {"name": "dwt_878", "table": 7, "file": "data/dwt_878.mtx", "paper_n": 878, "paper_lb": 23, "paper_best": 25},
    {"name": "dwt_918", "table": 7, "file": "data/dwt_918.mtx", "paper_n": 918, "paper_lb": 27, "paper_best": 32},
    {"name": "dwt_992", "table": 7, "file": "data/dwt_992.mtx", "paper_n": 992, "paper_lb": 35, "paper_best": 35},
    {"name": "fs_541_1", "table": 7, "file": "data/fs_541_1.mtx", "paper_n": 541, "paper_lb": 270, "paper_best": 270},
    {"name": "fs_680_1", "table": 7, "file": "data/fs_680_1.mtx", "paper_n": 680, "paper_lb": 17, "paper_best": 17},
    {"name": "fs_760_1", "table": 7, "file": "data/fs_760_1.mtx", "paper_n": 760, "paper_lb": 36, "paper_best": 37},
    {"name": "gr_30_30", "table": 7, "file": "data/gr_30_30.mtx", "paper_n": 900, "paper_lb": 31, "paper_best": 33},
    {"name": "gre_216a", "table": 7, "file": "data/gre_216a.mtx", "paper_n": 216, "paper_lb": 17, "paper_best": 21},
    {"name": "gre_343", "table": 7, "file": "data/gre_343.mtx", "paper_n": 343, "paper_lb": 23, "paper_best": 28},
]


def run_benchmark(
    table_filter=None,
    strategy="linear",
    amo="pairwise",
    timeout=600.0,
    output_csv="results/benchmark_summary.csv",
):
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    print("=" * 80)
    print("BẮT ĐẦU CHẠY THỰC NGHIỆM ĐỐI CHUẨN 4 BỘ GIẢI SAT TRÊN HARWELL-BOEING")
    print(f"Chiến lược tìm kiếm: {strategy.upper()} SEARCH | Phương pháp AMO: {amo.upper()}")
    print(f"Giới hạn thời gian (Timeout): {timeout}s (10 phút) | Giới hạn bộ nhớ: n > 400 -> MEM_EXCEED")
    print("Tối ưu kích hoạt: 4.4.2 (Heuristic Bounds RCM) & 4.4.3 (Connected Components)")
    print("=" * 80)

    # Lọc danh sách theo bảng
    items = BENCHMARK_SUITE
    if table_filter in (6, "6"):
        items = [x for x in items if x["table"] == 6]
    elif table_filter in (7, "7"):
        items = [x for x in items if x["table"] == 7]

    results_table = []

    for item in items:
        name = item["name"]
        file_path = item["file"]
        p_n = item["paper_n"]
        p_lb = item["paper_lb"]
        p_best = item["paper_best"]
        table_num = item["table"]

        # Tự động tải nếu file chưa có
        if not os.path.exists(file_path):
            print(f"\n[Auto-Download] Đang tải {name} từ NIST Matrix Market...")
            dl_res = download_hb_matrix(name, target_dir="data")
            if not dl_res or not os.path.exists(file_path):
                print(f"[Skip] Không thể tải {name}, bỏ qua.")
                continue

        graph = GraphData.from_mtx(file_path, name=name)
        lb = graph.compute_lb()
        rcm_ub = graph.compute_rcm_ub()
        comps = len(graph.get_connected_components())

        print(f"\n>>> [Table {table_num}] INSTANCE: {name} | n={graph.n}, m={graph.m} | Comps={comps}")
        print(f"    Link NIST: {get_matrix_url(name)}")
        print(f"    Cận tính toán: LB={lb}, RCM UB={rcm_ub} | Bài báo: LB={p_lb}, Best={p_best}")

        row = {
            "Table": table_num,
            "Instance": name,
            "n": graph.n,
            "m": graph.m,
            "Comps": comps,
            "LB_Heuristic": lb,
            "UB_RCM": rcm_ub,
            "Paper_LB": p_lb,
            "Paper_Best": p_best,
            "AMO_Method": amo,
            "Strategy": strategy,
            "NIST_URL": get_matrix_url(name),
        }

        # Kiểm tra điều kiện n > 400: Không giải, trực tiếp ghi nhận MEM_EXCEED
        if graph.n > 400:
            print(f"    [MEM_EXCEED] n = {graph.n} > 400: Đã ghi nhận Memory Exceeded theo quy định.")
            for s_name in ["Order_Inc", "Order_Iter", "Pairwise_Inc", "Pairwise_Iter"]:
                row[f"{s_name}_Bw"] = "MEM_EXCEED"
                row[f"{s_name}_Time"] = 0.0
                row[f"{s_name}_Iters"] = 0
                row[f"{s_name}_Clauses"] = 0
                row[f"{s_name}_Vars"] = 0
                row[f"{s_name}_Status"] = "MEM_EXCEED"
            results_table.append(row)
            _save_row_to_csv(output_csv, row)
            continue

        solvers = [
            ("Order_Inc", OrderIncrementalSolver(graph, amo_method=amo, timeout=timeout)),
            ("Order_Iter", OrderIterativeSolver(graph, amo_method=amo, timeout=timeout)),
            ("Pairwise_Inc", PairwiseIncrementalSolver(graph, amo_method=amo, timeout=timeout)),
            ("Pairwise_Iter", PairwiseIterativeSolver(graph, amo_method=amo, timeout=timeout)),
        ]

        for solver_name, solver in solvers:
            print(f"    -> Đang chạy {solver_name} (AMO={amo}) ...", end=" ", flush=True)
            t0 = time.time()
            try:
                res = solver.solve(
                    use_heuristics=True,
                    use_components=True,
                    strategy=strategy,
                    verbose=False,
                )
                dt = time.time() - t0
                status_str = f" [{res.status}]" if res.status != "OPTIMAL" else ""
                print(
                    f"Xong! Bw={res.bandwidth}{status_str} ({dt:.2f}s, {res.iterations} iters)"
                )

                row[f"{solver_name}_Bw"] = res.bandwidth
                row[f"{solver_name}_Time"] = round(dt, 3)
                row[f"{solver_name}_Iters"] = res.iterations
                row[f"{solver_name}_Clauses"] = res.clauses_count
                row[f"{solver_name}_Vars"] = res.vars_count
                row[f"{solver_name}_Status"] = res.status
            except Exception as e:
                print(f"Lỗi: {e}")
                row[f"{solver_name}_Bw"] = "ERROR"
                row[f"{solver_name}_Time"] = "N/A"
                row[f"{solver_name}_Iters"] = "N/A"
                row[f"{solver_name}_Clauses"] = "N/A"
                row[f"{solver_name}_Vars"] = "N/A"
                row[f"{solver_name}_Status"] = "ERROR"

        results_table.append(row)
        _save_row_to_csv(output_csv, row)
        print(f"    [Saved] Đã ghi kết quả {name} vào {output_csv}")

    # In bảng tổng kết
    print("\n" + "=" * 92)
    print("BẢNG TỔNG KẾT KẾT QUẢ THỰC NGHIỆM (SO SÁNH 4 BỘ GIẢI SAT)")
    print("=" * 92)
    print(
        f"{'Instance':<10} | {'n':<4} | {'Best':<4} | {'Order_Inc':<16} |"
        f" {'Order_Iter':<16} | {'Pair_Inc':<16} | {'Pair_Iter':<16}"
    )
    print("-" * 92)
    for r in results_table:
        o_inc = f"{r.get('Order_Inc_Bw', '-') } ({r.get('Order_Inc_Time', '-') }s)"
        o_iter = f"{r.get('Order_Iter_Bw', '-') } ({r.get('Order_Iter_Time', '-') }s)"
        p_inc = f"{r.get('Pairwise_Inc_Bw', '-') } ({r.get('Pairwise_Inc_Time', '-') }s)"
        p_iter = f"{r.get('Pairwise_Iter_Bw', '-') } ({r.get('Pairwise_Iter_Time', '-') }s)"
        print(
            f"{r['Instance']:<10} | {r['n']:<4} | {r['Paper_Best']:<4} |"
            f" {o_inc:<16} | {o_iter:<16} | {p_inc:<16} | {p_iter:<16}"
        )
    print("=" * 92)


def _save_row_to_csv(output_csv, row):
    file_exists = os.path.exists(output_csv)
    fieldnames = list(row.keys())
    with open(output_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chạy Benchmark Harwell-Boeing Bảng 6 & 7")
    parser.add_argument("--table", choices=["6", "7", "all"], default="all", help="Chọn Bảng 6, Bảng 7 hoặc tất cả")
    parser.add_argument("--amo", choices=["pairwise", "sequential", "binary", "commander", "product"], default="pairwise", help="Phương pháp mã hóa AMO/ALO")
    parser.add_argument("--strategy", choices=["linear", "binary"], default="linear", help="Chiến lược tìm kiếm")
    parser.add_argument("--timeout", type=float, default=600.0, help="Thời gian tối đa cho mỗi bài toán (giây)")
    parser.add_argument("--output", default="results/benchmark_summary.csv", help="File CSV đầu ra")
    args = parser.parse_args()

    run_benchmark(
        table_filter=args.table if args.table != "all" else None,
        strategy=args.strategy,
        amo=args.amo,
        timeout=args.timeout,
        output_csv=args.output,
    )

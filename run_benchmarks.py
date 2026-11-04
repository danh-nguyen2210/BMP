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
- n >= 400: LIMIT. Lưu SQLite sau từng lượt solver và tự động resume.
- Giới hạn thời gian (Timeout): Mỗi bài toán tối đa 10 phút (600 giây).
- Tối ưu 4.4.2 (Heuristic Bounds RCM) & 4.4.3 (Connected Components).
"""

import argparse
from contextlib import contextmanager
from importlib import metadata as package_metadata
import math
import platform
from pathlib import Path
import signal
import sys
import time

from src.benchmark_store import BenchmarkStore, digest, file_digest
from src.downloader import download_hb_matrix, get_matrix_url

ROOT = Path(__file__).resolve().parent
SOLVER_KEYS = ("order-inc", "order-iter", "pairwise-inc", "pairwise-iter")
AMO_METHODS = ("pairwise", "sequential", "binary", "commander", "product")

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


def _load_runtime():
    # Help/checkpoint tooling does not require optional SAT packages.
    from src.graph import GraphData
    from src.solvers import (
        OrderIncrementalSolver, OrderIterativeSolver,
        PairwiseIncrementalSolver, PairwiseIterativeSolver,
    )
    return GraphData, dict(zip(SOLVER_KEYS, (
        OrderIncrementalSolver, OrderIterativeSolver,
        PairwiseIncrementalSolver, PairwiseIterativeSolver,
    )))


def _environment():
    versions = {"python": platform.python_version(), "system": platform.system(),
                "architecture": platform.machine()}
    for name in ("python-sat", "numpy", "scipy"):
        try:
            versions[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            versions[name] = "not-installed"
    return versions


def _code_hash():
    return digest({name: file_digest(ROOT / name) for name in (
        "run_benchmarks.py", "src/benchmark_store.py", "src/solvers.py",
        "src/cardinality.py", "src/graph.py", "src/downloader.py",
    )})


@contextmanager
def _graceful_stop():
    requested = [False]

    def handler(signum, frame):
        requested[0] = True
        print("\n[Stop] Sẽ lưu lượt hiện tại rồi dừng. Hãy chờ thông báo đã dừng.", flush=True)

    previous = signal.signal(signal.SIGINT, handler)
    try:
        yield requested
    finally:
        signal.signal(signal.SIGINT, previous)


def _export(store, output):
    try:
        store.export_csv(output)
    except OSError as exc:
        print(f"[CSV] Chưa xuất được CSV (có thể đang mở trong Excel): {exc}. "
              "Kết quả đã lưu trong SQLite; chạy lại để xuất lại.", flush=True)


def run_benchmark(
    table_filter=None, strategy="linear", amo="pairwise", timeout=600.0,
    output_csv="results/benchmark_runs.csv",
    checkpoint="results/benchmark_resume.sqlite3", instances=None,
    solver_keys=None, session_hours=None, max_jobs=None, retry_errors=False,
    stop_file=None,
):
    """Resume between solver jobs, not inside an unfinished SAT search."""
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout phải là số dương hữu hạn.")
    if session_hours is not None and (not math.isfinite(session_hours) or session_hours <= 0):
        raise ValueError("session-hours phải là số dương hữu hạn.")
    if max_jobs is not None and max_jobs <= 0:
        raise ValueError("max-jobs phải lớn hơn 0.")
    if strategy not in ("linear", "binary"):
        raise ValueError("strategy không hợp lệ.")
    methods = list(AMO_METHODS) if amo == "all" else [amo]
    selected_solvers = list(dict.fromkeys(solver_keys or SOLVER_KEYS))
    if any(m not in AMO_METHODS for m in methods) or any(k not in SOLVER_KEYS for k in selected_solvers):
        raise ValueError("Solver hoặc AMO không hợp lệ.")
    if table_filter not in (None, "all", 6, "6", 7, "7"):
        raise ValueError("table phải là 6, 7 hoặc all.")
    items = [x for x in BENCHMARK_SUITE
             if table_filter in (None, "all") or x["table"] == int(table_filter)]
    if instances is not None:
        names = list(dict.fromkeys(instances))
        lookup = {x["name"]: x for x in items}
        unknown = set(names) - set(lookup)
        if unknown:
            raise ValueError(f"Instance không thuộc bảng đã chọn: {', '.join(sorted(unknown))}")
        items = [lookup[name] for name in names]

    checkpoint, output = Path(checkpoint).resolve(), Path(output_csv).resolve()
    stop_path = Path(stop_file).resolve() if stop_file else Path(str(checkpoint) + ".stop")
    if len({checkpoint, output, stop_path}) != 3:
        raise ValueError("Checkpoint, CSV và stop-file phải là các đường dẫn khác nhau.")
    # Do not overwrite the old wide-format experimental results.
    if output.exists():
        import csv
        with output.open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream), [])
        if "Job_ID" not in header or "Attempt" not in header:
            raise ValueError(f"{output} không phải CSV resume. Hãy chọn --output khác; file cũ được giữ nguyên.")

    deadline = time.monotonic() + session_hours * 3600 if session_hours else None
    versions = _environment()
    code_hash = _code_hash()
    runtime = None
    counters = {"completed": 0, "skipped": 0}
    print(f"Checkpoint: {checkpoint}\nCSV: {output}\nStop-file: {stop_path}")
    print(f"{len(items)} instances × {len(methods)} AMO × {len(selected_solvers)} SAT. "
          "Resume tự động; n >= 400: LIMIT. Nhấn Ctrl+C để dừng sau lượt hiện tại.", flush=True)

    with BenchmarkStore(checkpoint) as store, _graceful_stop() as stopping:
        def should_stop(reserve=0):
            return (stopping[0] or stop_path.exists()
                    or (max_jobs is not None and counters["completed"] >= max_jobs)
                    or (deadline is not None and time.monotonic() + reserve >= deadline))

        def saved(attempt, status, result):
            store.finish(attempt, status, result)
            counters["completed"] += 1
            _export(store, output)
            print(f"  [Saved] {status}", flush=True)
            if result.get("Error"):
                print(f"  {result['Error']}", flush=True)

        _export(store, output)
        try:
            for item in items:
                if should_stop():
                    break
                path = ROOT / item["file"]
                size_limited = item["paper_n"] >= 400
                input_error = None
                if not size_limited and not path.exists():
                    try:
                        downloaded = download_hb_matrix(item["name"], target_dir=str(path.parent))
                        if not downloaded or not path.exists():
                            input_error = "DOWNLOAD_ERROR", "Không tải được dataset."
                    except Exception as exc:
                        input_error = "DOWNLOAD_ERROR", str(exc)
                try:
                    data_hash = (f"size-limit:{item['paper_n']}" if size_limited
                                 else file_digest(path) if path.exists() and not input_error else "unavailable")
                except OSError as exc:
                    data_hash = "unavailable"
                    input_error = "ERROR", str(exc)
                graph = None
                graph_attempted = False
                for method in methods:
                    for solver_key in selected_solvers:
                        if should_stop():
                            return counters
                        identity = {
                            "Instance": item["name"], "Data_SHA256": data_hash,
                            "Code_SHA256": code_hash, "Environment": versions,
                            "Solver": solver_key, "AMO_Method": method, "Strategy": strategy,
                            "Timeout_s": float(timeout), "Use_Heuristics": True,
                            "Use_Components": True, "Size_Limit_Exclusive": 400,
                        }
                        job_id = digest(identity)
                        if not store.should_run(job_id, retry_errors=retry_errors):
                            counters["skipped"] += 1
                            print(f"[Resume] Bỏ qua {item['name']} / {solver_key} / {method}", flush=True)
                            continue
                        if should_stop(reserve=0 if size_limited else timeout):
                            print("[Session] Không bắt đầu lượt mới vì không đủ ngân sách thời gian.")
                            return counters
                        if not size_limited and not input_error and not graph_attempted:
                            graph_attempted = True
                            try:
                                if runtime is None:
                                    runtime = _load_runtime()
                                graph = runtime[0].from_mtx(str(path), name=item["name"])
                            except Exception as exc:
                                input_error = "ERROR", str(exc)
                        info = dict(identity, Table=item["table"], n=graph.n if graph else item["paper_n"],
                                    m=graph.m if graph else "", Paper_LB=item["paper_lb"],
                                    Paper_Best=item["paper_best"], NIST_URL=get_matrix_url(item["name"]),
                                    Machine=platform.node(), Platform=platform.platform())
                        if should_stop(reserve=0 if size_limited or input_error else timeout):
                            return counters
                        attempt = store.start(job_id, info)
                        print(f"[Run] {item['name']} / {solver_key} / {method}", flush=True)
                        if size_limited or (graph is not None and graph.n >= 400):
                            saved(attempt, "LIMIT", {"Reason": "n >= 400", "Runtime_s": 0})
                            continue
                        if input_error:
                            saved(attempt, input_error[0], {"Error": input_error[1]})
                            continue
                        started = time.monotonic()
                        try:
                            solver = runtime[1][solver_key](graph, amo_method=method, timeout=timeout)
                            result = solver.solve(use_heuristics=True, use_components=True,
                                                  strategy=strategy, verbose=False)
                            elapsed = time.monotonic() - started
                            saved(attempt, result.status, {
                                "Bandwidth": result.bandwidth, "Runtime_s": elapsed,
                                "Iterations": result.iterations, "Clauses": result.clauses_count,
                                "Vars": result.vars_count, "Labeling": result.labeling,
                            })
                        except KeyboardInterrupt:
                            saved(attempt, "INTERRUPTED", {"Runtime_s": time.monotonic() - started})
                            return counters
                        except Exception as exc:
                            saved(attempt, "ERROR", {"Error": str(exc), "Runtime_s": time.monotonic() - started})
        finally:
            _export(store, output)
            print(f"\nĐã dừng an toàn. Phiên này lưu {counters['completed']} lượt; "
                  f"bỏ qua {counters['skipped']} lượt đã có. Chạy lại cùng lệnh để tiếp tục.", flush=True)
            if stop_path.exists():
                print(f"Xóa stop-file trước khi chạy tiếp: {stop_path}")
    return counters


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Benchmark SAT với checkpoint/resume sau từng lượt solver")
    parser.add_argument("--table", choices=["6", "7", "all"], default="all")
    parser.add_argument("--amo", choices=[*AMO_METHODS, "all"], default="pairwise")
    parser.add_argument("--strategy", choices=["linear", "binary"], default="linear")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output", default="results/benchmark_runs.csv", help="CSV dạng dài, tự xuất từ checkpoint")
    parser.add_argument("--checkpoint", default="results/benchmark_resume.sqlite3")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--instances", nargs="+", help="Danh sách tên instance")
    selection.add_argument("--instances-file", help="File UTF-8: tên instance cách nhau bởi khoảng trắng; # là chú thích")
    parser.add_argument("--solvers", nargs="+", choices=SOLVER_KEYS)
    parser.add_argument("--session-hours", type=float, help="Ngừng nhận lượt mới khi không đủ thời gian cho timeout")
    parser.add_argument("--max-jobs", type=int, help="Dừng sau số lượt mới chỉ định")
    parser.add_argument("--retry-errors", action="store_true", help="Chạy lại ERROR/DOWNLOAD_ERROR; không chạy lại TIMEOUT")
    parser.add_argument("--stop-file", help="Tạo file này để dừng sau lượt hiện tại")
    parser.add_argument("--resume", action="store_true", help="Resume luôn bật; cờ này được giữ để lệnh dễ đọc")
    args = parser.parse_args()
    instances = args.instances
    try:
        if args.instances_file:
            instances = [word for line in Path(args.instances_file).read_text(encoding="utf-8-sig").splitlines()
                         for word in line.split("#", 1)[0].split()]
            if not instances:
                raise ValueError("instances-file không có instance nào.")
        run_benchmark(table_filter=args.table, strategy=args.strategy, amo=args.amo,
                      timeout=args.timeout, output_csv=args.output, checkpoint=args.checkpoint,
                      instances=instances, solver_keys=args.solvers, session_hours=args.session_hours,
                      max_jobs=args.max_jobs, retry_errors=args.retry_errors, stop_file=args.stop_file)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, f"Lỗi: {exc}\n")


if __name__ == "__main__":
    main()

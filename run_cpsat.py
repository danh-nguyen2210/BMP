"""Run OR-Tools CP-SAT with its own checkpoint, without changing prior job hashes."""
import argparse
import csv
import importlib.metadata
import math
import multiprocessing as mp
from pathlib import Path
from queue import Empty
import signal
import sys
import time

import run_baselines as common
from run_benchmarks import BENCHMARK_SUITE
from src.benchmark_store import BenchmarkStore, digest, file_digest
from src.downloader import download_hb_matrix


def native_solve(graph, initial, deadline, threads):
    from ortools.sat.python import cp_model
    low, high, labels = initial
    model = cp_model.CpModel()
    f = {u: model.new_int_var(1, graph.n, f'f_{u}') for u in range(1, graph.n+1)}
    b = model.new_int_var(low, high, 'bandwidth')
    model.add_all_different(list(f.values()))
    for u, v in sorted(graph.edges):
        diff = model.new_int_var(0, graph.n-1, f'diff_{u}_{v}')
        model.add_abs_equality(diff, f[u]-f[v])
        model.add(diff <= b)
    model.minimize(b)
    for u, var in f.items():
        model.add_hint(var, labels[u])
    model.add_hint(b, high)
    budget = deadline - time.monotonic()
    if budget <= 0:
        return common.finish_result(graph, initial, None, None, False, True,
                                    'budget exhausted during setup', 0, 0)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(.001, budget-min(2., budget*.1))
    solver.parameters.num_search_workers = threads
    solver.parameters.relative_gap_limit = 0
    solver.parameters.absolute_gap_limit = 0
    solver.parameters.log_search_progress = False
    status = solver.solve(model)
    if status in (cp_model.INFEASIBLE, cp_model.MODEL_INVALID):
        raise RuntimeError(f'CP-SAT contradicts known feasible model: {solver.status_name(status)}')
    candidate = ({u: int(solver.value(var)) for u, var in f.items()}
                 if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None)
    return common.finish_result(
        graph, initial, candidate, solver.best_objective_bound,
        status == cp_model.OPTIMAL, status in (cp_model.FEASIBLE, cp_model.UNKNOWN),
        solver.status_name(status), graph.n+graph.m+1, 1+2*graph.m,
        solver.num_branches)


def worker(graph, initial, deadline, threads, queue):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        queue.put(('RESULT', native_solve(graph, initial, deadline, threads)))
    except Exception as exc:
        queue.put(('ERROR', f'{type(exc).__name__}: {exc}'))


def solve_job(graph, timeout, threads):
    started = time.monotonic()
    initial = common.initial_bounds(graph)
    if initial[0] == initial[1]:
        result = common.finish_result(graph, initial, None, initial[0], False, False,
                                      'initial bounds meet', 0, 0)
    else:
        ctx = mp.get_context('spawn')
        queue = ctx.Queue()
        process = ctx.Process(target=worker, args=(graph, initial, started+timeout, threads, queue))
        result = None
        try:
            process.start()
            while time.monotonic()-started < timeout:
                try:
                    kind, value = queue.get(timeout=min(.1, max(.001, timeout-(time.monotonic()-started))))
                except Empty:
                    if not process.is_alive():
                        raise RuntimeError(f'Worker exited without result: {process.exitcode}')
                    continue
                if kind == 'ERROR':
                    raise RuntimeError(value)
                result = value
                break
            if result is None:
                result = common.finish_result(graph, initial, None, None, False, True,
                                              'watchdog; latest engine incumbent unavailable', 0, 0)
        finally:
            if process.pid is not None:
                process.join(timeout=.1)
                common.stop_worker(process)
                process.close()
            queue.close()
            queue.join_thread()
    result['Runtime_s'] = time.monotonic()-started
    return result


def run(args):
    from src.graph import GraphData
    # Fail before recording jobs if the optional engine is missing.
    version = importlib.metadata.version('ortools')
    names = args.instances
    if args.instances_file:
        names = [w for line in Path(args.instances_file).read_text(encoding='utf-8-sig').splitlines()
                 for w in line.split('#')[0].split()]
    lookup = {r['name']: r for r in BENCHMARK_SUITE}
    if not names or set(names)-set(lookup):
        raise ValueError('Empty list or unknown benchmark instance')
    items = [lookup[n] for n in dict.fromkeys(names)]
    checkpoint, output = Path(args.checkpoint).resolve(), Path(args.output).resolve()
    stop = Path(args.stop_file or str(checkpoint)+'.stop').resolve()
    if len({checkpoint, output, stop}) != 3:
        raise ValueError('Checkpoint, CSV and stop-file must be different paths')
    if output.exists():
        with output.open(encoding='utf-8-sig', newline='') as stream:
            header = next(csv.reader(stream), [])
        if 'Job_ID' not in header or 'Attempt' not in header:
            raise ValueError('Existing output is not a resume CSV; choose another path')
    versions = {k: v for k, v in common.environment().items() if k not in ('gurobipy', 'cplex', 'docplex')}
    versions['ortools'] = version
    versions['protobuf'] = importlib.metadata.version('protobuf')
    code_hash = digest({p: file_digest(common.ROOT/p) for p in (
        'run_cpsat.py', 'run_baselines.py', 'run_benchmarks.py',
        'src/graph.py', 'src/benchmark_store.py', 'src/downloader.py')})
    stopping = [False]
    saved = skipped = 0
    deadline = time.monotonic()+args.session_hours*3600 if args.session_hours else None
    def handler(*_):
        stopping[0] = True
        print('\n[Stop] Waiting for current job to finish and save.', flush=True)
    def should_stop(reserve=0):
        return (stopping[0] or stop.exists() or
                (args.max_jobs is not None and saved >= args.max_jobs) or
                (deadline is not None and time.monotonic()+reserve >= deadline))
    def export(store):
        try:
            store.export_csv(output)
        except OSError as exc:
            print(f'[CSV] Export failed; SQLite retained: {exc}', flush=True)
    previous = signal.signal(signal.SIGINT, handler)
    print(f'{len(items)} instances x CP-SAT; timeout={args.timeout}s; threads={args.threads}')
    print(f'Checkpoint: {checkpoint}\nCSV: {output}\nStop-file: {stop}', flush=True)
    try:
        with BenchmarkStore(checkpoint) as store:
            export(store)
            for item in items:
                if should_stop():
                    break
                limited = item['paper_n'] >= 400
                path = common.ROOT/item['file']
                if not limited and not path.exists():
                    download_hb_matrix(item['name'], target_dir=str(path.parent))
                identity = {
                    'Instance': item['name'], 'Solver': 'cp-sat', 'Timeout_s': args.timeout,
                    'Threads': args.threads, 'Use_Heuristics': True, 'Use_Components': False,
                    'Warm_Start': 'RCM', 'Data_SHA256': 'size-limit' if limited else file_digest(path),
                    'Code_SHA256': code_hash, 'Environment': versions,
                    'Machine': common.platform.node(), 'Platform': common.platform.platform(),
                    'Size_Limit_Exclusive': 400}
                job_id = digest(identity)
                if not store.should_run(job_id, retry_errors=args.retry_errors):
                    skipped += 1
                    print(f"[Resume] {item['name']} / cp-sat", flush=True)
                    continue
                if should_stop(0 if limited else args.timeout):
                    break
                attempt = store.start(job_id, dict(identity, Table=item['table'], n=item['paper_n'],
                                      Paper_LB=item['paper_lb'], Paper_Best=item['paper_best']))
                print(f"[Run] {item['name']} / cp-sat", flush=True)
                started = time.monotonic()
                try:
                    if limited:
                        result = {'Status': 'LIMIT', 'Runtime_s': 0, 'Reason': 'n >= 400'}
                    else:
                        graph = GraphData.from_mtx(path)
                        if graph.n >= 400:
                            result = {'Status': 'LIMIT', 'Runtime_s': 0, 'Reason': 'n >= 400'}
                        else:
                            result = solve_job(graph, args.timeout, args.threads)
                            result.update(n=graph.n, m=graph.m)
                except (KeyboardInterrupt, InterruptedError):
                    stopping[0] = True
                    result = {'Status': 'INTERRUPTED', 'Runtime_s': time.monotonic()-started}
                except Exception as exc:
                    stopping[0] = True
                    result = {'Status': 'ERROR', 'Error': str(exc), 'Runtime_s': time.monotonic()-started}
                store.finish(attempt, result['Status'], result)
                saved += 1
                export(store)
                print(f"  [Saved] {result['Status']} BW={result.get('Bandwidth', '-')} LB={result.get('LB_Proven', '-')}", flush=True)
                if result.get('Error'):
                    print(result['Error'], flush=True)
            export(store)
    finally:
        signal.signal(signal.SIGINT, previous)
    print(f'Stopped safely. Saved {saved}; skipped {skipped}.', flush=True)


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--instances-file')
    selection.add_argument('--instances', nargs='+')
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--checkpoint', default='results/cpsat.sqlite3')
    parser.add_argument('--output', default='results/cpsat.csv')
    parser.add_argument('--stop-file')
    parser.add_argument('--retry-errors', action='store_true')
    parser.add_argument('--max-jobs', type=int)
    parser.add_argument('--session-hours', type=float)
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0 or args.threads <= 0:
        parser.error('timeout and threads must be positive')
    if args.max_jobs is not None and args.max_jobs <= 0:
        parser.error('max-jobs must be positive')
    if args.session_hours is not None and (not math.isfinite(args.session_hours) or args.session_hours <= 0):
        parser.error('session-hours must be finite and positive')
    try:
        run(args)
    except (ValueError, RuntimeError, OSError, importlib.metadata.PackageNotFoundError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    sys.exit(main())

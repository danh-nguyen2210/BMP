"""Independent CP/MIP benchmark runner; does not alter SAT job identities.

Solve the whole graph (no component decomposition), with RCM as a feasible
starting solution. Native time limits leave a short margin before the watchdog.
Resume is between jobs, never inside a solver search.
"""
import argparse
import csv
import importlib.metadata
import importlib.util
import math
import multiprocessing as mp
import os
from pathlib import Path
import platform
from queue import Empty
import signal
import subprocess
import sys
import time

from run_benchmarks import BENCHMARK_SUITE
from src.benchmark_store import BenchmarkStore, digest, file_digest
from src.downloader import download_hb_matrix

ROOT = Path(__file__).resolve().parent
SOLVERS = ('cplex-cp', 'cplex-mip', 'gurobi')


def verify(graph, labels):
    if set(labels) != set(range(1, graph.n + 1)):
        raise ValueError('Invalid labeling: incorrect vertex set')
    if any(type(v) is not int for v in labels.values()):
        raise ValueError('Invalid labeling: non-integer labels')
    if set(labels.values()) != set(range(1, graph.n + 1)):
        raise ValueError('Invalid labeling: not a permutation')
    return max((abs(labels[u] - labels[v]) for u, v in graph.edges), default=0)


def initial_bounds(graph):
    labels = graph.get_rcm_labeling()
    upper = verify(graph, labels)
    # The diameter bound must be applied within each connected component.
    lower = max((c.compute_lb() if c.edges else 0
                 for c in graph.get_connected_components()), default=0)
    if lower > upper:
        raise ValueError('Computed lower bound exceeds verified RCM upper bound')
    return lower, upper, labels


def finish_result(graph, initial, candidate, bound, optimal, timed_out,
                  engine_status, variables, constraints, nodes=0):
    lower, upper, labels = initial
    source = 'RCM'
    if candidate is not None:
        actual = verify(graph, candidate)
        if actual <= upper:
            upper, labels, source = actual, candidate, 'solver'
    if bound is not None and math.isfinite(bound):
        # Bandwidth is integral; allow for solver floating point tolerances.
        lower = max(lower, math.ceil(bound - 1e-5))
    if lower > upper:
        raise ValueError('Solver bound contradicts verified feasible solution')
    if optimal:
        if candidate is None:
            raise ValueError('Engine reports optimality without a solution')
        lower = upper
    status = 'OPTIMAL' if optimal or lower == upper else ('TIMEOUT' if timed_out else 'FEASIBLE')
    return {'Status': status, 'Bandwidth': upper, 'LB_Proven': lower,
            'UB_Found': upper, 'Gap_Absolute': upper - lower,
            'Labeling': labels, 'Validation': 'VALID', 'Solution_Source': source,
            'Engine_Status': str(engine_status), 'Vars': variables,
            'Constraints': constraints, 'Nodes': nodes}


def native_solve(graph, key, budget, threads, initial):
    started = time.monotonic()
    low, high, labels = initial
    n = graph.n
    # Reserve time for extracting and serializing an incumbent before watchdog.
    def remaining():
        return budget - (time.monotonic() - started) - min(2.0, budget * .1)

    def expired():
        return finish_result(graph, initial, None, None, False, True,
                             'budget exhausted during setup', 0, 0)

    if key == 'gurobi':
        import gurobipy as gp
        with gp.Env(empty=True) as env:
            env.setParam('OutputFlag', 0)
            env.start()
            with gp.Model('BMP', env=env) as model:
                model.Params.Threads = threads
                model.Params.MIPGap = 0
                model.Params.MIPGapAbs = 0
                x = model.addVars(range(1, n+1), range(1, n+1), vtype=gp.GRB.BINARY)
                b = model.addVar(lb=low, ub=high, vtype=gp.GRB.INTEGER)
                for u in range(1, n+1):
                    model.addConstr(x.sum(u, '*') == 1)
                    model.addConstr(x.sum('*', u) == 1)
                pos = {u: gp.quicksum(i*x[u, i] for i in range(1, n+1)) for u in range(1, n+1)}
                for u, v in sorted(graph.edges):
                    model.addConstr(pos[u]-pos[v] <= b)
                    model.addConstr(pos[v]-pos[u] <= b)
                model.setObjective(b, gp.GRB.MINIMIZE)
                for (u, i), var in x.items():
                    var.Start = int(labels[u] == i)
                b.Start = high
                if remaining() <= 0:
                    return expired()
                model.Params.TimeLimit = remaining()
                model.optimize()
                if model.Status in (gp.GRB.INFEASIBLE, gp.GRB.INF_OR_UNBD, gp.GRB.UNBOUNDED):
                    raise RuntimeError('Engine contradicts known feasible bounded BMP model')
                candidate = None
                if model.SolCount:
                    candidate = {u: i for (u, i), var in x.items() if var.X > .5}
                return finish_result(graph, initial, candidate, model.ObjBound,
                                     model.Status == gp.GRB.OPTIMAL,
                                     model.Status == gp.GRB.TIME_LIMIT, model.Status,
                                     model.NumVars, model.NumConstrs, model.NodeCount)

    if key == 'cplex-mip':
        from docplex.mp.model import Model
        with Model('BMP') as model:
            x = model.binary_var_matrix(range(1, n+1), range(1, n+1))
            b = model.integer_var(lb=low, ub=high)
            for u in range(1, n+1):
                model.add_constraint(model.sum(x[u, i] for i in range(1, n+1)) == 1)
                model.add_constraint(model.sum(x[i, u] for i in range(1, n+1)) == 1)
            pos = {u: model.sum(i*x[u, i] for i in range(1, n+1)) for u in range(1, n+1)}
            for u, v in sorted(graph.edges):
                model.add_constraint(pos[u]-pos[v] <= b)
                model.add_constraint(pos[v]-pos[u] <= b)
            model.minimize(b)
            start = model.new_solution()
            for (u, i), var in x.items():
                start.add_var_value(var, int(labels[u] == i))
            start.add_var_value(b, high)
            model.add_mip_start(start)
            model.parameters.threads = threads
            model.parameters.mip.tolerances.mipgap = 0
            model.parameters.mip.tolerances.absmipgap = 0
            if remaining() <= 0:
                return expired()
            model.parameters.timelimit = remaining()
            solution = model.solve(log_output=False)
            details = model.solve_details
            status = details.status.lower()
            if 'infeasible' in status or 'unbounded' in status:
                raise RuntimeError('Engine contradicts known feasible bounded BMP model')
            candidate = None if solution is None else {
                u: i for (u, i), var in x.items() if solution.get_value(var) > .5}
            return finish_result(graph, initial, candidate, details.best_bound,
                                 'optimal' in status, details.has_hit_limit(), details.status,
                                 model.number_of_variables, model.number_of_constraints,
                                 details.nb_nodes_processed)

    if key == 'cplex-cp':
        from docplex.cp.model import CpoModel
        from docplex.cp.solution import CpoModelSolution, STOP_CAUSE_LIMIT
        model = CpoModel()
        f = {u: model.integer_var(1, n, name=f'f_{u}') for u in range(1, n+1)}
        b = model.integer_var(low, high, name='B')
        model.add(model.all_diff(list(f.values())))
        for u, v in sorted(graph.edges):
            model.add(model.abs(f[u]-f[v]) <= b)
        model.minimize(b)
        start = CpoModelSolution()
        for u, var in f.items():
            start.add_integer_var_solution(var, labels[u])
        start.add_integer_var_solution(b, high)
        model.set_starting_point(start)
        if remaining() <= 0:
            return expired()
        solution = model.solve(TimeLimit=remaining(), Workers=threads,
                               RelativeOptimalityTolerance=0, OptimalityTolerance=0,
                               LogVerbosity='Quiet', log_output=None)
        status = solution.get_solve_status()
        if status in ('Infeasible', 'Unbounded'):
            raise RuntimeError('Engine contradicts known feasible bounded BMP model')
        candidate = ({u: int(solution.get_value(var)) for u, var in f.items()}
                     if solution.is_solution() else None)
        bounds = solution.get_objective_bounds()
        stopped = solution.get_stop_cause()
        return finish_result(graph, initial, candidate, bounds[0] if bounds else None,
                             status == 'Optimal', stopped == STOP_CAUSE_LIMIT,
                             f'{status}; {stopped}', n+1, 1+graph.m)
    raise ValueError(f'Unknown solver: {key}')


def worker(graph, key, deadline, threads, initial, queue):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        budget = deadline - time.monotonic()
        if budget <= 0:
            result = finish_result(graph, initial, None, None, False, True,
                                   'budget exhausted during worker startup', 0, 0)
        else:
            result = native_solve(graph, key, budget, threads, initial)
        queue.put(('RESULT', result))
    except Exception as exc:
        queue.put(('ERROR', f'{type(exc).__name__}: {exc}'))


def stop_worker(process):
    if not process.is_alive():
        return
    if os.name == 'nt':
        # CP Optimizer launches a child executable: terminate that tree as well.
        subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    if process.is_alive():
        process.terminate()
    process.join(timeout=2)
    if process.is_alive():
        process.kill()
        process.join()


def solve_job(graph, key, timeout, threads):
    started = time.monotonic()
    initial = initial_bounds(graph)
    low, high, _ = initial
    if low == high:
        result = finish_result(graph, initial, None, low, False, False, 'initial bounds meet', 0, 0)
    else:
        ctx = mp.get_context('spawn')
        queue = ctx.Queue()
        process = ctx.Process(target=worker, args=(graph, key, started+timeout, threads, initial, queue))
        result = None
        try:
            process.start()
            while time.monotonic() - started < timeout:
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
                result = finish_result(graph, initial, None, None, False, True,
                                       'watchdog; latest engine incumbent unavailable', 0, 0)
        finally:
            if process.pid is not None:
                process.join(timeout=.1)
                stop_worker(process)
                process.close()
            queue.close()
            queue.join_thread()
    result['Runtime_s'] = time.monotonic() - started
    return result


def environment():
    versions = {'python': platform.python_version(), 'system': platform.system(),
                'architecture': platform.machine()}
    for name in ('numpy', 'scipy', 'gurobipy', 'cplex', 'docplex'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = 'not-installed'
    return versions


def run(args):
    from src.graph import GraphData
    names = args.instances
    if args.instances_file:
        names = [w for line in Path(args.instances_file).read_text(encoding='utf-8-sig').splitlines()
                 for w in line.split('#')[0].split()]
    lookup = {item['name']: item for item in BENCHMARK_SUITE}
    if not names or set(names) - set(lookup):
        raise ValueError('Empty list or unknown benchmark instance')
    items = [lookup[name] for name in dict.fromkeys(names)]
    solvers = list(dict.fromkeys(args.solvers))
    for key in solvers:
        modules = ('gurobipy',) if key == 'gurobi' else (('docplex', 'cplex') if key == 'cplex-mip' else ('docplex',))
        for module in modules:
            if importlib.util.find_spec(module) is None:
                raise ValueError(f'Missing Python package: {module}')
    checkpoint, output = Path(args.checkpoint).resolve(), Path(args.output).resolve()
    stop = Path(args.stop_file or str(checkpoint)+'.stop').resolve()
    if len({checkpoint, output, stop}) != 3:
        raise ValueError('Checkpoint, CSV and stop-file must be different paths')
    if output.exists():
        with output.open(encoding='utf-8-sig', newline='') as stream:
            header = next(csv.reader(stream), [])
        if 'Job_ID' not in header or 'Attempt' not in header:
            raise ValueError('Existing output is not a resume CSV; choose another path')
    code_hash = digest({p: file_digest(ROOT/p) for p in (
        'run_baselines.py', 'run_benchmarks.py', 'src/graph.py',
        'src/downloader.py', 'src/benchmark_store.py')})
    versions = environment()
    stopping = [False]
    def handler(*_):
        stopping[0] = True
        print('\n[Stop] Waiting for current job to finish and save.', flush=True)
    previous = signal.signal(signal.SIGINT, handler)
    saved = skipped = 0
    deadline = time.monotonic()+args.session_hours*3600 if args.session_hours else None
    def should_stop(reserve=0):
        return (stopping[0] or stop.exists() or
                (args.max_jobs is not None and saved >= args.max_jobs) or
                (deadline is not None and time.monotonic()+reserve >= deadline))
    def export(store):
        try:
            store.export_csv(output)
        except OSError as exc:
            print(f'[CSV] Export failed; SQLite retained: {exc}', flush=True)
    print(f'{len(items)} instances x {len(solvers)} baselines; timeout={args.timeout}s; threads={args.threads}')
    print(f'Checkpoint: {checkpoint}\nCSV: {output}\nStop-file: {stop}', flush=True)
    try:
        with BenchmarkStore(checkpoint) as store:
            export(store)
            for item in items:
                if should_stop():
                    break
                path = ROOT/item['file']
                limited = item['paper_n'] >= 400
                if not limited and not path.exists():
                    download_hb_matrix(item['name'], target_dir=str(path.parent))
                if not limited and not path.exists():
                    raise FileNotFoundError(path)
                data_hash = 'size-limit' if limited else file_digest(path)
                graph = None
                for key in solvers:
                    if should_stop():
                        break
                    identity = {'Instance': item['name'], 'Solver': key,
                                'Timeout_s': args.timeout, 'Threads': args.threads,
                                'Use_Heuristics': True, 'Use_Components': False,
                                'Warm_Start': 'RCM', 'Data_SHA256': data_hash,
                                'Code_SHA256': code_hash, 'Environment': versions,
                                'Machine': platform.node(), 'Platform': platform.platform(),
                                'Size_Limit_Exclusive': 400}
                    job_id = digest(identity)
                    if not store.should_run(job_id, retry_errors=args.retry_errors):
                        skipped += 1
                        print(f"[Resume] {item['name']} / {key}", flush=True)
                        continue
                    if should_stop(0 if limited else args.timeout):
                        break
                    attempt = store.start(job_id, dict(identity, Table=item['table'],
                                          n=item['paper_n'], Paper_LB=item['paper_lb'],
                                          Paper_Best=item['paper_best']))
                    print(f"[Run] {item['name']} / {key}", flush=True)
                    start = time.monotonic()
                    try:
                        if limited:
                            result = {'Status': 'LIMIT', 'Runtime_s': 0, 'Reason': 'n >= 400'}
                        else:
                            if graph is None:
                                graph = GraphData.from_mtx(path)
                            if graph.n >= 400:
                                result = {'Status': 'LIMIT', 'Reason': 'n >= 400'}
                            else:
                                result = solve_job(graph, key, args.timeout, args.threads)
                                result.update(n=graph.n, m=graph.m)
                    except (KeyboardInterrupt, InterruptedError):
                        stopping[0] = True
                        result = {'Status': 'INTERRUPTED', 'Runtime_s': time.monotonic()-start}
                    except Exception as exc:
                        result = {'Status': 'ERROR', 'Error': str(exc), 'Runtime_s': time.monotonic()-start}
                    store.finish(attempt, result['Status'], result)
                    saved += 1
                    export(store)
                    print(f"  [Saved] {result['Status']} BW={result.get('Bandwidth', '-')} LB={result.get('LB_Proven', '-')}", flush=True)
                    if result.get('Error'):
                        print(result['Error'], flush=True)
                        # Stop on installation/license errors rather than fail all jobs.
                        stopping[0] = True
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
    parser.add_argument('--solvers', nargs='+', choices=SOLVERS, default=list(SOLVERS))
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--threads', type=int, default=1)
    parser.add_argument('--checkpoint', default='results/baselines.sqlite3')
    parser.add_argument('--output', default='results/baselines.csv')
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
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    mp.freeze_support()
    sys.exit(main())

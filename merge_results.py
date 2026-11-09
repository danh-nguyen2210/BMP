"""Export the latest official 600-second results into one compact analysis CSV.

Original CSVs/checkpoints remain authoritative. Removing machine/environment
columns from this presentation export does not imply a single-machine study.
"""
import argparse
import csv
import math
import os
from pathlib import Path
from collections import Counter

from run_benchmarks import BENCHMARK_SUITE

ROOT = Path(__file__).resolve().parent
SAT_SOLVERS = ('order-inc', 'order-iter', 'pairwise-inc', 'pairwise-iter')
AMO_METHODS = ('pairwise', 'sequential', 'product')
BASELINES = ('cplex-cp', 'cplex-mip', 'gurobi', 'cp-sat')
CONFIGS = [(s, a) for a in AMO_METHODS for s in SAT_SOLVERS] + [(s, '') for s in BASELINES]
FIELDS = [
    'Instance', 'Table', 'n', 'm', 'Paper_LB', 'Paper_Best',
    'Solver', 'AMO_Method', 'Timeout_s', 'Status', 'Bandwidth', 'Runtime_s',
    'Iterations', 'Clauses', 'Vars', 'Constraints', 'LB_Proven', 'UB_Found',
    'Gap_Absolute', 'Use_Components', 'Threads', 'Error',
]


def merge(output):
    rows_by_config = {}
    source_files = []
    attempts = 0
    assigned = set()
    for person in (1, 2, 3):
        names = {word for line in (ROOT/f'config/split42_person{person}.txt').read_text(
            encoding='utf-8-sig').splitlines() for word in line.split('#')[0].split()}
        if len(names) != 14 or assigned & names:
            raise ValueError(f'Invalid assignment for person {person}')
        assigned.update(names)
        sources = [(f'split42_person{person}_{amo}_600.csv', SAT_SOLVERS, amo)
                   for amo in AMO_METHODS]
        sources += [(f'baselines_person{person}_600.csv', BASELINES[:3], ''),
                    (f'cpsat_person{person}_600.csv', ('cp-sat',), '')]
        for filename, solvers, amo in sources:
            path = ROOT/'results'/filename
            source_files.append(path.resolve())
            with path.open(encoding='utf-8-sig', newline='') as stream:
                records = list(csv.DictReader(stream))
            latest = {}
            for record in records:
                if None in record or any(value is None for value in record.values()):
                    raise ValueError(f'Malformed CSV row: {filename}')
                job_id = record['Job_ID']
                if not job_id:
                    raise ValueError(f'Missing Job_ID: {filename}')
                attempt = int(record['Attempt'])
                if job_id not in latest or attempt > int(latest[job_id]['Attempt']):
                    latest[job_id] = record
                elif attempt == int(latest[job_id]['Attempt']) and record != latest[job_id]:
                    raise ValueError(f'Conflicting records for attempt {attempt}: {filename}')
            attempts += len(records)
            for record in latest.values():
                instance = record['Instance']
                solver = record['Solver']
                if (instance not in names or solver not in solvers or
                        record.get('AMO_Method', '') != amo or float(record['Timeout_s']) != 600):
                    raise ValueError(f'Unexpected experiment configuration: {filename}')
                if record.get('Strategy', 'linear') != 'linear':
                    raise ValueError(f'Unexpected SAT strategy: {filename}')
                key = instance, solver, amo
                if key in rows_by_config:
                    # Do not silently choose between different code/environment jobs.
                    raise ValueError(f'Multiple Job_IDs for {key}; inspect source records first')
                clean = {field: record.get(field, '') for field in FIELDS}
                bandwidth = clean['Bandwidth']
                if bandwidth in ('', 'TIMEOUT', 'MEM_EXCEED', 'LIMIT', 'ERROR'):
                    clean['Bandwidth'] = ''
                else:
                    value = float(bandwidth)
                    if not math.isfinite(value) or value < 0 or not value.is_integer():
                        raise ValueError(f'Invalid numeric bandwidth for {key}: {bandwidth}')
                    clean['Bandwidth'] = str(int(value))
                rows_by_config[key] = clean

    expected_names = {r['name'] for r in BENCHMARK_SUITE if r['paper_n'] < 400}
    if assigned != expected_names:
        raise ValueError('Assignments do not cover all Table 6/7 instances with n < 400')
    expected = {(name, solver, amo) for name in assigned for solver, amo in CONFIGS}
    if set(rows_by_config) != expected:
        missing = expected - set(rows_by_config)
        extra = set(rows_by_config) - expected
        raise ValueError(f'Incomplete experiment grid: missing={sorted(missing)}, extra={sorted(extra)}')
    output = Path(output).resolve()
    if output in source_files:
        raise ValueError('Output must not overwrite an original result CSV')
    order = {config: index for index, config in enumerate(CONFIGS)}
    rows = sorted(rows_by_config.values(), key=lambda r: (
        int(r['Table']), int(r['n']), r['Instance'], order[(r['Solver'], r['AMO_Method'])]))
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix+'.tmp')
    try:
        with temporary.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(f'Input: {len(source_files)} CSVs, {attempts} historical attempts')
    print(f'Output: {len(rows)} rows, {len(FIELDS)} columns; {attempts-len(rows)} superseded attempts removed')
    print(f'Status: {dict(Counter(r["Status"] for r in rows))}')
    print(f'Saved: {output}')
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/merged_results.csv')
    args = parser.parse_args()
    merge(args.output)

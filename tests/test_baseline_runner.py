"""Validate certificates, statuses, interrupted attempts and resume separately from SAT."""
import argparse
from contextlib import closing, redirect_stdout
import importlib.util
import io
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import run_baselines as runner
from src.graph import GraphData


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.graph = GraphData(4, [(1, 2), (2, 3), (3, 4)])
        self.initial = (1, 3, {1: 1, 2: 4, 3: 2, 4: 3})

    def test_timeout_retains_valid_incumbent_without_claiming_optimal(self):
        labels = {1: 1, 2: 3, 3: 2, 4: 4}
        result = runner.finish_result(self.graph, self.initial, labels, 1,
                                      False, True, 'time limit', 17, 14)
        self.assertEqual(result['Status'], 'TIMEOUT')
        self.assertEqual(result['Bandwidth'], 2)
        self.assertEqual(result['LB_Proven'], 1)
        self.assertEqual(result['Labeling'], labels)

    def test_rejects_incorrect_certificate_and_contradictory_bound(self):
        with self.assertRaises(ValueError):
            runner.verify(self.graph, {1: 1, 2: 1, 3: 2, 4: 3})
        with self.assertRaises(ValueError):
            runner.finish_result(self.graph, self.initial, None, 4, False, True, '', 0, 0)

    def test_optimal_only_when_bound_or_engine_proves_it(self):
        result = runner.finish_result(self.graph, self.initial,
                                      {i: i for i in range(1, 5)}, 1,
                                      False, True, 'time limit', 0, 0)
        self.assertEqual(result['Status'], 'OPTIMAL')
        self.assertEqual(result['Gap_Absolute'], 0)

    def test_disconnected_lower_bound_is_valid(self):
        graph = GraphData(10, [(1, 2), (1, 3), (1, 4), (1, 5)])
        low, high, labels = runner.initial_bounds(graph)
        self.assertEqual(low, 2)
        self.assertLessEqual(low, high)
        self.assertEqual(high, runner.verify(graph, labels))

    @unittest.skipUnless(importlib.util.find_spec('cplex') and importlib.util.find_spec('docplex'),
                         'CPLEX and DOcplex are optional')
    def test_real_cplex_mip_solves_known_path(self):
        result = runner.native_solve(self.graph, 'cplex-mip', 10, 1, self.initial)
        self.assertEqual(result['Status'], 'OPTIMAL')
        self.assertEqual(result['Bandwidth'], 1)
        self.assertEqual(runner.verify(self.graph, result['Labeling']), 1)

    def test_watchdog_preserves_rcm_certificate(self):
        graph = GraphData.from_mtx(runner.ROOT/'data/pores_1.mtx')
        result = runner.solve_job(graph, 'cplex-mip', .001, 1)
        self.assertEqual(result['Status'], 'TIMEOUT')
        self.assertEqual(result['Solution_Source'], 'RCM')
        self.assertEqual(runner.verify(graph, result['Labeling']), result['Bandwidth'])

    @unittest.skipUnless(importlib.util.find_spec('docplex'), 'DOcplex is optional')
    def test_real_cp_timeout_is_not_reported_as_plain_feasible(self):
        graph = GraphData.from_mtx(runner.ROOT/'data/pores_1.mtx')
        result = runner.native_solve(graph, 'cplex-cp', 2, 1, runner.initial_bounds(graph))
        self.assertIn(result['Status'], ('OPTIMAL', 'TIMEOUT'))
        self.assertEqual(runner.verify(graph, result['Labeling']), result['Bandwidth'])


class ResumeTests(unittest.TestCase):
    def test_resume_and_retry_interrupted_or_error_but_not_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(instances=['pores_1'], instances_file=None,
                solvers=['cplex-mip'], timeout=600., threads=1,
                checkpoint=str(Path(directory)/'jobs.sqlite3'),
                output=str(Path(directory)/'jobs.csv'), stop_file=None,
                retry_errors=False, max_jobs=None, session_hours=None)
            result = {'Status': 'TIMEOUT', 'Bandwidth': 9}
            with patch.object(runner, 'solve_job', side_effect=InterruptedError()), \
                 patch.object(runner.importlib.util, 'find_spec', return_value=True), \
                 redirect_stdout(io.StringIO()):
                runner.run(args)
            with patch.object(runner, 'solve_job', return_value=result) as solve, \
                 patch.object(runner.importlib.util, 'find_spec', return_value=True), \
                 redirect_stdout(io.StringIO()):
                runner.run(args)
                self.assertEqual(solve.call_count, 1)
                runner.run(args)
                self.assertEqual(solve.call_count, 1)
            with closing(sqlite3.connect(args.checkpoint)) as con:
                self.assertEqual([r[0] for r in con.execute('SELECT status FROM attempts ORDER BY id')],
                                 ['INTERRUPTED', 'TIMEOUT'])
                con.execute("UPDATE attempts SET status='ERROR' WHERE id=2")
                con.commit()
            with patch.object(runner, 'solve_job', return_value=result) as solve, \
                 patch.object(runner.importlib.util, 'find_spec', return_value=True), \
                 redirect_stdout(io.StringIO()):
                runner.run(args)
                solve.assert_not_called()
                args.retry_errors = True
                runner.run(args)
                solve.assert_called_once()


if __name__ == '__main__':
    unittest.main()

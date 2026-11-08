"""Real CP-SAT certificate and timeout checks, plus resume/retry integration."""
import argparse
from contextlib import closing, redirect_stdout
import io
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

import run_cpsat as runner
from src.graph import GraphData


class CPSATTests(unittest.TestCase):
    def test_known_path_optimum_and_certificate(self):
        graph = GraphData(4, [(1, 2), (2, 3), (3, 4)])
        initial = (1, 3, {1: 1, 2: 4, 3: 2, 4: 3})
        result = runner.native_solve(graph, initial, time.monotonic()+10, 1)
        self.assertEqual(result['Status'], 'OPTIMAL')
        self.assertEqual(result['Bandwidth'], 1)
        self.assertEqual(result['LB_Proven'], 1)
        self.assertEqual(runner.common.verify(graph, result['Labeling']), 1)

    def test_native_timeout_keeps_feasible_solution(self):
        graph = GraphData.from_mtx(runner.common.ROOT/'data/pores_1.mtx')
        initial = runner.common.initial_bounds(graph)
        result = runner.native_solve(graph, initial, time.monotonic()+.1, 1)
        self.assertIn(result['Status'], ('TIMEOUT', 'OPTIMAL'))
        self.assertLessEqual(result['LB_Proven'], result['Bandwidth'])
        self.assertEqual(runner.common.verify(graph, result['Labeling']), result['Bandwidth'])

    def test_watchdog_retains_verified_fallback(self):
        graph = GraphData.from_mtx(runner.common.ROOT/'data/pores_1.mtx')
        result = runner.solve_job(graph, .001, 1)
        self.assertEqual(result['Status'], 'TIMEOUT')
        self.assertEqual(result['Solution_Source'], 'RCM')
        self.assertEqual(runner.common.verify(graph, result['Labeling']), result['Bandwidth'])

    def test_resume_retries_interrupted_and_errors_only(self):
        with tempfile.TemporaryDirectory() as directory:
            args = argparse.Namespace(instances=['pores_1'], instances_file=None,
                timeout=600., threads=1, checkpoint=str(Path(directory)/'jobs.sqlite3'),
                output=str(Path(directory)/'jobs.csv'), stop_file=None, retry_errors=False,
                max_jobs=None, session_hours=None)
            with patch.object(runner, 'solve_job', side_effect=InterruptedError()), redirect_stdout(io.StringIO()):
                runner.run(args)
            with patch.object(runner, 'solve_job', return_value={'Status': 'TIMEOUT'}) as solve, redirect_stdout(io.StringIO()):
                runner.run(args)
                runner.run(args)
                solve.assert_called_once()
            with closing(sqlite3.connect(args.checkpoint)) as con:
                self.assertEqual([r[0] for r in con.execute('SELECT status FROM attempts ORDER BY id')],
                                 ['INTERRUPTED', 'TIMEOUT'])
                con.execute("UPDATE attempts SET status='ERROR' WHERE id=2")
                con.commit()
            with patch.object(runner, 'solve_job', return_value={'Status': 'TIMEOUT'}) as solve, redirect_stdout(io.StringIO()):
                runner.run(args)
                solve.assert_not_called()
                args.retry_errors = True
                runner.run(args)
                solve.assert_called_once()


if __name__ == '__main__':
    unittest.main()

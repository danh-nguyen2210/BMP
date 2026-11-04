"""Checkpoint/runner tests; no optional SAT or scientific packages needed."""

from contextlib import closing, redirect_stdout
import csv
import io
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import run_benchmarks as runner
from src.benchmark_store import BenchmarkStore


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "checkpoint.sqlite3"

    def test_hard_exit_preserves_finished_and_recovers_running_attempt(self):
        script = """
import os, sys
from src.benchmark_store import BenchmarkStore
store = BenchmarkStore(sys.argv[1])
done = store.start('done', {'Instance': 'sample'})
store.finish(done, 'TIMEOUT', {'Bandwidth': 9})
store.start('unfinished', {'Instance': 'sample'})
os._exit(7)
"""
        process = subprocess.run([sys.executable, "-c", script, str(self.db)], cwd=runner.ROOT)
        self.assertEqual(process.returncode, 7)
        with BenchmarkStore(self.db) as store:
            self.assertFalse(store.should_run("done"))
            self.assertTrue(store.should_run("unfinished"))
            status = store.connection.execute("SELECT status FROM attempts WHERE job_id='unfinished'").fetchone()[0]
            self.assertEqual(status, "INTERRUPTED")
            attempt = store.start("unfinished", {"Instance": "sample"})
            store.finish(attempt, "OPTIMAL", {"Bandwidth": 2, "Labeling": {1: 1}})
            output = self.db.with_suffix(".csv")
            store.export_csv(output)
            with output.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["Status"] for row in rows], ["TIMEOUT", "INTERRUPTED", "OPTIMAL"])
            self.assertNotIn("Labeling", rows[-1])
            self.assertIn('"Labeling"', store.connection.execute("SELECT result FROM attempts WHERE id=?", (attempt,)).fetchone()[0])

    def test_exclusive_lock_prevents_duplicate_runners(self):
        with BenchmarkStore(self.db):
            with self.assertRaises(RuntimeError):
                BenchmarkStore(self.db)
        with BenchmarkStore(self.db):
            pass

    def test_retry_only_errors_not_timeout_or_limit(self):
        with BenchmarkStore(self.db) as store:
            for status in ("OPTIMAL", "TIMEOUT", "LIMIT", "ERROR", "DOWNLOAD_ERROR"):
                attempt = store.start(status, {})
                store.finish(attempt, status, {})
                self.assertFalse(store.should_run(status))
                self.assertEqual(store.should_run(status, retry_errors=True), status in ("ERROR", "DOWNLOAD_ERROR"))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.matrix = self.folder / "small.mtx"
        self.matrix.write_text("test input", encoding="utf-8")
        self.db = self.folder / "run.sqlite3"
        self.output = self.folder / "run.csv"
        self.calls = []
        self.behavior = None
        self.graph = SimpleNamespace(n=4, m=3)
        owner = self

        class Graph:
            @staticmethod
            def from_mtx(*args, **kwargs):
                return owner.graph

        def make_solver(key):
            class Solver:
                def __init__(self, graph, amo_method, timeout):
                    self.amo = amo_method

                def solve(self, **kwargs):
                    owner.calls.append((key, self.amo))
                    # Previous jobs must already be durable before starting this one.
                    with owner.output.open(encoding="utf-8") as f:
                        owner.previous_rows = list(csv.DictReader(f))
                    return owner.behavior() if owner.behavior else owner.result()
            return Solver

        mapping = {key: make_solver(key) for key in runner.SOLVER_KEYS}
        self.output.write_text("Attempt,Job_ID,Status\n", encoding="utf-8")
        self.suite = [{"name": "small", "table": 6, "file": str(self.matrix),
                       "paper_n": 4, "paper_lb": 1, "paper_best": 1}]
        for target, value in (
            ("BENCHMARK_SUITE", self.suite),
            ("_load_runtime", lambda: (Graph, mapping)),
            ("_code_hash", lambda: "code-version-1"),
            ("_environment", lambda: {"python": "test"}),
        ):
            patcher = patch.object(runner, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    @staticmethod
    def result(status="OPTIMAL"):
        return SimpleNamespace(status=status, bandwidth=1, iterations=2,
                               clauses_count=12, vars_count=10,
                               labeling={1: 1, 2: 2, 3: 3, 4: 4})

    def run_benchmark(self, **kwargs):
        with redirect_stdout(io.StringIO()):
            return runner.run_benchmark(checkpoint=self.db, output_csv=self.output, **kwargs)

    def records(self):
        with closing(sqlite3.connect(self.db)) as connection:
            return connection.execute("SELECT status, metadata, result FROM attempts ORDER BY id").fetchall()

    def test_resume_after_one_solver_and_complete_without_duplicates(self):
        self.run_benchmark(max_jobs=1)
        self.assertEqual(len(self.calls), 1)
        counters = self.run_benchmark()
        self.assertEqual(counters, {"completed": 3, "skipped": 1})
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(len(self.previous_rows), 3)
        self.assertEqual(self.run_benchmark(), {"completed": 0, "skipped": 4})
        self.assertEqual(len(self.records()), 4)

    def test_timeout_is_not_retried(self):
        self.behavior = lambda: self.result("TIMEOUT")
        self.run_benchmark()
        self.run_benchmark(retry_errors=True)
        self.assertEqual(len(self.calls), 4)

    def test_interrupted_job_is_retried_without_losing_previous_attempt(self):
        def interrupt():
            raise KeyboardInterrupt()
        self.behavior = interrupt
        self.run_benchmark()
        self.assertEqual(self.records()[0][0], "INTERRUPTED")
        self.behavior = None
        self.run_benchmark()
        self.assertEqual(len(self.calls), 5)
        self.assertEqual([r[0] for r in self.records()], ["INTERRUPTED"] + ["OPTIMAL"] * 4)

    def test_config_data_code_and_environment_changes_create_new_jobs(self):
        self.run_benchmark(solver_keys=["order-inc"])
        self.run_benchmark(solver_keys=["order-inc"], timeout=300)
        self.run_benchmark(solver_keys=["order-inc"], amo="product")
        self.run_benchmark(solver_keys=["order-inc"], strategy="binary")
        self.matrix.write_text("changed input")
        self.run_benchmark(solver_keys=["order-inc"])
        with patch.object(runner, "_code_hash", return_value="code-version-2"):
            self.run_benchmark(solver_keys=["order-inc"])
        with patch.object(runner, "_environment", return_value={"python": "changed"}):
            self.run_benchmark(solver_keys=["order-inc"])
        self.assertEqual(len(self.calls), 7)

    def test_ctrl_c_waits_for_current_result_then_resumes(self):
        def stop_during_job():
            signal.getsignal(signal.SIGINT)(signal.SIGINT, None)
            return self.result()
        self.behavior = stop_during_job
        self.run_benchmark()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.records()[0][0], "OPTIMAL")
        self.behavior = None
        self.run_benchmark()
        self.assertEqual(len(self.calls), 4)

    def test_stop_file_prevents_new_jobs(self):
        stop = Path(str(self.db) + ".stop")
        def stop_during_job():
            stop.touch()
            return self.result()
        self.behavior = stop_during_job
        self.run_benchmark()
        self.run_benchmark()
        self.assertEqual(len(self.calls), 1)
        stop.unlink()
        self.behavior = None
        self.run_benchmark()
        self.assertEqual(len(self.calls), 4)

    def test_session_does_not_start_job_without_timeout_budget(self):
        self.run_benchmark(session_hours=0.001, timeout=600)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.records(), [])

    def test_limit_includes_400_without_loading_or_downloading(self):
        self.suite[0]["paper_n"] = 400
        self.matrix.unlink()
        with patch.object(runner, "_load_runtime", side_effect=AssertionError), patch.object(
            runner, "download_hb_matrix", side_effect=AssertionError
        ):
            self.run_benchmark()
        self.assertEqual([r[0] for r in self.records()], ["LIMIT"] * 4)
        self.assertEqual(self.calls, [])

    def test_error_retry_is_explicit_and_preserves_attempt_history(self):
        def fail():
            raise RuntimeError("backend failed")
        self.behavior = fail
        self.run_benchmark()
        self.behavior = None
        self.run_benchmark()
        self.assertEqual(len(self.calls), 4)
        self.run_benchmark(retry_errors=True)
        self.assertEqual([r[0] for r in self.records()], ["ERROR"] * 4 + ["OPTIMAL"] * 4)

    def test_csv_failure_does_not_lose_checkpoint(self):
        with patch("src.benchmark_store.os.replace", side_effect=PermissionError("Excel lock")):
            self.run_benchmark(max_jobs=1)
        self.assertEqual(self.records()[0][0], "OPTIMAL")
        self.run_benchmark()
        self.assertEqual(len(self.calls), 4)
        with self.output.open(encoding="utf-8") as stream:
            self.assertEqual(len(list(csv.DictReader(stream))), 4)

    def test_old_csv_is_never_overwritten(self):
        old = "Instance,n,m\npores_1,30,103\n"
        self.output.write_text(old)
        with self.assertRaises(ValueError):
            self.run_benchmark()
        self.assertEqual(self.output.read_text(), old)

    def test_unknown_instance_rejected_before_running(self):
        with self.assertRaises(ValueError):
            self.run_benchmark(instances=["typo"])
        self.assertEqual(self.calls, [])

    def test_all_amo_runs_twenty_unique_jobs(self):
        self.run_benchmark(amo="all")
        self.assertEqual(len(set(self.calls)), 20)
        self.run_benchmark(amo="all")
        self.assertEqual(len(self.calls), 20)


if __name__ == "__main__":
    unittest.main()

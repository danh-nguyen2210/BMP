import subprocess
import sys
import textwrap
import unittest
from pathlib import Path


@unittest.skipUnless(sys.platform == "win32", "Windows job objects")
class WindowsMemoryTests(unittest.TestCase):
    def test_child_allocation_is_denied_and_parent_can_continue(self):
        # Assignment is process-lifetime. Keep the test runner outside the job.
        probe = textwrap.dedent("""
            import subprocess, sys, time
            from src.windows_memory_job import WindowsMemoryJob
            job = WindowsMemoryJob(0.25)
            child = "try:\\n bytearray(300 * 2**20)\\nexcept MemoryError:\\n raise SystemExit(42)"
            denied = subprocess.run([sys.executable, '-c', child])
            assert denied.returncode == 42, denied.returncode
            for _ in range(100):
                if job.limit_hit():
                    break
                time.sleep(.01)
            else:
                raise AssertionError("Missing memory limit notification")
            subprocess.run([sys.executable, '-c', 'bytearray(1024)'], check=True)
            assert not job.limit_hit()
            job.close()
        """)
        subprocess.run([sys.executable, "-c", probe], check=True, timeout=30,
                       cwd=Path(__file__).resolve().parents[1])

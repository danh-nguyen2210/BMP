"""Durable, per-solver benchmark checkpoints (standard library only)."""

import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from datetime import datetime, timezone


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


class BenchmarkStore:
    """SQLite is authoritative; CSV is a replaceable export, never a checkpoint.

    An exclusive connection lock prevents two runners using the same database.
    Every start/finish is committed with synchronous=FULL. A crashed RUNNING
    attempt is retained as INTERRUPTED; the next session starts a new attempt.
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=0)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA synchronous=FULL")
            self.connection.execute("PRAGMA locking_mode=EXCLUSIVE")
            self.connection.execute("BEGIN EXCLUSIVE")
            self.connection.execute("""
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    result TEXT
                )
            """)
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS attempts_job ON attempts(job_id, id)"
            )
            self.connection.execute("""
                UPDATE attempts SET status='INTERRUPTED', finished_at=?
                WHERE status='RUNNING'
            """, (timestamp(),))
            self.connection.commit()
        except sqlite3.OperationalError as exc:
            self.connection.close()
            raise RuntimeError(
                f"Không mở được checkpoint {path}. Có thể một runner khác đang sử dụng file này: {exc}"
            ) from exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def should_run(self, job_id, retry_errors=False):
        row = self.connection.execute(
            "SELECT status FROM attempts WHERE job_id=? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
        if row is None or row["status"] == "INTERRUPTED":
            return True
        return retry_errors and row["status"] in ("ERROR", "DOWNLOAD_ERROR")

    def start(self, job_id, metadata):
        with self.connection:
            cursor = self.connection.execute(
                "INSERT INTO attempts(job_id, metadata, status, started_at) VALUES (?, ?, 'RUNNING', ?)",
                (job_id, json.dumps(metadata, ensure_ascii=False), timestamp()),
            )
        return cursor.lastrowid

    def finish(self, attempt_id, status, result):
        with self.connection:
            self.connection.execute(
                "UPDATE attempts SET status=?, finished_at=?, result=? WHERE id=?",
                (status, timestamp(), json.dumps(result, ensure_ascii=False), attempt_id),
            )

    def export_csv(self, path):
        """Export all attempts so restarts/errors are not erased from the record."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for record in self.connection.execute("SELECT * FROM attempts ORDER BY id"):
            row = json.loads(record["metadata"])
            result = json.loads(record["result"] or "{}")
            # Labeling is kept in SQLite, not spread across a CSV cell.
            result.pop("Labeling", None)
            row.update(result)
            row.update(Attempt=record["id"], Job_ID=record["job_id"],
                       Status=record["status"], Started_UTC=record["started_at"],
                       Finished_UTC=record["finished_at"] or "")
            rows.append(row)
        if not rows:
            return
        fields = list(dict.fromkeys(key for row in rows for key in row))
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", newline="", encoding="utf-8", dir=path.parent,
                prefix=path.name + ".", suffix=".tmp", delete=False,
            ) as stream:
                temporary = stream.name
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary is not None and os.path.exists(temporary):
                os.unlink(temporary)

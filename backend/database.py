"""
Módulo de banco de dados SQLite para armazenar execuções e falhas de testes.
"""
import sqlite3
import json
from contextlib import contextmanager

DB_PATH = "bugmanager.db"


def init_db():
    """Cria as tabelas do banco de dados caso não existam."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                filename TEXT,
                total_failures INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_db_id INTEGER,
                test_name TEXT,
                suite TEXT,
                error_message TEXT,
                stack_trace TEXT,
                duration_ms INTEGER,
                timestamp TEXT,
                environment TEXT,
                cluster_id INTEGER,
                classification TEXT,
                ai_summary TEXT,
                FOREIGN KEY (run_db_id) REFERENCES runs (id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_db_id INTEGER,
                cluster_label INTEGER,
                representative_error TEXT,
                failure_count INTEGER,
                classification TEXT,
                ai_summary TEXT,
                FOREIGN KEY (run_db_id) REFERENCES runs (id)
            )
        """)

        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def save_run(run_id: str, filename: str, total_failures: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO runs (run_id, filename, total_failures) VALUES (?, ?, ?)",
            (run_id, filename, total_failures)
        )
        conn.commit()
        return cursor.lastrowid


def save_failure(run_db_id: int, failure: dict, cluster_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO failures (
                run_db_id, test_name, suite, error_message, stack_trace,
                duration_ms, timestamp, environment, cluster_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_db_id,
            failure.get("test_name"),
            failure.get("suite"),
            failure.get("error_message"),
            failure.get("stack_trace"),
            failure.get("duration_ms"),
            failure.get("timestamp"),
            failure.get("environment"),
            cluster_id
        ))
        conn.commit()


def save_cluster(run_db_id: int, cluster_label: int, representative_error: str,
                  failure_count: int, classification: str, ai_summary: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO clusters (
                run_db_id, cluster_label, representative_error,
                failure_count, classification, ai_summary
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (run_db_id, cluster_label, representative_error, failure_count, classification, ai_summary))
        conn.commit()
        return cursor.lastrowid


def get_run_history():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT 20")
        return [dict(row) for row in cursor.fetchall()]


def get_run_details(run_db_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM runs WHERE id = ?", (run_db_id,))
        run = cursor.fetchone()

        cursor.execute("SELECT * FROM clusters WHERE run_db_id = ?", (run_db_id,))
        clusters = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT * FROM failures WHERE run_db_id = ?", (run_db_id,))
        failures = [dict(row) for row in cursor.fetchall()]

        return {
            "run": dict(run) if run else None,
            "clusters": clusters,
            "failures": failures
        }

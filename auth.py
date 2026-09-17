import sqlite3
from pathlib import Path

import bcrypt

DB_PATH = Path(__file__).resolve().parent / "auth.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash BLOB NOT NULL
        )
        """
    )
    return conn


def create_user(username: str, password: str) -> None:
    """Hash and store/update a user's password. Never stores plaintext."""
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash) VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET password_hash = excluded.password_hash
            """,
            (username, password_hash),
        )


def verify_user(username: str, password: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if row is None:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), row[0])

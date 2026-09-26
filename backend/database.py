"""Small SQLite persistence layer for application users."""

import sqlite3
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "weather_auth.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def create_user(email: str, password_hash: str) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        user = connection.execute(
            "SELECT id, email, created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return dict(user)


def get_user_by_email(email: str) -> dict | None:
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    return dict(user) if user else None

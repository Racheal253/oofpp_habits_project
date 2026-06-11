"""Persistence layer for the habit tracker (SQLite).

This is the *only* module that knows SQL. It maps :class:`~habit_tracker.habit.Habit`
objects to and from two relational tables and keeps that translation in one
place, so the domain and analytics layers never see a database.

Schema
------
``habits``      : one row per habit (name is the primary key).
``completions`` : one row per check-off, linked to its habit by a foreign key.
                  This 1-to-many shape is the natural relational model for the
                  event log and is why a database is a better fit than flat JSON.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .habit import Habit, Periodicity

DEFAULT_DB_PATH = "habits.db"
_TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S.%f"


class HabitDB:
    """A thin object-relational wrapper around a SQLite database.

    :param db_path: Path to the SQLite file. Use ``":memory:"`` for tests.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        # check_same_thread=False keeps things simple for a single-user CLI tool.
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self.initialise_db()

    # ------------------------------------------------------------------ #
    # Schema
    # ------------------------------------------------------------------ #
    def initialise_db(self) -> None:
        """Create the tables if they do not already exist (idempotent)."""
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS habits (
                name        TEXT PRIMARY KEY,
                periodicity TEXT NOT NULL,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS completions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_name  TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                FOREIGN KEY (habit_name) REFERENCES habits(name) ON DELETE CASCADE
            );
            """
        )
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Write operations
    # ------------------------------------------------------------------ #
    def save_habit(self, habit: Habit) -> None:
        """Insert a new habit and all of its completions.

        Raises :class:`ValueError` if a habit with the same name already exists.
        """
        try:
            self.conn.execute(
                "INSERT INTO habits (name, periodicity, created_at) VALUES (?, ?, ?);",
                (habit.name, habit.periodicity.name, habit.created_at.strftime(_TIMESTAMP_FMT)),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"A habit named {habit.name!r} already exists.") from exc

        self.conn.executemany(
            "INSERT INTO completions (habit_name, completed_at) VALUES (?, ?);",
            [(habit.name, ts.strftime(_TIMESTAMP_FMT)) for ts in habit.completions],
        )
        self.conn.commit()

    def add_completion(self, habit_name: str, when: datetime | None = None) -> None:
        """Record a single check-off for an existing habit."""
        if not self.habit_exists(habit_name):
            raise ValueError(f"No habit named {habit_name!r}.")
        when = when or datetime.now()
        self.conn.execute(
            "INSERT INTO completions (habit_name, completed_at) VALUES (?, ?);",
            (habit_name, when.strftime(_TIMESTAMP_FMT)),
        )
        self.conn.commit()

    def delete_habit(self, habit_name: str) -> None:
        """Delete a habit and (via cascade) all of its completions."""
        if not self.habit_exists(habit_name):
            raise ValueError(f"No habit named {habit_name!r}.")
        self.conn.execute("DELETE FROM habits WHERE name = ?;", (habit_name,))
        self.conn.commit()

    # ------------------------------------------------------------------ #
    # Read operations
    # ------------------------------------------------------------------ #
    def habit_exists(self, habit_name: str) -> bool:
        """Return ``True`` if a habit with this name is stored."""
        cur = self.conn.execute("SELECT 1 FROM habits WHERE name = ?;", (habit_name,))
        return cur.fetchone() is not None

    def load_habit(self, habit_name: str) -> Habit:
        """Reconstruct a single :class:`Habit` object from the database."""
        row = self.conn.execute(
            "SELECT name, periodicity, created_at FROM habits WHERE name = ?;",
            (habit_name,),
        ).fetchone()
        if row is None:
            raise ValueError(f"No habit named {habit_name!r}.")
        return self._row_to_habit(row)

    def load_all_habits(self) -> list[Habit]:
        """Reconstruct every stored habit as a list of :class:`Habit` objects."""
        rows = self.conn.execute(
            "SELECT name, periodicity, created_at FROM habits ORDER BY created_at;"
        ).fetchall()
        return [self._row_to_habit(row) for row in rows]

    # ------------------------------------------------------------------ #
    # Internal helpers (object <-> relational mapping)
    # ------------------------------------------------------------------ #
    def _row_to_habit(self, row: tuple[str, str, str]) -> Habit:
        name, periodicity_name, created_at = row
        completions = [
            datetime.strptime(ts, _TIMESTAMP_FMT)
            for (ts,) in self.conn.execute(
                "SELECT completed_at FROM completions WHERE habit_name = ? ORDER BY completed_at;",
                (name,),
            ).fetchall()
        ]
        return Habit(
            name=name,
            periodicity=Periodicity[periodicity_name],
            created_at=datetime.strptime(created_at, _TIMESTAMP_FMT),
            completions=completions,
        )

    def close(self) -> None:
        """Close the underlying database connection."""
        self.conn.close()

"""Domain model for the habit tracker.

This module contains the object-oriented core of the application: the
:class:`Habit` class and the :class:`Periodicity` enum. A ``Habit`` encapsulates
everything about a single tracked habit -- its name, how often it must be
completed, when it was created, and the full event log of completions.

All "what counts as completed / broken / a streak" rules live here, in one
place, so the rest of the application (CLI, analytics, persistence) never has to
re-implement them.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum


class Periodicity(Enum):
    """How often a habit must be completed.

    The value of each member is the length of one period in days. Using an enum
    (rather than a free-text string like ``"daily"``) makes the period
    type-safe: a habit can never be created with an invalid periodicity.
    """

    DAILY = 1
    WEEKLY = 7

    @property
    def length(self) -> timedelta:
        """Return the length of one period as a :class:`~datetime.timedelta`."""
        return timedelta(days=self.value)

    def __str__(self) -> str:  # pragma: no cover - cosmetic only
        return self.name.lower()


class Habit:
    """A single habit and its completion history.

    A habit is a clearly defined task that must be completed (``checked off``)
    at least once within each recurring period. The :attr:`completions` list is
    the *event log*: every time the user completes the task, a timestamp is
    appended.

    :param name: The unique, human-readable name of the habit (e.g. ``"Brush teeth"``).
    :param periodicity: A :class:`Periodicity` value (daily or weekly).
    :param created_at: When the habit was created. Defaults to "now".
    :param completions: An optional pre-existing list of completion timestamps
        (used when reconstructing a habit loaded from the database).
    """

    def __init__(
        self,
        name: str,
        periodicity: Periodicity,
        created_at: datetime | None = None,
        completions: list[datetime] | None = None,
    ) -> None:
        if not name or not name.strip():
            raise ValueError("A habit must have a non-empty name.")
        if not isinstance(periodicity, Periodicity):
            raise TypeError("periodicity must be a Periodicity enum member.")

        self.name: str = name.strip()
        self.periodicity: Periodicity = periodicity
        self.created_at: datetime = created_at or datetime.now()
        # The event log of completion timestamps, always kept sorted ascending.
        self.completions: list[datetime] = sorted(completions or [])

    # ------------------------------------------------------------------ #
    # Behaviour
    # ------------------------------------------------------------------ #
    def complete(self, when: datetime | None = None) -> None:
        """Check the habit off (record a completion).

        :param when: The moment of completion. Defaults to "now".
        """
        when = when or datetime.now()
        self.completions.append(when)
        self.completions.sort()

    def period_index(self, moment: datetime) -> int:
        """Return the index of the period that ``moment`` falls into.

        Period 0 is the period that begins at :attr:`created_at`. The index is
        an integer count of how many whole periods have elapsed since creation.
        This is the key helper that lets us group raw timestamps into periods
        without caring about calendar boundaries.
        """
        elapsed = moment - self.created_at
        return int(elapsed.total_seconds() // self.periodicity.length.total_seconds())

    def completed_periods(self) -> set[int]:
        """Return the set of distinct period indices that contain a completion.

        Multiple check-offs in the same period count once, which matches the
        rule that a habit need only be completed *at least once* per period.
        """
        return {self.period_index(ts) for ts in self.completions}

    def current_period_index(self, now: datetime | None = None) -> int:
        """Return the index of the period we are in right now."""
        return self.period_index(now or datetime.now())

    def is_broken(self, now: datetime | None = None) -> bool:
        """Return ``True`` if the habit has been broken.

        A habit is broken if any period *before* the current one was missed
        (had no completion). The current period is not yet counted as broken,
        because the user may still complete it before it ends.
        """
        now = now or datetime.now()
        current = self.current_period_index(now)
        if current <= 0:
            # Still inside the very first period -- cannot be broken yet.
            return False
        completed = self.completed_periods()
        # Every period from 0 up to (current - 1) must contain a completion.
        return any(period not in completed for period in range(current))

    def is_active_today(self, now: datetime | None = None) -> bool:
        """Return ``True`` if the habit has already been completed this period."""
        return self.current_period_index(now) in self.completed_periods()

    # ------------------------------------------------------------------ #
    # Dunder helpers
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        return (
            f"Habit(name={self.name!r}, periodicity={self.periodicity.name}, "
            f"completions={len(self.completions)})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Habit):
            return NotImplemented
        return self.name == other.name and self.periodicity == other.periodicity

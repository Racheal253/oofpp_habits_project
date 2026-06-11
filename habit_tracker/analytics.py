"""Analytics for the habit tracker, written in the functional paradigm.

Every function in this module is **pure**: it takes data in, returns a new value,
and never mutates its arguments, touches the database, or relies on hidden state.
The functions are built from ``map``, ``filter``, ``functools.reduce`` and
comprehensions rather than imperative loops that mutate accumulators.

This satisfies the assignment requirement that the analytics module use
functional programming, and -- because the functions are pure -- makes them
trivial to unit-test against the predefined fixture data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import reduce
from typing import Iterable

from .habit import Habit, Periodicity


def list_all_habits(habits: Iterable[Habit]) -> list[str]:
    """Return the names of all currently tracked habits."""
    return list(map(lambda h: h.name, habits))


def habits_by_periodicity(habits: Iterable[Habit], periodicity: Periodicity) -> list[str]:
    """Return the names of all habits sharing the given periodicity."""
    return list(
        map(
            lambda h: h.name,
            filter(lambda h: h.periodicity == periodicity, habits),
        )
    )


def longest_streak_for_habit(habit: Habit) -> int:
    """Return the longest run streak (in periods) for a single habit.

    A streak is the number of consecutive completed periods. We sort the set of
    completed period indices and fold over them with ``reduce``, growing the run
    when indices are consecutive and resetting it otherwise. The fold carries a
    ``(best, current, previous)`` tuple, so no variable is ever mutated in place.
    """
    periods = sorted(habit.completed_periods())
    if not periods:
        return 0

    def step(acc: tuple[int, int, int | None], period: int) -> tuple[int, int, int | None]:
        best, current, previous = acc
        current = current + 1 if previous is not None and period == previous + 1 else 1
        return (max(best, current), current, period)

    best, _, _ = reduce(step, periods, (0, 0, None))
    return best


def longest_streak_all(habits: Iterable[Habit]) -> int:
    """Return the longest run streak across *all* defined habits."""
    streaks = list(map(longest_streak_for_habit, habits))
    return reduce(max, streaks, 0)


def habit_with_longest_streak(habits: Iterable[Habit]) -> tuple[str, int] | None:
    """Return the ``(name, streak)`` of the habit with the longest streak.

    Returns ``None`` if there are no habits. Useful for the "what's my longest
    habit streak?" user question.
    """
    pairs = list(map(lambda h: (h.name, longest_streak_for_habit(h)), habits))
    if not pairs:
        return None
    return reduce(lambda a, b: a if a[1] >= b[1] else b, pairs)


def broken_habits(habits: Iterable[Habit], now: datetime | None = None) -> list[str]:
    """Return the names of all habits that are currently broken."""
    moment = now or datetime.now()
    return list(
        map(
            lambda h: h.name,
            filter(lambda h: h.is_broken(moment), habits),
        )
    )


def struggled_last_month(habits: Iterable[Habit], now: datetime | None = None) -> list[tuple[str, int]]:
    """Return habits ranked by how many periods were missed in the last ~30 days.

    Answers the example user question "with which habits did I struggle most
    last month?". For each habit we count the periods in the last 30 days that
    *should* have had a completion but did not, then return the habits that
    missed at least one, sorted from most-missed to least.
    """
    moment = now or datetime.now()
    window_start = moment - timedelta(days=30)

    def missed_in_window(habit: Habit) -> int:
        start_idx = max(0, habit.period_index(window_start))
        end_idx = habit.period_index(moment)
        completed = habit.completed_periods()
        # Count periods in the window (excluding the still-open current period)
        # that have no completion.
        missing = filter(
            lambda idx: idx not in completed,
            range(start_idx, end_idx),
        )
        return len(list(missing))

    scored = map(lambda h: (h.name, missed_in_window(h)), habits)
    struggled = filter(lambda pair: pair[1] > 0, scored)
    return sorted(struggled, key=lambda pair: pair[1], reverse=True)

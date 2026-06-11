"""Predefined habits with four weeks of example tracking data.

The assignment requires the solution to ship with five predefined habits (at
least one daily and one weekly) and, for each, four weeks of example tracking
data to act as a reusable test fixture.

The data is generated *relative to a reference date* (28 days before "now" by
default) so it is always recent and the streak / broken-habit logic produces
meaningful, demonstrable results. Deliberate gaps are built into some habits so
that the analytics (broken habits, "struggled last month") have something real
to report.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .habit import Habit, Periodicity

# Number of days of history the fixtures cover.
FIXTURE_DAYS = 28


def _daily(name: str, present_days: set[int], start: datetime) -> Habit:
    """Build a daily habit completed on the given day-offsets from ``start``."""
    habit = Habit(name, Periodicity.DAILY, created_at=start)
    for day in sorted(present_days):
        # Complete it mid-morning of that day so it lands cleanly in the period.
        habit.complete(start + timedelta(days=day, hours=9))
    return habit


def _weekly(name: str, present_weeks: set[int], start: datetime) -> Habit:
    """Build a weekly habit completed in the given week-offsets from ``start``."""
    habit = Habit(name, Periodicity.WEEKLY, created_at=start)
    for week in sorted(present_weeks):
        habit.complete(start + timedelta(weeks=week, days=2, hours=9))
    return habit


def predefined_habits(reference: datetime | None = None) -> list[Habit]:
    """Return the five predefined habits seeded with four weeks of data.

    :param reference: The "now" to anchor the data to. Defaults to the real now.
        Passing a fixed value makes the fixtures fully deterministic for tests.
    """
    now = reference or datetime.now()
    start = now - timedelta(days=FIXTURE_DAYS)
    full_4_weeks = set(range(FIXTURE_DAYS))  # days 0..27

    return [
        # 1. A perfect daily habit -- completed every single day (28-day streak).
        _daily("Brush teeth", full_4_weeks, start),

        # 2. A daily habit with a broken patch in the middle (missed days 10-13),
        #    then resumed -- longest streak is the 14-day run at the end.
        _daily("Drink water", full_4_weeks - {10, 11, 12, 13}, start),

        # 3. A daily habit the user struggled with recently (missed several of
        #    the most recent days) -- shows up in "struggled last month".
        _daily(
            "Morning workout",
            {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 19, 21, 24},
            start,
        ),

        # 4. A perfect weekly habit -- completed all four weeks (4-week streak).
        _weekly("Weekly review", {0, 1, 2, 3}, start),

        # 5. A weekly habit with one missed week (week 2) -- broken, max streak 2.
        _weekly("Call family", {0, 1, 3}, start),
    ]

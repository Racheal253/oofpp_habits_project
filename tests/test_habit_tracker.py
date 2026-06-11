"""Unit test suite for the habit tracker.

Run from the project root with either:

    pytest
    python -m pytest -v

The tests exercise the three critical areas the assignment calls out: the habit
tracking components (streaks, break detection), the functional analytics module,
and the persistence round-trip. A fixed reference date makes the predefined
fixtures fully deterministic, so every expected number below is exact.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from habit_tracker.analytics import (
    broken_habits,
    habit_with_longest_streak,
    habits_by_periodicity,
    list_all_habits,
    longest_streak_all,
    longest_streak_for_habit,
    struggled_last_month,
)
from habit_tracker.database import HabitDB
from habit_tracker.fixtures import predefined_habits
from habit_tracker.habit import Habit, Periodicity
from habit_tracker.visualisation import render_bar_chart

# A fixed "now" so the relative fixture data is deterministic.
REFERENCE = datetime(2024, 1, 29, 12, 0, 0)


@pytest.fixture
def habits():
    """The five predefined habits anchored to the fixed reference date."""
    return predefined_habits(reference=REFERENCE)


@pytest.fixture
def db():
    """An in-memory database, closed automatically after each test."""
    database = HabitDB(":memory:")
    yield database
    database.close()


# --------------------------------------------------------------------------- #
# Habit class
# --------------------------------------------------------------------------- #
class TestHabit:
    def test_create_valid_habit(self):
        h = Habit("Read", Periodicity.DAILY)
        assert h.name == "Read"
        assert h.periodicity is Periodicity.DAILY
        assert h.completions == []

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError):
            Habit("   ", Periodicity.DAILY)

    def test_invalid_periodicity_rejected(self):
        with pytest.raises(TypeError):
            Habit("Read", "daily")  # type: ignore[arg-type]

    def test_complete_appends_and_sorts(self):
        h = Habit("Read", Periodicity.DAILY, created_at=REFERENCE)
        h.complete(REFERENCE + timedelta(days=2))
        h.complete(REFERENCE + timedelta(days=1))
        assert h.completions == sorted(h.completions)
        assert len(h.completions) == 2

    def test_completed_periods_dedupes_same_period(self):
        h = Habit("Read", Periodicity.DAILY, created_at=REFERENCE)
        h.complete(REFERENCE + timedelta(hours=1))
        h.complete(REFERENCE + timedelta(hours=5))  # same day
        assert h.completed_periods() == {0}

    def test_is_broken_true_when_period_missed(self):
        h = Habit("Read", Periodicity.DAILY, created_at=REFERENCE)
        h.complete(REFERENCE)  # day 0 only
        now = REFERENCE + timedelta(days=3)
        assert h.is_broken(now) is True

    def test_is_broken_false_when_all_completed(self):
        h = Habit("Read", Periodicity.DAILY, created_at=REFERENCE)
        for d in range(3):
            h.complete(REFERENCE + timedelta(days=d, hours=9))
        now = REFERENCE + timedelta(days=3)
        assert h.is_broken(now) is False


# --------------------------------------------------------------------------- #
# Analytics (functional)
# --------------------------------------------------------------------------- #
class TestAnalytics:
    def test_list_all_habits(self, habits):
        names = list_all_habits(habits)
        assert names == [
            "Brush teeth",
            "Drink water",
            "Morning workout",
            "Weekly review",
            "Call family",
        ]

    def test_habits_by_periodicity(self, habits):
        daily = habits_by_periodicity(habits, Periodicity.DAILY)
        weekly = habits_by_periodicity(habits, Periodicity.WEEKLY)
        assert daily == ["Brush teeth", "Drink water", "Morning workout"]
        assert weekly == ["Weekly review", "Call family"]

    def test_longest_streak_perfect_daily(self, habits):
        brush = next(h for h in habits if h.name == "Brush teeth")
        # 28 consecutive days completed.
        assert longest_streak_for_habit(brush) == 28

    def test_longest_streak_with_gap(self, habits):
        water = next(h for h in habits if h.name == "Drink water")
        # Missed days 10-13; the run from day 14..27 is 14 days long.
        assert longest_streak_for_habit(water) == 14

    def test_longest_streak_weekly(self, habits):
        review = next(h for h in habits if h.name == "Weekly review")
        assert longest_streak_for_habit(review) == 4

    def test_longest_streak_all(self, habits):
        # Brush teeth's 28-day streak is the longest overall.
        assert longest_streak_all(habits) == 28

    def test_habit_with_longest_streak(self, habits):
        name, streak = habit_with_longest_streak(habits)
        assert name == "Brush teeth"
        assert streak == 28

    def test_broken_habits(self, habits):
        broken = broken_habits(habits, now=REFERENCE)
        # Drink water (gap), Morning workout (gaps) and Call family (missed
        # week) are broken; the two perfect habits are not.
        assert "Drink water" in broken
        assert "Morning workout" in broken
        assert "Call family" in broken
        assert "Brush teeth" not in broken
        assert "Weekly review" not in broken

    def test_struggled_last_month_ranks_by_misses(self, habits):
        struggled = struggled_last_month(habits, now=REFERENCE)
        names = [name for name, _ in struggled]
        # Morning workout has the most misses, so it should rank first.
        assert names[0] == "Morning workout"
        # Counts are positive and sorted descending.
        counts = [c for _, c in struggled]
        assert counts == sorted(counts, reverse=True)
        assert all(c > 0 for c in counts)

    def test_pure_functions_do_not_mutate(self, habits):
        before = [len(h.completions) for h in habits]
        longest_streak_all(habits)
        broken_habits(habits, now=REFERENCE)
        struggled_last_month(habits, now=REFERENCE)
        after = [len(h.completions) for h in habits]
        assert before == after


# --------------------------------------------------------------------------- #
# Database persistence
# --------------------------------------------------------------------------- #
class TestDatabase:
    def test_save_and_load_roundtrip(self, db):
        h = Habit("Read", Periodicity.DAILY, created_at=REFERENCE)
        h.complete(REFERENCE + timedelta(hours=1))
        db.save_habit(h)

        loaded = db.load_habit("Read")
        assert loaded.name == "Read"
        assert loaded.periodicity is Periodicity.DAILY
        assert len(loaded.completions) == 1

    def test_duplicate_habit_rejected(self, db):
        db.save_habit(Habit("Read", Periodicity.DAILY))
        with pytest.raises(ValueError):
            db.save_habit(Habit("Read", Periodicity.WEEKLY))

    def test_add_completion(self, db):
        db.save_habit(Habit("Read", Periodicity.DAILY))
        db.add_completion("Read", REFERENCE)
        assert len(db.load_habit("Read").completions) == 1

    def test_add_completion_unknown_habit(self, db):
        with pytest.raises(ValueError):
            db.add_completion("Nope")

    def test_delete_cascades_completions(self, db):
        h = Habit("Read", Periodicity.DAILY)
        h.complete()
        db.save_habit(h)
        db.delete_habit("Read")
        assert db.habit_exists("Read") is False
        # Completions are gone too (foreign-key cascade).
        remaining = db.conn.execute("SELECT COUNT(*) FROM completions;").fetchone()[0]
        assert remaining == 0

    def test_load_all_fixtures_roundtrip(self, db):
        for habit in predefined_habits(reference=REFERENCE):
            db.save_habit(habit)
        loaded = db.load_all_habits()
        assert len(loaded) == 5
        # Streaks survive the round-trip unchanged.
        brush = next(h for h in loaded if h.name == "Brush teeth")
        assert longest_streak_for_habit(brush) == 28


# --------------------------------------------------------------------------- #
# Visualisation (ASCII chart)
# --------------------------------------------------------------------------- #
class TestVisualisation:
    def test_empty_data_renders_no_data(self):
        out = render_bar_chart([], title="Streaks")
        assert "no data" in out
        assert "Streaks" in out

    def test_renders_labels_and_values(self):
        out = render_bar_chart([("A", 3), ("B", 6)], title="t", width=10)
        # Both labels and both numeric values must appear in the output.
        assert "A" in out and "B" in out
        assert "3" in out and "6" in out
        # Title is rendered too.
        assert "t" in out

    def test_largest_bar_is_widest(self):
        out = render_bar_chart([("Small", 1), ("Big", 10)], width=20)
        # The 'Big' line should contain more block characters than 'Small'.
        small_line = next(l for l in out.splitlines() if "Small" in l)
        big_line = next(l for l in out.splitlines() if "Big" in l)
        assert big_line.count("\u2588") > small_line.count("\u2588")

    def test_works_with_fixture_data(self, habits):
        data = [(h.name, longest_streak_for_habit(h)) for h in habits]
        out = render_bar_chart(data, title="Streaks", width=30)
        # All five fixture habits appear in the chart output.
        for name in ["Brush teeth", "Drink water", "Morning workout", "Weekly review", "Call family"]:
            assert name in out

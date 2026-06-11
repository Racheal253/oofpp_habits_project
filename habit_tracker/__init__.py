"""Habit Tracker -- a small, well-tested habit tracking backend.

Public API
----------
- :class:`~habit_tracker.habit.Habit` and
  :class:`~habit_tracker.habit.Periodicity` -- the object-oriented domain model.
- :class:`~habit_tracker.database.HabitDB` -- the SQLite persistence layer.
- :mod:`habit_tracker.analytics` -- pure, functional analytics functions.
- :func:`~habit_tracker.fixtures.predefined_habits` -- the example fixture data.
"""

from .habit import Habit, Periodicity
from .database import HabitDB
from .fixtures import predefined_habits

__all__ = ["Habit", "Periodicity", "HabitDB", "predefined_habits"]
__version__ = "1.0.0"

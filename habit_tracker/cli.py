"""Command-line interface for the habit tracker, built with Click.

This is the presentation layer. It wires the domain, persistence and analytics
layers together and exposes them through clean sub-commands:

    create   -- define a new habit
    delete   -- remove a habit
    checkoff -- complete a habit's task for the current period
    list     -- show tracked habits
    seed     -- load the 5 predefined habits + 4 weeks of example data
    analyse  -- run the functional analytics
    chart    -- render an ASCII bar chart of longest streaks

Run ``python -m habit_tracker.cli --help`` (or ``habit --help`` if installed)
to see everything.
"""

from __future__ import annotations

import click

from .analytics import (
    broken_habits,
    habit_with_longest_streak,
    habits_by_periodicity,
    list_all_habits,
    longest_streak_all,
    longest_streak_for_habit,
    struggled_last_month,
)
from .database import DEFAULT_DB_PATH, HabitDB
from .fixtures import predefined_habits
from .habit import Habit, Periodicity
from .visualisation import render_bar_chart


# --------------------------------------------------------------------------- #
# Group + shared context
# --------------------------------------------------------------------------- #
@click.group()
@click.option(
    "--db",
    "db_path",
    default=DEFAULT_DB_PATH,
    show_default=True,
    help="Path to the SQLite database file.",
)
@click.pass_context
def cli(ctx: click.Context, db_path: str) -> None:
    """A simple, functional habit tracker.

    Habit data is stored in a SQLite database and analysed with pure functions.
    """
    ctx.obj = HabitDB(db_path)


# --------------------------------------------------------------------------- #
# create / delete / checkoff
# --------------------------------------------------------------------------- #
@cli.command()
@click.argument("name")
@click.option(
    "--periodicity",
    "-p",
    type=click.Choice(["daily", "weekly"], case_sensitive=False),
    required=True,
    help="How often the habit must be completed.",
)
@click.pass_obj
def create(db: HabitDB, name: str, periodicity: str) -> None:
    """Create a new habit, e.g. `create "Drink water" -p daily`."""
    habit = Habit(name, Periodicity[periodicity.upper()])
    try:
        db.save_habit(habit)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Created {periodicity.lower()} habit: {name!r}.")


@cli.command()
@click.argument("name")
@click.confirmation_option(prompt="Delete this habit and all its history?")
@click.pass_obj
def delete(db: HabitDB, name: str) -> None:
    """Delete a habit and all of its tracked completions."""
    try:
        db.delete_habit(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Deleted habit: {name!r}.")


@cli.command()
@click.argument("name")
@click.pass_obj
def checkoff(db: HabitDB, name: str) -> None:
    """Check off (complete) a habit for the current period."""
    try:
        db.add_completion(name)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Checked off {name!r}. Nice work!")


# --------------------------------------------------------------------------- #
# list / seed
# --------------------------------------------------------------------------- #
@cli.command(name="list")
@click.option(
    "--periodicity",
    "-p",
    type=click.Choice(["daily", "weekly"], case_sensitive=False),
    help="Only show habits with this periodicity.",
)
@click.pass_obj
def list_habits(db: HabitDB, periodicity: str | None) -> None:
    """List tracked habits (optionally filtered by periodicity)."""
    habits = db.load_all_habits()
    if not habits:
        click.echo("No habits yet. Create one or run `seed`.")
        return

    if periodicity:
        names = habits_by_periodicity(habits, Periodicity[periodicity.upper()])
        habits = [h for h in habits if h.name in names]

    for habit in habits:
        streak = longest_streak_for_habit(habit)
        flag = "broken" if habit.is_broken() else "on track"
        click.echo(
            f"  - {habit.name:<18} {str(habit.periodicity):<7} "
            f"longest streak: {streak:<3} ({flag})"
        )


@cli.command()
@click.confirmation_option(
    prompt="This loads 5 predefined habits with example data. Continue?"
)
@click.pass_obj
def seed(db: HabitDB) -> None:
    """Load the 5 predefined habits with 4 weeks of example tracking data."""
    loaded = 0
    for habit in predefined_habits():
        try:
            db.save_habit(habit)
            loaded += 1
        except ValueError:
            # Habit already exists -- skip it so seeding is safe to re-run.
            continue
    click.echo(f"Seeded {loaded} predefined habit(s).")


# --------------------------------------------------------------------------- #
# analyse (functional analytics)
# --------------------------------------------------------------------------- #
@cli.command()
@click.pass_obj
def analyse(db: HabitDB) -> None:
    """Run the analytics module over all tracked habits."""
    habits = db.load_all_habits()
    if not habits:
        click.echo("No habits to analyse. Run `seed` or create some habits.")
        return

    click.echo("All tracked habits:")
    for name in list_all_habits(habits):
        click.echo(f"  - {name}")

    click.echo("\nDaily habits:")
    for name in habits_by_periodicity(habits, Periodicity.DAILY):
        click.echo(f"  - {name}")

    click.echo("\nWeekly habits:")
    for name in habits_by_periodicity(habits, Periodicity.WEEKLY):
        click.echo(f"  - {name}")

    click.echo(f"\nLongest streak across all habits: {longest_streak_all(habits)} period(s).")

    best = habit_with_longest_streak(habits)
    if best:
        click.echo(f"Best habit: {best[0]!r} with a {best[1]}-period streak.")

    broken = broken_habits(habits)
    click.echo(f"\nCurrently broken: {', '.join(broken) if broken else 'none'}.")

    struggled = struggled_last_month(habits)
    if struggled:
        click.echo("\nStruggled with most last month (missed periods):")
        for name, missed in struggled:
            click.echo(f"  - {name}: {missed} missed")


# --------------------------------------------------------------------------- #
# chart (ASCII visualisation)
# --------------------------------------------------------------------------- #
@cli.command()
@click.option(
    "--periodicity",
    "-p",
    type=click.Choice(["daily", "weekly"], case_sensitive=False),
    help="Only chart habits with this periodicity.",
)
@click.option(
    "--width",
    type=click.IntRange(10, 80),
    default=40,
    show_default=True,
    help="Maximum bar width in characters.",
)
@click.pass_obj
def chart(db: HabitDB, periodicity: str | None, width: int) -> None:
    """Show an ASCII bar chart of the longest streak per habit."""
    habits = db.load_all_habits()
    if periodicity:
        chosen = habits_by_periodicity(habits, Periodicity[periodicity.upper()])
        habits = [h for h in habits if h.name in chosen]

    if not habits:
        click.echo("No habits to chart. Run `seed` or create some habits.")
        return

    data = [(h.name, longest_streak_for_habit(h)) for h in habits]
    title = "Longest streak by habit (periods)"
    if periodicity:
        title += f"  [{periodicity.lower()} only]"
    click.echo(render_bar_chart(data, title=title, width=width))


def main() -> None:  # pragma: no cover - entry point
    """Console-script entry point."""
    cli()


if __name__ == "__main__":  # pragma: no cover
    main()

"""Packaging for the habit tracker (enables `pip install -e .` and the `habit` command)."""

from setuptools import setup, find_packages

setup(
    name="habit-tracker",
    version="1.0.0",
    description="A habit tracking backend (OOP + functional programming).",
    packages=find_packages(exclude=["tests"]),
    python_requires=">=3.7",
    install_requires=["click>=8.0"],
    entry_points={"console_scripts": ["habit=habit_tracker.cli:main"]},
)

"""ASCII bar chart visualisation for the CLI.

A tiny, dependency-free helper that renders a horizontal bar chart in the
terminal. Kept as its own module so it can be unit-tested in isolation and so
the CLI module stays focused on wiring commands.

The chart uses Unicode block characters (\u2588 \u2589 ... \u258F) for smooth
bar ends, falling back to plain ASCII where needed.
"""

from __future__ import annotations

from typing import Iterable


# Full block + the seven partial blocks for sub-character precision.
_BLOCK_FULL = "\u2588"
_BLOCK_PARTIAL = ["", "\u258F", "\u258E", "\u258D", "\u258C", "\u258B", "\u258A", "\u2589"]


def _bar(value: float, scale: float, width: int) -> str:
    """Render one bar of ``width`` chars total, filled in proportion to ``value/scale``."""
    if scale <= 0:
        return ""
    filled = (value / scale) * width
    whole = int(filled)
    eighths = int(round((filled - whole) * 8))
    if eighths == 8:
        whole += 1
        eighths = 0
    return _BLOCK_FULL * whole + _BLOCK_PARTIAL[eighths]


def render_bar_chart(
    data: Iterable[tuple[str, float]],
    *,
    title: str = "",
    width: int = 40,
    label_width: int | None = None,
) -> str:
    """Return an ASCII bar chart as a multi-line string.

    :param data: Iterable of ``(label, value)`` pairs.
    :param title: Optional chart title rendered above the bars.
    :param width: Maximum bar width in characters (longest bar fills this).
    :param label_width: Width reserved for the label column. Auto if ``None``.
    """
    items = list(data)
    if not items:
        return (title + "\n" if title else "") + "(no data)"

    max_value = max((v for _, v in items), default=0)
    if label_width is None:
        label_width = max(len(label) for label, _ in items)

    lines: list[str] = []
    if title:
        lines.append(title)
        lines.append("-" * (label_width + width + 12))

    for label, value in items:
        bar = _bar(value, max_value, width) if max_value > 0 else ""
        lines.append(f"  {label:<{label_width}}  {bar}  {value:g}")

    return "\n".join(lines)

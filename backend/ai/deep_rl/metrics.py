"""CSV training metrics and optional plotting helpers."""

from __future__ import annotations

import csv
from pathlib import Path


class MetricsLogger:
    """Append metric records to a CSV file with a stable column order."""

    def __init__(self, csv_path: str | Path) -> None:
        self.csv_path = Path(csv_path)
        self._fields: list[str] | None = None

    def log(self, step: int, **values: float) -> None:
        """Append one metrics row, creating the CSV header on first use."""
        row = {"step": step, **values}
        if self._fields is None:
            exists = self.csv_path.exists() and self.csv_path.stat().st_size > 0
            if exists:
                with self.csv_path.open(newline="", encoding="utf-8") as stream:
                    self._fields = next(csv.reader(stream))
            else:
                self._fields = list(row)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not self.csv_path.exists() or self.csv_path.stat().st_size == 0
        with self.csv_path.open("a", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=self._fields, extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerow(row)


def plot(csv_path: str | Path, out_png: str | Path) -> None:
    """Plot available loss, win-rate, and epsilon columns to a PNG."""
    import matplotlib.pyplot as plt

    with Path(csv_path).open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("metrics CSV contains no data")
    x = [float(row["step"]) for row in rows]
    series = (
        ("loss", "loss"),
        ("win_rate", "win rate"),
        ("epsilon", "epsilon"),
    )
    plotted = False
    for key, label in series:
        if key in rows[0] and all(row.get(key, "") for row in rows):
            plt.plot(x, [float(row[key]) for row in rows], label=label)
            plotted = True
    if not plotted:
        raise ValueError("metrics CSV needs loss, win_rate, or epsilon")
    plt.xlabel("step")
    plt.legend()
    plt.tight_layout()
    output = Path(out_png)
    output.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output)
    plt.close()

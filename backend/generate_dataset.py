"""Generate SYNTHETIC household electricity data (not real Kenya Power data).

Usage:
    python generate_dataset.py --households 5 --days 180 --out datasets
Writes one CSV per household plus an *_anomaly_labels.csv with the injected anomalies.
"""
import argparse
from pathlib import Path

from app.ml.synthetic import generate_household


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--households", type=int, choices=(1, 5, 10), default=1)
    p.add_argument("--days", type=int, default=120, help="days of hourly data (>= 90 recommended)")
    p.add_argument("--start", default="2026-01-01")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="datasets")
    a = p.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sizes = [2, 3, 4, 5, 6]
    for i in range(a.households):
        df, labels = generate_household(a.start, a.days, sizes[i % len(sizes)], seed=a.seed + i)
        df.to_csv(out / f"synthetic_household_{i + 1}.csv", index=False)
        labels.to_csv(out / f"synthetic_household_{i + 1}_anomaly_labels.csv", index=False)
        print(f"household {i + 1}: {len(df)} hourly rows, {len(labels)} injected anomalies")
    print(f"SYNTHETIC data written to {out.resolve()}")


if __name__ == "__main__":
    main()

from pathlib import Path
import argparse
import sys
from datetime import datetime
from collections import Counter

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app


def load_records(csv_path: Path):
    dataframe = None
    for encoding in ("utf-8", "latin-1"):
        try:
            dataframe = pd.read_csv(csv_path, header=None, encoding=encoding)
            break
        except Exception:
            dataframe = None

    if dataframe is None:
        raise ValueError("could not parse CSV with utf-8 or latin-1")

    dataframe = dataframe.iloc[1:]
    column_a = dataframe[0].astype(str).str.strip()
    empty_mask = (column_a == "") | (column_a == "nan")

    if empty_mask.any():
        first_empty = empty_mask.idxmax()
        dataframe = dataframe.loc[: first_empty - 1]

    records = []
    for _, row in dataframe.iterrows():
        timestamp_text = str(row[0]).strip() if len(row) > 0 else ""
        action_text = str(row[1]).strip() if len(row) > 1 else ""

        if not timestamp_text or not action_text:
            continue

        try:
            parsed_dt = datetime.strptime(timestamp_text, app.TIMESTAMP_FORMAT)
        except ValueError:
            continue

        journey_id = ""
        if len(row) > 6 and not pd.isna(row[6]):
            journey_id = str(row[6]).strip()

        records.append(
            {
                "timestamp_text": timestamp_text,
                "dt": parsed_dt,
                "action": action_text,
                "journey_id": journey_id,
            }
        )

    return records


def sum_hour_usage(csv_path: Path):
    records = load_records(csv_path)
    timestamps = app.build_hourly_trip_timestamps(records)
    hour_counts = Counter(datetime.strptime(ts, app.TIMESTAMP_FORMAT).hour for ts in timestamps)
    return sum(hour_counts.values())


def main():
    parser = argparse.ArgumentParser(description="Print sum of hour-of-day usage for Compass CSV files.")
    parser.add_argument("paths", nargs="*", help="CSV file paths")
    parser.add_argument("--uploads", action="store_true", help="Process all CSV files under uploads/")
    args = parser.parse_args()

    root = ROOT
    targets = []

    if args.uploads:
        targets.extend(sorted((root / "uploads").glob("*.csv")))

    for raw_path in args.paths:
        path_obj = Path(raw_path)
        if not path_obj.is_absolute():
            path_obj = (root / path_obj).resolve()
        targets.append(path_obj)

    unique_targets = []
    seen = set()
    for target in targets:
        target_key = str(target).lower()
        if target_key in seen:
            continue
        seen.add(target_key)
        unique_targets.append(target)

    if not unique_targets:
        print("No CSV files specified. Use --uploads or pass one/more CSV paths.")
        return

    for target in unique_targets:
        if not target.exists() or target.suffix.lower() != ".csv":
            print(f"{target}: skipped (not a CSV file)")
            continue

        try:
            total = sum_hour_usage(target)
            print(f"{target.name}: sum(hour_values) = {total}")
        except Exception as error:
            print(f"{target.name}: error ({error})")


if __name__ == "__main__":
    main()

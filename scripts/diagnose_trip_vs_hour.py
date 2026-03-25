from pathlib import Path
import argparse
import csv
import sys
from collections import Counter
from datetime import datetime

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app
import utils


def load_actions(csv_path: Path):
    actions = []
    with open(csv_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if len(row) < 2 or row[1].strip() == "":
                break
            actions.append(row[1].strip())
    return actions


def compute_trips_num(actions):
    trips = utils.remove_refund_pairs(actions)
    ssw_taps = [
        stop for stop in trips
        if "Bus Stop" not in stop and "Loaded" not in stop and "SV" not in stop and "COS" not in stop and "Purchase" not in stop
    ]
    ssw_bus_taps = [
        stop for stop in trips
        if "Loaded" not in stop and "SV" not in stop and "COS" not in stop and "Purchase" not in stop
    ]

    trips_num = (len(ssw_bus_taps) - len(ssw_taps)) + len(ssw_taps) / 2

    ssw_tap_names = utils.ProcessList(ssw_taps)
    seabus_w_skytrain = []
    for i in range(0, len(ssw_tap_names), 2):
        first = ssw_tap_names[i]
        second = ssw_tap_names[i + 1] if i + 1 < len(ssw_tap_names) else ""
        if (
            ("Lonsdale" in first or "Lonsdale" in second)
            and "Waterfront" not in first and "Waterfront" not in second
            and "Missing" not in first and "Missing" not in second
        ):
            seabus_w_skytrain.append((first, second))
    trips_num += len(seabus_w_skytrain)

    return trips_num


def compute_hour_sum(csv_path: Path):
    dataframe = pd.read_csv(csv_path, header=None)
    dataframe = dataframe.iloc[1:]

    col_a = dataframe[0].astype(str).str.strip()
    empty_mask = (col_a == "") | (col_a == "nan")
    if empty_mask.any():
        first_empty = empty_mask.idxmax()
        dataframe = dataframe.loc[: first_empty - 1]

    parsed_records = []
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

        parsed_records.append({
            "timestamp_text": timestamp_text,
            "dt": parsed_dt,
            "action": action_text,
            "journey_id": journey_id,
        })

    timestamps = app.build_hourly_trip_timestamps(parsed_records)
    return len(timestamps)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    actions = load_actions(csv_path)
    trips_num = compute_trips_num(actions)
    hour_sum = compute_hour_sum(csv_path)

    print(f"TripsNum int: {int(trips_num)}")
    print(f"TripsNum raw: {trips_num}")
    print(f"sum(hour_values): {hour_sum}")
    print(f"delta: {hour_sum - int(trips_num)}")

    cleaned_actions = utils.remove_refund_pairs(actions)
    non_out_cleaned = [
        a for a in cleaned_actions
        if "out" not in a.lower() and all(k not in a for k in ("Loaded", "SV", "COS", "Purchase", "Refund"))
    ]
    print(f"non-out actions after refund-pair removal: {len(non_out_cleaned)}")

    original_non_out = [
        a for a in actions
        if "out" not in a.lower() and all(k not in a for k in ("Loaded", "SV", "COS", "Purchase", "Refund"))
    ]
    print(f"non-out actions before refund-pair removal: {len(original_non_out)}")

    missing_in = sum(1 for a in cleaned_actions if a.startswith("Missing Tap in"))
    missing_out = sum(1 for a in cleaned_actions if a.startswith("Missing Tap out"))
    print(f"missing tap-in count (cleaned): {missing_in}")
    print(f"missing tap-out count (cleaned): {missing_out}")


if __name__ == "__main__":
    main()

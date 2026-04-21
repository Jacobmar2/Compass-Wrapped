from flask import Flask, render_template, request, redirect, url_for,flash
import pandas as pd
import os
import csv
import uuid
import utils
from collections import Counter, OrderedDict
from datetime import datetime, timedelta, time
import calendar
import re
import heapq
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {".csv"}
MAX_CSV_ROWS = 150000
TIMESTAMP_FORMAT = "%b-%d-%Y %I:%M %p"

WCE_TERMINAL_STATION_KEYS = {"waterfront", "moody center"}
SEGMENTS_CSV_PATH = os.path.join("static", "data", "SkyTrain segments map- segments.csv")


def _normalize_graph_station_name(name):
    text = str(name or "").strip().lower()
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace(".", " ")
    text = re.sub(r"\bstn\b", "station", text)
    text = re.sub(r"\bstation\b", " ", text)
    text = re.sub(r"\bst\b", "street", text)
    text = re.sub(r"\bdr\b", "drive", text)
    text = re.sub(r"\bav\b", "avenue", text)
    text = re.sub(r"\bave\b", "avenue", text)
    text = re.sub(r"\bcentre\b", "center", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


GRAPH_STATION_ALIASES = {
    # Expo/Millennium
    "waterfront": "Waterfront",
    "burrard": "Burrard",
    "granville": "Granville",
    "stadium": "Stadium-Chinatown",
    "stadium chinatown": "Stadium-Chinatown",
    "main street science world": "Main Street-Science World",
    "science world": "Main Street-Science World",
    "main street": "Main Street-Science World",
    "commercial broadway": "Commercial-Broadway",
    "commercial": "Commercial-Broadway",
    "commercial drive": "Commercial-Broadway",
    "commercial dr": "Commercial-Broadway",
    "nanaimo": "Nanaimo",
    "29th": "29th Avenue",
    "29th av": "29th Avenue",
    "29th avenue": "29th Avenue",
    "joyce": "Joyce-Collingwood",
    "joyce collingwood": "Joyce-Collingwood",
    "patterson": "Patterson",
    "metrotown": "Metrotown",
    "royal oak": "Royal Oak",
    "edmonds": "Edmonds",
    "22nd": "22nd Street",
    "22nd st": "22nd Street",
    "22nd street": "22nd Street",
    "new west": "New Westminster",
    "new westminster": "New Westminster",
    "columbia": "Columbia",
    "scott rd": "Scott Road",
    "scott road": "Scott Road",
    "gateway": "Gateway",
    "surrey central": "Surrey Central",
    "king george": "King George",
    "sapperton": "Sapperton",
    "braid": "Braid",
    "lougheed": "Lougheed Town Centre",
    "lougheed town centre": "Lougheed Town Centre",
    "production": "Production Way-University",
    "production way": "Production Way-University",
    "production way university": "Production Way-University",
    "vcc clark": "VCC-Clark",
    "renfrew": "Renfrew",
    "rupert": "Rupert",
    "gilmore": "Gilmore",
    "brentwood": "Brentwood",
    "holdom": "Holdom",
    "sperling": "Sperling-Burnaby Lake",
    "sperling burnaby lake": "Sperling-Burnaby Lake",
    "lake city": "Lake City Way",
    "lake city way": "Lake City Way",
    "burquitlam": "Burquitlam",
    "moody": "Moody Centre",
    "moody center": "Moody Centre",
    "moody centre": "Moody Centre",
    "inlet": "Inlet Centre",
    "inlet center": "Inlet Centre",
    "inlet centre": "Inlet Centre",
    "coquitlam": "Coquitlam Central",
    "coquitlam central": "Coquitlam Central",
    "lincoln": "Lincoln",
    "lafarge": "Lafarge Lake-Douglas",
    "lafarge lake douglas": "Lafarge Lake-Douglas",
    "lafarge lake douglas college": "Lafarge Lake-Douglas",
    # Canada
    "vancouver city centre": "Vancouver City Centre",
    "vancouver city center": "Vancouver City Centre",
    "city center": "Vancouver City Centre",
    "city centre": "Vancouver City Centre",
    "yaletown": "Yaletown-Roundhouse",
    "yaletown roundhouse": "Yaletown-Roundhouse",
    "olympic": "Olympic Village",
    "olympic village": "Olympic Village",
    "broadway": "Broadway-City Hall",
    "broadway city hall": "Broadway-City Hall",
    "king edward": "King Edward",
    "oakridge": "Oakridge-41st Avenue",
    "oakridge 41st": "Oakridge-41st Avenue",
    "oakridge 41st avenue": "Oakridge-41st Avenue",
    "langara": "Langara-49th Avenue",
    "langara 49th": "Langara-49th Avenue",
    "langara 49th avenue": "Langara-49th Avenue",
    "marine": "Marine Drive",
    "marine drive": "Marine Drive",
    "bridgeport": "Bridgeport",
    "capstan": "Capstan",
    "aberdeen": "Aberdeen",
    "lansdowne": "Lansdowne",
    "brighouse": "Richmond-Brighouse",
    "richmond": "Richmond-Brighouse",
    "richmond brighouse": "Richmond-Brighouse",
    "templeton": "Templeton",
    "sea island": "Sea Island Centre",
    "sea island centre": "Sea Island Centre",
    "yvr": "YVR-Airport",
    "yvr airport": "YVR-Airport",
    # SeaBus bridge for pair counting
    "lonsdale": "Waterfront",
    "lonsdale quay": "Waterfront",
    "lonsdale quay northbound": "Waterfront",
    "lonsdale quay southbound": "Waterfront",
}


def canonical_graph_station_name(name):
    normalized = _normalize_graph_station_name(name)
    if not normalized:
        return ""
    return GRAPH_STATION_ALIASES.get(normalized, "")


EXPO_MAIN_EAST_STATIONS = {
    "Commercial-Broadway", "Nanaimo", "29th Avenue", "Joyce-Collingwood", "Patterson",
    "Metrotown", "Royal Oak", "Edmonds", "22nd Street", "New Westminster", "Columbia",
    "Scott Road", "Gateway", "Surrey Central", "King George",
}


def _add_edge(graph, station_a, station_b, minutes, line_name):
    graph.setdefault(station_a, {})
    graph.setdefault(station_b, {})
    existing = graph[station_a].get(station_b)
    if existing is None:
        edge = {"minutes": minutes, "lines": {line_name}}
        graph[station_a][station_b] = edge
        graph[station_b][station_a] = {"minutes": minutes, "lines": {line_name}}
        return

    if minutes < existing["minutes"]:
        existing["minutes"] = minutes
        existing["lines"] = {line_name}
    elif minutes == existing["minutes"]:
        existing["lines"].add(line_name)

    graph[station_b][station_a] = {
        "minutes": existing["minutes"],
        "lines": set(existing["lines"]),
    }


def build_skytrain_graph():
    graph = {}

    # Expo line: Waterfront -> King George branch
    expo_main = [
        "Waterfront", "Burrard", "Granville", "Stadium-Chinatown", "Main Street-Science World",
        "Commercial-Broadway", "Nanaimo", "29th Avenue", "Joyce-Collingwood", "Patterson",
        "Metrotown", "Royal Oak", "Edmonds", "22nd Street", "New Westminster", "Columbia",
        "Scott Road", "Gateway", "Surrey Central", "King George",
    ]
    expo_main_times = [2, 1, 2, 2, 3, 3, 1, 2, 2, 2, 1, 3, 3, 3, 1, 3, 3, 2, 1]

    # Expo line: Columbia -> Production Way branch
    expo_branch = ["Columbia", "Sapperton", "Braid", "Lougheed Town Centre", "Production Way-University"]
    expo_branch_times = [3, 2, 3, 2]

    # Millennium line
    millennium = [
        "VCC-Clark", "Commercial-Broadway", "Renfrew", "Rupert", "Gilmore", "Brentwood", "Holdom",
        "Sperling-Burnaby Lake", "Lake City Way", "Production Way-University", "Lougheed Town Centre",
        "Burquitlam", "Moody Centre", "Inlet Centre", "Coquitlam Central", "Lincoln", "Lafarge Lake-Douglas",
    ]
    millennium_times = [1, 3, 1, 2, 2, 2, 2, 3, 2, 2, 3, 5, 2, 3, 2, 1]

    # Canada line trunk and branches
    canada_trunk = [
        "Waterfront", "Vancouver City Centre", "Yaletown-Roundhouse", "Olympic Village",
        "Broadway-City Hall", "King Edward", "Oakridge-41st Avenue", "Langara-49th Avenue",
        "Marine Drive", "Bridgeport",
    ]
    canada_trunk_times = [2, 2, 2, 1, 2, 3, 2, 3, 3]

    canada_richmond = ["Bridgeport", "Capstan", "Aberdeen", "Lansdowne", "Richmond-Brighouse"]
    canada_richmond_times = [1, 2, 2, 1]

    canada_yvr = ["Bridgeport", "Templeton", "Sea Island Centre", "YVR-Airport"]
    canada_yvr_times = [2, 2, 3]

    for i, minutes in enumerate(expo_main_times):
        _add_edge(graph, expo_main[i], expo_main[i + 1], minutes, "Expo")
    for i, minutes in enumerate(expo_branch_times):
        _add_edge(graph, expo_branch[i], expo_branch[i + 1], minutes, "Expo")
    for i, minutes in enumerate(millennium_times):
        _add_edge(graph, millennium[i], millennium[i + 1], minutes, "Millennium")
    for i, minutes in enumerate(canada_trunk_times):
        _add_edge(graph, canada_trunk[i], canada_trunk[i + 1], minutes, "Canada")
    for i, minutes in enumerate(canada_richmond_times):
        _add_edge(graph, canada_richmond[i], canada_richmond[i + 1], minutes, "Canada")
    for i, minutes in enumerate(canada_yvr_times):
        _add_edge(graph, canada_yvr[i], canada_yvr[i + 1], minutes, "Canada")

    return graph


def _run_shortest_path_with_transfer_tiebreak(graph, start_station, end_station, banned_edges=None):
    queue = [(0, 0, start_station, None, [start_station])]
    best_cost = {}

    while queue:
        total_minutes, transfer_count, current_station, last_line, path = heapq.heappop(queue)

        state_key = (current_station, last_line)
        previous_best = best_cost.get(state_key)
        current_cost = (total_minutes, transfer_count)
        if previous_best is not None and current_cost >= previous_best:
            continue
        best_cost[state_key] = current_cost

        if current_station == end_station:
            return total_minutes, path, transfer_count

        for neighbor, edge_data in graph[current_station].items():
            edge_key = tuple(sorted((current_station, neighbor)))
            if banned_edges and edge_key in banned_edges:
                continue

            edge_minutes = edge_data["minutes"]
            edge_lines = edge_data["lines"]

            if last_line is None:
                next_lines = sorted(edge_lines)
            elif last_line in edge_lines:
                next_lines = [last_line]
            else:
                next_lines = sorted(edge_lines)

            for next_line in next_lines:
                add_transfer = 0 if last_line is None or next_line == last_line else 1
                heapq.heappush(
                    queue,
                    (
                        total_minutes + edge_minutes,
                        transfer_count + add_transfer,
                        neighbor,
                        next_line,
                        path + [neighbor],
                    ),
                )

    return None, [], None


def shortest_path_with_minutes(graph, start_station, end_station):
    if start_station not in graph or end_station not in graph:
        return None, []
    if start_station == end_station:
        return 0, [start_station]

    sapperton_or_braid = {"Sapperton", "Braid"}
    uses_expo_main_east_special = (
        (start_station in EXPO_MAIN_EAST_STATIONS and end_station in sapperton_or_braid)
        or (end_station in EXPO_MAIN_EAST_STATIONS and start_station in sapperton_or_braid)
    )

    if uses_expo_main_east_special:
        blocked_lougheed_side = {tuple(sorted(("Braid", "Lougheed Town Centre")))}
        total_minutes, path, _ = _run_shortest_path_with_transfer_tiebreak(
            graph,
            start_station,
            end_station,
            banned_edges=blocked_lougheed_side,
        )
        if total_minutes is not None:
            return total_minutes, path

    total_minutes, path, _ = _run_shortest_path_with_transfer_tiebreak(graph, start_station, end_station)
    if total_minutes is not None:
        return total_minutes, path

    return None, []


def all_skytrain_station_pair_counts(file_path):
    rows = None
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(file_path, newline="", encoding=encoding) as csvfile:
                rows = list(csv.reader(csvfile))[1:]
            break
        except UnicodeDecodeError:
            continue

    if rows is None:
        with open(file_path, newline="", encoding="utf-8", errors="replace") as csvfile:
            rows = list(csv.reader(csvfile))[1:]

    pair_counts = Counter()
    for i in range(0, len(rows) - 1):
        row = rows[i]
        next_row = rows[i + 1]
        if len(row) < 2 or len(next_row) < 2:
            continue

        action = str(row[1]).strip()
        next_action = str(next_row[1]).strip()
        lowered = action.lower()
        next_lowered = next_action.lower()

        if not action or not next_action:
            continue
        if "out" not in lowered:
            continue
        if "missing" in lowered or "missing" in next_lowered:
            continue

        first_name, second_name = utils.ProcessList([action, next_action])
        first_station = canonical_graph_station_name(first_name)
        second_station = canonical_graph_station_name(second_name)

        if not first_station or not second_station or first_station == second_station:
            continue

        pair_key = tuple(sorted((first_station, second_station)))
        pair_counts[pair_key] += 1

    return pair_counts


def build_segment_usage_from_pairs(pair_counts):
    graph = build_skytrain_graph()
    segment_uses = Counter()
    segment_minutes = Counter()
    shortest_pair_minutes = {}

    for pair_key, uses in pair_counts.items():
        start_station, end_station = pair_key
        total_minutes, path = shortest_path_with_minutes(graph, start_station, end_station)
        if total_minutes is None or len(path) < 2:
            continue

        shortest_pair_minutes[f"{start_station}__{end_station}"] = {
            "minutes": total_minutes,
            "uses": int(uses),
        }

        for i in range(len(path) - 1):
            left = path[i]
            right = path[i + 1]
            edge_key = tuple(sorted((left, right)))
            edge_minutes = graph[left][right]["minutes"]
            segment_uses[edge_key] += uses
            segment_minutes[edge_key] += uses * edge_minutes

    return segment_uses, segment_minutes, shortest_pair_minutes


def split_segment_name_to_stations(segment_name):
    tokens = str(segment_name or "").strip().split()
    if len(tokens) < 2:
        return "", ""

    for split_index in range(1, len(tokens)):
        left_text = " ".join(tokens[:split_index])
        right_text = " ".join(tokens[split_index:])
        left_station = canonical_graph_station_name(left_text)
        right_station = canonical_graph_station_name(right_text)
        if left_station and right_station and left_station != right_station:
            return left_station, right_station

    return "", ""


def build_segment_usage_by_csv_name(segment_uses, segment_minutes):
    usage_by_name = {}

    if not os.path.exists(SEGMENTS_CSV_PATH):
        return usage_by_name

    with open(SEGMENTS_CSV_PATH, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            segment_name = str(row.get("name", "")).strip()
            if not segment_name:
                continue

            left_station, right_station = split_segment_name_to_stations(segment_name)
            if not left_station or not right_station:
                usage_by_name[segment_name] = {
                    "uses": 0,
                    "minutes": 0,
                    "from": "",
                    "to": "",
                }
                continue

            edge_key = tuple(sorted((left_station, right_station)))
            usage_by_name[segment_name] = {
                "uses": int(segment_uses.get(edge_key, 0)),
                "minutes": int(segment_minutes.get(edge_key, 0)),
                "from": left_station,
                "to": right_station,
            }

    return usage_by_name


def format_last_used_for_display(last_used_dt):
    if not last_used_dt:
        return {
            "timestamp": "Unknown",
            "days_ago": None,
            "relative": "unknown",
            "display": "Unknown",
        }

    timestamp_text = last_used_dt.strftime(TIMESTAMP_FORMAT)
    day_delta = (datetime.now().date() - last_used_dt.date()).days

    if day_delta <= 0:
        relative_text = "today"
        day_delta = 0
    elif day_delta == 1:
        relative_text = "1 day ago"
    else:
        relative_text = f"{day_delta} days ago"

    return {
        "timestamp": timestamp_text,
        "days_ago": day_delta,
        "relative": relative_text,
        "display": f"{timestamp_text} ({relative_text})",
    }


def parse_uploaded_csv_rows(uploaded_file):
    uploaded_file.stream.seek(0)
    text_stream = uploaded_file.stream.read().decode("utf-8").splitlines()
    reader = csv.reader(text_stream)
    rows = list(reader)
    uploaded_file.stream.seek(0)
    return rows


def calculate_summary_metrics_from_rows(rows):
    if len(rows) <= 1:
        return {
            "trips": 0,
            "ssw_trips": 0,
            "skytrain_trips": 0,
            "seabus_trips": 0,
            "wce_trips": 0,
        }

    trips = []
    for row in rows[1:]:  # skip header row
        if len(row) < 2 or str(row[1]).strip() == "":
            break
        trips.append(str(row[1]).strip())

    trips = utils.remove_refund_pairs(trips)

    sswtaps = [
        stop for stop in trips
        if "Bus Stop" not in stop and "Loaded" not in stop and "SV" not in stop and "COS" not in stop and "Purchase" not in stop
    ]
    ssw_bus_taps = [
        stop for stop in trips
        if "Loaded" not in stop and "SV" not in stop and "COS" not in stop and "Purchase" not in stop
    ]

    ssw_trips_num = len(sswtaps) / 2
    ssw_bus_taps_num = len(ssw_bus_taps) - len(sswtaps)
    trips_num = ssw_bus_taps_num + ssw_trips_num

    ssw_tap_names = utils.ProcessList(sswtaps)
    seabus_with_skytrain = []
    for i in range(0, len(ssw_tap_names), 2):
        first = ssw_tap_names[i]
        second = ssw_tap_names[i + 1] if i + 1 < len(ssw_tap_names) else ""

        if (
            ("Lonsdale" in first or "Lonsdale" in second)
            and "Waterfront" not in first and "Waterfront" not in second
            and "Missing" not in first and "Missing" not in second
        ):
            seabus_with_skytrain.append((first, second))

    trips_num += len(seabus_with_skytrain)
    ssw_trips_num += len(seabus_with_skytrain)

    skytrain_trips_num = 0
    seabus_trips_num = 0
    wce_trips_num = 0

    for stop in ssw_tap_names:
        if stop.endswith("Stn"):
            skytrain_trips_num += 1
        elif stop.endswith("Quay"):
            seabus_trips_num += 1
        elif stop.endswith("Station") or stop.endswith("Stn - WCE"):
            wce_trips_num += 1

    for i in range(0, len(ssw_tap_names), 2):
        first = ssw_tap_names[i]
        second = ssw_tap_names[i + 1] if i + 1 < len(ssw_tap_names) else ""

        if "Missing" in first:
            other = second
        elif "Missing" in second:
            other = first
        else:
            continue

        if other.endswith("Stn") or other.endswith("Quay"):
            skytrain_trips_num += 1
        elif other.endswith("Station") or other.endswith("Stn - WCE"):
            wce_trips_num += 1

    for i in range(1, len(ssw_tap_names)):
        if "Waterfront Stn - WCE" in ssw_tap_names[i] and "Transfer" in sswtaps[i]:
            skytrain_trips_num, trips_num, ssw_trips_num, wce_trips_num = utils.adjust_wce_eastbound(
                ssw_tap_names, i, skytrain_trips_num, trips_num, ssw_trips_num, wce_trips_num
            )
        elif "Moody" in ssw_tap_names[i] and "Station" in ssw_tap_names[i] and "Transfer" in sswtaps[i]:
            skytrain_trips_num, trips_num, ssw_trips_num, wce_trips_num = utils.adjust_wce_westbound(
                ssw_tap_names, i, skytrain_trips_num, trips_num, ssw_trips_num, wce_trips_num
            )

    skytrain_trips_num += 2 * len(seabus_with_skytrain) - seabus_trips_num
    skytrain_trips_num /= 2
    wce_trips_num /= 2

    return {
        "trips": int(trips_num),
        "ssw_trips": int(ssw_trips_num),
        "skytrain_trips": int(round(skytrain_trips_num)),
        "seabus_trips": int(seabus_trips_num),
        "wce_trips": int(round(wce_trips_num)),
    }


def calculate_minutes_from_rows(rows):
    if len(rows) <= 2:
        return 0.0

    total_minutes = 0.0
    data = rows[1:]

    for i in range(len(data) - 1):
        if len(data[i]) < 2 or len(data[i + 1]) < 1:
            continue

        timestamp = str(data[i][0]).strip()
        action = str(data[i][1]).strip().lower()
        next_timestamp = str(data[i + 1][0]).strip()

        if not timestamp or not next_timestamp:
            continue

        if "out" in action and "missing" not in action:
            try:
                ts_out = datetime.strptime(timestamp, TIMESTAMP_FORMAT)
                ts_in = datetime.strptime(next_timestamp, TIMESTAMP_FORMAT)
            except ValueError:
                continue

            diff_minutes = (ts_out - ts_in).total_seconds() / 60
            if diff_minutes > 0:
                total_minutes += diff_minutes

    return round(total_minutes, 1)


def format_duration_days_hours_minutes(total_minutes):
    total_minutes_int = int(round(total_minutes))
    days, remaining_minutes = divmod(total_minutes_int, 24 * 60)
    hours, minutes = divmod(remaining_minutes, 60)
    return days, hours, minutes


def build_usage_breakdowns_from_rows(rows):
    if len(rows) <= 1:
        return {
            "station_counts": {},
            "hour_counts": [0] * 24,
            "weekday_counts": [0] * 7,
            "month_counts": [0] * 12,
        }

    trips = []
    for row in rows[1:]:
        if len(row) < 2 or str(row[1]).strip() == "":
            break
        trips.append(str(row[1]).strip())

    trips = utils.remove_refund_pairs(trips)
    sswtaps = [
        stop for stop in trips
        if "Bus Stop" not in stop and "Loaded" not in stop and "SV" not in stop and "COS" not in stop and "Purchase" not in stop
    ]
    ssw_tap_names = utils.ProcessList(sswtaps)
    station_counts = Counter(name for name in ssw_tap_names if name.endswith("Stn"))

    parsed_records = []
    for row in rows[1:]:
        if len(row) < 2:
            continue

        timestamp_text = str(row[0]).strip()
        action_text = str(row[1]).strip()

        if not action_text:
            break

        if not timestamp_text:
            continue

        try:
            parsed_dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
        except ValueError:
            continue

        journey_id = ""
        if len(row) > 6 and str(row[6]).strip().lower() != "nan":
            journey_id = str(row[6]).strip()

        parsed_records.append({
            "timestamp_text": timestamp_text,
            "dt": parsed_dt,
            "action": action_text,
            "journey_id": journey_id,
        })

    hourly_trip_timestamps = build_hourly_trip_timestamps(parsed_records)

    hour_counts = [0] * 24
    weekday_counts = [0] * 7
    month_counts = [0] * 12

    for ts in hourly_trip_timestamps:
        try:
            dt = datetime.strptime(str(ts).strip(), TIMESTAMP_FORMAT)
        except ValueError:
            continue

        hour_counts[dt.hour] += 1
        weekday_counts[dt.weekday()] += 1
        month_counts[dt.month - 1] += 1

    return {
        "station_counts": dict(station_counts),
        "hour_counts": hour_counts,
        "weekday_counts": weekday_counts,
        "month_counts": month_counts,
    }


def build_compare_taps_from_rows(rows):
    events = []
    skip_refund_tap_in = False
    data_rows = rows[1:]

    def classify_tap_mode(action_text, tap_name):
        lowered_action = action_text.lower()
        lowered_name = tap_name.lower()

        if "bus stop" in lowered_action or "bus stop" in lowered_name:
            return "bus"
        if lowered_name.endswith("quay"):
            return "seabus"
        if "wce" in lowered_action or "wce" in lowered_name:
            return "wce"
        if lowered_name.endswith("station"):
            return "wce"
        if lowered_name.endswith("stn"):
            return "skytrain"
        return "other"

    def classify_tap_kind(action_text):
        lowered = str(action_text).lower()
        if lowered.startswith("tap in at"):
            return "tap_in"
        if lowered.startswith("tap out at"):
            return "tap_out"
        if lowered.startswith("transfer at"):
            return "transfer"
        if lowered.startswith("missing tap in"):
            return "missing_in"
        if lowered.startswith("missing tap out"):
            return "missing_out"
        return "other"

    def infer_missing_tap_name(index, missing_kind):
        search_offsets = [1, -1, 2, -2]
        if missing_kind == "missing_out":
            search_offsets = [-1, 1, -2, 2]

        for offset in search_offsets:
            j = index + offset
            if j < 0 or j >= len(data_rows):
                continue

            candidate = data_rows[j]
            if len(candidate) < 2:
                continue
            candidate_action = str(candidate[1]).strip()
            candidate_lowered = candidate_action.lower()
            if not candidate_action or candidate_lowered.startswith("missing tap"):
                continue
            if " at " not in candidate_action:
                continue

            candidate_tap_name = candidate_action.split(" at ", 1)[1].strip()
            if "bus stop" in candidate_tap_name.lower():
                continue

            return candidate_tap_name

        return ""

    for index, row in enumerate(data_rows):
        if len(row) < 2:
            continue

        timestamp_text = str(row[0]).strip()
        action_text = str(row[1]).strip()

        if not action_text:
            break

        lowered = action_text.lower()

        if "refund" in lowered:
            # Refund rows are ignored, and the next Tap in for that refunded trip is ignored too.
            skip_refund_tap_in = True
            continue

        if skip_refund_tap_in:
            if action_text.startswith("Tap in at"):
                skip_refund_tap_in = False
                continue
            skip_refund_tap_in = False

        is_tap_like = (
            lowered.startswith("tap in at")
            or lowered.startswith("tap out at")
            or lowered.startswith("transfer at")
            or lowered.startswith("missing tap in")
            or lowered.startswith("missing tap out")
        )
        if not is_tap_like:
            continue

        tap_kind = classify_tap_kind(action_text)

        try:
            dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
        except ValueError:
            continue

        inferred_name = ""
        if tap_kind in {"missing_in", "missing_out"}:
            inferred_name = infer_missing_tap_name(index, tap_kind)
            tap_name = "(Missing)"
        elif " at " in action_text:
            tap_name = action_text.split(" at ", 1)[1].strip()
        else:
            tap_name = action_text.strip()

        tap_key_source = inferred_name if inferred_name else tap_name
        tap_key = re.sub(r"\s+", " ", tap_key_source).strip().lower()
        if not tap_key:
            continue

        is_missing = tap_kind in {"missing_in", "missing_out"}
        mode_name = inferred_name if inferred_name else tap_name
        mode = classify_tap_mode(action_text, mode_name)

        events.append({
            "timestamp": dt.isoformat(),
            "row_index": index,
            "tap_name": tap_name,
            "tap_key": tap_key,
            "mode": mode,
            "is_missing": is_missing,
            "tap_kind": tap_kind,
            "action_text": action_text,
        })

    return events


def build_compare_complete_trips_from_rows(rows):
    complete_trips = []
    data = rows[1:]

    def classify_tap_mode(action_text, tap_name):
        lowered_action = action_text.lower()
        lowered_name = tap_name.lower()

        if "bus stop" in lowered_action or "bus stop" in lowered_name:
            return "bus"
        if lowered_name.endswith("quay"):
            return "seabus"
        if "wce" in lowered_action or "wce" in lowered_name:
            return "wce"
        if lowered_name.endswith("station"):
            return "wce"
        if lowered_name.endswith("stn"):
            return "skytrain"
        return "other"

    for i in range(len(data) - 1):
        row = data[i]
        next_row = data[i + 1]
        if len(row) < 2 or len(next_row) < 1:
            continue

        timestamp_text = str(row[0]).strip()
        action_text = str(row[1]).strip()
        next_timestamp_text = str(next_row[0]).strip()

        if not action_text:
            break

        lowered = action_text.lower()
        if "refund" in lowered or "missing" in lowered:
            continue
        if "out" not in lowered:
            continue

        try:
            ts_out = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
            ts_in = datetime.strptime(next_timestamp_text, TIMESTAMP_FORMAT)
        except ValueError:
            continue

        duration_min = (ts_out - ts_in).total_seconds() / 60
        if duration_min <= 0:
            continue

        if " at " in action_text:
            tap_name = action_text.split(" at ", 1)[1].strip()
        else:
            tap_name = action_text.strip()

        tap_key = re.sub(r"\s+", " ", tap_name).strip().lower()
        if not tap_key:
            continue

        mode = classify_tap_mode(action_text, tap_name)
        if mode not in {"skytrain", "seabus", "wce"}:
            continue

        complete_trips.append({
            "id": i,
            "timestamp": ts_out.isoformat(),
            "tap_key": tap_key,
            "mode": mode,
            "duration_min": round(duration_min, 2),
        })

    return complete_trips


def build_shared_trip_matches(file_a_events, file_b_events):
    def tap_phase(event):
        tap_kind = str(event.get("tap_kind", ""))
        if tap_kind in {"tap_in", "transfer", "missing_in"}:
            return "in"
        if tap_kind in {"tap_out", "missing_out"}:
            return "out"
        return "other"

    grouped_a = {}
    grouped_b = {}

    for event in file_a_events:
        tap_key = str(event.get("tap_key", "")).strip()
        if not tap_key:
            continue
        key = f"{tap_key}::{tap_phase(event)}"
        grouped_a.setdefault(key, []).append(event)

    for event in file_b_events:
        tap_key = str(event.get("tap_key", "")).strip()
        if not tap_key:
            continue
        key = f"{tap_key}::{tap_phase(event)}"
        grouped_b.setdefault(key, []).append(event)

    matches = []
    for combined_key, events_a in grouped_a.items():
        events_b = grouped_b.get(combined_key, [])
        if not events_b:
            continue

        sorted_a = sorted(
            events_a,
            key=lambda e: (str(e.get("timestamp", "")), int(e.get("row_index", 0))),
        )
        sorted_b = sorted(
            events_b,
            key=lambda e: (str(e.get("timestamp", "")), int(e.get("row_index", 0))),
        )

        i = 0
        j = 0
        while i < len(sorted_a) and j < len(sorted_b):
            event_a = sorted_a[i]
            event_b = sorted_b[j]

            try:
                ts_a = datetime.fromisoformat(str(event_a.get("timestamp", "")))
                ts_b = datetime.fromisoformat(str(event_b.get("timestamp", "")))
            except ValueError:
                i += 1
                j += 1
                continue

            diff_seconds = abs((ts_a - ts_b).total_seconds())
            mode_a = str(event_a.get("mode", "other"))
            mode_b = str(event_b.get("mode", "other"))

            if diff_seconds <= 120:
                mode = mode_a if mode_a != "other" else mode_b

                tap_key = combined_key.split("::", 1)[0]
                export_timestamp = event_b.get("timestamp") if event_a.get("is_missing") else event_a.get("timestamp")
                export_action = event_b.get("action_text") if event_a.get("is_missing") else event_a.get("action_text")

                matches.append({
                    "tap_name": event_a.get("tap_name", ""),
                    "tap_name_a": event_a.get("tap_name", ""),
                    "tap_name_b": event_b.get("tap_name", ""),
                    "tap_key": tap_key,
                    "mode": mode,
                    "a_missing": bool(event_a.get("is_missing")),
                    "b_missing": bool(event_b.get("is_missing")),
                    "tap_a": event_a.get("tap_kind", ""),
                    "tap_b": event_b.get("tap_kind", ""),
                    "ts_a": str(event_a.get("timestamp", "")),
                    "ts_b": str(event_b.get("timestamp", "")),
                    "row_index_a": int(event_a.get("row_index", 0)),
                    "row_index_b": int(event_b.get("row_index", 0)),
                    "diff_min": f"{(diff_seconds / 60):.2f}",
                    "export_timestamp": str(export_timestamp or ""),
                    "export_action": str(export_action or ""),
                    "export_timestamp_a": str(event_a.get("timestamp", "") or ""),
                    "export_action_a": str(event_a.get("action_text", "") or ""),
                    "export_timestamp_b": str(event_b.get("timestamp", "") or ""),
                    "export_action_b": str(event_b.get("action_text", "") or ""),
                })
                i += 1
                j += 1
            elif ts_a < ts_b:
                i += 1
            else:
                j += 1

    matches.sort(
        key=lambda m: (
            -datetime.fromisoformat(str(m.get("ts_a", datetime.min.isoformat()))).timestamp(),
            int(m.get("row_index_a", 0)),
        )
    )

    return matches


def is_exact_shared_match(match):
    tap_a = str(match.get("tap_a", ""))
    tap_b = str(match.get("tap_b", ""))

    if tap_a in {"tap_in", "transfer"}:
        tap_a = "tap_in"
    if tap_b in {"tap_in", "transfer"}:
        tap_b = "tap_in"

    return (
        not bool(match.get("a_missing"))
        and not bool(match.get("b_missing"))
        and tap_a == tap_b
    )


def _is_tap_out_kind(tap_kind):
    return str(tap_kind) in {"tap_out", "missing_out"}


def _is_tap_in_kind(tap_kind):
    return str(tap_kind) in {"tap_in", "transfer", "missing_in"}


def build_partner_row_map(events):
    sorted_events = sorted(events, key=lambda e: int(e.get("row_index", 0)))
    partners = {}

    for i, event in enumerate(sorted_events):
        row_index = int(event.get("row_index", -1))
        tap_kind = str(event.get("tap_kind", ""))

        if _is_tap_out_kind(tap_kind):
            partner_index = None
            for j in range(i + 1, len(sorted_events)):
                if _is_tap_in_kind(sorted_events[j].get("tap_kind", "")):
                    partner_index = int(sorted_events[j].get("row_index", -1))
                    break
            partners[row_index] = partner_index
            continue

        if _is_tap_in_kind(tap_kind):
            partner_index = None
            for j in range(i - 1, -1, -1):
                if _is_tap_out_kind(sorted_events[j].get("tap_kind", "")):
                    partner_index = int(sorted_events[j].get("row_index", -1))
                    break
            partners[row_index] = partner_index
            continue

        partners[row_index] = None

    return partners


def annotate_match_trip_status(matches, file_a_events, file_b_events):
    partner_a = build_partner_row_map(file_a_events)
    partner_b = build_partner_row_map(file_b_events)
    match_lookup = {
        (int(match.get("row_index_a", -1)), int(match.get("row_index_b", -1))): match
        for match in matches
    }

    for match in matches:
        if not is_exact_shared_match(match):
            match["match_status"] = "mismatch"
            match["is_exact_trip"] = False
            continue

        if str(match.get("mode", "")) == "bus":
            # Bus taps are single-ended for fare data, so exact tap matches are treated as complete.
            match["match_status"] = "exact_trip"
            match["is_exact_trip"] = True
            continue

        row_a = int(match.get("row_index_a", -1))
        row_b = int(match.get("row_index_b", -1))
        partner_row_a = partner_a.get(row_a)
        partner_row_b = partner_b.get(row_b)

        if partner_row_a is None or partner_row_b is None:
            match["match_status"] = "one_end"
            match["is_exact_trip"] = False
            continue

        partner_match = match_lookup.get((partner_row_a, partner_row_b))
        is_exact_trip = bool(partner_match and is_exact_shared_match(partner_match))
        match["match_status"] = "exact_trip" if is_exact_trip else "one_end"
        match["is_exact_trip"] = is_exact_trip

    return matches


def build_rows_from_shared_matches(matches, side="a"):
    rows = [["DateTime", "Transaction"]]

    for match in matches:
        if side == "b":
            export_timestamp = str(match.get("export_timestamp_b", "")).strip()
            export_action = str(match.get("export_action_b", "")).strip()
        else:
            export_timestamp = str(match.get("export_timestamp_a", "")).strip()
            export_action = str(match.get("export_action_a", "")).strip()

        if export_timestamp:
            try:
                formatted_timestamp = datetime.fromisoformat(export_timestamp).strftime(TIMESTAMP_FORMAT)
            except ValueError:
                formatted_timestamp = export_timestamp
        else:
            formatted_timestamp = ""

        rows.append([formatted_timestamp, export_action])

    return rows


def normalize_station_key(action_text):
    if not action_text:
        return ""

    text = str(action_text).strip()
    if " at " in text:
        station = text.split(" at ", 1)[1].strip()
    else:
        station = text

    station = station.replace("- WCE", "")
    station = station.replace(" Station", "")
    station = station.replace(" Stn", "")
    station = re.sub(r"\s+", " ", station).strip().lower()
    if station == "commercial drive":
        return "commercial broadway"
    return station


def get_related_records(records, target_record):
    journey_id = str(target_record.get("journey_id", "")).strip()
    if not journey_id:
        return records
    return [record for record in records if str(record.get("journey_id", "")).strip() == journey_id]


def is_skytrain_station_action(action_text):
    lowered = action_text.lower()
    return (
        ("stn" in lowered or "station" in lowered)
        and "bus stop" not in lowered
        and "wce" not in lowered
        and "quay" not in lowered
    )


def is_wce_related_action(action_text):
    lowered = action_text.lower()
    return (
        "wce" in lowered
        or (
            " station" in lowered
            and "bus stop" not in lowered
            and "stn" not in lowered
        )
    )


def build_lonsdale_hour_timestamps(records):
    timestamps = []

    for record in records:
        action = str(record["action"])
        lowered = action.lower()
        if "lonsdale" not in lowered:
            continue

        related_records = get_related_records(records, record)

        if action.startswith("Tap out at"):
            has_non_waterfront_station = any(
                is_skytrain_station_action(str(candidate["action"]))
                and "waterfront" not in str(candidate["action"]).lower()
                and "lonsdale" not in str(candidate["action"]).lower()
                for candidate in related_records
            )

            if has_non_waterfront_station:
                seabus_start = record["dt"] - timedelta(minutes=15)
                timestamps.append(seabus_start.strftime(TIMESTAMP_FORMAT))
                continue

            has_waterfront_in_journey = any(
                "waterfront" in str(candidate["action"]).lower()
                for candidate in related_records
            )

            # Skip pure Waterfront↔Lonsdale pairs (no non-Waterfront station)
            if has_waterfront_in_journey:
                continue

        elif action.startswith("Tap in at") or action.startswith("Transfer at"):
            has_waterfront_in_journey = any(
                "waterfront" in str(candidate["action"]).lower()
                for candidate in related_records
            )
            is_lonsdale_transfer = action.startswith("Transfer at")

            station_tap_outs = [
                candidate for candidate in related_records
                if str(candidate["action"]).startswith("Tap out at")
                and is_skytrain_station_action(str(candidate["action"]))
                and "waterfront" not in str(candidate["action"]).lower()
                and "lonsdale" not in str(candidate["action"]).lower()
            ]

            if not station_tap_outs:
                timestamps.append(record["timestamp_text"])
                continue

            forward_station_tap_outs = [
                candidate for candidate in station_tap_outs if candidate["dt"] >= record["dt"]
            ]

            if forward_station_tap_outs:
                selected = min(forward_station_tap_outs, key=lambda candidate: candidate["dt"])
            else:
                selected = max(station_tap_outs, key=lambda candidate: candidate["dt"])

            timestamps.append(selected["timestamp_text"])

            has_non_waterfront_station_tap_out = bool(station_tap_outs)
            if (not has_waterfront_in_journey) or (is_lonsdale_transfer and has_non_waterfront_station_tap_out):
                timestamps.append(record["timestamp_text"])

    return timestamps


def build_hourly_trip_timestamps(records):
    if not records:
        return []

    cleaned = []
    skip_next = False
    for record in records:
        if skip_next:
            skip_next = False
            continue

        action_text = str(record["action"])
        if "refund" in action_text.lower():
            skip_next = True
            continue

        cleaned.append(record)

    has_seabus_or_wce = any(
        ("quay" in str(record["action"]).lower())
        or ("wce" in str(record["action"]).lower())
        or (
            " station" in str(record["action"]).lower()
            and "bus stop" not in str(record["action"]).lower()
        )
        for record in cleaned
    )

    if not has_seabus_or_wce:
        return build_hourly_trip_timestamps_no_seabus_wce(cleaned)

    cleaned = sorted(cleaned, key=lambda r: r["dt"])
    has_wce_in_file = any(
        is_wce_related_action(str(record["action"]))
        for record in cleaned
    )

    candidate_timestamps = []

    for i, record in enumerate(cleaned):
        action = record["action"]
        lowered = action.lower()

        if "loaded" in lowered or "sv" in lowered or "cos" in lowered or "purchase" in lowered or "refund" in lowered:
            continue
        if "out" in lowered:
            continue

        if (action.startswith("Tap in at") or action.startswith("Transfer at")) and "waterfront" in lowered:
            related_records = get_related_records(cleaned, record)
            related_lonsdale_tap_outs = [
                candidate for candidate in related_records
                if str(candidate["action"]).startswith("Tap out at")
                and "lonsdale" in str(candidate["action"]).lower()
            ]

            should_skip_waterfront = False
            for _lonsdale_tap_out in related_lonsdale_tap_outs:
                has_non_waterfront_station = any(
                    is_skytrain_station_action(str(candidate["action"]))
                    and "waterfront" not in str(candidate["action"]).lower()
                    and "lonsdale" not in str(candidate["action"]).lower()
                    for candidate in related_records
                )
                if has_non_waterfront_station:
                    should_skip_waterfront = True
                    break

            if should_skip_waterfront:
                waterfront_in_transfer_records = [
                    candidate for candidate in related_records
                    if (
                        str(candidate["action"]).startswith("Tap in at")
                        or str(candidate["action"]).startswith("Transfer at")
                    )
                    and "waterfront" in str(candidate["action"]).lower()
                ]

                if len(waterfront_in_transfer_records) <= 1:
                    continue

                latest_waterfront_in_transfer = max(
                    waterfront_in_transfer_records,
                    key=lambda candidate: candidate["dt"],
                )

                if record is not latest_waterfront_in_transfer:
                    continue

        if "lonsdale" in lowered and (action.startswith("Tap in at") or action.startswith("Transfer at")):
            continue

        keep_event = True

        if action.startswith("Transfer at") and has_wce_in_file:
            transfer_station = normalize_station_key(action)
            previous_tap_in_station = ""

            for j in range(i - 1, -1, -1):
                previous = cleaned[j]
                if record["journey_id"] and previous["journey_id"] != record["journey_id"]:
                    continue
                if previous["action"].startswith("Tap in at"):
                    previous_tap_in_station = normalize_station_key(previous["action"])
                    break

            if transfer_station and previous_tap_in_station and transfer_station == previous_tap_in_station:
                keep_event = False

        elif action.startswith("Missing Tap in") and has_wce_in_file:
            next_tap_out_station = ""

            for j in range(i + 1, len(cleaned)):
                following = cleaned[j]
                if record["journey_id"] and following["journey_id"] != record["journey_id"]:
                    continue
                if following["action"].startswith("Tap out at"):
                    next_tap_out_station = normalize_station_key(following["action"])
                    break

            if not next_tap_out_station:
                for j in range(i + 1, len(cleaned)):
                    following = cleaned[j]
                    if following["action"].startswith("Tap out at"):
                        next_tap_out_station = normalize_station_key(following["action"])
                        break

            if not next_tap_out_station:
                for j in range(i - 1, -1, -1):
                    previous = cleaned[j]
                    if previous["action"].startswith("Tap out at"):
                        next_tap_out_station = normalize_station_key(previous["action"])
                        break

            if next_tap_out_station in WCE_TERMINAL_STATION_KEYS:
                keep_event = False

        if keep_event:
            candidate_timestamps.append(record["timestamp_text"])

    candidate_timestamps.extend(build_lonsdale_hour_timestamps(cleaned))

    return candidate_timestamps


def build_hourly_trip_timestamps_no_seabus_wce(records):
    candidate_timestamps = []

    for record in records:
        action = str(record["action"])
        lowered = action.lower()

        if "loaded" in lowered or "sv" in lowered or "cos" in lowered or "purchase" in lowered or "refund" in lowered:
            continue

        if "bus stop" in lowered:
            if "out" in lowered:
                continue
            candidate_timestamps.append(record["timestamp_text"])
            continue

        if action.startswith("Tap out at"):
            candidate_timestamps.append(record["timestamp_text"])
            continue

        if action.startswith("Missing Tap out"):
            candidate_timestamps.append(record["timestamp_text"])

    return candidate_timestamps


def validate_compass_csv(file_path):
    try:
        with open(file_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)
            if not header or len(header) < 2:
                return False, "CSV must include at least 2 columns."

            data_rows = 0
            for line_num, row in enumerate(reader, start=2):
                if not row or all(not str(cell).strip() for cell in row):
                    break

                if len(row) < 2:
                    return False, f"CSV row {line_num} is missing required columns."

                timestamp = str(row[0]).strip()
                action = str(row[1]).strip()

                if action == "":
                    break

                if not timestamp:
                    return False, f"CSV row {line_num} is missing a timestamp in column A."

                try:
                    datetime.strptime(timestamp, TIMESTAMP_FORMAT)
                except ValueError:
                    return False, (
                        f"CSV row {line_num} has an invalid timestamp format. "
                        "Expected values like 'Jan-31-2025 05:45 PM'."
                    )

                data_rows += 1
                if data_rows > MAX_CSV_ROWS:
                    return False, f"CSV has too many rows. Maximum allowed is {MAX_CSV_ROWS}."

            if data_rows == 0:
                return False, "CSV has no usable transaction rows."

    except UnicodeDecodeError:
        return False, "CSV must be UTF-8 encoded."
    except csv.Error:
        return False, "CSV parsing failed due to malformed CSV structure."
    except OSError:
        return False, "Could not read uploaded CSV file."

    return True, None


def parse_balance_amount(balance_text):
    text = str(balance_text or "").strip()
    if not text:
        return None

    # Compass exports can include extra text; use the last money-like number as balance.
    matches = re.findall(r"\(?-?\$?\s*\d+(?:,\d{3})*(?:\.\d+)?\)?", text)
    if not matches:
        return None

    candidate = matches[-1].strip()
    is_parenthesized_negative = candidate.startswith("(") and candidate.endswith(")")
    candidate = candidate.replace("(", "").replace(")", "")
    candidate = candidate.replace("$", "").replace(",", "").strip()
    try:
        value = float(candidate)
        return -value if is_parenthesized_negative else value
    except ValueError:
        return None


def parse_amount_value(amount_text):
    text = str(amount_text or "").strip()
    if not text:
        return None

    matches = re.findall(r"\(?-?\$?\s*\d+(?:,\d{3})*(?:\.\d+)?\)?", text)
    if not matches:
        return None

    candidate = matches[0].strip()
    is_parenthesized_negative = candidate.startswith("(") and candidate.endswith(")")
    candidate = candidate.replace("(", "").replace(")", "")
    candidate = candidate.replace("$", "").replace(",", "").strip()

    try:
        value = float(candidate)
        return -value if is_parenthesized_negative else value
    except ValueError:
        return None


MONTHLY_FARE_EFFECTIVE_BY_ZONE = {
    1: [
        (datetime(2023, 7, 1).date(), 104.90),
        (datetime(2024, 7, 1).date(), 107.30),
        (datetime(2025, 7, 1).date(), 111.60),
    ],
    2: [
        (datetime(2023, 7, 1).date(), 140.25),
        (datetime(2024, 7, 1).date(), 143.50),
        (datetime(2025, 7, 1).date(), 149.25),
    ],
    3: [
        (datetime(2023, 7, 1).date(), 189.45),
        (datetime(2024, 7, 1).date(), 193.80),
        (datetime(2025, 7, 1).date(), 201.55),
    ],
}

DAYPASS_FARE_EFFECTIVE = [
    (datetime(2023, 7, 1).date(), 11.25),
    (datetime(2024, 7, 1).date(), 11.50),
    (datetime(2025, 7, 1).date(), 11.95),
]

UPASS_FARE_EFFECTIVE = [
    (datetime(2023, 5, 1).date(), 45.10),
    (datetime(2024, 5, 1).date(), 46.00),
    (datetime(2025, 9, 1).date(), 46.90),
]

COMPASS_FARE_EFFECTIVE_BY_ZONE = {
    1: [
        (datetime(2023, 7, 1).date(), 2.55),
        (datetime(2024, 7, 1).date(), 2.60),
        (datetime(2025, 7, 1).date(), 2.70),
    ],
    2: [
        (datetime(2023, 7, 1).date(), 3.75),
        (datetime(2024, 7, 1).date(), 3.85),
        (datetime(2025, 7, 1).date(), 4.00),
    ],
    3: [
        (datetime(2023, 7, 1).date(), 4.80),
        (datetime(2024, 7, 1).date(), 4.90),
        (datetime(2025, 7, 1).date(), 5.10),
    ],
}

AIRPORT_ADD_FARE = 5.00

ZONE_1_STATIONS = {
    "Waterfront Stn", "Burrard Stn", "Granville Stn", "Stadium Stn", "Main Street Stn",
    "Commercial-Broadway Stn", "Nanaimo Stn", "29th Av Stn", "Joyce Stn", "VCC-Clark Stn",
    "Renfrew Stn", "Rupert Stn", "Vancouver City Centre Stn", "Yaletown-Roundhouse Stn",
    "Olympic Village Stn", "Broadway-City Hall Stn", "King Edward Stn", "Oakridge-41st Stn",
    "Langara-49th Stn", "Marine Drive Stn",
}

ZONE_2_STATIONS = {
    "Patterson Stn", "Metrotown Stn", "Royal Oak Stn", "Edmonds Stn", "22nd St Stn",
    "New Westminster Stn", "Columbia Stn", "Sapperton Stn", "Braid Stn", "Lougheed Stn",
    "Production Way Stn", "Gilmore Stn", "Brentwood Stn", "Holdom Stn", "Sperling Stn",
    "Lake City Way Stn", "Bridgeport Stn", "Capstan Stn", "Aberdeen Stn", "Lansdowne Stn",
    "Brighouse Stn",
}

ZONE_2_LONSDALE_STATIONS = {"Lonsdale Quay", "Lonsdale Quay Stn"}

AIRPORT_STATIONS = {"Sea Island Centre Stn", "Templeton Stn", "YVR-Airport Stn"}

ZONE_3A_STATIONS = {"Scott Road Stn", "Gateway Stn", "Surrey Central Stn", "King George Stn"}
ZONE_3B_STATIONS = {
    "Burquitlam Stn", "Moody Center Stn", "Inlet Centre Stn", "Coquitlam Central Stn",
    "Lincoln Stn", "Lafarge Lake/Douglas College Stn",
}

STATION_NAME_ZONE_ALIASES = {
    "Vancouver City Center Stn": "Vancouver City Centre Stn",
    "Stadium-Chinatown Stn": "Stadium Stn",
    "Main Street-Science World Stn": "Main Street Stn",
    "Joyce-Collingwood Stn": "Joyce Stn",
    "Lougheed Town Centre Stn": "Lougheed Stn",
    "Brentwood Town Centre Stn": "Brentwood Stn",
    "Sperling-Burnaby Lake Stn": "Sperling Stn",
    "Lafarge Lake-Douglas Stn": "Lafarge Lake/Douglas College Stn",
    "YVR Airport Stn": "YVR-Airport Stn",
    "Lonsdale Quay - Seabus": "Lonsdale Quay",
}


def fare_for_date(effective_price_points, target_date):
    if not effective_price_points:
        return 0.0

    selected = effective_price_points[0][1]
    for effective_date, price in effective_price_points:
        if target_date >= effective_date:
            selected = price
        else:
            break
    return float(selected)


def normalize_station_for_zone_lookup(raw_station_name):
    station_name = utils.canonicalize_station_name(str(raw_station_name or "").strip())
    station_name = station_name.replace("- WCE", "").strip()
    station_name = STATION_NAME_ZONE_ALIASES.get(station_name, station_name)
    return station_name


def station_zone_key(station_name):
    normalized = normalize_station_for_zone_lookup(station_name)
    if normalized in AIRPORT_STATIONS:
        return "airport"
    if normalized in ZONE_1_STATIONS:
        return "z1"
    if normalized in ZONE_2_LONSDALE_STATIONS:
        return "z2lq"
    if normalized in ZONE_2_STATIONS:
        return "z2"
    if normalized in ZONE_3A_STATIONS:
        return "z3a"
    if normalized in ZONE_3B_STATIONS:
        return "z3b"
    return None


def parse_tap_event(action_text):
    action = str(action_text or "").strip()
    lowered = action.lower()

    is_tap_like = (
        lowered.startswith("tap in at")
        or lowered.startswith("tap out at")
        or lowered.startswith("transfer at")
        or lowered.startswith("missing tap in at")
        or lowered.startswith("missing tap out at")
    )
    if not is_tap_like:
        return None

    if " at " not in action:
        return None

    location_name = action.split(" at ", 1)[1].strip()
    is_bus = "bus stop" in location_name.lower() or "bus stop" in lowered

    return {
        "action": action,
        "is_bus": is_bus,
        "station": None if is_bus else normalize_station_for_zone_lookup(location_name),
        "is_tap_in": lowered.startswith("tap in at"),
    }


def build_trip_blocks(rows):
    tap_rows = []
    for row in rows:
        parsed = parse_tap_event(row.get("action", ""))
        if not parsed:
            continue
        tap_rows.append({
            "dt": row["dt"],
            "event": parsed,
        })

    blocks = []
    current_block = None

    for item in tap_rows:
        if item["event"]["is_tap_in"]:
            if current_block:
                blocks.append(current_block)
            current_block = [item]
            continue

        if current_block:
            current_block.append(item)

    if current_block:
        blocks.append(current_block)

    return blocks


def simulated_stored_value_fare_for_block(block, travel_date):
    if not block:
        return 0.0

    events = [entry["event"] for entry in block]
    station_events = [event for event in events if not event["is_bus"] and event["station"]]
    has_bus = any(event["is_bus"] for event in events)

    if not station_events:
        return fare_for_date(COMPASS_FARE_EFFECTIVE_BY_ZONE[1], travel_date)

    zone_keys = {station_zone_key(event["station"]) for event in station_events}
    zone_keys.discard(None)

    start_dt = block[0]["dt"] if block and block[0].get("dt") else None
    one_zone_override = False
    if start_dt:
        starts_after_evening_cutoff = start_dt.time() > time(18, 30)
        starts_on_weekend = start_dt.weekday() >= 5
        one_zone_override = starts_after_evening_cutoff or starts_on_weekend

    airport_only = bool(zone_keys) and zone_keys == {"airport"} and not has_bus
    if one_zone_override:
        base_fare = fare_for_date(COMPASS_FARE_EFFECTIVE_BY_ZONE[1], travel_date)
    elif airport_only:
        base_fare = 0.0
    else:
        if len(zone_keys) <= 1:
            zone_count = 1
        elif "z1" in zone_keys and ("z3a" in zone_keys or "z3b" in zone_keys):
            zone_count = 3
        else:
            zone_count = 2

        base_fare = fare_for_date(COMPASS_FARE_EFFECTIVE_BY_ZONE[zone_count], travel_date)

    add_fare = 0.0
    first_station_tap_in = next(
        (event for event in events if event["is_tap_in"] and not event["is_bus"] and event["station"]),
        None,
    )
    if first_station_tap_in and station_zone_key(first_station_tap_in["station"]) == "airport" and not airport_only:
        add_fare = AIRPORT_ADD_FARE

    return round(base_fare + add_fare, 2)


def period_balance_spent(filtered_rows):
    if not filtered_rows:
        return 0.0

    sorted_rows = sorted(filtered_rows, key=lambda item: item["dt"])
    top_balance = next((row["balance"] for row in reversed(sorted_rows) if row["balance"] is not None), None)
    bottom_balance = next((row["balance"] for row in sorted_rows if row["balance"] is not None), None)

    topups = 0.0
    bottom_index = len(sorted_rows) - 1
    for index, row in enumerate(sorted_rows):
        action_lower = str(row["action"]).strip().lower()
        if not (action_lower.startswith("loaded at") or action_lower.startswith("purchase at")):
            continue
        if index == bottom_index:
            continue
        amount_value = row["amount"]
        if amount_value is not None and amount_value > 0:
            topups += amount_value

    if top_balance is not None and bottom_balance is not None:
        spent = (bottom_balance - top_balance) + topups
    else:
        spent = topups

    return round(max(0.0, spent), 2)


def build_balance_spend_summary(file_path):
    rows = []

    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        _header = next(reader, None)

        for row in reader:
            if len(row) > 1 and not str(row[1]).strip():
                break

            if len(row) <= 5:
                continue

            timestamp_text = str(row[0]).strip()
            action_text = str(row[1]).strip() if len(row) > 1 else ""
            product_text = str(row[2]).strip() if len(row) > 2 else ""
            amount_text = str(row[4]).strip() if len(row) > 4 else ""
            balance_text = str(row[5]).strip() if len(row) > 5 else ""

            if not timestamp_text:
                continue

            try:
                dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
            except ValueError:
                continue

            rows.append({
                "dt": dt,
                "action": action_text,
                "product": product_text,
                "amount": parse_amount_value(amount_text),
                "balance": parse_balance_amount(balance_text),
            })

    if not rows:
        return {
            "stored_value_spent": 0.0,
            "pass_spend": 0.0,
            "pass_count": 0,
            "total_spent": 0.0,
            "extra_stored_value_if_no_pass": 0.0,
            "extra_stored_value_by_month": {},
            "extra_stored_value_by_day": {},
        }

    top_balance = next((row["balance"] for row in rows if row["balance"] is not None), None)
    bottom_balance = next((row["balance"] for row in reversed(rows) if row["balance"] is not None), None)

    loaded_sum = 0.0
    bottom_index = len(rows) - 1
    for index, row in enumerate(rows):
        action_lower = str(row["action"]).strip().lower()
        is_top_up_row = action_lower.startswith("loaded at") or action_lower.startswith("purchase at")
        if not is_top_up_row:
            continue

        # Exclude oldest-row top-up if it represents the initial loaded balance baseline.
        if index == bottom_index:
            continue

        amount_value = row["amount"]
        if amount_value is not None and amount_value > 0:
            loaded_sum += amount_value

    stored_value_spent = 0.0
    if top_balance is not None and bottom_balance is not None:
        stored_value_spent = (bottom_balance - top_balance) + loaded_sum
    else:
        stored_value_spent = loaded_sum

    monthly_seen = set()
    upass_seen = set()
    daypass_seen = set()
    covered_months = set()
    covered_daypasses = set()
    pass_spend = 0.0
    pass_count = 0

    for row in rows:
        product_lower = str(row["product"]).strip().lower()
        action_lower = str(row["action"]).strip().lower()
        dt = row["dt"]

        if not product_lower:
            continue

        # Do not count pass products from reload events like "Loaded at ...".
        if action_lower.startswith("loaded at"):
            continue

        if "upass" in product_lower:
            key = (dt.year, dt.month)
            if key in upass_seen:
                continue
            upass_seen.add(key)
            covered_months.add(key)
            pass_spend += fare_for_date(UPASS_FARE_EFFECTIVE, dt.date())
            pass_count += 1
            continue

        if "monthly pass" in product_lower:
            zone_match = re.search(r"([123])\s*zone", product_lower)
            zone = int(zone_match.group(1)) if zone_match else 1
            key = (dt.year, dt.month, zone)
            if key in monthly_seen:
                continue
            monthly_seen.add(key)
            covered_months.add((dt.year, dt.month))
            pass_spend += fare_for_date(MONTHLY_FARE_EFFECTIVE_BY_ZONE.get(zone, MONTHLY_FARE_EFFECTIVE_BY_ZONE[1]), dt.date())
            pass_count += 1
            continue

        if "day pass" in product_lower or "daypass" in product_lower:
            key = dt.date()
            if key in daypass_seen:
                continue
            daypass_seen.add(key)
            covered_daypasses.add(dt.date())
            pass_spend += fare_for_date(DAYPASS_FARE_EFFECTIVE, dt.date())
            pass_count += 1

    effective_daypasses = {
        day for day in covered_daypasses if (day.year, day.month) not in covered_months
    }

    def coverage_bucket(target_date):
        month_key = (target_date.year, target_date.month)
        if month_key in covered_months:
            return ("month", month_key)
        if target_date in effective_daypasses:
            return ("day", target_date)
        return None

    rows_chronological = sorted(rows, key=lambda item: item["dt"])
    trip_blocks = build_trip_blocks(rows_chronological)

    simulated_stored_value_by_month = {}
    simulated_stored_value_by_day = {}
    for block in trip_blocks:
        start_dt = block[0]["dt"]
        travel_date = start_dt.date()
        bucket = coverage_bucket(travel_date)
        if not bucket:
            continue
        bucket_kind, bucket_key = bucket
        simulated_fare = simulated_stored_value_fare_for_block(block, travel_date)
        if bucket_kind == "month":
            simulated_stored_value_by_month[bucket_key] = (
                simulated_stored_value_by_month.get(bucket_key, 0.0) + simulated_fare
            )
        else:
            simulated_stored_value_by_day[bucket_key] = (
                simulated_stored_value_by_day.get(bucket_key, 0.0) + simulated_fare
            )

    actual_balance_spent_by_month = {}
    for year, month in covered_months:
        month_rows = [
            row for row in rows
            if row["dt"].year == year and row["dt"].month == month
        ]
        actual_balance_spent_by_month[(year, month)] = period_balance_spent(month_rows)

    actual_balance_spent_by_day = {}
    for day in effective_daypasses:
        day_rows = [row for row in rows if row["dt"].date() == day]
        actual_balance_spent_by_day[day] = period_balance_spent(day_rows)

    extra_stored_value_by_month = {}
    for year, month in sorted(covered_months):
        month_key = f"{year:04d}-{month:02d}"
        simulated_value = simulated_stored_value_by_month.get((year, month), 0.0)
        actual_value = actual_balance_spent_by_month.get((year, month), 0.0)
        extra_stored_value_by_month[month_key] = round(max(0.0, simulated_value - actual_value), 2)

    extra_stored_value_by_day = {}
    for day in sorted(effective_daypasses):
        day_key = day.isoformat()
        simulated_value = simulated_stored_value_by_day.get(day, 0.0)
        actual_value = actual_balance_spent_by_day.get(day, 0.0)
        extra_stored_value_by_day[day_key] = round(max(0.0, simulated_value - actual_value), 2)

    extra_stored_value_if_no_pass = sum(extra_stored_value_by_month.values()) + sum(extra_stored_value_by_day.values())

    stored_value_spent = round(max(0.0, stored_value_spent), 2)
    pass_spend = round(max(0.0, pass_spend), 2)
    total_spent = round(stored_value_spent + pass_spend, 2)
    extra_stored_value_if_no_pass = round(max(0.0, extra_stored_value_if_no_pass), 2)

    return {
        "stored_value_spent": stored_value_spent,
        "pass_spend": pass_spend,
        "pass_count": int(pass_count),
        "total_spent": total_spent,
        "extra_stored_value_if_no_pass": extra_stored_value_if_no_pass,
        "extra_stored_value_by_month": extra_stored_value_by_month,
        "extra_stored_value_by_day": extra_stored_value_by_day,
    }


def build_pass_timeline_entries(file_path):
    rows = []

    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        _header = next(reader, None)

        for row in reader:
            if len(row) > 1 and not str(row[1]).strip():
                break

            if len(row) <= 2:
                continue

            timestamp_text = str(row[0]).strip()
            action_text = str(row[1]).strip()
            product_text = str(row[2]).strip()

            if not timestamp_text or not product_text:
                continue

            try:
                dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
            except ValueError:
                continue

            rows.append({
                "dt": dt,
                "action": action_text,
                "product": product_text,
            })

    if not rows:
        return []

    rows.sort(key=lambda item: item["dt"])

    entries = []
    monthly_seen = set()
    upass_seen = set()
    daypass_seen = set()

    for row in rows:
        product_text = str(row["product"]).strip()
        product_lower = product_text.lower()
        action_lower = str(row["action"]).strip().lower()
        dt = row["dt"]

        # Exclude reload-only rows from pass timeline entries.
        if action_lower.startswith("loaded at"):
            continue

        if "upass" in product_lower:
            key = (dt.year, dt.month)
            if key in upass_seen:
                continue
            upass_seen.add(key)
            price = fare_for_date(UPASS_FARE_EFFECTIVE, dt.date())
            entries.append({
                "label": f"UPass - {dt.strftime('%b')}",
                "date": dt.strftime("%Y-%m-%d"),
                "timestamp": dt.strftime(TIMESTAMP_FORMAT),
                "price": round(price, 2),
                "month_key": dt.strftime("%Y-%m"),
                "period_type": "month",
                "period_key": dt.strftime("%Y-%m"),
            })
            continue

        if "monthly pass" in product_lower:
            zone_match = re.search(r"([123])\s*zone", product_text, flags=re.IGNORECASE)
            zone = int(zone_match.group(1)) if zone_match else 1
            zone_label = f"{zone_match.group(1)} Zone Monthly Pass" if zone_match else "Monthly Pass"
            key = (zone_label.lower(), dt.year, dt.month)
            if key in monthly_seen:
                continue
            monthly_seen.add(key)
            price = fare_for_date(MONTHLY_FARE_EFFECTIVE_BY_ZONE.get(zone, MONTHLY_FARE_EFFECTIVE_BY_ZONE[1]), dt.date())
            entries.append({
                "label": f"{zone_label} - {dt.strftime('%b')}",
                "date": dt.strftime("%Y-%m-%d"),
                "timestamp": dt.strftime(TIMESTAMP_FORMAT),
                "price": round(price, 2),
                "month_key": dt.strftime("%Y-%m"),
                "period_type": "month",
                "period_key": dt.strftime("%Y-%m"),
            })
            continue

        if "day pass" in product_lower or "daypass" in product_lower:
            key = dt.date().isoformat()
            if key in daypass_seen:
                continue
            daypass_seen.add(key)
            price = fare_for_date(DAYPASS_FARE_EFFECTIVE, dt.date())
            entries.append({
                "label": f"Day Pass - {dt.strftime('%b')} {dt.day}",
                "date": dt.strftime("%Y-%m-%d"),
                "timestamp": dt.strftime(TIMESTAMP_FORMAT),
                "price": round(price, 2),
                "month_key": dt.strftime("%Y-%m"),
                "period_type": "day",
                "period_key": dt.strftime("%Y-%m-%d"),
            })

    return entries


def is_station_pair_tap(action_text):
    action = str(action_text or "").strip()
    lowered = action.lower()

    if not lowered.startswith("tap in at"):
        return False
    if "bus stop" in lowered:
        return False
    if "loaded" in lowered or "purchase" in lowered or "refund" in lowered:
        return False
    return True


def is_station_pair_settlement(action_text):
    action = str(action_text or "").strip().lower()
    if "bus stop" in action:
        return False
    return (
        action.startswith("tap out at")
        or action.startswith("transfer at")
        or action.startswith("missing tap out")
    )


def increment_month(month_start):
    year = month_start.year + (1 if month_start.month == 12 else 0)
    month = 1 if month_start.month == 12 else month_start.month + 1
    return datetime(year, month, 1).date()


def build_balance_time_series(file_path):
    raw_records = []

    with open(file_path, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        header = next(reader, None)
        if not header:
            return {
                "labels": [],
                "values": [],
                "granularity": "month",
                "change_labels": [],
                "change_values": [],
                "timeline_start": None,
                "timeline_days": 0,
                "change_points": [],
                "intraday_days": [],
            }

        for row in reader:
            # Mirror existing row cutoff logic: stop at first blank action row (column B).
            if len(row) > 1 and not str(row[1]).strip():
                break

            if len(row) <= 5:
                continue

            timestamp_text = str(row[0]).strip()
            if not timestamp_text:
                continue

            try:
                dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
            except ValueError:
                continue

            # Balance is expected in column F.
            amount = parse_balance_amount(row[5])
            if amount is None:
                continue

            action_text = str(row[1]).strip() if len(row) > 1 else ""
            journey_id = str(row[6]).strip() if len(row) > 6 else ""

            raw_records.append({
                "dt": dt,
                "action": action_text,
                "journey_id": journey_id,
                "balance": amount,
            })

    if not raw_records:
        return {
            "labels": [],
            "values": [],
            "granularity": "month",
            "change_labels": [],
            "change_values": [],
            "timeline_start": None,
            "timeline_days": 0,
            "change_points": [],
            "intraday_days": [],
        }

    raw_records.sort(key=lambda item: item["dt"])

    # Ignore in-journey intermediate station balances: keep only the final
    # balance state for each multi-row journey that touches station-system events.
    journey_indices = {}
    for idx, record in enumerate(raw_records):
        journey_id = record["journey_id"]
        if not journey_id:
            continue
        journey_indices.setdefault(journey_id, []).append(idx)

    journey_compacted = [True] * len(raw_records)

    def is_station_system_action(action_text):
        action = str(action_text or "").strip().lower()
        if not action:
            return False
        if "bus stop" in action:
            return False
        return (
            action.startswith("tap in at")
            or action.startswith("tap out at")
            or action.startswith("transfer at")
            or action.startswith("missing tap in")
            or action.startswith("missing tap out")
        )

    for _, indices in journey_indices.items():
        if len(indices) < 2:
            continue

        group = [raw_records[idx] for idx in indices]
        has_station_activity = any(is_station_system_action(item["action"]) for item in group)
        if not has_station_activity:
            continue

        keep_pos = len(group) - 1

        for pos, idx in enumerate(indices):
            if pos != keep_pos:
                journey_compacted[idx] = False

    # For records without JourneyId, keep the previous fallback: if a station-pair Tap in
    # is immediately followed by a settlement event with a higher balance, skip Tap in.
    records = []
    for i, current in enumerate(raw_records):
        if not journey_compacted[i]:
            continue

        skip_as_provisional = False
        if not current["journey_id"] and i + 1 < len(raw_records):
            following = raw_records[i + 1]

            if is_station_pair_tap(current["action"]) and is_station_pair_settlement(following["action"]):
                current_balance = current["balance"]
                next_balance = following["balance"]
                # Temporary charge then partial add-back pattern.
                if next_balance > current_balance:
                    skip_as_provisional = True

        if not skip_as_provisional:
            records.append((current["dt"], current["balance"]))

    if not records:
        return {
            "labels": [],
            "values": [],
            "granularity": "month",
            "change_labels": [],
            "change_values": [],
            "timeline_start": None,
            "timeline_days": 0,
            "change_points": [],
            "intraday_days": [],
        }

    start_date = records[0][0].date()
    end_date = records[-1][0].date()
    total_days = (end_date - start_date).days + 1
    granularity = "week" if total_days <= 120 else "month"

    def period_start_for(date_value):
        if granularity == "week":
            return date_value - timedelta(days=date_value.weekday())
        return datetime(date_value.year, date_value.month, 1).date()

    def period_label_for(period_start):
        if granularity == "week":
            return period_start.strftime("Week of %b %d, %Y")
        return period_start.strftime("%b %Y")

    change_labels = []
    change_values = []
    change_points = []
    previous_balance = None
    for dt, amount in records:
        if previous_balance is None or abs(amount - previous_balance) > 1e-9:
            day_index = (dt.date() - start_date).days
            change_labels.append(dt.strftime("%b-%d-%Y"))
            change_values.append(round(amount, 2))
            change_points.append({
                "x": day_index,
                "y": round(amount, 2),
                "date": dt.strftime("%b-%d-%Y"),
            })
            previous_balance = amount

    intraday_days = []
    points_by_day = OrderedDict()
    for record in raw_records:
        day_key = record["dt"].date().isoformat()
        if day_key not in points_by_day:
            points_by_day[day_key] = []

        time_fraction = (
            record["dt"].hour
            + (record["dt"].minute / 60.0)
            + (record["dt"].second / 3600.0)
        )

        points_by_day[day_key].append({
            "timestamp": record["dt"].strftime("%b-%d-%Y %I:%M %p"),
            "time": record["dt"].strftime("%I:%M %p"),
            "hour_value": round(time_fraction, 4),
            "balance": round(record["balance"], 2),
            "action": record["action"],
        })

    for day_key, points in points_by_day.items():
        date_value = datetime.strptime(day_key, "%Y-%m-%d").date()
        change_count = 0
        previous_value = None
        for point in points:
            value = point["balance"]
            if previous_value is not None and abs(value - previous_value) > 1e-9:
                change_count += 1
            previous_value = value

        intraday_days.append({
            "date": day_key,
            "display_date": date_value.strftime("%b %d, %Y"),
            "day_index": (date_value - start_date).days,
            "change_count": change_count,
            "points": points,
        })

    period_latest = {}
    for dt, amount in records:
        current_date = dt.date()
        period_key = period_start_for(current_date)

        existing = period_latest.get(period_key)
        if not existing or dt > existing[0]:
            period_latest[period_key] = (dt, amount)

    if granularity == "week":
        period_cursor = start_date - timedelta(days=start_date.weekday())
        final_period = end_date - timedelta(days=end_date.weekday())
    else:
        period_cursor = datetime(start_date.year, start_date.month, 1).date()
        final_period = datetime(end_date.year, end_date.month, 1).date()

    labels = []
    values = []
    carry_balance = None

    while period_cursor <= final_period:
        if period_cursor in period_latest:
            carry_balance = period_latest[period_cursor][1]

        labels.append(period_label_for(period_cursor))

        values.append(round(carry_balance, 2) if carry_balance is not None else None)

        if granularity == "week":
            period_cursor = period_cursor + timedelta(days=7)
        else:
            period_cursor = increment_month(period_cursor)

    return {
        "labels": labels,
        "values": values,
        "granularity": granularity,
        "change_labels": change_labels,
        "change_values": change_values,
        "timeline_start": start_date.isoformat(),
        "timeline_days": total_days,
        "change_points": change_points,
        "intraday_days": intraday_days,
    }


@app.errorhandler(413)
def file_too_large(_error):
    flash("CSV is too large. Maximum file size is 5 MB.")
    return redirect(url_for("upload_file"))

@app.route("/howto")
def howto():
    return render_template("howto.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/more")
def more():
    return render_template("more.html")


@app.route("/more/upload-multiple", methods=["POST"])
def more_upload_multiple():
    files = request.files.getlist("files")
    valid_files = [uploaded for uploaded in files if uploaded and uploaded.filename]

    if len(valid_files) < 2:
        flash("Please add at least two CSV files.")
        return redirect(url_for("more"))

    for uploaded in valid_files:
        _, extension = os.path.splitext(uploaded.filename.lower())
        if extension not in ALLOWED_EXTENSIONS:
            flash("All files must be CSV.")
            return redirect(url_for("more"))

    selected_names = [secure_filename(uploaded.filename) for uploaded in valid_files]
    total_trips = 0
    total_ssw_trips = 0
    total_skytrain_trips = 0
    total_seabus_trips = 0
    total_wce_trips = 0
    total_minutes = 0.0
    usage_by_file = []
    compare_tap_data = []
    map_file_station_names = []

    chart_colors = [
        "#3b82f6",
        "#22c55e",
        "#ef4444",
        "#f59e0b",
        "#8b5cf6",
        "#14b8a6",
        "#ec4899",
        "#84cc16",
    ]

    for uploaded in valid_files:
        try:
            rows = parse_uploaded_csv_rows(uploaded)
        except UnicodeDecodeError:
            flash("CSV must be UTF-8 encoded.")
            return redirect(url_for("more"))
        except csv.Error:
            flash("CSV parsing failed due to malformed CSV structure.")
            return redirect(url_for("more"))

        summary_metrics = calculate_summary_metrics_from_rows(rows)
        total_trips += summary_metrics["trips"]
        total_ssw_trips += summary_metrics["ssw_trips"]
        total_skytrain_trips += summary_metrics["skytrain_trips"]
        total_seabus_trips += summary_metrics["seabus_trips"]
        total_wce_trips += summary_metrics["wce_trips"]
        total_minutes += calculate_minutes_from_rows(rows)

        usage_breakdown = build_usage_breakdowns_from_rows(rows)
        compare_taps = build_compare_taps_from_rows(rows)
        compare_complete_trips = build_compare_complete_trips_from_rows(rows)

        visited_station_names = set()
        for station_name, count in usage_breakdown["station_counts"].items():
            if not count:
                continue
            location = utils.get_station_location(station_name)
            if location:
                visited_station_names.add(location["name"])

        usage_by_file.append({
            "label": secure_filename(uploaded.filename),
            "color": chart_colors[(len(usage_by_file)) % len(chart_colors)],
            "trips": summary_metrics["trips"],
            "ssw_trips": summary_metrics["ssw_trips"],
            "skytrain_trips": summary_metrics["skytrain_trips"],
            "seabus_trips": summary_metrics["seabus_trips"],
            "wce_trips": summary_metrics["wce_trips"],
            "station_counts": usage_breakdown["station_counts"],
            "hour_counts": usage_breakdown["hour_counts"],
            "weekday_counts": usage_breakdown["weekday_counts"],
            "month_counts": usage_breakdown["month_counts"],
        })
        map_file_station_names.append(sorted(visited_station_names))
        compare_tap_data.append({
            "label": secure_filename(uploaded.filename),
            "events": compare_taps,
            "complete_trips": compare_complete_trips,
        })

    days, hours, mins = format_duration_days_hours_minutes(total_minutes)
    percent_ssw = (total_ssw_trips / total_trips) * 100 if total_trips else 0

    station_total_counts = Counter()
    for file_usage in usage_by_file:
        station_total_counts.update(file_usage["station_counts"])

    station_labels = [
        station for station, _count in sorted(
            station_total_counts.items(),
            key=lambda item: (-item[1], item[0])
        )
    ]

    hour_labels = [
        f"{(hour % 12) or 12} {'AM' if hour < 12 else 'PM'}"
        for hour in range(24)
    ]
    weekday_labels = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    month_labels = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]

    station_datasets = []
    hour_datasets = []
    weekday_datasets = []
    month_datasets = []

    pie_labels = [file_usage["label"] for file_usage in usage_by_file]
    pie_colors = [file_usage["color"] for file_usage in usage_by_file]
    pie_total_trips = [file_usage["trips"] for file_usage in usage_by_file]
    pie_bus_only = [max(0, file_usage["trips"] - file_usage["ssw_trips"]) for file_usage in usage_by_file]
    pie_skytrain = [file_usage["skytrain_trips"] for file_usage in usage_by_file]
    pie_seabus = [file_usage["seabus_trips"] for file_usage in usage_by_file]
    pie_wce = [file_usage["wce_trips"] for file_usage in usage_by_file]
    shared_pair_metrics = {}
    shared_pair_station_names = {}

    for i in range(len(compare_tap_data)):
        for j in range(i + 1, len(compare_tap_data)):
            matches = build_shared_trip_matches(
                compare_tap_data[i].get("events", []),
                compare_tap_data[j].get("events", []),
            )
            matches = annotate_match_trip_status(
                matches,
                compare_tap_data[i].get("events", []),
                compare_tap_data[j].get("events", []),
            )
            exact_matches = [match for match in matches if bool(match.get("is_exact_trip"))]
            match_rows = build_rows_from_shared_matches(exact_matches, side="a")
            metrics = calculate_summary_metrics_from_rows(match_rows)
            minutes = int(round(calculate_minutes_from_rows(match_rows)))
            pair_key = f"{i}-{j}"
            shared_pair_metrics[pair_key] = {
                "trips": int(metrics["trips"]),
                "ssw_trips": int(metrics["ssw_trips"]),
                "skytrain_trips": int(metrics["skytrain_trips"]),
                "seabus_trips": int(metrics["seabus_trips"]),
                "wce_trips": int(metrics["wce_trips"]),
                "percent_ssw": round((metrics["ssw_trips"] / metrics["trips"] * 100) if metrics["trips"] else 0, 1),
                "minutes": minutes,
            }

            shared_trip_stations = set()
            for match in exact_matches:
                if match.get("tap_name_a"):
                    location = utils.get_station_location(match["tap_name_a"])
                    if location:
                        shared_trip_stations.add(location["name"])
                if match.get("tap_name_b"):
                    location = utils.get_station_location(match["tap_name_b"])
                    if location:
                        shared_trip_stations.add(location["name"])
            shared_pair_station_names[pair_key] = sorted(shared_trip_stations)

    for file_usage in usage_by_file:
        station_datasets.append({
            "label": file_usage["label"],
            "backgroundColor": file_usage["color"],
            "data": [file_usage["station_counts"].get(label, 0) for label in station_labels],
        })
        hour_datasets.append({
            "label": file_usage["label"],
            "backgroundColor": file_usage["color"],
            "data": file_usage["hour_counts"],
        })
        weekday_datasets.append({
            "label": file_usage["label"],
            "backgroundColor": file_usage["color"],
            "data": file_usage["weekday_counts"],
        })
        month_datasets.append({
            "label": file_usage["label"],
            "backgroundColor": file_usage["color"],
            "data": file_usage["month_counts"],
        })

    station_chart_height = max(420, len(station_labels) * 30)

    map_station_points = []
    seen_map_station_names = set()
    for station_name in utils.SkyTrainStns:
        location = utils.get_station_location(station_name)
        if not location:
            continue
        source_name = location["name"]
        if source_name in seen_map_station_names:
            continue
        seen_map_station_names.add(source_name)
        map_station_points.append({
            "name": station_name,
            "source_name": source_name,
            "lat": location["lat"],
            "lon": location["lon"],
        })

    return render_template(
        "more_multi_results.html",
        total_trips=total_trips,
        total_ssw_trips=total_ssw_trips,
        percent_ssw=percent_ssw,
        total_skytrain_trips=total_skytrain_trips,
        total_seabus_trips=total_seabus_trips,
        total_wce_trips=total_wce_trips,
        total_days=days,
        total_hours=hours,
        total_mins=mins,
        selected_count=len(selected_names),
        station_labels=station_labels,
        hour_labels=hour_labels,
        weekday_labels=weekday_labels,
        month_labels=month_labels,
        station_datasets=station_datasets,
        hour_datasets=hour_datasets,
        weekday_datasets=weekday_datasets,
        month_datasets=month_datasets,
        station_chart_height=station_chart_height,
        pie_labels=pie_labels,
        pie_colors=pie_colors,
        pie_total_trips=pie_total_trips,
        pie_bus_only=pie_bus_only,
        pie_skytrain=pie_skytrain,
        pie_seabus=pie_seabus,
        pie_wce=pie_wce,
        compare_tap_data=compare_tap_data,
        shared_pair_metrics=shared_pair_metrics,
        map_station_points=map_station_points,
        map_file_station_names=map_file_station_names,
        shared_pair_station_names=shared_pair_station_names,
    )


@app.route("/more/upload-slideshow", methods=["POST"])
def more_upload_slideshow():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        flash("Please choose a CSV file to upload.")
        return redirect(url_for("more"))

    _, extension = os.path.splitext(uploaded.filename.lower())
    if extension not in ALLOWED_EXTENSIONS:
        flash("Upload a CSV file.")
        return redirect(url_for("more"))

    selected_name = secure_filename(uploaded.filename)

    try:
        rows = parse_uploaded_csv_rows(uploaded)
    except UnicodeDecodeError:
        flash("CSV must be UTF-8 encoded.")
        return redirect(url_for("more"))
    except csv.Error:
        flash("CSV parsing failed due to malformed CSV structure.")
        return redirect(url_for("more"))

    slideshow_steps = build_slideshow_steps_from_rows(rows)

    if not slideshow_steps:
        flash("No slideshow rows found. Use a Compass CSV with transit tap rows.")
        return redirect(url_for("more"))

    return render_template(
        "more_slideshow.html",
        selected_name=selected_name,
        slideshow_steps=slideshow_steps,
    )


SLIDESHOW_EXCLUDED_KEYWORDS = ("loaded", "sv", "cos", "purchase")

SLIDESHOW_FIXED_LOCATIONS = {
    "lonsdale quay": {
        "name": "Lonsdale Quay",
        "lat": 49.310161,
        "lon": -123.083358,
    },
    "lonsdale quay northbound": {
        "name": "Lonsdale Quay",
        "lat": 49.310161,
        "lon": -123.083358,
    },
    "lonsdale quay southbound": {
        "name": "Lonsdale Quay",
        "lat": 49.310161,
        "lon": -123.083358,
    },
}


def should_exclude_slideshow_action(action_text):
    lowered = str(action_text).lower()
    return any(keyword in lowered for keyword in SLIDESHOW_EXCLUDED_KEYWORDS)


def classify_slideshow_marker_type(action_text, tap_name):
    lowered_action = str(action_text).lower()
    lowered_name = str(tap_name).lower()

    if "bus stop" in lowered_action or "bus stop" in lowered_name:
        return "bus"
    if lowered_name.endswith("quay"):
        return "seabus"
    if "wce" in lowered_action or "wce" in lowered_name:
        return "wce"
    if lowered_name.endswith("station"):
        return "wce"
    if lowered_name.endswith("stn"):
        return "station"
    return "station"


def resolve_slideshow_location(action_text):
    text = str(action_text).strip()
    if not text:
        return {
            "display_name": "Unknown",
            "warning": "stop Unknown not found",
            "location": None,
            "marker_type": "station",
        }

    if " at " in text:
        tap_name = text.split(" at ", 1)[1].strip()
    else:
        tap_name = text

    marker_type = classify_slideshow_marker_type(text, tap_name)

    if marker_type == "bus":
        code_match = re.search(r"\d{5}", text)
        stop_code = code_match.group() if code_match else ""
        display_name = stop_code if stop_code else tap_name
        location = utils.get_bus_stop_location(stop_code) if stop_code else None
        if location:
            return {
                "display_name": location["name"],
                "warning": "",
                "location": location,
                "marker_type": marker_type,
            }
        return {
            "display_name": display_name,
            "warning": f"stop {display_name} not found",
            "location": None,
            "marker_type": marker_type,
        }

    clean_name = tap_name.replace("(Missing)", "").strip() if tap_name else ""
    if not clean_name:
        clean_name = "Unknown"

    fixed_location = SLIDESHOW_FIXED_LOCATIONS.get(clean_name.lower())
    if fixed_location:
        return {
            "display_name": fixed_location["name"],
            "warning": "",
            "location": fixed_location,
            "marker_type": marker_type,
        }

    location = utils.get_station_location(clean_name)
    if location:
        return {
            "display_name": clean_name,
            "warning": "",
            "location": location,
            "marker_type": marker_type,
        }

    return {
        "display_name": clean_name,
        "warning": f"stop {clean_name} not found",
        "location": None,
        "marker_type": marker_type,
    }


def build_slideshow_steps_from_rows(rows):
    if len(rows) <= 1:
        return []

    steps = []
    for row in rows[1:]:
        if len(row) < 2:
            continue

        timestamp_text = str(row[0]).strip()
        action_text = str(row[1]).strip()

        if not action_text:
            break

        if should_exclude_slideshow_action(action_text):
            continue

        resolved = resolve_slideshow_location(action_text)
        location = resolved["location"]

        step = {
            "timestamp": timestamp_text,
            "action": action_text,
            "name": resolved["display_name"],
            "marker_type": resolved["marker_type"],
            "warning": resolved["warning"],
            "found": bool(location),
            "lat": location["lat"] if location else None,
            "lon": location["lon"] if location else None,
        }
        steps.append(step)

    return steps


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file was uploaded.")
            return redirect(url_for("upload_file"))

        file = request.files["file"]
        if not file.filename:
            flash("Please choose a CSV file to upload.")
            return redirect(url_for("upload_file"))

        _, extension = os.path.splitext(file.filename.lower())
        if extension not in ALLOWED_EXTENSIONS:
            flash("Upload a CSV file.")
            return redirect(url_for("upload_file"))

        safe_name = secure_filename(file.filename)
        if not safe_name:
            flash("Invalid file name.")
            return redirect(url_for("upload_file"))

        fileName = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4().hex}_{safe_name}")

        try:
            file.save(fileName)
        except OSError:
            flash("Could not save uploaded CSV.")
            return redirect(url_for("upload_file"))

        is_valid, validation_error = validate_compass_csv(fileName)
        if is_valid:
            
            # 🔽 This is where you add your custom logic
            # --------------------------------------------------
            # Example: Read CSV and process it
            trip_rows = []
            with open(fileName, newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # skip header row
                for row in reader:
                    if len(row) < 2 or row[1].strip() == "":
                        break  # stop at first empty cell
                    timestamp_text = str(row[0]).strip()
                    action_text = str(row[1]).strip()

                    parsed_dt = None
                    if timestamp_text:
                        try:
                            parsed_dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
                        except ValueError:
                            parsed_dt = None

                    trip_rows.append({
                        "timestamp": parsed_dt,
                        "action": action_text,
                    })

            trips = [entry["action"] for entry in trip_rows]

                        # All SkyTrain/Seabus/WCE taps
            trips = utils.remove_refund_pairs(trips)

            # All SkyTrain/Seabus/WCE taps
            SSWTaps = [stop for stop in trips if "Bus Stop" not in stop and "Loaded" not in stop 
                    and "SV" not in stop and "COS" not in stop and "Purchase" not in stop]

            SSWBusTaps = [stop for stop in trips if "Loaded" not in stop 
                    and "SV" not in stop and "COS" not in stop and "Purchase" not in stop]

            #printOutList(SSWTaps)

            SSWtripsNum = len(SSWTaps)/2

            SSWBusTapsNum = len(SSWBusTaps) - len(SSWTaps)

            TripsNum = SSWBusTapsNum + SSWtripsNum

            SSWTapsNames = utils.ProcessList(SSWTaps)

            stationLastUsedByName = {}
            swceLastUsedByName = {}
            busStopLastUsedById = {}
            cleaned_trip_rows = []
            skip_refund_tap_in = False

            for entry in trip_rows:
                action = entry["action"]
                lowered = action.lower()

                if "refund" in lowered:
                    skip_refund_tap_in = True
                    continue

                if skip_refund_tap_in:
                    if lowered.startswith("tap in at"):
                        skip_refund_tap_in = False
                        continue
                    skip_refund_tap_in = False

                cleaned_trip_rows.append(entry)

                processed_name = action
                if "Missing" in action:
                    processed_name = "(Missing)"
                elif "at" in action:
                    processed_name = action.split("at", 1)[1].strip()

                processed_name = utils.canonicalize_station_name(processed_name)

                entry_dt = entry["timestamp"]
                if not entry_dt:
                    continue

                if processed_name.endswith("Stn"):
                    previous_station_dt = stationLastUsedByName.get(processed_name)
                    if not previous_station_dt or entry_dt > previous_station_dt:
                        stationLastUsedByName[processed_name] = entry_dt

                if processed_name.endswith("Quay") or processed_name.endswith("Stn - WCE") or processed_name.endswith("Station"):
                    previous_swce_dt = swceLastUsedByName.get(processed_name)
                    if not previous_swce_dt or entry_dt > previous_swce_dt:
                        swceLastUsedByName[processed_name] = entry_dt

                if "Bus Stop" in action:
                    match = re.search(r"\d{5}", action)
                    if match:
                        stop_id = match.group()
                        previous_bus_dt = busStopLastUsedById.get(stop_id)
                        if not previous_bus_dt or entry_dt > previous_bus_dt:
                            busStopLastUsedById[stop_id] = entry_dt

            # Extract and count bus stops
            BusStops = [stop for stop in trips if "Bus Stop" in stop]
            BusStopNumbers = []

            for stop in BusStops:
                # Extract 5-digit number from bus stop entry (e.g., "Bus Stop 50123")
                match = re.search(r'\d{5}', stop)
                if match:
                    BusStopNumbers.append(match.group())
            
            # Count bus stops by their 5-digit number
            BusStopCounts = utils.CountElementsInList(BusStopNumbers)
            BusStopCounts = sorted(
                BusStopCounts,
                key=lambda item: (
                    -item[1],
                    -(busStopLastUsedById.get(item[0], datetime(1970, 1, 1))).timestamp(),
                    item[0],
                )
            )
            
            # Get top 10 bus stops and map them to their names
            Top10BusStops = BusStopCounts[:10]
            Top10BusStopsWithNames = []
            for stop_id, count in Top10BusStops:
                # Try to get the stop name from the dictionary, fallback to "Bus Stop {id}"
                stop_name = utils.busStopNames.get(stop_id, f"Bus Stop {stop_id}")
                Top10BusStopsWithNames.append((stop_name, stop_id, count))

            RemainingBusStops = BusStopCounts[10:]
            RemainingBusStopsWithNames = []
            for stop_id, count in RemainingBusStops:
                stop_name = utils.busStopNames.get(stop_id, f"Bus Stop {stop_id}")
                RemainingBusStopsWithNames.append((stop_name, stop_id, count))

            topBusStopMapPoints = []
            for rank, (stop_name, stop_id, count) in enumerate(Top10BusStopsWithNames, start=1):
                location = utils.get_bus_stop_location(stop_id)
                if not location:
                    continue
                last_used_meta = format_last_used_for_display(busStopLastUsedById.get(stop_id))
                topBusStopMapPoints.append({
                    "rank": rank,
                    "name": stop_name,
                    "stop_id": stop_id,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "last_used_timestamp": last_used_meta["timestamp"],
                    "last_used_days_ago": last_used_meta["days_ago"],
                    "last_used_relative": last_used_meta["relative"],
                    "last_used_display": last_used_meta["display"],
                })

            remainingBusStopMapPoints = []
            for rank, (stop_name, stop_id, count) in enumerate(RemainingBusStopsWithNames, start=11):
                location = utils.get_bus_stop_location(stop_id)
                if not location:
                    continue
                last_used_meta = format_last_used_for_display(busStopLastUsedById.get(stop_id))
                remainingBusStopMapPoints.append({
                    "rank": rank,
                    "name": stop_name,
                    "stop_id": stop_id,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "last_used_timestamp": last_used_meta["timestamp"],
                    "last_used_days_ago": last_used_meta["days_ago"],
                    "last_used_relative": last_used_meta["relative"],
                    "last_used_display": last_used_meta["display"],
                })

            #utils.printOutList(SSWTapsNames) #print out every SSW tap name

            SeabusWSkyTrain = []

            # Considering seabus trips that includes seabus + skytrain trip

            for i in range(0, len(SSWTapsNames), 2):
                first = SSWTapsNames[i]
                second = SSWTapsNames[i+1] if i+1 < len(SSWTapsNames) else ""
                
                # Only include if "Lonsdale" is in the pair and second element is valid
                if ("Lonsdale" in first or "Lonsdale" in second) and \
                "Waterfront" not in first and "Waterfront" not in second and \
                "Missing" not in first and "Missing" not in second:
                    
                    if "Lonsdale" in first:
                        SeabusWSkyTrain.append(f"{first} & {second} (at index {i+1})")
                    else:
                        SeabusWSkyTrain.append(f"{first} & {second} (at index {i+1})")  # keeps pair order

            #printOutList(SeabusWSkyTrain)

            TripsNum += len(SeabusWSkyTrain)

            SSWtripsNum += len(SeabusWSkyTrain)

            # Counting types of trips in SSWTapsNames

            # Step 1: Count normally
            SkytrainTripsNum = 0
            SeabusTripsNum = 0
            WCETripsNum = 0

            for stop in SSWTapsNames:
                if stop.endswith("Stn"):
                    SkytrainTripsNum += 1
                elif stop.endswith("Quay"):
                    SeabusTripsNum += 1
                elif stop.endswith("Station") or stop.endswith("Stn - WCE"):
                    WCETripsNum += 1

            # Step 2: Count the other element in pair if one is "Missing"
            MissingPairs = []

            for i in range(0, len(SSWTapsNames), 2):
                first = SSWTapsNames[i]
                second = SSWTapsNames[i+1] if i+1 < len(SSWTapsNames) else ""
                
                # Check if one element contains "Missing"
                if "Missing" in first:
                    other = second
                    MissingPairs.append(f"{first} & {other} (at index {i+1})")
                elif "Missing" in second:
                    other = first
                    MissingPairs.append(f"{other} & {second} (at index {i+1})")
                else:
                    continue  # no missing, skip

                # Count the other element again
                if other.endswith("Stn") or other.endswith("Quay"):
                    SkytrainTripsNum += 1
                elif other.endswith("Station") or other.endswith("Stn - WCE"):
                    WCETripsNum += 1


            # Step 3a: Adjust for special WCE trip cases

            for i in range(1,len(SSWTapsNames)):
                if ("Waterfront Stn - WCE" in SSWTapsNames[i] and "Transfer" in SSWTaps[i]):
                    SkytrainTripsNum, TripsNum, SSWtripsNum, WCETripsNum = utils.adjust_wce_eastbound(SSWTapsNames,i,SkytrainTripsNum,TripsNum,SSWtripsNum,WCETripsNum)
                elif ("Moody" in SSWTapsNames[i] and "Station" in SSWTapsNames[i] and "Transfer" in SSWTaps[i]):
                    SkytrainTripsNum, TripsNum, SSWtripsNum, WCETripsNum = utils.adjust_wce_westbound(SSWTapsNames,i,SkytrainTripsNum,TripsNum,SSWtripsNum,WCETripsNum)


            SkytrainTripsNum += 2*len(SeabusWSkyTrain) - SeabusTripsNum # remove seabus without skytrain

            SkytrainTripsNum /= 2
            WCETripsNum /= 2

            #print("------------------------------")



            #print("Skytrain trips:", SkytrainTripsNum)      #test lines
            #print("Seabus trips:", SeabusTripsNum)
            #print("WCE trips:", WCETripsNum)
            #print("\nPairs containing 'Missing':")
            #for pair in MissingPairs:
            #    print(pair)

            StationsCount = utils.CountElementsInList(SSWTapsNames)
            #utils.PrintElements(StationsCount)

            #splitting between SkyTrain stns and WCE/Seabus stns

            SkyTrainStns = []
            SWCEStns = []

            for name, count in StationsCount:
                if name.endswith("Stn"):
                    SkyTrainStns.append((name, count))
                elif name.endswith("Quay") or name.endswith("Stn - WCE") or name.endswith("Station"):
                    SWCEStns.append((name, count))

            #utils.PrintElements(SkyTrainStns)
            #utils.PrintElements(SWCEStns)

            #extracting timestamps of compass card usage: each hour of the day

            df = pd.read_csv(fileName, header=None)  # no header row

            # Skip header row (Excel row 2 → index 1 onward)
            df = df.iloc[1:]

            # Stop at first empty cell in column A
            colA = df[0].astype(str).str.strip()
            empty_mask = (colA == "") | (colA == "nan")

            if empty_mask.any():
                first_empty = empty_mask.idxmax()
                df = df.loc[:first_empty - 1]

            parsed_records = []
            for _, row in df.iterrows():
                timestamp_text = str(row[0]).strip() if len(row) > 0 else ""
                action_text = str(row[1]).strip() if len(row) > 1 else ""

                if not timestamp_text or not action_text:
                    continue

                try:
                    parsed_dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
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

            result = build_hourly_trip_timestamps(parsed_records)

            filtered_df = pd.DataFrame(parsed_records)

            allNighterTransitUses = 0
            midnightSkyTrainUses = 0
            firstTrainSkyTrainUses = 0

            for _, row in filtered_df.iterrows():
                timestamp_text = str(row["timestamp_text"]).strip()
                action_text = str(row["action"]).strip()

                if "out" in action_text.lower():
                    continue

                if not timestamp_text:
                    continue

                dt = datetime.strptime(timestamp_text, TIMESTAMP_FORMAT)
                hour = dt.hour

                if 2 <= hour < 4:
                    allNighterTransitUses += 1

                isSkyTrainTap = (
                    "Stn" in action_text
                    and "Bus Stop" not in action_text
                    and "WCE" not in action_text
                    and "Quay" not in action_text
                )

                if isSkyTrainTap:
                    if hour < 3:
                        midnightSkyTrainUses += 1
                    if 4 <= hour < 6:
                        firstTrainSkyTrainUses += 1

            #print(result)
            #print("==============================")

            hour_counts = Counter()
            def count_by_hour_all(timestamps):

                # Parse timestamps
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, TIMESTAMP_FORMAT)
                    hour_counts[dt.hour] += 1

                # Print all 24 hours INCLUDING zeros
                for hour in range(24):
                    # Convert 24h → 12h format
                    hour_12 = hour % 12
                    hour_12 = 12 if hour_12 == 0 else hour_12

                    suffix = "AM" if hour < 12 else "PM"

                    #print(f"{hour_12:02d}:00–{hour_12:02d}:59 {suffix} → {hour_counts.get(hour, 0)}")

            hourly = count_by_hour_all(result)

            #print("==============================")

            weekday_counts = Counter()
            def count_by_weekday(timestamps):

                # Parse timestamps and count weekdays
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, TIMESTAMP_FORMAT)
                    weekday_counts[dt.weekday()] += 1  # Monday = 0, Sunday = 6

                # Day labels
                days = ["Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday"]

                # Print all 7 days including zero-count ones
                # for i, day in enumerate(days):
                #     print(f"{day}: {weekday_counts.get(i, 0)}")

            count_by_weekday(result)

            # 7 x 24 matrix: each weekday has hourly usage counts
            day_hour_values = [[0 for _ in range(24)] for _ in range(7)]
            for ts in result:
                dt = datetime.strptime(ts.strip(), TIMESTAMP_FORMAT)
                day_hour_values[dt.weekday()][dt.hour] += 1

            #print("==============================")
            month_counts = Counter()

            def count_by_month(timestamps):

                # Parse timestamps and count months
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, TIMESTAMP_FORMAT)
                    month_counts[dt.month - 1] += 1   # Jan = 0, Dec = 11

                # Month labels
                months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

                # Print all 12 months including zero-count ones
                #for i, month in enumerate(months):
                #    print(f"{month}: {month_counts.get(i, 0)}")

                return month_counts
            
            count_by_month(result)

            #Counting different days used transit
            def count_unique_days(timestamps):
                unique_days = set()

                for ts in timestamps:
                    dt = datetime.strptime(ts, TIMESTAMP_FORMAT)
                    day_only = dt.date()  # strips off time, keeps just yyyy-mm-dd
                    unique_days.add(day_only)

                return len(unique_days)

            countDays = count_unique_days(result)

            #Counting longest streak
            def longest_transit_streak_with_dates(timestamps):
                # Convert timestamps → unique dates
                dates = set()
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
                    dates.add(dt.date())

                if not dates:
                    return 0, None, None

                sorted_dates = sorted(dates)

                longest = 1
                current = 1

                longest_start = sorted_dates[0]
                longest_end = sorted_dates[0]

                current_start = sorted_dates[0]

                for i in range(1, len(sorted_dates)):
                    if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
                        current += 1
                    else:
                        current = 1
                        current_start = sorted_dates[i]

                    if current > longest:
                        longest = current
                        longest_start = current_start
                        longest_end = sorted_dates[i]

                return longest, longest_start, longest_end

            def has_full_month_coverage(timestamps):
                used_dates = set()
                for ts in timestamps:
                    dt = datetime.strptime(ts.strip(), TIMESTAMP_FORMAT)
                    used_dates.add(dt.date())

                if not used_dates:
                    return False

                months_with_usage = {(d.year, d.month) for d in used_dates}
                for year, month in months_with_usage:
                    days_in_month = calendar.monthrange(year, month)[1]
                    if all(datetime(year, month, day).date() in used_dates for day in range(1, days_in_month + 1)):
                        return True

                return False

            #Getting top 5 used SkyTrain Stns

            sortedSkyTrainStns = sorted(
                SkyTrainStns,
                key=lambda item: (
                    -item[1],
                    -(stationLastUsedByName.get(item[0], datetime(1970, 1, 1))).timestamp(),
                    item[0],
                )
            )

            Top5SkyTrainStns = sortedSkyTrainStns[:5]

            RemainingSkyTrainStns = sortedSkyTrainStns[5:]

            topStationMapPoints = []
            for rank, (name, count) in enumerate(Top5SkyTrainStns, start=1):
                location = utils.get_station_location(name)
                if not location:
                    continue
                last_used_meta = format_last_used_for_display(stationLastUsedByName.get(name))
                topStationMapPoints.append({
                    "rank": rank,
                    "name": name,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "source_name": location["name"],
                    "last_used_timestamp": last_used_meta["timestamp"],
                    "last_used_days_ago": last_used_meta["days_ago"],
                    "last_used_relative": last_used_meta["relative"],
                    "last_used_display": last_used_meta["display"],
                })

            remainingStationMapPoints = []
            for rank, (name, count) in enumerate(RemainingSkyTrainStns, start=6):
                location = utils.get_station_location(name)
                if not location:
                    continue
                last_used_meta = format_last_used_for_display(stationLastUsedByName.get(name))
                remainingStationMapPoints.append({
                    "rank": rank,
                    "name": name,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "source_name": location["name"],
                    "last_used_timestamp": last_used_meta["timestamp"],
                    "last_used_days_ago": last_used_meta["days_ago"],
                    "last_used_relative": last_used_meta["relative"],
                    "last_used_display": last_used_meta["display"],
                })

            #counting minutes spent on SSW
            
            def total_minutes_spent(fileName):
                total_minutes = 0.0

                with open(fileName, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)

                # Skip header row
                data = rows[1:]

                for i in range(len(data) - 1):
                    timestamp = data[i][0].strip()   # Column A
                    action = data[i][1].strip().lower()  # Column B

                    # Only end-of-trip rows
                    if "out" in action and "missing" not in action:
                        ts_out = datetime.strptime(timestamp, TIMESTAMP_FORMAT)
                        ts_in = datetime.strptime(data[i + 1][0].strip(), TIMESTAMP_FORMAT)

                        diff_minutes = (ts_out - ts_in).total_seconds() / 60
                        total_minutes += diff_minutes

                return round(total_minutes, 1)

            # --- Top station pairs (unordered) for rows where action contains "out" ---
            def top_station_pairs(fileName, top_n=10):
                # Read CSV rows (skip header)
                with open(fileName, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    rows = list(reader)[1:]

                pair_counts = Counter()

                # iterate up to the penultimate row so we can look at the next row
                for i in range(0, len(rows) - 1):
                    action = str(rows[i][1]).strip()
                    if "out" in action.lower() and "missing" not in action.lower():
                        next_action = str(rows[i + 1][1]).strip()

                        # Normalize names using utils.ProcessList to extract text after 'at'
                        first_name, second_name = utils.ProcessList([action, next_action])

                        # Keep only meaningful station-like entries OR include Missing
                        def is_station_like(name):
                            name = name or ""
                            return (name.endswith("Stn") or name.endswith("Quay") or name.endswith("Station") or "Missing" in name)

                        if not (is_station_like(first_name) or is_station_like(second_name)):
                            # skip pairs that are not SSW station types
                            continue

                        # Use unordered pair (direction doesn't matter)
                        pair_key = tuple(sorted([first_name, second_name]))
                        pair_counts[pair_key] += 1

                # Produce sorted list: by count desc, then names
                pairs_sorted = sorted(pair_counts.items(), key=lambda x: (-x[1], x[0]))[:top_n]
                return pairs_sorted

            Top10StationPairs = top_station_pairs(fileName, top_n=10)

            allSkytrainPairCounts = all_skytrain_station_pair_counts(fileName)
            segmentUses, segmentMinutes, shortestPairMinutes = build_segment_usage_from_pairs(allSkytrainPairCounts)
            skytrainSegmentUsage = build_segment_usage_by_csv_name(segmentUses, segmentMinutes)

            UsageDict = dict(SkyTrainStns)

            UnusedStations = [stn for stn in utils.SkyTrainStns if UsageDict.get(stn, 0) == 0]

            wceStationCanonical = [
                "Waterfront Stn - WCE",
                "Moody Centre Station",
                "Coquitlam Central Station",
                "Port Coquitlam Station",
                "Pitt Meadows Station",
                "Maple Meadows Station",
                "Mission City Station",
            ]

            wceVisitedStations = set()
            for station_name in SSWTapsNames:
                normalized = station_name.strip().lower()
                if "waterfront" in normalized and "wce" in normalized:
                    wceVisitedStations.add("Waterfront Stn - WCE")
                elif "moody" in normalized and "station" in normalized:
                    wceVisitedStations.add("Moody Centre Station")
                elif "coquitlam central station" in normalized:
                    wceVisitedStations.add("Coquitlam Central Station")
                elif "port coquitlam station" in normalized:
                    wceVisitedStations.add("Port Coquitlam Station")
                elif "pitt meadows station" in normalized:
                    wceVisitedStations.add("Pitt Meadows Station")
                elif "maple meadows station" in normalized:
                    wceVisitedStations.add("Maple Meadows Station")
                elif "mission city station" in normalized:
                    wceVisitedStations.add("Mission City Station")

            unusedWCEStations = [station for station in wceStationCanonical if station not in wceVisitedStations]

            SWCEUsageDict = {name.lower(): count for name, count in SWCEStns}

            def get_swce_usage(*aliases):
                for alias in aliases:
                    if alias.lower() in SWCEUsageDict:
                        return SWCEUsageDict[alias.lower()]
                return 0

            def get_swce_last_used(*aliases):
                best_dt = None
                for alias in aliases:
                    candidate_dt = swceLastUsedByName.get(alias)
                    if candidate_dt and (not best_dt or candidate_dt > best_dt):
                        best_dt = candidate_dt
                return format_last_used_for_display(best_dt)

            wceLonsdaleStations = [
                {
                    "name": "Lonsdale Quay",
                    "type": "seabus",
                    "uses": get_swce_usage("Lonsdale Quay"),
                    "lat": 49.310161,
                    "lon": -123.083358,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Lonsdale Quay").items()
                    },
                },
                {
                    "name": "Waterfront",
                    "type": "wce",
                    "uses": get_swce_usage("Waterfront Stn - WCE", "Waterfront Station"),
                    "lat": 49.286053,
                    "lon": -123.11158,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Waterfront Stn - WCE", "Waterfront Station").items()
                    },
                },
                {
                    "name": "Moody Centre",
                    "type": "wce",
                    "uses": get_swce_usage("Moody Centre Station", "Moody Center Station"),
                    "lat": 49.278067,
                    "lon": -122.846248,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Moody Centre Station", "Moody Center Station").items()
                    },
                },
                {
                    "name": "Coquitlam Central",
                    "type": "wce",
                    "uses": get_swce_usage("Coquitlam Central Station"),
                    "lat": 49.273909,
                    "lon": -122.800056,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Coquitlam Central Station").items()
                    },
                },
                {
                    "name": "Port Coquitlam",
                    "type": "wce",
                    "uses": get_swce_usage("Port Coquitlam Station"),
                    "lat": 49.261481,
                    "lon": -122.77402,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Port Coquitlam Station").items()
                    },
                },
                {
                    "name": "Pitt Meadows",
                    "type": "wce",
                    "uses": get_swce_usage("Pitt Meadows Station"),
                    "lat": 49.225772,
                    "lon": -122.688381,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Pitt Meadows Station").items()
                    },
                },
                {
                    "name": "Maple Meadows",
                    "type": "wce",
                    "uses": get_swce_usage("Maple Meadows Station"),
                    "lat": 49.216465,
                    "lon": -122.666097,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Maple Meadows Station").items()
                    },
                },
                {
                    "name": "Port Haney",
                    "type": "wce",
                    "uses": get_swce_usage("Port Haney Station"),
                    "lat": 49.212168,
                    "lon": -122.605242,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Port Haney Station").items()
                    },
                },
                {
                    "name": "Mission City",
                    "type": "wce",
                    "uses": get_swce_usage("Mission City Station"),
                    "lat": 49.133594,
                    "lon": -122.30486,
                    **{
                        f"last_used_{key}": value
                        for key, value in get_swce_last_used("Mission City Station").items()
                    },
                },
            ]

            print("==============================")

            print(f"You made a total of {(TripsNum)} trips")

            percentSSW = (SSWtripsNum/TripsNum) * 100

            print(f"Of which {percentSSW:.1f}% ({(SSWtripsNum)} trips) are SkyTrain/SeaBus/WCE")

            print("------------------------------")

            print("Among these trips, you have made:")
            print(" ", (SkytrainTripsNum), "Skytrain trips,")
            print(" ", SeabusTripsNum, "Seabus trips, and")
            print(" ", (WCETripsNum), "WCE trips")

            print("------------------------------")

            print("Your top 5 SkyTrain Stations are: ")
            utils.PrintElements(Top5SkyTrainStns)

            #print("These are SkyTrain stations you have not used:")
            #for stn in UnusedStations:
            #    print(" ", stn)

            print("------------------------------")

            print(f"You have used Transit on {countDays} days!")

            print("On average, you have taken:")

            print(f"{TripsNum/365:.2f} trips per day")

            print(f"{TripsNum/countDays:.2f} trips per day you used Transit")

            print(f"{TripsNum/52:.2f} trips per week")

            print(f"{TripsNum/12:.2f} trips per month")

            print("------------------------------")

            streak, StreakStart, StreakEnd = longest_transit_streak_with_dates(result)
            fullMonthCoverage = has_full_month_coverage(result)

            print(f"🔥 Longest transit streak: {streak} days")
            print(f"📅 From {StreakStart} to {StreakEnd}")

            minutes = total_minutes_spent(fileName)
            print(f"⏱ Total minutes spent on transit: {minutes}")
            print(f"📊 Sum of hours-of-day usage: {sum(hour_counts.values())}")


            
            # 👇 Replace this with your real processing logic
            # For now, just dummy data to show it works:
            #stations = [
            #    {"rank": 1, "name": "Commercial Broadway", "lines": "Expo Line, Millennium Line", "highlight": False, "icon": "icons/expo"},
            #    {"rank": 2, "name": "Metrotown", "lines": "Expo Line", "highlight": False, "icon": "icons/expo"},
            #    {"rank": 3, "name": "Surrey Central", "lines": "Expo Line", "highlight": False, "icon": "icons/expo"},
            #    {"rank": 4, "name": "Lougheed", "lines": "Millennium Line, Expo Line", "highlight": False, "icon": "icons/millennium"},
            #    {"rank": 5, "name": "Waterfront", "lines": "Expo Line, Millennium Line, Canada Line", "highlight": False, "icon": "icons/expo"}
            #]
            # --------------------------------------------------

            stations = []
            for rank, (name, count) in enumerate(Top5SkyTrainStns, start=1):
                # Use your full stationIcons dictionary
                # Try exact match first; fallback to generic if not found
                icon = utils.stationIcons.get(name, "icons/expo")

                # Optional: derive the line name based on icon path
                if "expmil" in icon:
                    lines = "Expo & Millennium Line"
                elif "expo" in icon:
                    lines = "Expo Line"
                elif "millennium" in icon:
                    lines = "Millennium Line"
                elif "canada" in icon:
                    lines = "Canada Line"
                elif "expcan" in icon:
                    lines = "Expo & Canada Line"
                else:
                    lines = "Unknown Line"

                stations.append({
                    "rank": rank,
                    "name": name,
                    "lines": f"{lines}",
                    "highlight": False,
                    "icon": icon
                })

            skytrainStationPoints = []
            for station_name in utils.SkyTrainStns:
                location = utils.get_station_location(station_name)
                if not location:
                    continue

                icon = utils.stationIcons.get(station_name, "")
                line_keys = []
                if "expmil" in icon:
                    line_keys = ["expo", "millennium"]
                elif "expcan" in icon:
                    line_keys = ["expo", "canada"]
                elif "millennium" in icon:
                    line_keys = ["millennium"]
                elif "canada" in icon:
                    line_keys = ["canada"]
                elif "expo" in icon:
                    line_keys = ["expo"]

                skytrainStationPoints.append({
                    "name": station_name,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "line_keys": line_keys,
                })

            topName, topCount = Top5SkyTrainStns[0] if Top5SkyTrainStns else ("N/A", 0)

            # 1. Station usage (top/bottom or full list — your choice)
            station_labels = [name for (name, count) in SkyTrainStns]
            station_values = [count for (name, count) in SkyTrainStns]


            # 2. Hour of day
            hours = list(range(24))
            hour_values = [hour_counts.get(h, 0) for h in hours]

            # 3. Day of week
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            weekday_values = [weekday_counts.get(i, 0) for i in range(7)]
            weekday_full_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

            # 4. Month of year
            months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            month_values = [month_counts.get(i, 0) for i in range(12)]

            balance_series = build_balance_time_series(fileName)
            balance_spend_summary = build_balance_spend_summary(fileName)
            pass_timeline_entries = build_pass_timeline_entries(fileName)

            os.remove(fileName)
            
            # Determine top station image URL (if available in utils.stationImages)
            topImage = None
            topImageRaw = utils.stationImages.get(topName)
            if topImageRaw:
                if topImageRaw.startswith("http://") or topImageRaw.startswith("https://"):
                    topImage = topImageRaw
                else:
                    topImage = url_for('static', filename=topImageRaw)

            awardsByTier = [
                {
                    "tier": "Easy / Bronze",
                    "awards": [
                        {
                            "title": "7-Day Streak (Sun–Sat)",
                            "description": "Used Transit every day of the week",
                            "icon": "awards/fire-icon-free-png-bronze.png",
                            "earned": streak >= 7,
                        },
                        {
                            "title": "50 Active Days",
                            "description": "Used Transit for 50 days of the year",
                            "icon": "awards/TranslinkCompasslogo-bronze.png",
                            "earned": countDays >= 50,
                        },
                        {
                            "title": "Basic Transit Rider",
                            "description": "Rode transit at least 200 times in a year",
                            "icon": "awards/Translinkbus-bronze.png",
                            "earned": TripsNum >= 200,
                        },
                        {
                            "title": "Basic SkyTrain Rider",
                            "description": "Rode the SkyTrain at least 50 times",
                            "icon": "awards/Translinkexpo-bronze.png",
                            "earned": SkytrainTripsNum >= 50,
                        },
                        {
                            "title": "SeaBus First Voyage",
                            "description": "Took at least 1 SeaBus trip",
                            "icon": "awards/Translinkseabus.svg.png",
                            "earned": SeabusTripsNum >= 1,
                        },
                        {
                            "title": "West Coast Express First Ride",
                            "description": "Took at least 1 WCE trip",
                            "icon": "awards/Translinkwce.svg.png",
                            "earned": WCETripsNum >= 1,
                        },
                    ],
                },
                {
                    "tier": "Medium / Silver",
                    "awards": [
                        {
                            "title": "100 Active Days",
                            "description": "Used Transit for 100 days of the year",
                            "icon": "awards/TranslinkCompasslogo-silver.png",
                            "earned": countDays >= 100,
                        },
                        {
                            "title": "2-Week Streak",
                            "description": "Used Transit for 14 days in a row",
                            "icon": "awards/fire-icon-free-png-silver.png",
                            "earned": streak >= 14,
                        },
                        {
                            "title": "Common Transit Rider",
                            "description": "Rode transit at least 500 times in a year",
                            "icon": "awards/Translinkbus-silver.png",
                            "earned": TripsNum >= 500,
                        },
                        {
                            "title": "Regular SkyTrain Rider",
                            "description": "Rode the SkyTrain at least 200 times in a year",
                            "icon": "awards/Translinkexpo-silver.png",
                            "earned": SkytrainTripsNum >= 200,
                        },
                        {
                            "title": "All Nighters",
                            "description": "Used transit 2 or more times between 2–4 AM",
                            "icon": "awards/Translinkbus-night.png",
                            "earned": allNighterTransitUses >= 2,
                            "hover_count": allNighterTransitUses,
                            "hover_label": "Tap-ins between 2–4 AM",
                        },
                        {
                            "title": "Midnight Trains",
                            "description": "Used SkyTrain 5 or more times past 12 AM",
                            "icon": "awards/Translinkexpo-midnight.png",
                            "earned": midnightSkyTrainUses >= 5,
                            "hover_count": midnightSkyTrainUses,
                            "hover_label": "SkyTrain tap-ins past 12 AM",
                        },
                        {
                            "title": "First Trains",
                            "description": "Used SkyTrain 5 or more times between 4–6 AM",
                            "icon": "awards/Translinkexpo-early.png",
                            "earned": firstTrainSkyTrainUses >= 5,
                            "hover_count": firstTrainSkyTrainUses,
                            "hover_label": "SkyTrain tap-ins between 4–6 AM",
                        },
                    ],
                },
                {
                    "tier": "Hard / Gold",
                    "awards": [
                        {
                            "title": "1-Month Streak",
                            "description": "Used Transit every day for a full calendar month",
                            "icon": "awards/fire-icon-free-png-gold.png",
                            "earned": fullMonthCoverage,
                        },
                        {
                            "title": "250 Active Days",
                            "description": "Used Transit for 250 days of the year",
                            "icon": "awards/TranslinkCompasslogo-gold.png",
                            "earned": countDays >= 250,
                        },
                        {
                            "title": "Round the Clock",
                            "description": "Used transit at least once for every hour of the day",
                            "icon": "awards/clock-icon-in-flat-design-style-analog-time-signs-illustration-png.png",
                            "earned": all(hour_counts.get(hour, 0) > 0 for hour in range(24)),
                        },
                        {
                            "title": "Station Fan",
                            "description": "At least 200 uses of a station in a year",
                            "icon": "awards/Translinkexpo-gold.png",
                            "icon_url": topImage,
                            "earned": topCount >= 200,
                        },
                        {
                            "title": "Frequent Transit Rider",
                            "description": "Rode transit at least 1000 times in a year",
                            "icon": "awards/Translinkbus-gold.png",
                            "earned": TripsNum >= 1000,
                        },
                        {
                            "title": "Frequent SkyTrain Rider",
                            "description": "Rode the SkyTrain at least 600 times in a year",
                            "icon": "awards/Translinkexpo-gold.png",
                            "earned": SkytrainTripsNum >= 600,
                        },
                    ],
                },
                {
                    "tier": "Extreme / Diamond",
                    "awards": [
                        {
                            "title": "350 Active Days",
                            "description": "Used Transit for 350 days of the year",
                            "icon": "awards/TranslinkCompasslogo-diamond.png",
                            "earned": countDays >= 350,
                        },
                        {
                            "title": "All SkyTrain Stations Visited",
                            "description": "Visited every SkyTrain station at least once in the year",
                            "icon": "awards/Translinkexpo-diamond.png",
                            "earned": len(UnusedStations) == 0,
                        },
                        {
                            "title": "All WCE Stations Visited",
                            "description": "Visited every WCE station at least once in the year",
                            "icon": "awards/Translinkwce-diamond.png",
                            "earned": len(unusedWCEStations) == 0,
                        },
                    ],
                },
            ]
            
            return render_template("results.html", stations=stations,
                TripsNum=int(TripsNum),
                SSWtripsNum=int(SSWtripsNum),
                percentSSW=percentSSW,
                SkytrainTripsNum=int(SkytrainTripsNum),
                SeabusTripsNum=SeabusTripsNum,
                WCETripsNum=int(WCETripsNum),

                station_labels=station_labels,
                station_values=station_values,
                hours=hours,
                hour_values=hour_values,
                days=days,
                weekday_values=weekday_values,
                weekday_full_names=weekday_full_names,
                day_hour_values=day_hour_values,
                UnusedStations=UnusedStations,
                wceLonsdaleStations=wceLonsdaleStations,
                countDays=countDays,
                month=months,
                month_values=month_values,
                balance_labels=balance_series["labels"],
                balance_values=balance_series["values"],
                balance_granularity=balance_series["granularity"],
                balance_change_labels=balance_series["change_labels"],
                balance_change_values=balance_series["change_values"],
                balance_timeline_start=balance_series["timeline_start"],
                balance_timeline_days=balance_series["timeline_days"],
                balance_change_points=balance_series["change_points"],
                balance_intraday_days=balance_series["intraday_days"],
                stored_value_spent=balance_spend_summary["stored_value_spent"],
                pass_spend=balance_spend_summary["pass_spend"],
                pass_count=balance_spend_summary["pass_count"],
                total_transit_spent=balance_spend_summary["total_spent"],
                extra_stored_value_if_no_pass=balance_spend_summary["extra_stored_value_if_no_pass"],
                extra_stored_value_by_month=balance_spend_summary["extra_stored_value_by_month"],
                extra_stored_value_by_day=balance_spend_summary["extra_stored_value_by_day"],
                pass_timeline_entries=pass_timeline_entries,
                streak=streak, StreakStart=StreakStart, StreakEnd=StreakEnd,
                topName=topName, topCount=topCount, topImage=topImage,
                minutes=int(minutes),
                top10BusStops=Top10BusStopsWithNames,
                top10StationPairs=Top10StationPairs,
                skytrainSegmentUsage=skytrainSegmentUsage,
                shortestPairMinutes=shortestPairMinutes,
                topStationMapPoints=topStationMapPoints,
                topBusStopMapPoints=topBusStopMapPoints,
                remainingStationMapPoints=remainingStationMapPoints,
                remainingBusStopMapPoints=remainingBusStopMapPoints,
                skytrainStationPoints=skytrainStationPoints,
                awardsByTier=[
                    {**tier, "awards": sorted(tier["awards"], key=lambda a: not a["earned"])}
                    for tier in awardsByTier
                ]
                )

        if os.path.exists(fileName):
            os.remove(fileName)
        flash(validation_error)
        return redirect(url_for("upload_file"))

    return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True)

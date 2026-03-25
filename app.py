from flask import Flask, render_template, request, redirect, url_for,flash
import pandas as pd
import os
import csv
import uuid
import utils
from collections import Counter, OrderedDict
from datetime import datetime, timedelta
import calendar
import re
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

    if not valid_files:
        flash("Please choose one or more CSV files to upload.")
        return redirect(url_for("more"))

    for uploaded in valid_files:
        _, extension = os.path.splitext(uploaded.filename.lower())
        if extension not in ALLOWED_EXTENSIONS:
            flash("All files must be CSV.")
            return redirect(url_for("more"))

    selected_names = [secure_filename(uploaded.filename) for uploaded in valid_files]
    upload_detail = f"Selected {len(selected_names)} CSV file(s): {', '.join(selected_names)}"

    return render_template(
        "more_todo.html",
        message="todo soon, for comparing trips between several csv's",
        upload_detail=upload_detail,
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

    return render_template(
        "more_todo.html",
        message="also todo soon, only 1 csv like original upload",
        upload_detail=f"Selected CSV file: {selected_name}",
    )


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
            trips = []
            with open(fileName, newline="", encoding="utf-8") as csvfile:
                reader = csv.reader(csvfile)
                next(reader)  # skip header row
                for row in reader:
                    if len(row) < 2 or row[1].strip() == "":
                        break  # stop at first empty cell
                    trips.append(row[1])

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

            # Extract and count bus stops
            BusStops = [stop for stop in trips if "Bus Stop" in stop]
            BusStopNumbers = []
            
            import re
            for stop in BusStops:
                # Extract 5-digit number from bus stop entry (e.g., "Bus Stop 50123")
                match = re.search(r'\d{5}', stop)
                if match:
                    BusStopNumbers.append(match.group())
            
            # Count bus stops by their 5-digit number
            BusStopCounts = utils.CountElementsInList(BusStopNumbers)
            
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
                topBusStopMapPoints.append({
                    "rank": rank,
                    "name": stop_name,
                    "stop_id": stop_id,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                })

            remainingBusStopMapPoints = []
            for rank, (stop_name, stop_id, count) in enumerate(RemainingBusStopsWithNames, start=11):
                location = utils.get_bus_stop_location(stop_id)
                if not location:
                    continue
                remainingBusStopMapPoints.append({
                    "rank": rank,
                    "name": stop_name,
                    "stop_id": stop_id,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
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

            Top5SkyTrainStns = sorted(
                SkyTrainStns,
                key=lambda x: (-x[1], x[0])
            )[:5]

            RemainingSkyTrainStns = sorted(
                SkyTrainStns,
                key=lambda x: (-x[1], x[0])
            )[5:]

            topStationMapPoints = []
            for rank, (name, count) in enumerate(Top5SkyTrainStns, start=1):
                location = utils.get_station_location(name)
                if not location:
                    continue
                topStationMapPoints.append({
                    "rank": rank,
                    "name": name,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "source_name": location["name"],
                })

            remainingStationMapPoints = []
            for rank, (name, count) in enumerate(RemainingSkyTrainStns, start=6):
                location = utils.get_station_location(name)
                if not location:
                    continue
                remainingStationMapPoints.append({
                    "rank": rank,
                    "name": name,
                    "count": count,
                    "lat": location["lat"],
                    "lon": location["lon"],
                    "source_name": location["name"],
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

            wceLonsdaleStations = [
                {
                    "name": "Lonsdale Quay",
                    "type": "seabus",
                    "uses": get_swce_usage("Lonsdale Quay"),
                    "lat": 49.310161,
                    "lon": -123.083358,
                },
                {
                    "name": "Waterfront",
                    "type": "wce",
                    "uses": get_swce_usage("Waterfront Stn - WCE", "Waterfront Station"),
                    "lat": 49.286053,
                    "lon": -123.11158,
                },
                {
                    "name": "Moody Centre",
                    "type": "wce",
                    "uses": get_swce_usage("Moody Centre Station", "Moody Center Station"),
                    "lat": 49.278067,
                    "lon": -122.846248,
                },
                {
                    "name": "Coquitlam Central",
                    "type": "wce",
                    "uses": get_swce_usage("Coquitlam Central Station"),
                    "lat": 49.273909,
                    "lon": -122.800056,
                },
                {
                    "name": "Port Coquitlam",
                    "type": "wce",
                    "uses": get_swce_usage("Port Coquitlam Station"),
                    "lat": 49.261481,
                    "lon": -122.77402,
                },
                {
                    "name": "Pitt Meadows",
                    "type": "wce",
                    "uses": get_swce_usage("Pitt Meadows Station"),
                    "lat": 49.225772,
                    "lon": -122.688381,
                },
                {
                    "name": "Maple Meadows",
                    "type": "wce",
                    "uses": get_swce_usage("Maple Meadows Station"),
                    "lat": 49.216465,
                    "lon": -122.666097,
                },
                {
                    "name": "Port Haney",
                    "type": "wce",
                    "uses": get_swce_usage("Port Haney Station"),
                    "lat": 49.212168,
                    "lon": -122.605242,
                },
                {
                    "name": "Mission City",
                    "type": "wce",
                    "uses": get_swce_usage("Mission City Station"),
                    "lat": 49.133594,
                    "lon": -122.30486,
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
                streak=streak, StreakStart=StreakStart, StreakEnd=StreakEnd,
                topName=topName, topCount=topCount, topImage=topImage,
                minutes=int(minutes),
                top10BusStops=Top10BusStopsWithNames,
                top10StationPairs=Top10StationPairs,
                topStationMapPoints=topStationMapPoints,
                topBusStopMapPoints=topBusStopMapPoints,
                remainingStationMapPoints=remainingStationMapPoints,
                remainingBusStopMapPoints=remainingBusStopMapPoints,
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

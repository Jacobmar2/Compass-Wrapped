from flask import Flask, render_template, request, redirect, url_for,flash
import pandas as pd
import os
import csv
import utils
from collections import Counter, OrderedDict
from datetime import datetime, timedelta

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

@app.route("/howto")
def howto():
    return render_template("howto.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        file = request.files["file"]
        if file.filename.endswith(".csv"):
            fileName = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            file.save(fileName)
            
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

            # Column A = column index 0
            # Column B = column index 1

            # Skip header row (Excel row 2 → index 1 onward)
            df = df.iloc[1:]

            # Stop at first empty cell in column A
            colA = df[0].astype(str).str.strip()
            empty_mask = (colA == "") | (colA == "nan")

            if empty_mask.any():
                first_empty = empty_mask.idxmax()
                df = df.loc[:first_empty - 1]

            # Filter conditions on column B
            exclude_keywords = ["Loaded", "SV", "COS", "Purchase", "Refund","out"]
            # out excluded as SkyTrain trips only counted upon entry

            def is_excluded(value):
                text = str(value)
                return any(k in text for k in exclude_keywords)

            mask = ~df[1].apply(is_excluded)

            filtered_df = df[mask]

            # Convert column A to list
            result = filtered_df[0].tolist()

            #print(result)
            #print("==============================")

            hour_counts = Counter()
            def count_by_hour_all(timestamps):

                # Parse timestamps
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
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
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
                    weekday_counts[dt.weekday()] += 1  # Monday = 0, Sunday = 6

                # Day labels
                days = ["Monday", "Tuesday", "Wednesday", "Thursday",
                        "Friday", "Saturday", "Sunday"]

                # Print all 7 days including zero-count ones
                # for i, day in enumerate(days):
                #     print(f"{day}: {weekday_counts.get(i, 0)}")

            count_by_weekday(result)

            #print("==============================")
            month_counts = Counter()

            def count_by_month(timestamps):

                # Parse timestamps and count months
                for ts in timestamps:
                    ts = ts.strip()
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
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
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
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

            #Getting top 5 used SkyTrain Stns

            Top5SkyTrainStns = sorted(
                SkyTrainStns,
                key=lambda x: (-x[1], x[0])
            )[:5]

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
                        ts_out = datetime.strptime(timestamp, "%b-%d-%Y %I:%M %p")
                        ts_in = datetime.strptime(data[i + 1][0].strip(), "%b-%d-%Y %I:%M %p")

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

            print(f"🔥 Longest transit streak: {streak} days")
            print(f"📅 From {StreakStart} to {StreakEnd}")

            minutes = total_minutes_spent(fileName)
            print(f"⏱ Total minutes spent on transit: {minutes}")


            
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
                UnusedStations=UnusedStations,
                countDays=countDays,
                month=months,
                month_values=month_values,
                streak=streak, StreakStart=StreakStart, StreakEnd=StreakEnd,
                topName=topName, topCount=topCount, topImage=topImage,
                minutes=int(minutes),
                top10BusStops=Top10BusStopsWithNames,
                top10StationPairs=Top10StationPairs
                )
        
        elif not file.filename.lower().endswith(".csv"):
            flash("Upload a CSV file.")
            return redirect(url_for("upload_file"))
        else:
            return "Please upload a CSV file."
    return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True)

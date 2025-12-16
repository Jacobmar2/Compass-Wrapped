from flask import Flask, render_template, request, redirect, url_for,flash
import pandas as pd
import os
import csv
import utils
from collections import Counter
from datetime import datetime

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

            utils.PrintElements(SkyTrainStns)
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
            print("==============================")

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

                    print(f"{hour_12:02d}:00–{hour_12:02d}:59 {suffix} → {hour_counts.get(hour, 0)}")

            hourly = count_by_hour_all(result)

            print("==============================")

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
                for i, day in enumerate(days):
                    print(f"{day}: {weekday_counts.get(i, 0)}")

            count_by_weekday(result)

            #Counting different days used transit
            def count_unique_days(timestamps):
                unique_days = set()

                for ts in timestamps:
                    dt = datetime.strptime(ts, "%b-%d-%Y %I:%M %p")
                    day_only = dt.date()  # strips off time, keeps just yyyy-mm-dd
                    unique_days.add(day_only)

                return len(unique_days)

            countDays = count_unique_days(result)


            #Getting top 5 used SkyTrain Stns

            Top5SkyTrainStns = sorted(
                SkyTrainStns,
                key=lambda x: (-x[1], x[0])
            )[:5]

            UsageDict = dict(SkyTrainStns)

            UnusedStations = [stn for stn in utils.SkyTrainStns if UsageDict.get(stn, 0) == 0]

            print("==============================")

            print(f"You made a total of {int(TripsNum)} trips")

            percentSSW = (SSWtripsNum/TripsNum) * 100

            print(f"Of which {percentSSW:.1f}% ({int(SSWtripsNum)} trips) are SkyTrain/SeaBus/WCE")

            print("------------------------------")

            print("Among these trips, you have made:")
            print(" ", int(SkytrainTripsNum), "Skytrain trips,")
            print(" ", SeabusTripsNum, "Seabus trips, and")
            print(" ", int(WCETripsNum), "WCE trips")

            print("------------------------------")

            print("Your top 5 SkyTrain Stations are: ")
            utils.PrintElements(Top5SkyTrainStns)

            print("These are SkyTrain stations you have not used:")
            for stn in UnusedStations:
                print(" ", stn)

            print("------------------------------")

            print(f"You have used Transit on {countDays} days!")

            print("On average, you have taken:")

            print(f"{TripsNum/365:.2f} trips per day")

            print(f"{TripsNum/countDays:.2f} trips per day you used Transit")

            print(f"{TripsNum/52:.2f} trips per week")

            print(f"{TripsNum/12:.2f} trips per month")
            
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

            # 1. Station usage (top/bottom or full list — your choice)
            station_labels = [name for (name, count) in SkyTrainStns]
            station_values = [count for (name, count) in SkyTrainStns]


            # 2. Hour of day
            hours = list(range(24))
            hour_values = [hour_counts.get(h, 0) for h in hours]

            # 3. Day of week
            days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
            weekday_values = [weekday_counts.get(i, 0) for i in range(7)]

            os.remove(fileName)
            
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
                countDays=countDays
                )
        
        elif not file.filename.lower().endswith(".csv"):
            flash("Upload a CSV file.")
            return redirect(url_for("upload_file"))
        else:
            return "Please upload a CSV file."
    return render_template("home.html")


if __name__ == "__main__":
    app.run(debug=True)

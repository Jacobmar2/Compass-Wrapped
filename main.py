# Compass Wrapped
import csv
import utils
import pandas as pd
from collections import Counter
from datetime import datetime
import matplotlib.pyplot as plt

#main part


trips = []
fileName = "CompassData/Compass Wrapped 2025.csv"

with open(fileName, newline="", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)
    next(reader)  # Skip the header (row 1)
    
    for row in reader:
        # Make sure row has at least 2 columns
        if len(row) < 2 or row[1].strip() == "":
            break  # Stop at first empty cell in column B
        trips.append(row[1])

# ======== tests =========
# trips = ["Transfer at Production Way Stn","Tap out at Edmonds Stn"]

# trips = ["Transfer at Production Way Stn","Transfer at Lonsdale Quay"]

# trips = ["Tap in at Edmonds Stn","Transfer at Lonsdale Quay"]

# trips = ["Tap in at Bus Stop 52460","Loaded at Bus Stop 52460","Transfer at Production Way Stn","Tap out at Edmonds Stn"]


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
exclude_keywords = ["Loaded", "SV", "COS", "Purchase"]

def is_excluded(value):
    text = str(value)
    return any(k in text for k in exclude_keywords)

mask = ~df[1].apply(is_excluded)

filtered_df = df[mask]

# Convert column A to list
result = filtered_df[0].tolist()

#print(result)
print("==============================")

def count_by_hour_all(timestamps):
    hour_counts = Counter()

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

    plt.figure(figsize=(10,4))
    hours = list(range(24))
    values = [hour_counts.get(h, 0) for h in hours]

    plt.bar(hours, values)
    plt.xlabel("Hour (AM/PM handled in data)")
    plt.ylabel("Count")
    plt.title("Trips by Hour of Day")
    plt.xticks(hours)
    plt.tight_layout()
    plt.show()

hourly = count_by_hour_all(result)

print("==============================")

def count_by_weekday(timestamps):
    weekday_counts = Counter()

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

    plt.figure(figsize=(8,4))

    days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    values = [weekday_counts.get(i, 0) for i in range(7)]

    plt.bar(days, values)
    plt.xlabel("Day of Week")
    plt.ylabel("Count")
    plt.title("Trips by Day of Week")
    plt.tight_layout()
    plt.show()

count_by_weekday(result)



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

print("------------------------------")

print("These are SkyTrain stations you have not used:")
for stn in UnusedStations:
    print(" ", stn)

print("------------------------------")

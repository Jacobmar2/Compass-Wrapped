# Compass Wrapped


import csv
import utils

#main part


trips = []

with open("CompassData/Compass Wrapped.csv", newline="", encoding="utf-8") as csvfile:
    reader = csv.reader(csvfile)
    next(reader)  # Skip the header (row 1)
    
    for row in reader:
        # Make sure row has at least 2 columns
        if len(row) < 2 or row[1].strip() == "":
            break  # Stop at first empty cell in column B
        trips.append(row[1])

# All SkyTrain/Seabus/WCE taps
SSWTaps = [stop for stop in trips if "Bus Stop" not in stop and "Loaded" not in stop 
           and "SV" not in stop and "COS" not in stop and "Purchase" not in stop]

#testing section
#SSWTaps = ["at Edmonds Stn","at Scott Rd Stn","at Edmonds Stn","at Lonsdale Quay","at Edmonds Stn","at Lonsdale Quay"]

#SSWTaps = ["at Edmonds Stn","at Scott Rd Stn","at Edmonds Stn","at Lonsdale Quay","at Edmonds Stn","at Lonsdale Quay"]

#printOutList(SSWTaps)

SSWtripsNum = len(SSWTaps)/2

BusTapsNum = len(trips) - len(SSWTaps)

TripsNum = BusTapsNum + SSWtripsNum

SSWTapsNames = utils.ProcessList(SSWTaps)

utils.printOutList(SSWTapsNames)

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
print(int(SkytrainTripsNum), "Skytrain trips,")
print(SeabusTripsNum, "Seabus trips, and")
print(int(WCETripsNum), "WCE trips")

print("------------------------------")

print("Your top 5 SkyTrain Stations are: ")
utils.PrintElements(Top5SkyTrainStns)

print("------------------------------")

print("These are SkyTrain stations you have not used:")
for stn in UnusedStations:
    print(stn)

print("------------------------------")

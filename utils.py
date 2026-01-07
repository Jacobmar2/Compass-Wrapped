#functions

def printOutList(lst):
    for i, item in enumerate(lst, start=1):
        print(f"{i}. {item}")

def ProcessList(data):
    result = []
    for item in data:
        if "Missing" in item:
            result.append("(Missing)")
        elif "at" in item:
            # split only once at the first "at" and take what follows
            result.append(item.split("at", 1)[1].strip())
        else:
            result.append(item)
    return result

def CountElementsInList(items):    # Each element has a station name and number (representing amount of times used)
    counts = []  # list of (element, count)

    for item in items:
        found = False
        for i, (element, count) in enumerate(counts):
            if element == item:   # already seen this element
                counts[i] = (element, count + 1)
                found = True
                break
        if not found:  # brand new element
            counts.append((item, 1))
    
    # Sort by count (descending), then element (alphabetical ascending)
    counts.sort(key=lambda x: (-x[1], x[0]))
    return counts

def PrintElements(result):      # prints the list of stations and their counts
    for element, count in result:
        print(" ", f"{element}: {count}")

def remove_refund_pairs(taps):
    cleaned = []
    skip_next = False

    for tap in taps:
        if skip_next:
            # Skip the item after "Refund"
            skip_next = False
            continue

        if "Refund" in tap:
            # Skip this element AND the next one
            skip_next = True
            continue
        
        cleaned.append(tap)

    return cleaned

def adjust_wce_eastbound(SSWTapsNames,i,SkytrainTripsNum,TripsNum,SSWtripsNum,WCETripsNum):
    if (i <= len(SSWTapsNames) - 2):

        if (
            "Waterfront Stn" in SSWTapsNames[i+2]
        ):
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1

    if "Moody" in SSWTapsNames[i-1] and "Station" in SSWTapsNames[i-1]:
        if "Moody Center Stn" in SSWTapsNames[i-3]:
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1

    elif "Stn" in SSWTapsNames[i-1]:
        print("here")
        WCETripsNum += 1
        SkytrainTripsNum += 1
        TripsNum += 1  
        SSWtripsNum += 1
        if "Moody" in SSWTapsNames[i-1]:
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1

    elif ("(Missing)" in SSWTapsNames[i-1]
          and "(Missing)" in SSWTapsNames[i-2]
          and "Moody Center Stn" in SSWTapsNames[i-3]):
        SkytrainTripsNum -= 2
        TripsNum -= 1  
        SSWtripsNum -= 1
        

    return SkytrainTripsNum, TripsNum, SSWtripsNum, WCETripsNum

def adjust_wce_westbound(SSWTapsNames,i,SkytrainTripsNum,TripsNum,SSWtripsNum,WCETripsNum):
    if (i <= len(SSWTapsNames) - 2):

        if (
            "Moody Center Stn" in SSWTapsNames[i+2]
        ):
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1

    if "Waterfront Stn - WCE" in SSWTapsNames[i-1]:
        if "Waterfront Stn" in SSWTapsNames[i-3]:
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1

    elif "Stn" in SSWTapsNames[i-1]:
        
        WCETripsNum += 1
        SkytrainTripsNum += 1
        TripsNum += 1  
        SSWtripsNum += 1
        if "Waterfront" in SSWTapsNames[i-1]:
            print("here")
            SkytrainTripsNum -= 2
            TripsNum -= 1  
            SSWtripsNum -= 1
    
    elif "Quay" in SSWTapsNames[i-1]:
        WCETripsNum += 1
        SkytrainTripsNum -= 1

    elif ("(Missing)" in SSWTapsNames[i-1]
          and "(Missing)" in SSWTapsNames[i-2]
          and "Waterfront Stn" in SSWTapsNames[i-3]):
        SkytrainTripsNum -= 2
        TripsNum -= 1  
        SSWtripsNum -= 1

    return SkytrainTripsNum, TripsNum, SSWtripsNum, WCETripsNum

SkyTrainStns = [
    # --- Expo Line (Waterfront → King George branch) ---
    "Waterfront Stn",
    "Burrard Stn",
    "Granville Stn",
    "Stadium Stn",
    "Main Street Stn",
    "Commercial Drive Stn",
    "Nanaimo Stn",
    "29th Av Stn",
    "Joyce Stn",
    "Patterson Stn",
    "Metrotown Stn",
    "Royal Oak Stn",
    "Edmonds Stn",
    "22nd St Stn",
    "New Westminster Stn",
    "Columbia Stn",
    "Scott Road Stn",
    "Gateway Stn",
    "Surrey Central Stn",
    "King George Stn",

    # --- Expo Line (Columbia → Production Way-University branch) ---
    "Sapperton Stn",
    "Braid Stn",
    "Lougheed Stn",
    "Production Way Stn",

    # --- Millennium Line (Lafarge Lake-Douglas → VCC-Clark) ---
    "Lafarge Lake/Douglas College Stn",
    "Lincoln Stn",
    "Coquitlam Central Stn",
    "Inlet Centre Stn",
    "Moody Center Stn",
    "Burquitlam Stn",
    "Lake City Way Stn",
    "Sperling Stn",
    "Holdom Stn",
    "Brentwood Stn",
    "Gilmore Stn",
    "Rupert Stn",
    "Renfrew Stn",
    "VCC-Clark Stn",

    # --- Canada Line (Waterfront → YVR/Richmond branches) ---
    "Vancouver City Centre Stn",
    "Yaletown-Roundhouse Stn",
    "Olympic Village Stn",
    "Broadway-City Hall Stn",
    "King Edward Stn",
    "Oakridge-41st Stn",
    "Langara-49th Stn",
    "Marine Drive Stn",
    "Bridgeport Stn",
    "Templeton Stn",
    "Sea Island Centre Stn",
    "YVR-Airport Stn",
    "Capstan Stn",
    "Aberdeen Stn",
    "Lansdowne Stn",
    "Brighouse Stn"
]

stationIcons = {
    # --- Expo Line (Waterfront → King George branch) ---
    "Waterfront Stn": "icons/expcan",
    "Burrard Stn": "icons/expo",
    "Granville Stn": "icons/expo",
    "Stadium Stn": "icons/expo",
    "Main Street Stn": "icons/expo",
    "Commercial Drive Stn": "icons/expmil",
    "Nanaimo Stn": "icons/expo",
    "29th Av Stn": "icons/expo",
    "Joyce Stn": "icons/expo",
    "Patterson Stn": "icons/expo",
    "Metrotown Stn": "icons/expo",
    "Royal Oak Stn": "icons/expo",
    "Edmonds Stn": "icons/expo",
    "22nd St Stn": "icons/expo",
    "New Westminster Stn": "icons/expo",
    "Columbia Stn": "icons/expo",
    "Scott Road Stn": "icons/expo",
    "Gateway Stn": "icons/expo",
    "Surrey Central Stn": "icons/expo",
    "King George Stn": "icons/expo",

    # --- Expo Line (Columbia → Production Way-University branch) ---
    "Sapperton Stn": "icons/expo",
    "Braid Stn": "icons/expo",
    "Lougheed Stn": "icons/expmil",
    "Production Way Stn": "icons/expmil",

    # --- Millennium Line (Lafarge Lake–Douglas → VCC–Clark) ---
    "Lafarge Lake/Douglas College Stn": "icons/millennium",
    "Lincoln Stn": "icons/millennium",
    "Coquitlam Central Stn": "icons/millennium",
    "Inlet Centre Stn": "icons/millennium",
    "Moody Center Stn": "icons/millennium",
    "Burquitlam Stn": "icons/millennium",
    "Lake City Way Stn": "icons/millennium",
    "Sperling Stn": "icons/millennium",
    "Holdom Stn": "icons/millennium",
    "Brentwood Stn": "icons/millennium",
    "Gilmore Stn": "icons/millennium",
    "Rupert Stn": "icons/millennium",
    "Renfrew Stn": "icons/millennium",
    "VCC-Clark Stn": "icons/millennium",

    # --- Canada Line (Waterfront → YVR/Richmond branches) ---
    "Vancouver City Centre Stn": "icons/canada",
    "Yaletown-Roundhouse Stn": "icons/canada",
    "Olympic Village Stn": "icons/canada",
    "Broadway-City Hall Stn": "icons/canada",
    "King Edward Stn": "icons/canada",
    "Oakridge-41st Stn": "icons/canada",
    "Langara-49th Stn": "icons/canada",
    "Marine Drive Stn": "icons/canada",
    "Bridgeport Stn": "icons/canada",
    "Templeton Stn": "icons/canada",
    "Sea Island Centre Stn": "icons/canada",
    "YVR-Airport Stn": "icons/canada",
    "Capstan Stn": "icons/canada",
    "Aberdeen Stn": "icons/canada",
    "Lansdowne Stn": "icons/canada",
    "Brighouse Stn": "icons/canada"
}

# --- Station images (generated) ---
stationImages = {
    "22nd St Stn": "https://upload.wikimedia.org/wikipedia/commons/5/5a/YVR22ndstrstn.JPG",
    "29th Av Stn": "https://upload.wikimedia.org/wikipedia/commons/b/ba/29th_Avenue_platform_level_%2820190626_123343%29.jpg",
    "Aberdeen Stn": "https://upload.wikimedia.org/wikipedia/commons/1/1c/Aberdeen_Station_2017-05-22_17.45.38.jpg",
    "Braid Stn": "https://upload.wikimedia.org/wikipedia/commons/6/6c/Braid_station_entrance.jpg",
    "Brentwood Stn": "https://upload.wikimedia.org/wikipedia/commons/5/59/Brentwood_Station_2022.jpg",
    "Bridgeport Stn": "https://upload.wikimedia.org/wikipedia/commons/4/48/Bridgeport_Stn.jpg",
    "Brighouse Stn": "https://upload.wikimedia.org/wikipedia/commons/f/f8/Richmond%E2%80%93Brighouse_platform_level%2C_May_2019_%283%29.jpg",
    "Broadway-City Hall Stn": "https://upload.wikimedia.org/wikipedia/commons/f/f6/Broadway_Cityhall_stn.jpg",
    "Burquitlam Stn": "https://upload.wikimedia.org/wikipedia/commons/b/be/Burquitlam_Station_Exterior.jpg",
    "Burrard Stn": "https://upload.wikimedia.org/wikipedia/commons/f/f8/Vancouver_-_Burrard_Station_entrance_01.jpg",
    "Capstan Stn": "https://upload.wikimedia.org/wikipedia/commons/8/82/Capstan_Station_Entrance_20241220.jpg",
    "Columbia Stn": "https://upload.wikimedia.org/wikipedia/commons/3/32/Columbia_platform_level.jpg",
    "Commercial Drive Stn": "https://upload.wikimedia.org/wikipedia/commons/a/a3/Commercial-Broadway_station.jpg",
    "Coquitlam Central Stn": "https://upload.wikimedia.org/wikipedia/commons/a/a7/Coquitlam_Central_Station_Exterior.jpg",
    "Edmonds Stn": "https://upload.wikimedia.org/wikipedia/commons/d/d3/Edmonds_station%2C_August_2018.jpg",
    "Gateway Stn": "https://upload.wikimedia.org/wikipedia/commons/0/07/Gateway_station%2C_October_2018.jpg",
    "Gilmore Stn": "https://upload.wikimedia.org/wikipedia/commons/b/be/Gilmore_Station_Platform_2025.jpg",
    "Granville Stn": "https://upload.wikimedia.org/wikipedia/commons/a/a1/Granville-Dunsmuir_Street_entrance.jpg",
    "Holdom Stn": "https://upload.wikimedia.org/wikipedia/commons/5/57/Holdom_platform_level.jpg",
    "Inlet Centre Stn": "https://upload.wikimedia.org/wikipedia/commons/0/02/Inlet_Centre_station.jpg",
    "Joyce Stn": "https://upload.wikimedia.org/wikipedia/commons/3/37/Joyce%E2%80%93Collingwood_station_%2820190626_120404%29.jpg",
    "King Edward Stn": "https://upload.wikimedia.org/wikipedia/commons/1/17/King_Edward_station_entrance.jpg",
    "King George Stn": "https://upload.wikimedia.org/wikipedia/commons/b/bb/King_George_station_%282024%29.jpg",
    "Lafarge Lake/Douglas College Stn": "https://upload.wikimedia.org/wikipedia/commons/d/d9/Lafarge_Lake_%E2%80%93_Douglas_SkyTrain_Station_Exterior.jpg",
    "Lake City Way Stn": "https://upload.wikimedia.org/wikipedia/commons/5/56/Lake_City_Way_Station.JPG",
    "Langara-49th Stn": "https://upload.wikimedia.org/wikipedia/commons/9/9e/Langara%E2%80%9349th_Avenue_station_entrance%2C_May_2019_%282%29.jpg",
    "Lansdowne Stn": "https://upload.wikimedia.org/wikipedia/commons/6/65/Lansdowne_stn.jpg",
    "Lincoln Stn": "https://upload.wikimedia.org/wikipedia/commons/c/c9/Lincoln_Station_Exterior.jpg",
    "Lougheed Stn": "https://upload.wikimedia.org/wikipedia/commons/7/7d/Lougheed_Town_Centre_platform_level.jpg",
    "Main Street Stn": "https://upload.wikimedia.org/wikipedia/commons/4/4f/Main_Street%E2%80%93Science_World_platform_level.jpg",
    "Marine Drive Stn": "https://upload.wikimedia.org/wikipedia/commons/8/8d/Marine_Drive_station%2C_January_2018.jpg",
    "Metrotown Stn": "https://upload.wikimedia.org/wikipedia/commons/e/e5/Metrotown_Station_at_evening_2024.jpg",
    "Moody Center Stn": "https://upload.wikimedia.org/wikipedia/commons/2/21/Moody_Centre_Station_2025.jpg",
    "Nanaimo Stn": "https://upload.wikimedia.org/wikipedia/commons/1/1f/Nanaimo_station_entrance.jpg",
    "New Westminster Stn": "https://upload.wikimedia.org/wikipedia/commons/2/28/New_Westminster_platform_level_%282%29.jpg",
    "Oakridge-41st Stn": "https://upload.wikimedia.org/wikipedia/commons/6/6d/Oakridge-41st_Avenue_Station.JPG",
    "Olympic Village Stn": "https://upload.wikimedia.org/wikipedia/commons/c/c4/Olympic_Village_station_entrance%2C_May_2019_%281%29.jpg",
    "Production Way Stn": "https://upload.wikimedia.org/wikipedia/commons/4/45/Production_Way%E2%80%93University_station_platform.jpg",
    "Renfrew Stn": "https://upload.wikimedia.org/wikipedia/commons/7/7c/MLine-Renfrew.jpg",
    "Royal Oak Stn": "https://upload.wikimedia.org/wikipedia/commons/5/52/Royal_Oak_station%2C_March_2019.jpg",
    "Rupert Stn": "https://upload.wikimedia.org/wikipedia/commons/1/11/Vancouver_Skytrain_Rupert_station_train.jpg",
    "Sapperton Stn": "https://upload.wikimedia.org/wikipedia/commons/4/4f/Sapperton_platform_level.jpg",
    "Scott Road Stn": "https://upload.wikimedia.org/wikipedia/commons/1/1a/Scott_Road_platform_level.jpg",
    "Sea Island Centre Stn": "https://upload.wikimedia.org/wikipedia/commons/6/66/Sea_Island_Stn.jpg",
    "Sperling Stn": "https://upload.wikimedia.org/wikipedia/commons/e/e6/Sperling_Station_Exterior_20100116.jpg",
    "Stadium Stn": "https://upload.wikimedia.org/wikipedia/commons/c/c7/Stadium%E2%80%93Chinatown_station%2C_March_2018.jpg",
    "Surrey Central Stn": "https://upload.wikimedia.org/wikipedia/commons/e/e6/Surrey_Central%E2%80%93City_Parkway_entrance.jpg",
    "Templeton Stn": "https://upload.wikimedia.org/wikipedia/commons/f/f0/Templeton_Stn.jpg",
    "VCC-Clark Stn": "https://upload.wikimedia.org/wikipedia/commons/d/db/VCC-Clark_Station_Entrance.jpg",
    "Vancouver City Centre Stn": "https://upload.wikimedia.org/wikipedia/commons/0/0d/Vancouver-City_Centre_station.jpg",
    "Waterfront Stn": "https://upload.wikimedia.org/wikipedia/commons/0/04/Waterfront_station_2025.jpg",
    "YVR-Airport Stn": "https://upload.wikimedia.org/wikipedia/commons/f/f8/YVR-Airport_Stn.JPG",
    "Yaletown-Roundhouse Stn": "https://upload.wikimedia.org/wikipedia/commons/4/41/Yaletown_Roundhouse_Station_ext.jpg",
}


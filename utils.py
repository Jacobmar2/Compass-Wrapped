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
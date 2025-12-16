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


def plot_station_counts(result):
    # Unpack
    elements = [item[0] for item in result]
    counts = [item[1] for item in result]

    # Reverse so highest is at the top
    elements = elements[::-1]
    counts = counts[::-1]

    plt.figure(figsize=(10, len(result) * 0.4))
    plt.barh(elements, counts)

    plt.xlabel("Count")
    plt.ylabel("Station")
    plt.title("Station Usage Counts")

    plt.tight_layout()
    plt.show()

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


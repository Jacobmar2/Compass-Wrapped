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
        print(f"{element}: {count}")
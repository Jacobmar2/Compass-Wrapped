"""
Parse TransLink stops.txt and generate bus stop dictionary
"""

import csv

def parse_stops_file(filepath):
    """
    Parses the stops.txt file and creates a dictionary mapping
    5-digit stop_code to stop_name
    """
    bus_stops = {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            stop_code = row['stop_code'].strip()
            stop_name = row['stop_name'].strip()
            
            # Only include stops with 5-digit codes
            if stop_code.isdigit() and len(stop_code) == 5:
                bus_stops[stop_code] = stop_name
    
    return bus_stops

def generate_python_dict(bus_stops):
    """
    Generates a Python dictionary string for the utils.py file
    """
    # Sort by stop_code for readability
    sorted_stops = sorted(bus_stops.items())
    
    dict_str = "busStopNames = {\n"
    for stop_code, stop_name in sorted_stops:
        # Escape quotes in stop names
        escaped_name = stop_name.replace('"', '\\"')
        dict_str += f'    "{stop_code}": "{escaped_name}",\n'
    dict_str += "}\n"
    
    return dict_str

if __name__ == "__main__":
    filepath = "textfiles/stops.txt"
    
    print(f"Parsing {filepath}...")
    bus_stops = parse_stops_file(filepath)
    
    if bus_stops:
        print(f"Found {len(bus_stops)} bus stops with 5-digit codes")
        
        # Generate Python code
        python_dict = generate_python_dict(bus_stops)
        
        # Save to file
        output_file = "bus_stops_dict.py"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(python_dict)
        
        print(f"Saved to {output_file}")
        print(f"\nFirst 10 stops:")
        for i, (stop_code, stop_name) in enumerate(sorted(bus_stops.items())[:10]):
            print(f"  {stop_code}: {stop_name}")
        
        print(f"\nLast 10 stops:")
        for stop_code, stop_name in sorted(bus_stops.items())[-10:]:
            print(f"  {stop_code}: {stop_name}")
    else:
        print("No bus stops found")

# Rides-Review

A Spotify Wrapped style Transit Ridership Stats Infographic Maker

How to use (as of now):

1. Make a folder called "CompassData" in the project folder (same folder that contains main.py)
2. Download your compass card CSV file from the official compass website, preferrably an entire year's worth of data (choose previous year, or custom date range with start date at today of last year)
- You can also choose any custom date range on the compass website itself, by setting the start and end dates first, then downloading the CSV file after setting those dates
3. Upload your CSV download file into the CompassData folder
4. In main.py, at line 12, replace the part that says "CompassData/Compass Wrapped.csv" with "CompassData/(Your compass datafile name).csv"
5. Run: python main.py
- Your output should appear similar to the screenshot below:

Sample Terminal Output (Not real ridership data):
![Sample Output](Images/Screenshot%202025-09-08%20214851.jpg)

Goals:
- Use Flask to turn my project into a usable webapp
- Upload top 5 stations used like a "Spotify Wrapped" on stories
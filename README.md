# Rides-Review

A Spotify Wrapped style Transit Ridership Stats Infographic Maker

How to use (as of now):

1. Make a folder called "CompassData" in the project folder (same folder that contains main.py)
2. Download your compass card CSV file from the official website, preferrably an entire year's worth of data (choose previous year, or custom date range with start date at today of last year)
3. Upload your CSV download file into the CompassData folder
4. In main.py, at line 12, replace the part that says "CompassData/Compass Wrapped.csv" with "CompassData/(Your compass datafile name).csv"
5. Run: python main.py

Goals:
- Use Flask to turn my project into a usable webapp
- Upload top 5 stations used like a "Spotify Wrapped" on stories
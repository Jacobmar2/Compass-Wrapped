# Compass-Wrapped

Live Project: [https://compass-wrapped.onrender.com/](https://compass-wrapped.onrender.com/)

## What is Compass Wrapped?
 A “Spotify Wrapped” style transit ridership stats generator for Compass Card data

Compass-Wrapped takes your Compass Card CSV file and generates a fun, shareable “Wrapped” style summary of your annual transit usage. It shows stats like:

● 🎉 Total trips taken, as well as SkyTrain, SeaBus, WCE trips

● 🚉 Top 5 most-used SkyTrain stations

● 🗺️ Stations you’ve never visited

● Hours of the day bar graph

● Days of the week bar graph

The goal is to make your ridership patterns visual and shareable, similar to Spotify Wrapped.

Made by Jacob Martinez 

## Preview

![Compass Wrapped Summary](static/screenshots%20README/compass-wrapped-summary.png)

![Compass Wrapped Top 5 Stations](static/screenshots%20README/compass-wrapped-top-5-stations.png)

![Compass Wrapped Top Station](static/screenshots%20README/compass-wrapped-top-station.png)


## Notes

● Each trip is counted by each tap on a bus or each pair of taps on SkyTrain/SeaBus/WCE.

● SkyTrain trips are counted once for every 2 taps (entering and exiting) and for hours of day, days of week bar graphs (entrance timestamp only, just like buses), while station usage are counted both for each entry and each exit.

● Your CSV files will be private and will never be saved or uploaded anywhere. No data generated here will be saved anywhere either.

● You may insert a time range shorter than a year, where all of the stats except for average number of trips per day/week/month (in the green box) will stay accurate

● Image credit for Your Top Station goes to Wikimedia Commons, where all images are licensed under Creative Commons. Images are found from the station's main Wikipedia page.

● Not affiliated or supported by TransLink

● Uses MIT License

## How to Get Your Compass Card CSV File

1. Log in to your Compass Card account

- Go to the Compass Card website and sign in with your account. You will need access to the trip history section to download your CSV.

2. Select your Compass Card

3. Under “Compass Card Information”, select "View card usage”

4. Select your usage date range

- To get a year of ridership data, choose "previous year” for last year`s ridership, or “custom date range” with start date on January 1 of this year, and end date being today 

5. Download CSV from the download button.

## How to Host Locally

1. Download ZIP and extract files into a selected folder.

2. Using a terminal (with command prompt or an IDE of your choice), navigate to the selected folder, then to the Compass-Wrapped-main folder, by typing the following:

```bash
cd Compass-Wrapped-main
```

3. Type in terminal: 

```bash
python app.py
```

4. Open your browser at http://127.0.0.1:5000/ and upload your Compass Card CSV.

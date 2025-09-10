# Rides-Review

A “Spotify Wrapped” style transit ridership stats generator for Compass Card data

Rides-Review takes your Compass Card CSV file and generates a fun, shareable “Wrapped” style summary of your annual transit usage.
It shows stats like:
- 🎉 Total trips taken, as well as SkyTrain, SeaBus, WCE trips
- 🚉 Top 5 most-used SkyTrain stations
- 🗺️ Stations you’ve never visited

The goal is to make your ridership patterns visual and shareable, similar to Spotify Wrapped.

## Getting Started

### How to use (as of now)
1. Download Your Compass Data
- Log in to the Compass Card website
- Export your usage data as a CSV file (ideally 1 year of history)
2. Set Up the Project
- Clone this repo and create a folder called CompassData in the project root (same level as main.py).
3. Add Your CSV File
- Place your downloaded CSV into the CompassData/ folder
- In main.py, line 12, update the path from:
"CompassData/Compass Wrapped.csv"
to:
"CompassData/YourFileName.csv"
4. Run the Program
- python main.py
5. View Your Results

Your ridership stats will print in the terminal, like this (not real ridership data):
![Sample Output](Images/Screenshot%202025-09-08%20214851.jpg)

### Future Goals
- Build a web app version with Flask
- Add bar chart visualizations (Matplotlib / Plotly)
- Generate “Wrapped-style” graphics for Instagram sharing
- Add gamified stats (badges, milestones, etc.)

### Privacy Note
- This project runs entirely locally.
- Your Compass CSV is never uploaded or stored anywhere.
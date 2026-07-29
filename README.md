# Overview
A Python script that checks for active wildfires through NIFC WFIGS and active power outages through Cal OES near a location, and prints a report.

# Features

  - Pulls current wildfire incidents from the National Interagency Fire Center (NIFC) feed, excluding prescribed burns
  - Pulls active power outage data from Cal OES (PG&E, SCE, SDG&E, SMUD, LADWP), including planned and unplanned outages
  - Geocodes any address or place name via OpenStreetMap Nominatim, or accepts latitude and longitude coordinates
  - Checks within a chosen mileage of your location
  - Can repeat on a chosen interval
  - Prints a list to the terminal

# Requirements

  - Python 3.8+
  - requests module

# Usage

You can choose settings for the code to use:
  - MY_ADDRESS = "XYZ"
  - MY_RADIUS_MILES = 100
  - MY_INTERVAL_SECONDS = 300

Then just run it!

# Data Sources

  - Wildfires: NIFC WFIGS Incident Locations
  - Power outages: Cal OES Power Outages
  - Geocoding: OpenStreetMap Nominatim

# Limitations

  - Power outage information only covers California
  - Fire information only covers USA
  - Nominatim's usage policy limits request frequency, so avoid setting very small intervals

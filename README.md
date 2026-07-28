# wildfire-power-api
This project includes an API that gives fire information and an API that gives power outage information.

The fire information API inputs your location (in latitude and longitude coordinates or your city and state), a radius in miles, and a time x in seconds. It searches for wildfires within the radius of your location every x seconds and for each wildfire outputs the fire name, the distance from your location in miles, the acres burned, the containment as a percentage, and the county the fire is in.

The power outage API inputs your location (in latitude and longitude coordinates or your city and state), a radius in miles, and a time x in seconds. It searches for power outages within the radius of your location every x seconds and for each power outage outputs the electric company provider name that is experiencing an outage, the distance from your location in miles, the start date and time, the estimated restoration date and time, the county the outage is in, whether or not the outage was planned, the cause of the outage, and the number of customers impacted.


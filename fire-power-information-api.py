import argparse
import math
import sys
import time
from datetime import datetime
 
import requests
 
# ============================================================
#  SET YOUR VARIABLES HERE
# ============================================================
MY_ADDRESS = "Healdsburg, CA"   # <-- change this to your address, city, or coordinates
MY_RADIUS_MILES = 100           # <-- how far around you to search (used for both fires & outages)
MY_INTERVAL_SECONDS = 300       # <-- how often to refresh (300 = 5 min)
# ============================================================
 
NIFC_INCIDENTS_URL = (
    "https://services3.arcgis.com/T4QMspbfLg3qTGWY/arcgis/rest/services/"
    "WFIGS_Incident_Locations_Current/FeatureServer/0/query"
)
OUTAGE_QUERY_URL = (
    "https://services.arcgis.com/BLN4oKB0N1YSgvY8/ArcGIS/rest/services/"
    "Power_Outages_(View)/FeatureServer/0/query"
)
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "local-alerts-nearby-monitor/1.0 (personal use script)"
EARTH_RADIUS_MILES = 3958.8
 
 
# ------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------
def geocode_address(address: str):
    """Turn a free-text address/place into (lat, lon) using OSM Nominatim."""
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": USER_AGENT}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"Could not geocode address: {address!r}")
    return float(results[0]["lat"]), float(results[0]["lon"])
 
 
def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))
 
 
def extract_field(props: dict, *candidates, default="Unknown"):
    """Return the first present/non-empty value among several possible key names."""
    for key in candidates:
        if key in props and props[key] not in (None, ""):
            return props[key]
    return default
 
 
# ------------------------------------------------------------
# Wildfire section
# ------------------------------------------------------------
def fetch_incidents():
    """Fetch the current active wildland fire incidents from NIFC's WFIGS feed."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        # Exclude prescribed burns (RX) so results are actual wildfires/complexes.
        "where": "IncidentTypeCategory <> 'RX'",
        "outFields": "IncidentName,IncidentSize,PercentContained,POOCity,POOCounty,POOState",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(NIFC_INCIDENTS_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("features", [])
 
 
def build_location_desc(props: dict) -> str:
    """Build a human-readable location string from city/county/state fields."""
    city = props.get("POOCity")
    county = props.get("POOCounty")
    state = props.get("POOState")
    parts = []
    if city:
        parts.append(str(city))
    if county:
        county_str = str(county)
        parts.append(county_str if county_str.lower().endswith("county") else f"{county_str} County")
    if state:
        parts.append(str(state))
    return ", ".join(parts) if parts else "No location description available"
 
 
def nearby_fires(user_lat, user_lon, radius_miles=50.0):
    """Return a list of dicts describing active fires within radius_miles."""
    features = fetch_incidents()
    results = []
 
    for feature in features:
        props = feature.get("attributes", {}) or {}
        geom = feature.get("geometry", {}) or {}
        fire_lon, fire_lat = geom.get("x"), geom.get("y")
        if fire_lon is None or fire_lat is None:
            continue
 
        try:
            distance = haversine_miles(user_lat, user_lon, float(fire_lat), float(fire_lon))
        except (TypeError, ValueError):
            continue
 
        if distance > radius_miles:
            continue
 
        name = extract_field(props, "IncidentName")
        acres = extract_field(props, "IncidentSize", default="Not reported")
        containment = extract_field(props, "PercentContained", default="Not reported")
        location_desc = build_location_desc(props)
 
        results.append({
            "name": name,
            "acres": acres,
            "containment": containment,
            "location": location_desc,
            "distance_miles": round(distance, 1),
        })
 
    results.sort(key=lambda f: f["distance_miles"])
    return results
 
 
def format_containment(value):
    if isinstance(value, (int, float)):
        return f"{value}%"
    return str(value)
 
 
def print_fire_list(fires, radius_miles):
    print(f"\n=== Wildfire incidents within {radius_miles} miles ===")
    if not fires:
        print("No active fires found in range.")
        return
    for i, fire in enumerate(fires, 1):
        print(f"\n{i}. {fire['name']}  (~{fire['distance_miles']} mi away)")
        print(f"   Acres burned : {fire['acres']}")
        print(f"   Containment  : {format_containment(fire['containment'])}")
        print(f"   Location     : {fire['location']}")
 
 
# ------------------------------------------------------------
# Power outage section
# ------------------------------------------------------------
def fetch_active_outages():
    """Fetch currently active power outage incidents from Cal OES."""
    headers = {"User-Agent": USER_AGENT}
    params = {
        "where": "OutageStatus='Active'",
        "outFields": (
            "UtilityCompany,StartDate,EstimatedRestoreDate,Cause,"
            "ImpactedCustomers,County,OutageStatus,OutageType,IncidentId"
        ),
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "json",
    }
    resp = requests.get(OUTAGE_QUERY_URL, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("features", [])
 
 
def format_epoch_ms(value):
    """Convert an Esri epoch-milliseconds timestamp to a readable local string."""
    if value is None:
        return "Not reported"
    try:
        return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d %I:%M %p")
    except (TypeError, ValueError, OSError):
        return "Not reported"
 
 
def nearby_outages(user_lat, user_lon, radius_miles=3.0):
    """Return a list of dicts describing active outages within radius_miles."""
    features = fetch_active_outages()
    results = []
 
    for feature in features:
        props = feature.get("attributes", {}) or {}
        geom = feature.get("geometry", {}) or {}
        outage_lon, outage_lat = geom.get("x"), geom.get("y")
        if outage_lon is None or outage_lat is None:
            continue
 
        try:
            distance = haversine_miles(user_lat, user_lon, float(outage_lat), float(outage_lon))
        except (TypeError, ValueError):
            continue
 
        if distance > radius_miles:
            continue
 
        results.append({
            "utility": props.get("UtilityCompany") or "Unknown utility",
            "started": format_epoch_ms(props.get("StartDate")),
            "eta_restore": format_epoch_ms(props.get("EstimatedRestoreDate")),
            "location": (props.get("County") or "Unknown") + " County",
            "planned": props.get("OutageType") or "Unknown",
            "cause": props.get("Cause") or "Not reported",
            "impacted_customers": props.get("ImpactedCustomers"),
            "incident_id": props.get("IncidentId") or "N/A",
            "distance_miles": round(distance, 1),
        })
 
    results.sort(key=lambda o: o["distance_miles"])
    return results
 
 
def print_outage_status(outages, radius_miles):
    print(f"\n=== Power outage check within {radius_miles} mi ===")
 
    if not outages:
        print("No active tracked outages found near you. You do not appear to be in an outage.")
        return
 
    print(f"You ARE near {len(outages)} active outage(s):")
    for i, o in enumerate(outages, 1):
        print(f"\n{i}. {o['utility']}  (~{o['distance_miles']} mi away, incident {o['incident_id']})")
        print(f"   Started              : {o['started']}")
        print(f"   Estimated restoration: {o['eta_restore']}")
        print(f"   Location             : {o['location']}")
        print(f"   Planned outage?      : {o['planned']}")
        print(f"   Cause                : {o['cause']}")
        if o["impacted_customers"] is not None:
            print(f"   Customers impacted   : {o['impacted_customers']}")
 
 
# ------------------------------------------------------------
# Combined runner
# ------------------------------------------------------------
def run_checks(lat, lon, radius_miles):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n############################################")
    print(f"#  Local Alerts Check — {timestamp}")
    print(f"############################################")
 
    try:
        fires = nearby_fires(lat, lon, radius_miles)
        print_fire_list(fires, radius_miles)
    except requests.RequestException as e:
        print(f"[Error] Failed to fetch wildfire data: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[Error] Unexpected failure (fires): {e}", file=sys.stderr)
 
    try:
        outages = nearby_outages(lat, lon, radius_miles)
        print_outage_status(outages, radius_miles)
    except requests.RequestException as e:
        print(f"[Error] Failed to fetch outage data: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[Error] Unexpected failure (outages): {e}", file=sys.stderr)
 
 
def main():
    parser = argparse.ArgumentParser(
        description="Monitor nearby active wildfire incidents AND power outages in one pass (California)."
    )
    loc_group = parser.add_mutually_exclusive_group()
    loc_group.add_argument("--address", help="Address or place name to geocode.")
    loc_group.add_argument("--lat", type=float, help="Latitude of your location.")
    parser.add_argument("--lon", type=float, help="Longitude of your location (required with --lat).")
    parser.add_argument("--radius", type=float, default=MY_RADIUS_MILES, help=f"Search radius in miles (default: {MY_RADIUS_MILES}).")
    parser.add_argument("--interval", type=int, default=MY_INTERVAL_SECONDS, help=f"Polling interval in seconds (default: {MY_INTERVAL_SECONDS}).")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit, instead of polling.")
    args = parser.parse_args()
 
    # If no --address/--lat was passed on the command line, fall back to
    # the MY_ADDRESS variable set at the top of this file.
    if not args.address and args.lat is None:
        args.address = MY_ADDRESS
 
    if args.address:
        try:
            lat, lon = geocode_address(args.address)
        except Exception as e:
            print(f"Error geocoding address: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        if args.lon is None:
            parser.error("--lon is required when using --lat")
        lat, lon = args.lat, args.lon
 
    print(f"Monitoring location: {lat:.4f}, {lon:.4f}  |  radius: {args.radius} mi  |  interval: {args.interval}s")
    print("Note: power outage data covers California only (PG&E, SCE, SDG&E, SMUD, LADWP).")
 
    while True:
        run_checks(lat, lon, args.radius)
 
        if args.once:
            break
        time.sleep(args.interval)
 
 
if __name__ == "__main__":
    main()
import os

import requests

from config import CURRENCY, MAX_RESULTS

SERPAPI_URL = "https://serpapi.com/search"
REQUEST_TIMEOUT = 15

TRIP_TYPE_CODES = {"one_way": "2", "round_trip": "1"}


class FlightSearchError(Exception):
    pass


def _parse_flight_group(group: dict, origin: str, destination: str, is_best: bool) -> dict:
    legs = group.get("flights", [])
    first, last = legs[0], legs[-1]

    return {
        "airline": first.get("airline", "Unknown"),
        "flight_number": first.get("flight_number", "N/A"),
        "departure_airport": first.get("departure_airport", {}).get("name", origin),
        "departure_time": first.get("departure_airport", {}).get("time", "N/A"),
        "arrival_airport": last.get("arrival_airport", {}).get("name", destination),
        "arrival_time": last.get("arrival_airport", {}).get("time", "N/A"),
        "stops": len(legs) - 1,
        "duration_minutes": group.get("total_duration", 0),
        "price": group.get("price", 0),
        "is_best": is_best,
    }


def search_flights(origin, destination, outbound_date, trip_type="one_way", return_date=None):
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": outbound_date,
        "type": TRIP_TYPE_CODES.get(trip_type, "2"),
        "currency": CURRENCY,
        "hl": "en",
        "api_key": api_key,
    }
    if trip_type == "round_trip" and return_date:
        params["return_date"] = return_date

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise FlightSearchError("The flight provider did not respond in time.")
    except requests.exceptions.RequestException as exc:
        raise FlightSearchError(f"Flight provider request failed: {exc}")

    payload = response.json()
    best = payload.get("best_flights", [])
    others = payload.get("other_flights", [])
    groups = best + others

    if not groups:
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "date": outbound_date,
            "flights": [],
            "message": f"No flights found from {origin.upper()} to {destination.upper()} on {outbound_date}.",
        }

    best_ids = {id(g) for g in best}
    flights = [
        _parse_flight_group(g, origin, destination, id(g) in best_ids)
        for g in groups[:MAX_RESULTS]
        if g.get("flights")
    ]
    flights.sort(key=lambda f: f["price"])

    return {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "date": outbound_date,
        "trip_type": trip_type,
        "total_found": len(groups),
        "flights": flights,
    }

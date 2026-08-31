import os
import time

import requests

from config import CURRENCY, MAX_RESULTS
import booking_links

SERPAPI_URL = "https://serpapi.com/search"
REQUEST_TIMEOUT = 15
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1

TRIP_TYPE_CODES = {"one_way": "2", "round_trip": "1"}
CABIN_CLASS_CODES = {"economy": "1", "premium_economy": "2", "business": "3", "first": "4"}


class FlightSearchError(Exception):
    pass


def _request_with_retry(params):
    """GET the SerpAPI endpoint, retrying once on transient network failures
    (timeout, connection drop). Does not retry on non-transient errors like a
    bad API key or malformed request — a retry would just fail the same way."""
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(SERPAPI_URL, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.Timeout:
            last_error = FlightSearchError("The flight provider did not respond in time.")
        except requests.exceptions.ConnectionError:
            last_error = FlightSearchError("Could not connect to the flight provider.")
        except requests.exceptions.RequestException as exc:
            raise FlightSearchError(f"Flight provider request failed: {exc}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(RETRY_DELAY_SECONDS)

    raise last_error


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
        "booking_token": group.get("booking_token"),
    }


def search_flights(
    origin,
    destination,
    outbound_date,
    trip_type="one_way",
    return_date=None,
    cabin_class="economy",
    passengers=1,
):
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": outbound_date,
        "type": TRIP_TYPE_CODES.get(trip_type, "2"),
        "travel_class": CABIN_CLASS_CODES.get(cabin_class, "1"),
        "adults": passengers,
        "currency": CURRENCY,
        "hl": "en",
        "api_key": api_key,
    }
    if trip_type == "round_trip" and return_date:
        params["return_date"] = return_date

    response = _request_with_retry(params)

    payload = response.json()
    best = payload.get("best_flights", [])
    others = payload.get("other_flights", [])
    groups = best + others

    if not groups:
        return {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "date": outbound_date,
            "cabin_class": cabin_class,
            "passengers": passengers,
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
    for i, f in enumerate(flights, start=1):
        f["option"] = i

    return {
        "origin": origin.upper(),
        "destination": destination.upper(),
        "date": outbound_date,
        "trip_type": trip_type,
        "cabin_class": cabin_class,
        "passengers": passengers,
        "total_found": len(groups),
        "flights": flights,
    }


def get_booking_options(
    booking_token,
    origin,
    destination,
    outbound_date,
    trip_type="one_way",
    return_date=None,
    cabin_class="economy",
    passengers=1,
):
    """Resolve a specific flight's booking_token into real ways to book it:
    a seller name, a price, and either a bookable link or a phone number.
    Requires the same search parameters as the original search_flights call —
    SerpAPI ties the booking_token to that exact query context."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": origin.upper(),
        "arrival_id": destination.upper(),
        "outbound_date": outbound_date,
        "type": TRIP_TYPE_CODES.get(trip_type, "2"),
        "travel_class": CABIN_CLASS_CODES.get(cabin_class, "1"),
        "adults": passengers,
        "currency": CURRENCY,
        "hl": "en",
        "booking_token": booking_token,
        "api_key": api_key,
    }
    if trip_type == "round_trip" and return_date:
        params["return_date"] = return_date

    response = _request_with_retry(params)
    payload = response.json()

    raw_options = payload.get("booking_options", [])
    if not raw_options:
        return {"options": [], "message": "No booking options were returned for this flight."}

    options = []
    for i, opt in enumerate(raw_options, start=1):
        
        if opt.get("separate_tickets") and opt.get("departing"):
            leg = opt["departing"]
        else:
            leg = opt.get("together") or opt.get("departing")
        if not leg:
            continue

        entry = {
            "option": i,
            "book_with": leg.get("book_with", "Unknown seller"),
            "price": leg.get("price"),
        }
        if leg.get("option_title"):
            entry["fare_type"] = leg["option_title"]

        booking_request = leg.get("booking_request")
        if booking_request and booking_request.get("post_data"):
            entry["booking_link"] = booking_links.create_link(
                booking_request["url"], booking_request["post_data"]
            )
        elif leg.get("booking_phone"):
            entry["booking_phone"] = leg["booking_phone"]

        options.append(entry)

    return {"options": options}
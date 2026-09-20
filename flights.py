import os
import time

import requests
from pydantic import ValidationError

from config import CURRENCY, MAX_RESULTS
import booking_links
from schemas import (
    BookingOptionsRequest,
    BookingOptionsResult,
    FlightSearchRequest,
    FlightSearchResult,
    ReturnFlightSearchRequest,
    ReturnFlightSearchResult,
)

SERPAPI_URL = "https://serpapi.com/search"
REQUEST_TIMEOUT = 15
MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1

TRIP_TYPE_CODES = {"one_way": "2", "round_trip": "1"}
CABIN_CLASS_CODES = {"economy": "1", "premium_economy": "2", "business": "3", "first": "4"}


class FlightSearchError(Exception):
    pass


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _request_with_retry(params):
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
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in RETRYABLE_STATUS_CODES:
                last_error = FlightSearchError(
                    f"The flight provider returned a temporary error ({status})."
                )
            else:
                raise FlightSearchError(f"Flight provider request failed: {exc}")
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
        "departure_token": group.get("departure_token"),
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
    try:
        req = FlightSearchRequest(
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            trip_type=trip_type,
            return_date=return_date,
            cabin_class=cabin_class,
            passengers=passengers,
        )
    except ValidationError as exc:
        raise FlightSearchError(f"Invalid search parameters: {exc}")

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": req.origin,
        "arrival_id": req.destination,
        "outbound_date": req.outbound_date,
        "type": TRIP_TYPE_CODES.get(req.trip_type, "2"),
        "travel_class": CABIN_CLASS_CODES.get(req.cabin_class, "1"),
        "adults": req.passengers,
        "currency": CURRENCY,
        "hl": "en",
        "api_key": api_key,
    }
    if req.trip_type == "round_trip" and req.return_date:
        params["return_date"] = req.return_date

    response = _request_with_retry(params)

    payload = response.json()
    best = payload.get("best_flights", [])
    others = payload.get("other_flights", [])
    groups = best + others

    if not groups:
        return FlightSearchResult(
            origin=req.origin,
            destination=req.destination,
            date=req.outbound_date,
            cabin_class=req.cabin_class,
            passengers=req.passengers,
            flights=[],
            message=f"No flights found from {req.origin} to {req.destination} on {req.outbound_date}.",
        ).model_dump(exclude_none=True)

    best_ids = {id(g) for g in best}
    flights = [
        _parse_flight_group(g, req.origin, req.destination, id(g) in best_ids)
        for g in groups[:MAX_RESULTS]
        if g.get("flights")
    ]
    flights.sort(key=lambda f: f["price"])
    for i, f in enumerate(flights, start=1):
        f["option"] = i

    return FlightSearchResult(
        origin=req.origin,
        destination=req.destination,
        date=req.outbound_date,
        trip_type=req.trip_type,
        cabin_class=req.cabin_class,
        passengers=req.passengers,
        total_found=len(groups),
        flights=flights,
    ).model_dump(exclude_none=True)


def search_return_flights(
    departure_token,
    origin,
    destination,
    outbound_date,
    return_date,
    cabin_class="economy",
    passengers=1,
):
    try:
        req = ReturnFlightSearchRequest(
            departure_token=departure_token,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            return_date=return_date,
            cabin_class=cabin_class,
            passengers=passengers,
        )
    except ValidationError as exc:
        raise FlightSearchError(f"Invalid return-flight request: {exc}")

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": req.origin,
        "arrival_id": req.destination,
        "outbound_date": req.outbound_date,
        "return_date": req.return_date,
        "type": TRIP_TYPE_CODES["round_trip"],
        "travel_class": CABIN_CLASS_CODES.get(req.cabin_class, "1"),
        "adults": req.passengers,
        "currency": CURRENCY,
        "hl": "en",
        "departure_token": req.departure_token,
        "api_key": api_key,
    }

    response = _request_with_retry(params)
    payload = response.json()

    best = payload.get("best_flights", [])
    others = payload.get("other_flights", [])
    groups = best + others

    if not groups:
        return ReturnFlightSearchResult(
            origin=req.origin,
            destination=req.destination,
            return_date=req.return_date,
            return_flights=[],
            message="No return flight combinations were found for this outbound flight.",
        ).model_dump(exclude_none=True)

    best_ids = {id(g) for g in best}
    return_flights = [
        _parse_flight_group(g, req.destination, req.origin, id(g) in best_ids)
        for g in groups[:MAX_RESULTS]
        if g.get("flights")
    ]
    return_flights.sort(key=lambda f: f["price"])
    for i, f in enumerate(return_flights, start=1):
        f["return_option"] = i

    return ReturnFlightSearchResult(
        origin=req.origin,
        destination=req.destination,
        outbound_date=req.outbound_date,
        return_date=req.return_date,
        return_flights=return_flights,
    ).model_dump(exclude_none=True)


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
    try:
        req = BookingOptionsRequest(
            booking_token=booking_token,
            origin=origin,
            destination=destination,
            outbound_date=outbound_date,
            trip_type=trip_type,
            return_date=return_date,
            cabin_class=cabin_class,
            passengers=passengers,
        )
    except ValidationError as exc:
        raise FlightSearchError(f"Invalid booking request: {exc}")

    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        raise FlightSearchError("SERPAPI_KEY is not configured.")

    params = {
        "engine": "google_flights",
        "departure_id": req.origin,
        "arrival_id": req.destination,
        "outbound_date": req.outbound_date,
        "type": TRIP_TYPE_CODES.get(req.trip_type, "2"),
        "travel_class": CABIN_CLASS_CODES.get(req.cabin_class, "1"),
        "adults": req.passengers,
        "currency": CURRENCY,
        "hl": "en",
        "booking_token": req.booking_token,
        "api_key": api_key,
    }
    if req.trip_type == "round_trip" and req.return_date:
        params["return_date"] = req.return_date

    response = _request_with_retry(params)
    payload = response.json()

    raw_options = payload.get("booking_options", [])
    if not raw_options:
        return BookingOptionsResult(
            options=[], message="No booking options were returned for this flight."
        ).model_dump(exclude_none=True)

    def _make_entry(leg: dict, leg_label=None) -> dict:
        entry = {
            "book_with": leg.get("book_with", "Unknown seller"),
            "price": leg.get("price"),
        }
        if leg_label:
            entry["leg"] = leg_label
        if leg.get("option_title"):
            entry["fare_type"] = leg["option_title"]

        booking_request = leg.get("booking_request")
        if booking_request and booking_request.get("post_data") and booking_request.get("url"):
            entry["booking_link"] = booking_links.create_link(
                booking_request["url"], booking_request["post_data"]
            )
        elif leg.get("booking_phone"):
            entry["booking_phone"] = leg["booking_phone"]
        else:
            entry["no_direct_booking"] = True

        return entry

    options = []
    for opt in raw_options:
        if opt.get("separate_tickets"):
            if opt.get("departing"):
                options.append(_make_entry(opt["departing"], "outbound"))
            if opt.get("returning"):
                options.append(_make_entry(opt["returning"], "return"))
        else:
            leg = opt.get("together") or opt.get("departing")
            if leg:
                options.append(_make_entry(leg, None))

    return BookingOptionsResult(options=options).model_dump(exclude_none=True)
from datetime import datetime

SKYSCANNER_CABIN_CODES = {
    "economy": "economy",
    "premium_economy": "premiumeconomy",
    "business": "business",
    "first": "first",
}


def _to_skyscanner_date(date_str: str) -> str:
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%y%m%d")


def build_skyscanner_link(
    origin,
    destination,
    outbound_date,
    return_date=None,
    cabin_class="economy",
    passengers=1,
) -> str:
    origin_code = origin.lower()
    destination_code = destination.lower()
    outbound = _to_skyscanner_date(outbound_date)

    url = f"https://www.skyscanner.net/transport/flights/{origin_code}/{destination_code}/{outbound}/"
    if return_date:
        url += f"{_to_skyscanner_date(return_date)}/"

    cabin = SKYSCANNER_CABIN_CODES.get(cabin_class, "economy")
    url += f"?adultsv2={passengers}&cabinclass={cabin}&rtn={1 if return_date else 0}"
    return url


def search_budget_carriers(
    origin,
    destination,
    outbound_date,
    trip_type="one_way",
    return_date=None,
    cabin_class="economy",
    passengers=1,
) -> dict:
    link = build_skyscanner_link(
        origin,
        destination,
        outbound_date,
        return_date if trip_type == "round_trip" else None,
        cabin_class,
        passengers,
    )
    return {
        "provider": "Skyscanner",
        "origin": origin.upper(),
        "destination": destination.upper(),
        "date": outbound_date,
        "search_link": link,
        "message": (
            "This is a prefilled search link, not live prices pulled into this "
            "chat — open it to see results including budget carriers Google "
            "Flights' data often misses (e.g. Pegasus, Wizz Air, Ryanair). "
            "Kiwi.com is also worth checking separately for the same reason."
        ),
    }
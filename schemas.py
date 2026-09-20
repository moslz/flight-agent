import re
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

IATA_RE = re.compile(r"^[A-Za-z]{3}$")
TRIP_TYPES = ("one_way", "round_trip")
CABIN_CLASSES = ("economy", "premium_economy", "business", "first")


def _parse_date(v):
    try:
        parsed = date.fromisoformat(v)
    except (TypeError, ValueError):
        raise ValueError(f"'{v}' is not a valid YYYY-MM-DD date")
    if parsed < date.today():
        raise ValueError(f"'{v}' is in the past")
    return v


def _check_return_after_outbound(outbound_date, return_date):
    if return_date is not None and date.fromisoformat(return_date) < date.fromisoformat(outbound_date):
        raise ValueError("return_date cannot be before outbound_date")


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    outbound_date: str
    trip_type: str = "one_way"
    return_date: Optional[str] = None
    cabin_class: str = "economy"
    passengers: int = Field(default=1, ge=1)

    @field_validator("origin", "destination")
    @classmethod
    def _iata(cls, v):
        if not IATA_RE.match(v):
            raise ValueError(f"'{v}' is not a 3-letter IATA code")
        return v.upper()

    @field_validator("outbound_date", "return_date")
    @classmethod
    def _date(cls, v):
        return _parse_date(v) if v is not None else v

    @field_validator("trip_type")
    @classmethod
    def _trip_type(cls, v):
        if v not in TRIP_TYPES:
            raise ValueError(f"'{v}' is not one_way or round_trip")
        return v

    @field_validator("cabin_class")
    @classmethod
    def _cabin_class(cls, v):
        if v not in CABIN_CLASSES:
            raise ValueError(f"'{v}' is not a recognized cabin class")
        return v

    @model_validator(mode="after")
    def _check_dates(self):
        if self.trip_type == "round_trip":
            _check_return_after_outbound(self.outbound_date, self.return_date)
        return self


class ReturnFlightSearchRequest(BaseModel):
    departure_token: str
    origin: str
    destination: str
    outbound_date: str
    return_date: str
    cabin_class: str = "economy"
    passengers: int = Field(default=1, ge=1)

    @field_validator("departure_token")
    @classmethod
    def _token(cls, v):
        if not v or v.strip().lower() == "null":
            raise ValueError("departure_token is missing or invalid")
        return v

    @field_validator("origin", "destination")
    @classmethod
    def _iata(cls, v):
        if not IATA_RE.match(v):
            raise ValueError(f"'{v}' is not a 3-letter IATA code")
        return v.upper()

    @field_validator("outbound_date", "return_date")
    @classmethod
    def _date(cls, v):
        return _parse_date(v)

    @field_validator("cabin_class")
    @classmethod
    def _cabin_class(cls, v):
        if v not in CABIN_CLASSES:
            raise ValueError(f"'{v}' is not a recognized cabin class")
        return v

    @model_validator(mode="after")
    def _check_dates(self):
        _check_return_after_outbound(self.outbound_date, self.return_date)
        return self


class BookingOptionsRequest(BaseModel):
    booking_token: str
    origin: str
    destination: str
    outbound_date: str
    trip_type: str = "one_way"
    return_date: Optional[str] = None
    cabin_class: str = "economy"
    passengers: int = Field(default=1, ge=1)

    @field_validator("booking_token")
    @classmethod
    def _token(cls, v):
        if not v or v.strip().lower() == "null":
            raise ValueError("booking_token is missing or invalid")
        return v

    @field_validator("origin", "destination")
    @classmethod
    def _iata(cls, v):
        if not IATA_RE.match(v):
            raise ValueError(f"'{v}' is not a 3-letter IATA code")
        return v.upper()

    @field_validator("outbound_date", "return_date")
    @classmethod
    def _date(cls, v):
        return _parse_date(v) if v is not None else v

    @field_validator("trip_type")
    @classmethod
    def _trip_type(cls, v):
        if v not in TRIP_TYPES:
            raise ValueError(f"'{v}' is not one_way or round_trip")
        return v

    @field_validator("cabin_class")
    @classmethod
    def _cabin_class(cls, v):
        if v not in CABIN_CLASSES:
            raise ValueError(f"'{v}' is not a recognized cabin class")
        return v

    @model_validator(mode="after")
    def _check_dates(self):
        if self.trip_type == "round_trip":
            _check_return_after_outbound(self.outbound_date, self.return_date)
        return self


class Flight(BaseModel):
    airline: str
    flight_number: str
    departure_airport: str
    departure_time: str
    arrival_airport: str
    arrival_time: str
    stops: int
    duration_minutes: int
    price: float
    is_best: bool
    booking_token: Optional[str] = None
    departure_token: Optional[str] = None
    option: Optional[int] = None
    return_option: Optional[int] = None


class FlightSearchResult(BaseModel):
    origin: str
    destination: str
    date: str
    trip_type: Optional[str] = None
    cabin_class: str
    passengers: int
    total_found: Optional[int] = None
    flights: list[Flight] = Field(default_factory=list)
    message: Optional[str] = None


class ReturnFlightSearchResult(BaseModel):
    origin: str
    destination: str
    outbound_date: Optional[str] = None
    return_date: str
    return_flights: list[Flight] = Field(default_factory=list)
    message: Optional[str] = None


class BookingOption(BaseModel):
    book_with: str
    price: Optional[float] = None
    fare_type: Optional[str] = None
    leg: Optional[str] = None
    booking_link: Optional[str] = None
    booking_phone: Optional[str] = None
    no_direct_booking: Optional[bool] = None


class BookingOptionsResult(BaseModel):
    options: list[BookingOption] = Field(default_factory=list)
    message: Optional[str] = None
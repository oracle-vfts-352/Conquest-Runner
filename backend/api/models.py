"""Data types shared inside the API layer."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class GpsSample:
    """One validated GPS point from a route."""

    latitude: float
    longitude: float
    timestamp: datetime  # timezone-aware, UTC
    accuracy_meters: float

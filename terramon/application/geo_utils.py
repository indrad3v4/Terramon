"""Geo helpers shared between the application layer and the TMA frontend.

G03: the TMA capture path validates raw coordinates before building a
GeoContext. _validate_coords lives here (application layer) so the frontend
imports it without reaching into adapters, and so the validation rules are
unit-testable offline.
"""

from __future__ import annotations

import math


def _validate_coords(lat, lon) -> tuple[float, float] | None:
    """Sanitize a raw (lat, lon) pair into floats, or None if unusable.

    Rules:
      - lat must be a finite number in [-90, 90];
      - lon must be a finite number in [-180, 180];
      - None / NaN / strings that don't parse / out-of-range -> None.

    Returns the float tuple so callers always store canonical WGS84 floats.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(lat_f) or not math.isfinite(lon_f):
        return None
    if not (-90.0 <= lat_f <= 90.0):
        return None
    if not (-180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f

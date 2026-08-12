"""Place-name geocoding backed by OpenStreetMap Nominatim."""

import httpx


def geocode(place: str) -> tuple[float, float] | None:
    if not place.strip():
        return None
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{place.strip()}, 대한민국", "format": "jsonv2", "limit": 1, "countrycodes": "kr"},
            headers={"User-Agent": "Hawk-AI/1.0 local-inspection-app"},
            timeout=10,
            follow_redirects=True,
        )
        response.raise_for_status()
        results = response.json()
        return (float(results[0]["lat"]), float(results[0]["lon"])) if results else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None

"""Google Maps Geocoding API implementation."""

import os
import re
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class StandardizedAddress:
    """Standardized Australian address components."""

    street_number: Optional[str] = None
    street_name: Optional[str] = None
    suburb: Optional[str] = None
    state: Optional[str] = None
    postcode: Optional[str] = None
    unit: Optional[str] = None
    level: Optional[str] = None
    lot_no: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class GoogleMapsGeocoder:
    """Client for Google Maps Geocoding API address standardization."""

    BASE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize Google Maps Geocoder.

        Args:
            api_key: Google Maps API key (defaults to GOOGLE_MAPS_API_KEY env var)
            timeout: HTTP request timeout in seconds

        Raises:
            ValueError: If API key not provided and env var not set
        """
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")
        self.timeout = timeout

        if not self.api_key:
            raise ValueError(
                "API key required. Provide as argument or set GOOGLE_MAPS_API_KEY env var."
            )

    def geocode_address(self, address: str) -> StandardizedAddress:
        """
        Geocode a free-text Australian address and standardize it.

        Args:
            address: Free-text address string

        Returns:
            StandardizedAddress with parsed components

        Raises:
            ValueError: If address cannot be geocoded or is not in Australia
        """
        params = {
            "address": address,
            "region": "au",
            "key": self.api_key,
        }

        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"

        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as e:
            raise ValueError(f"Failed to geocode address: {e}")

        results = data.get("results", [])
        if not results:
            raise ValueError(f"Address not found: {address}")

        # Use the first result (most relevant match)
        result = results[0]

        # Extract coordinates
        lat = result.get("geometry", {}).get("location", {}).get("lat")
        lng = result.get("geometry", {}).get("location", {}).get("lng")

        # Parse address components
        address_components = result.get("address_components", [])
        return self._parse_address_components(address_components, lat, lng)

    def _parse_address_components(
        self, components: list, lat: Optional[float], lng: Optional[float]
    ) -> StandardizedAddress:
        """
        Parse Google Maps address components into StandardizedAddress.

        Args:
            components: Address components from Google Maps API
            lat: Latitude coordinate
            lng: Longitude coordinate

        Returns:
            StandardizedAddress with extracted fields
        """
        address = StandardizedAddress(latitude=lat, longitude=lng)

        component_map = {}
        for component in components:
            types = component.get("types", [])
            short_name = component.get("short_name", "")
            long_name = component.get("long_name", "")

            for type_key in types:
                component_map[type_key] = (short_name, long_name)

        # Extract standard address components
        if "street_number" in component_map:
            address.street_number = component_map["street_number"][0]

        if "route" in component_map:
            address.street_name = component_map["route"][1]

        if "locality" in component_map:
            address.suburb = component_map["locality"][1]

        if "administrative_area_level_1" in component_map:
            address.state = component_map["administrative_area_level_1"][0]

        if "postal_code" in component_map:
            address.postcode = component_map["postal_code"][0]

        return address

    def parse_free_text_address(self, address: str) -> StandardizedAddress:
        """
        Parse a free-text address string, handling edge cases.

        This method attempts to extract unit/level/lot numbers from the address
        before geocoding, then combines results.

        Args:
            address: Free-text address string (may include unit, level, lot numbers)

        Returns:
            StandardizedAddress with all parsed components

        Raises:
            ValueError: If address cannot be parsed or geocoded
        """
        # Extract edge case components (unit, level, lot)
        unit, level, lot_no, clean_address = self._extract_edge_cases(address)

        # Geocode the clean address
        standardized = self.geocode_address(clean_address)

        # Add extracted edge case components
        if unit:
            standardized.unit = unit
        if level:
            standardized.level = level
        if lot_no:
            standardized.lot_no = lot_no

        return standardized

    def _extract_edge_cases(self, address: str) -> tuple[Optional[str], Optional[str], Optional[str], str]:
        """
        Extract unit, level, and lot numbers from address string.

        Args:
            address: Free-text address string

        Returns:
            Tuple of (unit, level, lot_no, clean_address)
        """
        unit = None
        level = None
        lot_no = None
        clean = address

        # Extract unit number (Unit X, Unit #X, U X, etc.)
        unit_match = re.search(r"(?:Unit|U\.?|Apt\.?|Apartment)\s*(?:#)?(\d+[A-Z]?)", clean, re.IGNORECASE)
        if unit_match:
            unit = unit_match.group(1)
            clean = re.sub(r"(?:Unit|U\.?|Apt\.?|Apartment)\s*(?:#)?\d+[A-Z]?\s*[,/-]?\s*", "", clean, flags=re.IGNORECASE)

        # Extract level number (Level X, L X, Floor X, etc.)
        level_match = re.search(r"(?:Level|L\.?|Floor|Fl\.?)\s*(?:#)?(\d+)", clean, re.IGNORECASE)
        if level_match:
            level = level_match.group(1)
            clean = re.sub(r"(?:Level|L\.?|Floor|Fl\.?)\s*(?:#)?\d+\s*[,/-]?\s*", "", clean, flags=re.IGNORECASE)

        # Extract lot number (Lot X, LOT X, etc.)
        lot_match = re.search(r"(?:Lot|LOT)\s*(?:#)?(\d+)", clean, re.IGNORECASE)
        if lot_match:
            lot_no = lot_match.group(1)
            clean = re.sub(r"(?:Lot|LOT)\s*(?:#)?\d+\s*[,/-]?\s*", "", clean, flags=re.IGNORECASE)

        # Clean up extra whitespace and commas
        clean = re.sub(r"\s+", " ", clean).strip()
        clean = re.sub(r"[,\s]+$", "", clean)

        return unit, level, lot_no, clean

"""Integration layer combining address standardisation and NBN lookup."""

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from gmaps.geocoder import GoogleMapsGeocoder, StandardizedAddress
from iperium.client import IperiumClient

logger = logging.getLogger(__name__)


def serviceability_status_to_numeric(status: Optional[str]) -> Optional[int]:
    """Convert serviceability status text to numeric code.

    Codes:
    1 = Serviceable
    2 = Future serviceable
    3 = Not serviceable
    4 = Unknown
    """
    if not status:
        return None
    status_lower = status.lower()
    mapping = {
        "serviceable": 1,
        "future serviceable": 2,
        "not serviceable": 3,
    }
    return mapping.get(status_lower, 4)


@dataclass
class NBNResult:
    """Parsed NBN availability result for a single address entry."""

    input_address: Optional[str]
    loc_id: Optional[str]
    match: Optional[str]
    address: Optional[str]
    technology: Optional[str]
    serviceability: Optional[int]
    ports_free: Optional[int]
    ports_used: Optional[int]
    ports_total: Optional[int]
    # Legacy fields (kept for backwards compatibility but not displayed)
    service_class: Optional[str]
    fibre_on_demand: Optional[bool]

    def format_message(self) -> str:
        lines = []
        if self.input_address:
            lines.append(f"*Input Address:* {self.input_address}")
        if self.address:
            lines.append(f"*Matched Address:* {self.address}")
        if self.loc_id:
            lines.append(f"*Location ID:* {self.loc_id}")
        if self.technology:
            lines.append(f"*Available Technology:* {self.technology}")
        if self.serviceability is not None:
            status_text = {
                1: "Serviceable",
                2: "Future Serviceable",
                3: "Not Serviceable",
                4: "Unknown",
            }.get(self.serviceability, f"Unknown ({self.serviceability})")
            lines.append(f"*Serviceability:* {status_text}")
        if self.ports_total is not None:
            ports_display = f"{self.ports_free}/{self.ports_used}/{self.ports_total}"
            lines.append(f"*Ports:* {ports_display}")
        return "\n".join(lines) if lines else "No details available."


class NBNService:
    """Orchestrates address geocoding and Iperium NBN lookup."""

    def __init__(
        self,
        iperium_client: Optional[IperiumClient] = None,
        geocoder: Optional[GoogleMapsGeocoder] = None,
    ):
        self.iperium = iperium_client or IperiumClient()
        self.geocoder = geocoder or GoogleMapsGeocoder()

    async def lookup(self, free_text_address: str) -> List[NBNResult]:
        """
        Geocode a free-text address then perform an NBN lookup.

        Args:
            free_text_address: Natural-language address string

        Returns:
            List of NBNResult objects (may be empty if address not serviceable)

        Raises:
            ValueError: If address cannot be geocoded
            httpx.HTTPError: If Iperium API call fails
        """
        logger.info("Geocoding address: %s", free_text_address)
        addr: StandardizedAddress = self.geocoder.parse_free_text_address(free_text_address)
        logger.info("Standardised: %s", addr)

        if not addr.street_name or not addr.suburb or not addr.state or not addr.postcode:
            raise ValueError(
                f"Could not extract required address fields from: {free_text_address!r}"
            )

        lookup_kwargs: Dict[str, Any] = {
            "street_name": addr.street_name,
            "suburb": addr.suburb,
            "state": addr.state,
            "postcode": addr.postcode,
        }
        if addr.street_number:
            try:
                lookup_kwargs["street_number"] = int(addr.street_number)
            except ValueError:
                pass
        if addr.unit:
            lookup_kwargs["unit"] = addr.unit
        if addr.level:
            lookup_kwargs["level"] = addr.level
        if addr.lot_no:
            try:
                lookup_kwargs["lot_no"] = int(addr.lot_no)
            except ValueError:
                pass

        logger.info("Calling Iperium with: %s", lookup_kwargs)
        response = await self.iperium.lookup_address(**lookup_kwargs)
        logger.info("Full API response: %s", response)
        results = self._parse_response(response, free_text_address)

        # Fetch service details for each result to get port information
        enriched_results = []
        for result in results:
            if result.loc_id:
                try:
                    service_details = await self.iperium.get_service_details(result.loc_id)
                    result = self._enrich_with_service_details(result, service_details)
                except Exception as exc:
                    logger.warning("Failed to get service details for %s: %s", result.loc_id, exc)
            enriched_results.append(result)

        return enriched_results

    def _parse_response(self, response: Dict[str, Any], input_address: Optional[str] = None) -> List[NBNResult]:
        results = response.get("result") or []
        if not results:
            return []

        parsed = []
        for item in results:
            status_text = item.get("serviceability_status")
            parsed.append(
                NBNResult(
                    input_address=input_address,
                    loc_id=item.get("location_id") or item.get("id"),
                    match=item.get("match"),
                    address=item.get("formattedAddress") or item.get("address"),
                    technology=item.get("access_technology") or item.get("alternate_technology"),
                    serviceability=serviceability_status_to_numeric(status_text),
                    ports_free=None,  # Not provided by this API
                    ports_used=None,  # Not provided by this API
                    ports_total=None,  # Not provided by this API
                    # Legacy fields
                    service_class=item.get("service_class"),
                    fibre_on_demand=item.get("fibreOnDemandAvailable"),
                )
            )
        return parsed

    def _enrich_with_service_details(self, result: NBNResult, service_details: Dict[str, Any]) -> NBNResult:
        """Enrich NBN result with service details (ports info)."""
        # Try to extract ports information from service details response
        # The exact structure depends on the API response format
        ports = service_details.get("ports", {})
        if ports:
            result.ports_free = ports.get("free")
            result.ports_used = ports.get("used")
            result.ports_total = ports.get("total")
        return result

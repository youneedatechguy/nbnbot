"""Iperium API client implementation."""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import httpx

logger = logging.getLogger(__name__)


class TokenCache:
    """Manages token caching with auto-refresh before expiry."""

    def __init__(self, refresh_before_seconds: int = 300):
        """
        Initialize token cache.

        Args:
            refresh_before_seconds: Refresh token this many seconds before expiry.
        """
        self.token: Optional[str] = None
        self.expires_at: Optional[datetime] = None
        self.refresh_before_seconds = refresh_before_seconds

    def is_valid(self) -> bool:
        """Check if cached token is still valid."""
        if self.token is None or self.expires_at is None:
            return False
        threshold = datetime.utcnow() + timedelta(seconds=self.refresh_before_seconds)
        return self.expires_at > threshold

    def set(self, token: str, exp: int) -> None:
        """
        Set token and expiry time.

        Args:
            token: JWT token
            exp: Unix timestamp when token expires
        """
        self.token = token
        self.expires_at = datetime.utcfromtimestamp(exp)

    def get(self) -> Optional[str]:
        """Get token if valid, else None."""
        if self.is_valid():
            return self.token
        return None


class IperiumClient:
    """Client for Iperium API authentication and address lookup."""

    BASE_URL = "https://portal.iperium.com.au/api"

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize Iperium API client.

        Args:
            email: Iperium email (defaults to IPERIUM_EMAIL env var)
            password: Iperium password (defaults to IPERIUM_PASSWORD env var)
            timeout: HTTP request timeout in seconds

        Raises:
            ValueError: If email or password not provided and env vars not set
        """
        self.email = email or os.getenv("IPERIUM_EMAIL")
        self.password = password or os.getenv("IPERIUM_PASSWORD")
        self.timeout = timeout
        self.token_cache = TokenCache()

        if not self.email or not self.password:
            raise ValueError(
                "Email and password required. Provide as arguments or set "
                "IPERIUM_EMAIL and IPERIUM_PASSWORD env vars."
            )

    async def _parse_token(self, jwt_token: str) -> tuple[str, int]:
        """
        Parse JWT token to extract expiry time.

        Args:
            jwt_token: JWT token string

        Returns:
            Tuple of (token, exp_timestamp)

        Raises:
            ValueError: If token format is invalid
        """
        parts = jwt_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format")

        # Decode the payload (second part)
        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        import base64
        import json

        try:
            decoded = base64.urlsafe_b64decode(payload)
            payload_dict = json.loads(decoded)
            exp = payload_dict.get("exp")
            if exp is None:
                raise ValueError("Token missing exp claim")
            return jwt_token, exp
        except Exception as e:
            raise ValueError(f"Failed to parse token: {e}")

    async def get_token(self, force_refresh: bool = False) -> str:
        """
        Get authentication token, using cache or fetching fresh.

        Args:
            force_refresh: Force a fresh token fetch, ignoring cache

        Returns:
            Valid JWT token

        Raises:
            httpx.HTTPError: If API request fails
        """
        if not force_refresh:
            cached = self.token_cache.get()
            if cached:
                return cached

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}/auth",
                json={"email": self.email, "password": self.password},
            )
            response.raise_for_status()
            data = response.json()

        token = data.get("token") or data.get("access_token")
        if not token:
            raise ValueError(f"No token in auth response: {data}")

        token, exp = await self._parse_token(token)
        self.token_cache.set(token, exp)
        return token

    async def lookup_address(
        self,
        street_name: str,
        suburb: str,
        state: str,
        postcode: str,
        street_number: Optional[int] = None,
        unit: Optional[str] = None,
        level: Optional[str] = None,
        lot_no: Optional[int] = None,
        fibre_on_demand: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lookup NBN address details.

        Args:
            street_name: Street name (required)
            suburb: Suburb (required)
            state: State code (required)
            postcode: Postcode (required)
            street_number: Street number (optional)
            unit: Unit number (optional)
            level: Level number (optional)
            lot_no: Lot number (optional)
            fibre_on_demand: Fibre on demand status (optional)

        Returns:
            API response dict with address lookup results

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If address cannot be matched (API returns status: false)
        """
        token = await self.get_token()

        # Build form data, only including provided fields
        form_data = {
            "street_name": street_name,
            "suburb": suburb,
            "state": state,
            "postcode": postcode,
        }
        if street_number is not None:
            form_data["street_number"] = street_number
        if unit:
            form_data["unit"] = unit
        if level:
            form_data["level"] = level
        if lot_no is not None:
            form_data["lot_no"] = lot_no
        if fibre_on_demand:
            form_data["fibreOnDemand"] = fibre_on_demand

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}/nbn/address",
                data=form_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            # Check if the address could not be matched
            # The API returns status: false when no match is found
            if not data.get("status", True):
                logger.warning(
                    "Address could not be matched: %s %s, %s %s",
                    street_number or "",
                    street_name,
                    suburb,
                    postcode
                )
                raise ValueError("Address could not be matched")

            return data

    async def get_service_details(
        self,
        loc_id: str,
    ) -> Dict[str, Any]:
        """
        Get detailed service information for a specific location ID.

        Args:
            loc_id: Location ID from address lookup result

        Returns:
            API response dict with detailed service information

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If loc_id is not provided
        """
        if not loc_id:
            raise ValueError("loc_id is required")

        token = await self.get_token()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/nbn/premises/{loc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            return data

    async def get_available_speed_tiers(
        self,
        street_name: str,
        suburb: str,
        state: str,
        postcode: str,
        street_number: Optional[int] = None,
        unit: Optional[str] = None,
        level: Optional[str] = None,
        lot_no: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get available speed tiers for an address.

        Args:
            street_name: Street name (required)
            suburb: Suburb (required)
            state: State code (required)
            postcode: Postcode (required)
            street_number: Street number (optional)
            unit: Unit number (optional)
            level: Level number (optional)
            lot_no: Lot number (optional)

        Returns:
            API response dict with available speed tiers information

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If required parameters are missing
        """
        # Validate required parameters
        if not all([street_name, suburb, state, postcode]):
            raise ValueError("street_name, suburb, state, and postcode are required")

        token = await self.get_token()

        # Build form data, only including provided fields
        form_data = {
            "street_name": street_name,
            "suburb": suburb,
            "state": state,
            "postcode": postcode,
        }
        if street_number is not None:
            form_data["street_number"] = street_number
        if unit:
            form_data["unit"] = unit
        if level:
            form_data["level"] = level
        if lot_no is not None:
            form_data["lot_no"] = lot_no

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.BASE_URL}/nbn/speed-tiers",
                data=form_data,
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            return data

    async def get_installation_status(
        self,
        loc_id: str,
    ) -> Dict[str, Any]:
        """
        Get installation and service activation status for a location.

        Args:
            loc_id: Location ID from address lookup result

        Returns:
            API response dict with installation status information

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If loc_id is not provided
        """
        if not loc_id:
            raise ValueError("loc_id is required")

        token = await self.get_token()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/nbn/installation-status/{loc_id}",
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()

            return data

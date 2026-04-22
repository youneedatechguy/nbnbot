"""Tests for Google Maps Geocoding API client."""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from gmaps.geocoder import GoogleMapsGeocoder, StandardizedAddress


class TestStandardizedAddress:
    """Tests for StandardizedAddress dataclass."""

    def test_to_dict_excludes_none_values(self):
        """Test that to_dict() excludes None values."""
        address = StandardizedAddress(
            street_number="11",
            street_name="Wattle Drive",
            suburb="Yamba",
            state="NSW",
            postcode="2464",
            unit=None,
            latitude=-29.5,
        )

        result = address.to_dict()

        assert result == {
            "street_number": "11",
            "street_name": "Wattle Drive",
            "suburb": "Yamba",
            "state": "NSW",
            "postcode": "2464",
            "latitude": -29.5,
        }
        assert "unit" not in result

    def test_to_dict_all_none(self):
        """Test to_dict() with all None values returns empty dict."""
        address = StandardizedAddress()
        assert address.to_dict() == {}

    def test_to_dict_all_fields(self):
        """Test to_dict() includes all provided fields."""
        address = StandardizedAddress(
            street_number="10A",
            street_name="Main Street",
            suburb="Sydney",
            state="NSW",
            postcode="2000",
            unit="5",
            level="2",
            lot_no="101",
            latitude=-33.8688,
            longitude=151.2093,
        )

        result = address.to_dict()

        assert len(result) == 10
        assert result["unit"] == "5"
        assert result["level"] == "2"
        assert result["lot_no"] == "101"


class TestGoogleMapsGeocoder:
    """Tests for GoogleMapsGeocoder client."""

    def test_init_with_api_key_argument(self):
        """Test initialization with api_key argument."""
        geocoder = GoogleMapsGeocoder(api_key="test_key_12345")
        assert geocoder.api_key == "test_key_12345"

    def test_init_with_env_var(self):
        """Test initialization reads from GOOGLE_MAPS_API_KEY env var."""
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "env_key_67890"}):
            geocoder = GoogleMapsGeocoder()
            assert geocoder.api_key == "env_key_67890"

    def test_init_raises_without_api_key(self):
        """Test initialization raises ValueError without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="API key required"):
                GoogleMapsGeocoder()

    def test_init_prefers_argument_over_env_var(self):
        """Test that argument API key takes precedence over env var."""
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "env_key"}):
            geocoder = GoogleMapsGeocoder(api_key="arg_key")
            assert geocoder.api_key == "arg_key"

    def test_geocode_address_success(self):
        """Test successful address geocoding."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {
            "results": [
                {
                    "address_components": [
                        {"short_name": "11", "long_name": "11", "types": ["street_number"]},
                        {
                            "short_name": "Wattle Drive",
                            "long_name": "Wattle Drive",
                            "types": ["route"],
                        },
                        {"short_name": "Yamba", "long_name": "Yamba", "types": ["locality"]},
                        {"short_name": "NSW", "long_name": "New South Wales", "types": ["administrative_area_level_1"]},
                        {"short_name": "2464", "long_name": "2464", "types": ["postal_code"]},
                        {"short_name": "AU", "long_name": "Australia", "types": ["country"]},
                    ],
                    "geometry": {
                        "location": {"lat": -29.4462, "lng": 153.3605},
                    },
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            result = geocoder.geocode_address("11 Wattle Drive Yamba NSW 2464")

        assert isinstance(result, StandardizedAddress)
        assert result.street_number == "11"
        assert result.street_name == "Wattle Drive"
        assert result.suburb == "Yamba"
        assert result.state == "NSW"
        assert result.postcode == "2464"
        assert result.latitude == -29.4462
        assert result.longitude == 153.3605

    @pytest.mark.asyncio
    async def test_geocode_address_not_found(self):
        """Test geocoding raises ValueError when address not found."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {"results": []}

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            with pytest.raises(ValueError, match="Address not found"):
                await geocoder.geocode_address("Invalid Address XYZ 9999")

    def test_parse_free_text_address_with_unit(self):
        """Test parsing address with unit number."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {
            "results": [
                {
                    "address_components": [
                        {"short_name": "255", "long_name": "255", "types": ["street_number"]},
                        {
                            "short_name": "George Street",
                            "long_name": "George Street",
                            "types": ["route"],
                        },
                        {"short_name": "Sydney", "long_name": "Sydney", "types": ["locality"]},
                        {
                            "short_name": "NSW",
                            "long_name": "New South Wales",
                            "types": ["administrative_area_level_1"],
                        },
                        {"short_name": "2000", "long_name": "2000", "types": ["postal_code"]},
                    ],
                    "geometry": {
                        "location": {"lat": -33.8688, "lng": 151.2093},
                    },
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            result = geocoder.parse_free_text_address("Unit 5, 255 George Street, Sydney NSW 2000")

        assert result.unit == "5"
        assert result.street_number == "255"
        assert result.street_name == "George Street"
        assert result.suburb == "Sydney"

    def test_parse_free_text_address_with_level(self):
        """Test parsing address with level number."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {
            "results": [
                {
                    "address_components": [
                        {"short_name": "100", "long_name": "100", "types": ["street_number"]},
                        {
                            "short_name": "Miller Street",
                            "long_name": "Miller Street",
                            "types": ["route"],
                        },
                        {"short_name": "North Sydney", "long_name": "North Sydney", "types": ["locality"]},
                        {
                            "short_name": "NSW",
                            "long_name": "New South Wales",
                            "types": ["administrative_area_level_1"],
                        },
                        {"short_name": "2060", "long_name": "2060", "types": ["postal_code"]},
                    ],
                    "geometry": {
                        "location": {"lat": -33.8388, "lng": 151.2093},
                    },
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            result = geocoder.parse_free_text_address("Level 3, 100 Miller Street, North Sydney NSW 2060")

        assert result.level == "3"
        assert result.street_number == "100"
        assert result.street_name == "Miller Street"

    def test_parse_free_text_address_with_lot(self):
        """Test parsing address with lot number."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {
            "results": [
                {
                    "address_components": [
                        {"short_name": "50", "long_name": "50", "types": ["street_number"]},
                        {
                            "short_name": "Main Road",
                            "long_name": "Main Road",
                            "types": ["route"],
                        },
                        {"short_name": "Parramatta", "long_name": "Parramatta", "types": ["locality"]},
                        {
                            "short_name": "NSW",
                            "long_name": "New South Wales",
                            "types": ["administrative_area_level_1"],
                        },
                        {"short_name": "2150", "long_name": "2150", "types": ["postal_code"]},
                    ],
                    "geometry": {
                        "location": {"lat": -33.8156, "lng": 151.0093},
                    },
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            result = geocoder.parse_free_text_address("Lot 42, 50 Main Road, Parramatta NSW 2150")

        assert result.lot_no == "42"
        assert result.street_number == "50"

    def test_parse_free_text_address_complex_case(self):
        """Test parsing address with multiple edge cases."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        mock_response = {
            "results": [
                {
                    "address_components": [
                        {"short_name": "100", "long_name": "100", "types": ["street_number"]},
                        {
                            "short_name": "York Street",
                            "long_name": "York Street",
                            "types": ["route"],
                        },
                        {"short_name": "Sydney", "long_name": "Sydney", "types": ["locality"]},
                        {
                            "short_name": "NSW",
                            "long_name": "New South Wales",
                            "types": ["administrative_area_level_1"],
                        },
                        {"short_name": "2000", "long_name": "2000", "types": ["postal_code"]},
                    ],
                    "geometry": {
                        "location": {"lat": -33.8688, "lng": 151.2093},
                    },
                }
            ]
        }

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response_obj = MagicMock()
            mock_response_obj.read.return_value = json.dumps(mock_response).encode("utf-8")
            mock_response_obj.__enter__.return_value = mock_response_obj
            mock_response_obj.__exit__.return_value = None

            mock_urlopen.return_value = mock_response_obj

            result = geocoder.parse_free_text_address(
                "Unit 5A, Level 2, 100 York Street, Sydney NSW 2000"
            )

        assert result.unit == "5A"
        assert result.level == "2"
        assert result.street_number == "100"
        assert result.street_name == "York Street"

    def test_extract_edge_cases_unit_variations(self):
        """Test extracting unit numbers with various formats."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        # Test "Unit"
        unit, level, lot, clean = geocoder._extract_edge_cases("Unit 5, 10 Main St")
        assert unit == "5"
        assert "Unit" not in clean

        # Test "U"
        unit, level, lot, clean = geocoder._extract_edge_cases("U 7, 10 Main St")
        assert unit == "7"

        # Test "Apt"
        unit, level, lot, clean = geocoder._extract_edge_cases("Apt 3, 10 Main St")
        assert unit == "3"

        # Test "U." with hash
        unit, level, lot, clean = geocoder._extract_edge_cases("U.#10, 10 Main St")
        assert unit == "10"

    def test_extract_edge_cases_level_variations(self):
        """Test extracting level numbers with various formats."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        # Test "Level"
        unit, level, lot, clean = geocoder._extract_edge_cases("Level 3, 10 Main St")
        assert level == "3"

        # Test "L"
        unit, level, lot, clean = geocoder._extract_edge_cases("L 2, 10 Main St")
        assert level == "2"

        # Test "Floor"
        unit, level, lot, clean = geocoder._extract_edge_cases("Floor 5, 10 Main St")
        assert level == "5"

        # Test "Fl."
        unit, level, lot, clean = geocoder._extract_edge_cases("Fl. 4, 10 Main St")
        assert level == "4"

    def test_extract_edge_cases_lot_variations(self):
        """Test extracting lot numbers with various formats."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        # Test "Lot"
        unit, level, lot, clean = geocoder._extract_edge_cases("Lot 101, 10 Main St")
        assert lot == "101"

        # Test "LOT" (uppercase)
        unit, level, lot, clean = geocoder._extract_edge_cases("LOT 42, 10 Main St")
        assert lot == "42"

    def test_extract_edge_cases_whitespace_cleanup(self):
        """Test that extra whitespace is cleaned up."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        unit, level, lot, clean = geocoder._extract_edge_cases(
            "Unit 5,  -  Level  2,    10   Main   Street"
        )

        assert unit == "5"
        assert level == "2"
        # Multiple spaces should be collapsed
        assert "  " not in clean

    def test_extract_edge_cases_all_together(self):
        """Test extracting all edge cases from single address."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        unit, level, lot, clean = geocoder._extract_edge_cases(
            "Lot 10, Unit 5, Level 2, 100 York Street, Sydney"
        )

        assert unit == "5"
        assert level == "2"
        assert lot == "10"
        assert "100 York Street, Sydney" in clean or "100 York Street Sydney" in clean

    def test_extract_edge_cases_no_matches(self):
        """Test extraction when no edge cases present."""
        geocoder = GoogleMapsGeocoder(api_key="test_key")

        unit, level, lot, clean = geocoder._extract_edge_cases("10 Main Street, Sydney NSW 2000")

        assert unit is None
        assert level is None
        assert lot is None
        assert clean == "10 Main Street, Sydney NSW 2000"

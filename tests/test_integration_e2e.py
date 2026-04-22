"""End-to-end integration tests for the NBN Address Lookup Bot."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import StringIO
import json
import base64

from bot.nbn_service import NBNService, NBNResult
from iperium.client import IperiumClient
from gmaps.geocoder import GoogleMapsGeocoder, StandardizedAddress


# ============================================================================
# Fixtures: Real-ish responses from each integration point
# ============================================================================

@pytest.fixture
def mock_jwt_token():
    """Generate a valid mock JWT token with expiry claim."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(
        json.dumps({"exp": 1800000000}).encode()
    ).decode().rstrip("=")
    signature = "mock_signature"
    return f"{header}.{payload}.{signature}"


@pytest.fixture
def mock_iperium_response():
    """Realistic Iperium API response for a serviceable address."""
    return {
        "requestid": 12345,
        "status": True,
        "result": [
            {
                "location_id": "LOC_ABC_123",
                "formattedAddress": "11 Wattle Drive, Yamba NSW 2464",
                "access_technology": "Fibre to the Premises",
                "service_class": "20/5",
                "serviceability_status": "Serviceable",
                "fibreOnDemandAvailable": False,
            }
        ],
    }


@pytest.fixture
def mock_StandardizedAddress():
    """Mock geocoded address from Google Maps."""
    return StandardizedAddress(
        street_number="11",
        street_name="Wattle Drive",
        suburb="Yamba",
        state="NSW",
        postcode="2464",
        unit=None,
        level=None,
        lot_no=None,
    )


# ============================================================================
# Test: Full flow from free-text to NBN result
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_address_lookup_success(mock_iperium_response, mock_StandardizedAddress):
    """Test complete flow: free text → geocode → Iperium → result formatting."""
    # Setup mocks
    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(return_value=mock_iperium_response)
    mock_iperium.get_service_details = AsyncMock(return_value={})

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = mock_StandardizedAddress

    # Create service with mocked dependencies
    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)

    # Execute: Lookup a human-readable address
    results = await service.lookup("11 Wattle Drive, Yamba NSW 2464")

    # Verify the full chain executed
    mock_geocoder.parse_free_text_address.assert_called_once_with("11 Wattle Drive, Yamba NSW 2464")
    mock_iperium.lookup_address.assert_called_once()

    # Verify result is properly transformed
    assert len(results) == 1
    result = results[0]
    assert result.loc_id == "LOC_ABC_123"
    assert result.address == "11 Wattle Drive, Yamba NSW 2464"
    assert result.technology == "Fibre to the Premises"
    assert result.service_class == "20/5"
    assert result.serviceability == 1
    assert result.fibre_on_demand is False


@pytest.mark.asyncio
async def test_e2e_unit_apartment_lookup(mock_iperium_response):
    """Test flow with unit/level apartment address."""
    # Setup response for apartment
    apartment_response = {
        "requestid": 12346,
        "status": True,
        "result": [
            {
                "location_id": "LOC_APT_456",
                "formattedAddress": "Unit 3/45 Smith Street, Brisbane QLD 4000",
                "techType": "FTTN",
                "serviceClass": "25/10",
                "serviceability_status": "Serviceable",
                "fibreOnDemandAvailable": True,
            }
        ],
    }

    apartment_address = StandardizedAddress(
        street_number="45",
        street_name="Smith Street",
        suburb="Brisbane",
        state="QLD",
        postcode="4000",
        unit="3",
        level=None,
        lot_no=None,
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(return_value=apartment_response)
    mock_iperium.get_service_details = AsyncMock(return_value={})

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = apartment_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)
    results = await service.lookup("Unit 3/45 Smith Street, Brisbane QLD 4000")

    # Verify unit was passed to Iperium
    call_kwargs = mock_iperium.lookup_address.call_args.kwargs
    assert call_kwargs["unit"] == "3"
    assert call_kwargs["street_number"] == 45

    # Verify result
    assert len(results) == 1
    assert results[0].loc_id == "LOC_APT_456"
    assert results[0].fibre_on_demand is True


@pytest.mark.asyncio
async def test_e2e_lot_based_address_lookup():
    """Test flow with lot-based rural address."""
    lot_response = {
        "requestid": 12347,
        "status": True,
        "result": [
            {
                "location_id": "LOC_LOT_789",
                "formattedAddress": "Lot 5 Rural Road, Grafton NSW 2460",
                "access_technology": "Fixed Wireless",
                "service_class": "NA",
                "serviceability_status": "Future serviceable",
                "fibreOnDemandAvailable": False,
            }
        ],
    }

    lot_address = StandardizedAddress(
        street_number=None,
        street_name="Rural Road",
        suburb="Grafton",
        state="NSW",
        postcode="2460",
        unit=None,
        level=None,
        lot_no="5",
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(return_value=lot_response)
    mock_iperium.get_service_details = AsyncMock(return_value={})

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = lot_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)
    results = await service.lookup("Lot 5 Rural Road, Grafton NSW 2460")

    # Verify lot_no was passed
    call_kwargs = mock_iperium.lookup_address.call_args.kwargs
    assert call_kwargs["lot_no"] == 5
    assert "street_number" not in call_kwargs or call_kwargs.get("street_number") is None

    assert len(results) == 1
    assert results[0].technology == "Fixed Wireless"  # Already matches new field name


# ============================================================================
# Test: Error handling across the integration chain
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_geocoding_failure():
    """Test graceful handling when geocoding fails."""
    mock_iperium = MagicMock(spec=IperiumClient)
    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.side_effect = ValueError("Could not parse address")

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)

    with pytest.raises(ValueError, match="Could not parse address"):
        await service.lookup("garbage address ~~~~~~")

    # Iperium should never be called if geocoding fails
    mock_iperium.lookup_address.assert_not_called()


@pytest.mark.asyncio
async def test_e2e_missing_required_fields():
    """Test validation when geocoding returns incomplete address."""
    incomplete_address = StandardizedAddress(
        street_number="11",
        street_name="Incomplete Street",
        suburb=None,  # Missing suburb
        state="NSW",
        postcode=None,  # Missing postcode
        unit=None,
        level=None,
        lot_no=None,
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = incomplete_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)

    with pytest.raises(ValueError, match="required address fields"):
        await service.lookup("11 Incomplete Street NSW")

    # Iperium should not be called with incomplete data
    mock_iperium.lookup_address.assert_not_called()


@pytest.mark.asyncio
async def test_e2e_iperium_api_error():
    """Test handling of Iperium API errors."""
    mock_address = StandardizedAddress(
        street_number="11",
        street_name="Wattle Drive",
        suburb="Yamba",
        state="NSW",
        postcode="2464",
        unit=None,
        level=None,
        lot_no=None,
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(
        side_effect=Exception("Connection timeout to Iperium")
    )

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = mock_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)

    # Error should propagate
    with pytest.raises(Exception, match="Connection timeout"):
        await service.lookup("11 Wattle Drive, Yamba NSW 2464")


@pytest.mark.asyncio
async def test_e2e_iperium_no_results():
    """Test empty result set handling."""
    no_results_response = {
        "requestid": 12348,
        "status": True,
        "result": [],
    }

    mock_address = StandardizedAddress(
        street_number="999",
        street_name="Nonexistent Lane",
        suburb="Nowhere",
        state="QLD",
        postcode="9999",
        unit=None,
        level=None,
        lot_no=None,
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(return_value=no_results_response)
    mock_iperium.get_service_details = AsyncMock(return_value={})

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = mock_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)
    results = await service.lookup("999 Nonexistent Lane, Nowhere QLD 9999")

    # Empty results should return empty list, not error
    assert results == []


# ============================================================================
# Test: Bot handler integration
# ============================================================================

@pytest.mark.asyncio
async def test_bot_handler_e2e_lookup_flow():
    """Test full bot handler flow with real NBN service."""
    from bot.handlers import handle_message
    import bot.handlers as handlers

    # Create realistic response chain
    mock_iperium_response = {
        "requestid": 99999,
        "status": True,
        "result": [
            {
                "location_id": "LOC_E2E_999",
                "formattedAddress": "42 Test Avenue, Sydney NSW 2000",
                "access_technology": "Fibre to the Premises",
                "serviceClass": "100/40",
                "serviceability_status": "Serviceable",
                "fibreOnDemandAvailable": False,
            }
        ],
    }

    # Mock Telegram update/context
    message = MagicMock()
    message.text = "42 Test Avenue, Sydney NSW 2000"
    thinking_msg = AsyncMock()
    thinking_msg.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=thinking_msg)

    update = MagicMock()
    update.message = message
    context = MagicMock()

    # Mock the service to return realistic results
    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(
        return_value=[
            NBNResult(
                input_address="42 Test Avenue, Sydney NSW 2000",
                loc_id="LOC_E2E_999",
                match=None,
                address="42 Test Avenue, Sydney NSW 2000",
                technology="FTTP",
                serviceability=1,
                ports_free=None,
                ports_used=None,
                ports_total=None,
                service_class="100/40",
                fibre_on_demand=False,
            )
        ]
    )

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    # Verify the thinking message was edited with results
    thinking_msg.edit_text.assert_called_once()
    result_text = thinking_msg.edit_text.call_args[0][0]
    assert "Fibre" in result_text or "Technology" in result_text
    assert "1" in result_text  # Serviceability code for Serviceable
    # Service class should NOT be in output anymore
    assert "100/40" not in result_text


@pytest.mark.asyncio
async def test_bot_handler_e2e_multiple_results():
    """Test bot handling of multiple address matches."""
    from bot.handlers import handle_message
    import bot.handlers as handlers

    message = MagicMock()
    message.text = "Main Street Sydney"
    thinking_msg = AsyncMock()
    thinking_msg.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=thinking_msg)

    update = MagicMock()
    update.message = message
    context = MagicMock()

    # Multiple results for a broad address
    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(
        return_value=[
            NBNResult(
                input_address="Main Street Sydney",
                loc_id="LOC_M1",
                match=None,
                address="1 Main Street, Sydney NSW 2000",
                technology="FTTP",
                serviceability=1,
                ports_free=None,
                ports_used=None,
                ports_total=None,
                service_class="100/20",
                fibre_on_demand=False,
            ),
            NBNResult(
                input_address="Main Street Sydney",
                loc_id="LOC_M2",
                match=None,
                address="3 Main Street, Sydney NSW 2000",
                technology="FTTN",
                serviceability=1,
                ports_free=None,
                ports_used=None,
                ports_total=None,
                service_class="50/10",
                fibre_on_demand=False,
            ),
        ]
    )

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    result_text = thinking_msg.edit_text.call_args[0][0]
    assert "Result 1:" in result_text
    assert "Result 2:" in result_text
    assert "Fibre" in result_text or "Technology" in result_text
    assert "Fibre" in result_text or "Technology" in result_text


@pytest.mark.asyncio
async def test_bot_handler_e2e_no_serviceable_address():
    """Test bot handling when address exists but is not serviceable."""
    from bot.handlers import handle_message
    import bot.handlers as handlers

    message = MagicMock()
    message.text = "Remote Rural Address NSW"
    thinking_msg = AsyncMock()
    thinking_msg.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=thinking_msg)

    update = MagicMock()
    update.message = message
    context = MagicMock()

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(return_value=[])

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    result_text = thinking_msg.edit_text.call_args[0][0]
    assert "No NBN results" in result_text


@pytest.mark.asyncio
async def test_bot_handler_e2e_geocoding_error_handling():
    """Test bot gracefully handles geocoding errors."""
    from bot.handlers import handle_message
    import bot.handlers as handlers

    message = MagicMock()
    message.text = "gibberish ~~~~ not an address"
    thinking_msg = AsyncMock()
    thinking_msg.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=thinking_msg)

    update = MagicMock()
    update.message = message
    context = MagicMock()

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(side_effect=ValueError("Could not geocode"))

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    result_text = thinking_msg.edit_text.call_args[0][0]
    assert "geocode" in result_text.lower() or "Could not" in result_text


@pytest.mark.asyncio
async def test_bot_handler_e2e_iperium_failure():
    """Test bot handles Iperium API failures gracefully."""
    from bot.handlers import handle_message
    import bot.handlers as handlers

    message = MagicMock()
    message.text = "11 Wattle Drive, Yamba NSW 2464"
    thinking_msg = AsyncMock()
    thinking_msg.edit_text = AsyncMock()
    message.reply_text = AsyncMock(return_value=thinking_msg)

    update = MagicMock()
    update.message = message
    context = MagicMock()

    mock_service = MagicMock()
    mock_service.lookup = AsyncMock(
        side_effect=Exception("Connection error to Iperium")
    )

    with patch.object(handlers, "_get_service", return_value=mock_service):
        await handle_message(update, context)

    result_text = thinking_msg.edit_text.call_args[0][0]
    assert "error" in result_text.lower()
    assert "try again" in result_text.lower()


# ============================================================================
# Test: Result formatting across multiple scenarios
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_result_formatting_full():
    """Test NBN result formatting with all fields populated."""
    result = NBNResult(
        input_address="111 Complete Street, Brisbane QLD 4000",
        loc_id="LOC_FULL",
        match=None,
        address="111 Complete Street, Brisbane QLD 4000",
        technology="FTTP",
        serviceability="Serviceable",
        ports_free=5,
        ports_used=2,
        ports_total=8,
        service_class="1000/400",
        fibre_on_demand=True,
    )

    message = result.format_message()
    assert "111 Complete Street" in message
    assert "LOC_FULL" in message
    assert "FTTP" in message
    assert "Serviceable" in message
    # Ports should be shown
    assert "5/2/8" in message
    # These should NOT be in output anymore
    assert "1000/400" not in message  # service_class removed from display
    assert "Fibre on Demand" not in message  # fibre_on_demand removed from display


@pytest.mark.asyncio
async def test_e2e_result_formatting_partial():
    """Test NBN result formatting with missing optional fields."""
    result = NBNResult(
        input_address="Some Street, NSW",
        loc_id="LOC_PARTIAL",
        match=None,
        address="Some Street",
        technology=None,
        serviceability=2,
        ports_free=None,
        ports_used=None,
        ports_total=None,
        service_class=None,
        fibre_on_demand=None,
    )

    message = result.format_message()
    assert "Some Street" in message
    assert "2" in message
    # Missing fields should not appear
    assert "Technology" not in message or "None" not in message


@pytest.mark.asyncio
async def test_e2e_result_formatting_empty():
    """Test NBN result formatting with all fields None."""
    result = NBNResult(
        input_address=None,
        loc_id=None,
        match=None,
        address=None,
        technology=None,
        serviceability=None,
        ports_free=None,
        ports_used=None,
        ports_total=None,
        service_class=None,
        fibre_on_demand=None,
    )

    message = result.format_message()
    assert message == "No details available."


# ============================================================================
# Test: Data flow transformations
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_iperium_response_parsing_variants():
    """Test the service correctly parses various Iperium response field names."""
    # Iperium responses might use different field names
    variant_response = {
        "requestid": 55555,
        "status": True,
        "result": [
            {
                "id": "ALT_ID_123",  # Alternative field name for location_id
                "address": "99 Variant Field Road",  # Alternative field name for formattedAddress
                "alternate_technology": "Fibre to the Premises",  # Alternative field name for access_technology
                "serviceability_status": "Serviceable",
                "fibreOnDemandAvailable": False,
            }
        ],
    }

    mock_address = StandardizedAddress(
        street_number="99",
        street_name="Variant Field Road",
        suburb="TestTown",
        state="VIC",
        postcode="3000",
        unit=None,
        level=None,
        lot_no=None,
    )

    mock_iperium = MagicMock(spec=IperiumClient)
    mock_iperium.lookup_address = AsyncMock(return_value=variant_response)
    mock_iperium.get_service_details = AsyncMock(return_value={})

    mock_geocoder = MagicMock(spec=GoogleMapsGeocoder)
    mock_geocoder.parse_free_text_address.return_value = mock_address

    service = NBNService(iperium_client=mock_iperium, geocoder=mock_geocoder)
    results = await service.lookup("99 Variant Field Road, TestTown VIC 3000")

    # Should handle alternative field names
    assert len(results) == 1
    assert results[0].loc_id == "ALT_ID_123"  # Fallback from id field
    assert results[0].address == "99 Variant Field Road"
    assert results[0].technology == "Fibre to the Premises"

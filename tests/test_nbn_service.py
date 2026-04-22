"""Tests for the NBN service integration layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from bot.nbn_service import NBNService, NBNResult
from gmaps.geocoder import StandardizedAddress


def make_geocoder(street_number="11", street_name="Wattle Drive", suburb="Yamba",
                  state="NSW", postcode="2464", unit=None, level=None, lot_no=None):
    geocoder = MagicMock()
    geocoder.parse_free_text_address.return_value = StandardizedAddress(
        street_number=street_number,
        street_name=street_name,
        suburb=suburb,
        state=state,
        postcode=postcode,
        unit=unit,
        level=level,
        lot_no=lot_no,
    )
    return geocoder


def make_iperium(response, service_details_response=None):
    client = MagicMock()
    client.lookup_address = AsyncMock(return_value=response)
    client.get_service_details = AsyncMock(return_value=service_details_response or {})
    return client


@pytest.mark.asyncio
async def test_lookup_returns_results():
    iperium = make_iperium({
        "requestid": 66,
        "status": True,
        "result": [
            {
                "location_id": "LOC123",
                "formattedAddress": "11 Wattle Drive, Yamba NSW 2464",
                "access_technology": "Fibre To The Node",
                "service_class": "20",
                "serviceability_status": "Serviceable",
                "fibreOnDemandAvailable": False,
            }
        ],
    })
    geocoder = make_geocoder()
    service = NBNService(iperium_client=iperium, geocoder=geocoder)

    results = await service.lookup("11 Wattle Drive Yamba NSW 2464")

    assert len(results) == 1
    r = results[0]
    assert r.input_address == "11 Wattle Drive Yamba NSW 2464"
    assert r.loc_id == "LOC123"
    assert r.technology == "Fibre To The Node"
    assert r.service_class == "20"
    assert r.serviceability == 1
    assert r.fibre_on_demand is False


@pytest.mark.asyncio
async def test_lookup_empty_result():
    iperium = make_iperium({"requestid": 1, "status": True, "result": []})
    geocoder = make_geocoder()
    service = NBNService(iperium_client=iperium, geocoder=geocoder)

    results = await service.lookup("Some Unknown Address NSW 2000")
    assert results == []


@pytest.mark.asyncio
async def test_lookup_passes_street_number_as_int():
    iperium = make_iperium({"result": []})
    geocoder = make_geocoder(street_number="11")
    service = NBNService(iperium_client=iperium, geocoder=geocoder)

    await service.lookup("11 Wattle Drive Yamba NSW 2464")

    call_kwargs = iperium.lookup_address.call_args.kwargs
    assert call_kwargs["street_number"] == 11
    assert isinstance(call_kwargs["street_number"], int)


@pytest.mark.asyncio
async def test_lookup_raises_on_missing_fields():
    geocoder = MagicMock()
    geocoder.parse_free_text_address.return_value = StandardizedAddress(
        street_name="Wattle Drive"
        # missing suburb, state, postcode
    )
    iperium = make_iperium({"result": []})
    service = NBNService(iperium_client=iperium, geocoder=geocoder)

    with pytest.raises(ValueError, match="required address fields"):
        await service.lookup("Incomplete Address")


@pytest.mark.asyncio
async def test_lookup_passes_unit_and_level():
    iperium = make_iperium({"result": []})
    geocoder = make_geocoder(unit="3", level="2")
    service = NBNService(iperium_client=iperium, geocoder=geocoder)

    await service.lookup("Unit 3 Level 2 / 45 Smith St Brisbane QLD 4000")

    call_kwargs = iperium.lookup_address.call_args.kwargs
    assert call_kwargs["unit"] == "3"
    assert call_kwargs["level"] == "2"


def test_nbn_result_format_message():
    result = NBNResult(
        input_address="11 Wattle Drive Yamba NSW 2464",
        loc_id="LOC1",
        match=None,
        address="11 Wattle Drive, Yamba NSW 2464",
        technology="FTTP",
        serviceability=1,
        ports_free=None,
        ports_used=None,
        ports_total=None,
        service_class="20",
        fibre_on_demand=False,
    )
    msg = result.format_message()
    assert "11 Wattle Drive Yamba NSW 2464" in msg  # input_address
    assert "LOC1" in msg
    assert "11 Wattle Drive, Yamba NSW 2464" in msg
    assert "FTTP" in msg
    assert "Serviceable" in msg  # Serviceability text
    # These should NOT be in the output anymore
    assert "Fibre on Demand" not in msg
    assert "Service Class" not in msg
    assert "20" not in msg


def test_nbn_result_format_message_empty():
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
    assert result.format_message() == "No details available."

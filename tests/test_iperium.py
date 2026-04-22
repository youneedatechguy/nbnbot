"""Unit tests for Iperium API client."""

import json
import base64
import time
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock, MagicMock
import pytest
import httpx

from iperium import IperiumClient


def create_test_token(exp_offset_seconds: int = 3600) -> str:
    """
    Create a test JWT token.

    Args:
        exp_offset_seconds: Seconds from now until expiry

    Returns:
        Valid JWT token string
    """
    exp = int(time.time()) + exp_offset_seconds
    header = {"typ": "JWT", "alg": "HS256"}
    payload = {
        "iat": int(time.time()),
        "exp": exp,
        "clientID": "2300",
        "userID": "2550",
        "email": "test@example.com",
    }

    # Encode parts
    header_encoded = base64.urlsafe_b64encode(
        json.dumps(header).encode()
    ).decode().rstrip("=")
    payload_encoded = base64.urlsafe_b64encode(
        json.dumps(payload).encode()
    ).decode().rstrip("=")
    signature = "signature123"

    return f"{header_encoded}.{payload_encoded}.{signature}"


@pytest.mark.asyncio
async def test_client_initialization():
    """Test client initialization with direct credentials."""
    client = IperiumClient(email="test@example.com", password="testpass")
    assert client.email == "test@example.com"
    assert client.password == "testpass"


@pytest.mark.asyncio
async def test_client_initialization_env_vars(monkeypatch):
    """Test client initialization with environment variables."""
    monkeypatch.setenv("IPERIUM_EMAIL", "env@example.com")
    monkeypatch.setenv("IPERIUM_PASSWORD", "envpass")
    client = IperiumClient()
    assert client.email == "env@example.com"
    assert client.password == "envpass"


def test_client_initialization_missing_credentials():
    """Test that client raises error when credentials are missing."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="Email and password required"):
            IperiumClient()


@pytest.mark.asyncio
async def test_token_cache_is_valid():
    """Test token cache validity checking."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)
    _, exp = await client._parse_token(token)
    client.token_cache.set(token, exp)

    assert client.token_cache.is_valid() is True


@pytest.mark.asyncio
async def test_token_cache_expired():
    """Test that expired tokens are not valid."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=-10)  # Expired 10s ago
    _, exp = await client._parse_token(token)
    client.token_cache.set(token, exp)

    assert client.token_cache.is_valid() is False


@pytest.mark.asyncio
async def test_token_cache_refresh_before_expiry():
    """Test that tokens are refreshed before expiry."""
    client = IperiumClient(email="test@example.com", password="testpass")
    # Token expires in 100 seconds (within default refresh window of 300s)
    token = create_test_token(exp_offset_seconds=100)
    _, exp = await client._parse_token(token)
    client.token_cache.set(token, exp)

    # Should be invalid since it's within refresh window
    assert client.token_cache.is_valid() is False


@pytest.mark.asyncio
async def test_parse_token_valid():
    """Test JWT token parsing."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)
    parsed_token, exp = await client._parse_token(token)

    assert parsed_token == token
    assert exp > int(time.time())


@pytest.mark.asyncio
async def test_parse_token_invalid_format():
    """Test that invalid token format raises error."""
    client = IperiumClient(email="test@example.com", password="testpass")
    with pytest.raises(ValueError, match="Invalid JWT format"):
        await client._parse_token("invalid.token")


@pytest.mark.asyncio
async def test_parse_token_missing_exp():
    """Test that token without exp claim raises error."""
    client = IperiumClient(email="test@example.com", password="testpass")
    # Create token without exp
    header = base64.urlsafe_b64encode(json.dumps({"typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"test": "data"}).encode()).decode().rstrip("=")
    invalid_token = f"{header}.{payload}.sig"

    with pytest.raises(ValueError, match="Token missing exp claim"):
        await client._parse_token(invalid_token)


@pytest.mark.asyncio
async def test_get_token_from_cache():
    """Test that get_token returns cached token when valid."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)
    _, exp = await client._parse_token(token)
    client.token_cache.set(token, exp)

    cached = await client.get_token()
    assert cached == token


@pytest.mark.asyncio
async def test_get_token_fresh_fetch(monkeypatch):
    """Test fetching fresh token when cache is invalid."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)

    mock_response = AsyncMock()
    mock_response.json.return_value = {"token": token}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    fetched = await client.get_token()
    assert fetched == token
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_get_token_force_refresh(monkeypatch):
    """Test force refresh ignores cache."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)
    _, exp = await client._parse_token(token)
    client.token_cache.set(token, exp)

    new_token = create_test_token(exp_offset_seconds=3600)
    mock_response = AsyncMock()
    mock_response.json.return_value = {"token": new_token}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    fetched = await client.get_token(force_refresh=True)
    assert fetched == new_token


@pytest.mark.asyncio
async def test_get_token_auth_response_variants(monkeypatch):
    """Test that get_token handles both 'token' and 'access_token' fields."""
    client = IperiumClient(email="test@example.com", password="testpass")

    # Test with 'access_token' field
    token = create_test_token(exp_offset_seconds=3600)
    mock_response = AsyncMock()
    mock_response.json.return_value = {"access_token": token}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    fetched = await client.get_token()
    assert fetched == token


@pytest.mark.asyncio
async def test_get_token_missing_token(monkeypatch):
    """Test that missing token in response raises error."""
    client = IperiumClient(email="test@example.com", password="testpass")

    mock_response = AsyncMock()
    mock_response.json.return_value = {"error": "Invalid credentials"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    with pytest.raises(ValueError, match="No token in auth response"):
        await client.get_token()


@pytest.mark.asyncio
async def test_lookup_address_all_fields(monkeypatch):
    """Test address lookup with all optional fields."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)

    expected_response = {
        "requestid": 66,
        "status": True,
        "result": [{"address": "11 Wattle Drive, Yamba NSW 2464"}],
    }

    mock_response = AsyncMock()
    mock_response.json.return_value = expected_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    # Mock get_token to return our test token
    original_get_token = client.get_token
    async def mock_get_token(*args, **kwargs):
        return token
    client.get_token = mock_get_token

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.lookup_address(
        street_name="Wattle Drive",
        suburb="Yamba",
        state="NSW",
        postcode="2464",
        street_number=11,
        unit="1",
        level="2",
        lot_no=123,
        fibre_on_demand="yes",
    )

    assert result == expected_response
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[1]["data"]["street_name"] == "Wattle Drive"
    assert call_args[1]["data"]["street_number"] == 11
    assert call_args[1]["headers"]["Authorization"] == f"Bearer {token}"


@pytest.mark.asyncio
async def test_lookup_address_not_matched(monkeypatch):
    """Test that ValueError is raised when address cannot be matched."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)

    # API response indicating address could not be matched
    no_match_response = {
        "requestid": 68,
        "status": False,
        "result": [],
    }

    mock_response = AsyncMock()
    mock_response.json.return_value = no_match_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    client.get_token = AsyncMock(return_value=token)

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    # Should raise ValueError when address cannot be matched
    with pytest.raises(ValueError, match="Address could not be matched"):
        await client.lookup_address(
            street_name="Nonexistent Street",
            suburb="Nowhere",
            state="NSW",
            postcode="9999",
        )


@pytest.mark.asyncio
async def test_lookup_address_required_fields_only(monkeypatch):
    """Test address lookup with only required fields."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)

    expected_response = {"requestid": 67, "status": True, "result": []}

    mock_response = AsyncMock()
    mock_response.json.return_value = expected_response
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    client.get_token = AsyncMock(return_value=token)

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.lookup_address(
        street_name="Main Street",
        suburb="Sydney",
        state="NSW",
        postcode="2000",
    )

    assert result == expected_response
    call_args = mock_client.post.call_args
    form_data = call_args[1]["data"]
    assert form_data["street_name"] == "Main Street"
    assert form_data["suburb"] == "Sydney"
    assert "street_number" not in form_data
    assert "unit" not in form_data


@pytest.mark.asyncio
async def test_lookup_address_http_error(monkeypatch):
    """Test that HTTP errors are propagated."""
    client = IperiumClient(email="test@example.com", password="testpass")
    token = create_test_token(exp_offset_seconds=3600)

    mock_response = AsyncMock()
    mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError(
        "401 Unauthorized", request=None, response=None
    ))

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    client.get_token = AsyncMock(return_value=token)

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    with pytest.raises(httpx.HTTPStatusError):
        await client.lookup_address(
            street_name="Test",
            suburb="Test",
            state="NSW",
            postcode="2000",
        )


@pytest.mark.asyncio
async def test_get_service_details(monkeypatch):
    """Test getting service details for a location ID."""
    client = IperiumClient(email="test@example.com", password="testpass")
    loc_id = "LOC123"
    expected_response = {
        "locId": loc_id,
        "technology": "FTTP",
        "serviceClass": "100/40",
        "status": "Active",
        "fibreOnDemandAvailable": True,
    }

    # Mock the auth response
    auth_token = create_test_token(exp_offset_seconds=3600)
    auth_mock_response = AsyncMock()
    auth_mock_response.json.return_value = {"token": auth_token}
    auth_mock_response.raise_for_status = MagicMock()

    # Mock the service details response
    service_mock_response = AsyncMock()
    service_mock_response.json.return_value = expected_response
    service_mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    # First call is to auth, second call is to service details
    mock_client.post.return_value = auth_mock_response
    mock_client.get.return_value = service_mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.get_service_details(loc_id)
    assert result == expected_response
    # Should have made two calls: one POST to auth, one GET to service details
    assert mock_client.post.call_count == 1
    assert mock_client.get.call_count == 1

    # Check auth call
    auth_call_args = mock_client.post.call_args
    assert auth_call_args[0][0] == f"{client.BASE_URL}/auth"

    # Check service details call
    service_call_args = mock_client.get.call_args
    assert service_call_args[0][0] == f"{client.BASE_URL}/nbn/premises/{loc_id}"
    assert "Authorization" in service_call_args[1]["headers"]


@pytest.mark.asyncio
async def test_get_service_details_missing_loc_id():
    """Test that ValueError is raised when loc_id is not provided."""
    client = IperiumClient(email="test@example.com", password="testpass")

    with pytest.raises(ValueError, match="loc_id is required"):
        await client.get_service_details("")


@pytest.mark.asyncio
async def test_get_available_speed_tiers(monkeypatch):
    """Test getting available speed tiers for an address."""
    client = IperiumClient(email="test@example.com", password="testpass")
    expected_response = {
        "status": True,
        "result": [
            {"speedTier": "25/5", "available": True},
            {"speedTier": "100/20", "available": True},
            {"speedTier": "1000/400", "available": False},
        ],
    }

    # Mock the auth response
    auth_token = create_test_token(exp_offset_seconds=3600)
    auth_mock_response = AsyncMock()
    auth_mock_response.json.return_value = {"token": auth_token}
    auth_mock_response.raise_for_status = MagicMock()

    # Mock the speed tiers response
    speed_tiers_mock_response = AsyncMock()
    speed_tiers_mock_response.json.return_value = expected_response
    speed_tiers_mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    # First call is to auth, second call is to speed tiers
    mock_client.post.return_value = auth_mock_response
    # We need to handle both POST (auth) and POST (speed-tiers) calls
    # Let's use side_effect to return different responses based on the URL
    def mock_post(*args, **kwargs):
        if args[0] == f"{client.BASE_URL}/auth":
            return auth_mock_response
        elif args[0] == f"{client.BASE_URL}/nbn/speed-tiers":
            return speed_tiers_mock_response
        else:
            raise ValueError(f"Unexpected POST to {args[0]}")

    mock_client.post.side_effect = mock_post
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.get_available_speed_tiers(
        street_name="Test Street",
        suburb="Test Suburb",
        state="NSW",
        postcode="2000",
    )
    assert result == expected_response
    # Should have made two POST calls: one to auth, one to speed-tiers
    assert mock_client.post.call_count == 2

    # Check the speed-tiers call (second call)
    speed_tiers_call_args = mock_client.post.call_args_list[1]
    assert speed_tiers_call_args[0][0] == f"{client.BASE_URL}/nbn/speed-tiers"
    assert speed_tiers_call_args[1]["data"]["street_name"] == "Test Street"
    assert speed_tiers_call_args[1]["data"]["suburb"] == "Test Suburb"
    assert speed_tiers_call_args[1]["data"]["state"] == "NSW"
    assert speed_tiers_call_args[1]["data"]["postcode"] == "2000"
    assert "Authorization" in speed_tiers_call_args[1]["headers"]


@pytest.mark.asyncio
async def test_get_available_speed_tiers_with_optional_fields(monkeypatch):
    """Test getting speed tiers with optional fields provided."""
    client = IperiumClient(email="test@example.com", password="testpass")
    expected_response = {"status": True, "result": []}

    # Mock the auth response
    auth_token = create_test_token(exp_offset_seconds=3600)
    auth_mock_response = AsyncMock()
    auth_mock_response.json.return_value = {"token": auth_token}
    auth_mock_response.raise_for_status = MagicMock()

    # Mock the speed tiers response
    speed_tiers_mock_response = AsyncMock()
    speed_tiers_mock_response.json.return_value = expected_response
    speed_tiers_mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    # First call is to auth, second call is to speed tiers
    def mock_post(*args, **kwargs):
        if args[0] == f"{client.BASE_URL}/auth":
            return auth_mock_response
        elif args[0] == f"{client.BASE_URL}/nbn/speed-tiers":
            return speed_tiers_mock_response
        else:
            raise ValueError(f"Unexpected POST to {args[0]}")

    mock_client.post.side_effect = mock_post
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.get_available_speed_tiers(
        street_name="Test Street",
        suburb="Test Suburb",
        state="NSW",
        postcode="2000",
        street_number=123,
        unit="4B",
        level="2",
        lot_no=456,
    )
    assert result == expected_response
    # Check the speed-tiers call (second call)
    speed_tiers_call_args = mock_client.post.call_args_list[1]
    assert speed_tiers_call_args[1]["data"]["street_number"] == 123
    assert speed_tiers_call_args[1]["data"]["unit"] == "4B"
    assert speed_tiers_call_args[1]["data"]["level"] == "2"
    assert speed_tiers_call_args[1]["data"]["lot_no"] == 456


@pytest.mark.asyncio
async def test_get_available_speed_tiers_missing_required():
    """Test that ValueError is raised when required parameters are missing."""
    client = IperiumClient(email="test@example.com", password="testpass")

    with pytest.raises(ValueError, match="street_name, suburb, state, and postcode are required"):
        await client.get_available_speed_tiers(
            street_name="Test Street",
            suburb="",  # Missing suburb
            state="NSW",
            postcode="2000",
        )


@pytest.mark.asyncio
async def test_get_installation_status(monkeypatch):
    """Test getting installation status for a location ID."""
    client = IperiumClient(email="test@example.com", password="testpass")
    loc_id = "LOC456"
    expected_response = {
        "locId": loc_id,
        "installationStatus": "Completed",
        "serviceStatus": "Active",
        "estimatedCompletion": "2026-04-30",
        "notes": "Installation finished successfully",
    }

    # Mock the auth response
    auth_token = create_test_token(exp_offset_seconds=3600)
    auth_mock_response = AsyncMock()
    auth_mock_response.json.return_value = {"token": auth_token}
    auth_mock_response.raise_for_status = MagicMock()

    # Mock the installation status response
    install_mock_response = AsyncMock()
    install_mock_response.json.return_value = expected_response
    install_mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    # First call is to auth, second call is to installation status
    def mock_get(*args, **kwargs):
        # This is a GET call, check if it's to the installation status endpoint
        if args[0] == f"{client.BASE_URL}/nbn/installation-status/{loc_id}":
            return install_mock_response
        else:
            raise ValueError(f"Unexpected GET to {args[0]}")

    mock_client.get.side_effect = mock_get
    # We also need to mock the POST for auth
    mock_client.post.return_value = auth_mock_response
    mock_client.__aenter__.return_value = mock_client

    monkeypatch.setattr("iperium.client.httpx.AsyncClient", lambda **kwargs: mock_client)

    result = await client.get_installation_status(loc_id)
    assert result == expected_response
    # Should have made one POST (auth) and one GET (installation status)
    assert mock_client.post.call_count == 1
    assert mock_client.get.call_count == 1

    # Check auth call
    auth_call_args = mock_client.post.call_args
    assert auth_call_args[0][0] == f"{client.BASE_URL}/auth"

    # Check installation status call
    install_call_args = mock_client.get.call_args
    assert install_call_args[0][0] == f"{client.BASE_URL}/nbn/installation-status/{loc_id}"
    assert "Authorization" in install_call_args[1]["headers"]


@pytest.mark.asyncio
async def test_get_installation_status_missing_loc_id():
    """Test that ValueError is raised when loc_id is not provided."""
    client = IperiumClient(email="test@example.com", password="testpass")

    with pytest.raises(ValueError, match="loc_id is required"):
        await client.get_installation_status("")

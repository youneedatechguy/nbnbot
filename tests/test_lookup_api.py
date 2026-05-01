import pytest

from fastapi.testclient import TestClient

from app.main import app, get_lookup_service
from bot.nbn_service import NBNResult


class FakeNBNService:
    async def lookup(self, free_text_address: str):
        return [
            NBNResult(
                input_address=free_text_address,
                loc_id="LOC123",
                match=None,
                address="11 Wattle Drive, Yamba NSW 2464",
                technology="FTTP",
                serviceability=1,
                ports_free=None,
                ports_used=None,
                ports_total=None,
                service_class=None,
                fibre_on_demand=None,
            )
        ]


def test_lookup_endpoint_returns_formatted_message():
    app.dependency_overrides[get_lookup_service] = lambda: FakeNBNService()
    try:
        client = TestClient(app)
        resp = client.post("/lookup", json={"address": "11 Wattle Drive Yamba NSW 2464"})
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "📡" in data["message"]
        assert "LOC123" in data["message"]
        assert "FTTP" in data["message"]
        assert "Serviceable" in data["message"]
    finally:
        app.dependency_overrides.clear()

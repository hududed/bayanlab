"""
End-to-end tests for Halal API endpoints.

Tests the tiered access system (demo vs full) and data validation.
Runs against the live Neon database.

Usage:
    uv run pytest backend/tests/e2e/test_halal_api.py -v
    uv run pytest backend/tests/e2e/test_halal_api.py -v -k "demo"  # Only demo tests
"""
import os
import pytest
import httpx
from typing import Generator

# Test against localhost by default, can override with env var
BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:8100")
VALID_API_KEY = os.getenv("TEST_API_KEY", "")  # Set this to test full access (use any valid bl_* key)


@pytest.fixture(scope="module")
def client() -> Generator[httpx.Client, None, None]:
    """HTTP client for API tests."""
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        yield client


class TestHalalEateriesAPI:
    """Tests for /v1/halal-eateries endpoint."""

    def test_demo_mode_returns_limited_results(self, client: httpx.Client):
        """Demo mode (no API key) should return max 10 items."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert data["access_tier"] == "demo"
        assert data["count"] <= 10
        # Total only shown if there's more data than displayed (teaser)
        if data["total"] is not None:
            assert data["total"] > data["count"]

    def test_demo_mode_redacts_contact_info(self, client: httpx.Client):
        """Demo mode should redact phone, website, hours, google_place_id."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert data["access_tier"] == "demo"

        for item in data["items"]:
            assert item["phone"] is None, "Phone should be redacted in demo mode"
            assert item["website"] is None, "Website should be redacted in demo mode"
            assert item["hours_raw"] is None, "Hours should be redacted in demo mode"
            assert item["google_place_id"] is None, "Google Place ID should be redacted in demo mode"

    def test_demo_mode_shows_addresses(self, client: httpx.Client):
        """Demo mode should still show addresses and coordinates (like Enigma)."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["address"] is not None
            assert item["address"]["city"] is not None
            assert item["address"]["state"] == "CO"
            # Lat/lng should be visible
            if item["latitude"] is not None:
                assert isinstance(item["latitude"], float)

    def test_response_structure(self, client: httpx.Client):
        """Verify response has correct structure."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "region" in data
        assert "count" in data
        assert "access_tier" in data
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_city_filter(self, client: httpx.Client):
        """Test filtering by city."""
        response = client.get("/v1/halal-eateries", params={"region": "CO", "city": "Denver"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["address"]["city"].lower() == "denver"

    def test_invalid_region_returns_empty(self, client: httpx.Client):
        """Invalid region should return empty results, not error."""
        response = client.get("/v1/halal-eateries", params={"region": "XX"})
        assert response.status_code == 200

        data = response.json()
        assert data["count"] == 0
        assert data["items"] == []

    @pytest.mark.skipif(not VALID_API_KEY, reason="No API key configured")
    def test_full_mode_with_api_key(self, client: httpx.Client):
        """Full mode (with API key) should return all data."""
        response = client.get(
            "/v1/halal-eateries",
            params={"region": "CO"},
            headers={"X-API-Key": VALID_API_KEY}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["access_tier"] == "full"
        assert data["total"] is None  # Total not shown in full mode


class TestHalalMarketsAPI:
    """Tests for /v1/halal-markets endpoint."""

    def test_demo_mode_returns_limited_results(self, client: httpx.Client):
        """Demo mode should return max 5 items for markets."""
        response = client.get("/v1/halal-markets", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert data["access_tier"] == "demo"
        assert data["count"] <= 5
        # Total only shown if there's more data than displayed (teaser)
        if data["total"] is not None:
            assert data["total"] > data["count"]

    def test_demo_mode_redacts_contact_info(self, client: httpx.Client):
        """Demo mode should redact contact info for markets."""
        response = client.get("/v1/halal-markets", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["phone"] is None
            assert item["website"] is None
            assert item["hours_raw"] is None
            assert item["google_place_id"] is None

    def test_market_specific_fields(self, client: httpx.Client):
        """Markets should have category and market-specific boolean fields."""
        response = client.get("/v1/halal-markets", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["category"] in ["grocery", "butcher", "wholesale"]
            assert isinstance(item["has_butcher"], bool)
            assert isinstance(item["has_deli"], bool)
            assert isinstance(item["sells_turkey"], bool)

    def test_response_structure(self, client: httpx.Client):
        """Verify markets response has correct structure."""
        response = client.get("/v1/halal-markets", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "region" in data
        assert "count" in data
        assert "total" in data
        assert "access_tier" in data
        assert "items" in data


class TestHalalPlacesAPI:
    """Tests for /v1/halal-places combined endpoint."""

    def test_demo_mode_returns_limited_results(self, client: httpx.Client):
        """Demo mode should return max 10 combined items."""
        response = client.get("/v1/halal-places", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert data["access_tier"] == "demo"
        assert data["count"] <= 10
        # Total only shown if there's more data than displayed (teaser)
        if data["total"] is not None:
            assert data["total"] > data["count"]

    def test_includes_both_eateries_and_markets(self, client: httpx.Client):
        """Combined endpoint should include both place types."""
        response = client.get("/v1/halal-places", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert data["eateries_count"] > 0
        assert data["markets_count"] > 0

        place_types = {item["place_type"] for item in data["items"]}
        # At least one type should be present in demo results
        assert len(place_types) >= 1

    def test_place_type_filter_eatery(self, client: httpx.Client):
        """Filter by place_type=eatery should only return eateries."""
        response = client.get("/v1/halal-places", params={"region": "CO", "place_type": "eatery"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["place_type"] == "eatery"

    def test_place_type_filter_market(self, client: httpx.Client):
        """Filter by place_type=market should only return markets."""
        response = client.get("/v1/halal-places", params={"region": "CO", "place_type": "market"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["place_type"] == "market"

    def test_response_structure(self, client: httpx.Client):
        """Verify combined response has correct structure."""
        response = client.get("/v1/halal-places", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        assert "version" in data
        assert "region" in data
        assert "count" in data
        assert "total" in data
        assert "access_tier" in data
        assert "eateries_count" in data
        assert "markets_count" in data
        assert "items" in data

    def test_demo_mode_redacts_contact_info(self, client: httpx.Client):
        """Demo mode should redact contact info for all place types."""
        response = client.get("/v1/halal-places", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["phone"] is None
            assert item["website"] is None
            assert item["hours_raw"] is None
            assert item["google_place_id"] is None


class TestDataQuality:
    """Tests for data quality and consistency."""

    def test_eateries_have_required_fields(self, client: httpx.Client):
        """All eateries should have required fields populated."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["eatery_id"] is not None
            assert item["name"] is not None and len(item["name"]) > 0
            assert item["halal_status"] in ["validated", "likely_halal", "unverified"]
            assert item["source"] is not None

    def test_markets_have_required_fields(self, client: httpx.Client):
        """All markets should have required fields populated."""
        response = client.get("/v1/halal-markets", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            assert item["market_id"] is not None
            assert item["name"] is not None and len(item["name"]) > 0
            assert item["halal_status"] is not None
            assert item["source"] is not None

    def test_coordinates_are_valid(self, client: httpx.Client):
        """Coordinates should be within valid Colorado bounds."""
        response = client.get("/v1/halal-eateries", params={"region": "CO"})
        assert response.status_code == 200

        data = response.json()
        for item in data["items"]:
            if item["latitude"] is not None:
                # Colorado lat bounds: ~37 to ~41
                assert 36.0 < item["latitude"] < 42.0, f"Invalid latitude: {item['latitude']}"
            if item["longitude"] is not None:
                # Colorado lng bounds: ~-109 to ~-102
                assert -110.0 < item["longitude"] < -101.0, f"Invalid longitude: {item['longitude']}"

"""
Unit tests for Pydantic models
"""
import pytest
from datetime import datetime, timezone
from uuid import uuid4

# Import from services (path is set up in conftest.py)
from services.common.models import (
    EventBase, BusinessBase, Address, Venue,
    EventAPI, BusinessAPI
)


def test_address_model():
    """Test Address model"""
    address = Address(
        street="123 Main St",
        city="Denver",
        state="CO",
        zip="80202"
    )
    assert address.city == "Denver"
    assert address.state == "CO"


def test_venue_model():
    """Test Venue model"""
    venue = Venue(
        name="Test Venue",
        address=Address(city="Denver", state="CO"),
        latitude=39.7392,
        longitude=-104.9903
    )
    assert venue.name == "Test Venue"
    assert venue.address.city == "Denver"


def test_event_base_validation():
    """Test EventBase validation"""
    # Valid event
    event = EventBase(
        title="Test Event",
        start_time=datetime(2025, 11, 15, 13, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 11, 15, 14, 0, tzinfo=timezone.utc),
        venue_name="Test Venue",
        address_city="Denver",
        address_state="CO",
        source="csv",
        region="CO"
    )
    assert event.title == "Test Event"

    # Invalid: end before start
    with pytest.raises(ValueError):
        EventBase(
            title="Bad Event",
            start_time=datetime(2025, 11, 15, 14, 0, tzinfo=timezone.utc),
            end_time=datetime(2025, 11, 15, 13, 0, tzinfo=timezone.utc),
            venue_name="Test Venue",
            address_city="Denver",
            address_state="CO",
            source="csv",
            region="CO"
        )


def test_business_base_model():
    """Test BusinessBase model"""
    business = BusinessBase(
        name="Test Restaurant",
        category="restaurant",
        address_city="Boulder",
        address_state="CO",
        halal_certified=True,
        source="csv",
        region="CO"
    )
    assert business.name == "Test Restaurant"
    assert business.category == "restaurant"
    assert business.halal_certified is True


def test_event_api_model():
    """Test EventAPI response model"""
    event = EventAPI(
        event_id=uuid4(),
        title="API Test Event",
        start_time=datetime(2025, 11, 15, 13, 0, tzinfo=timezone.utc),
        end_time=datetime(2025, 11, 15, 14, 0, tzinfo=timezone.utc),
        all_day=False,
        venue=Venue(
            name="Test Venue",
            address=Address(city="Denver", state="CO"),
            latitude=39.7392,
            longitude=-104.9903
        ),
        organizer={"name": "Test Organizer", "contact": "test@example.com"},
        source="ics",
        region="CO",
        updated_at=datetime.now(timezone.utc)
    )
    assert event.title == "API Test Event"
    assert event.venue.name == "Test Venue"


def test_business_api_model():
    """Test BusinessAPI response model"""
    business = BusinessAPI(
        business_id=uuid4(),
        name="API Test Business",
        category="grocery",
        address=Address(
            street="456 Oak St",
            city="Boulder",
            state="CO",
            zip="80301"
        ),
        latitude=40.0150,
        longitude=-105.2705,
        self_identified_muslim_owned=True,
        halal_certified=False,
        source="csv",
        region="CO",
        updated_at=datetime.now(timezone.utc)
    )
    assert business.name == "API Test Business"
    assert business.category == "grocery"
    assert business.self_identified_muslim_owned is True

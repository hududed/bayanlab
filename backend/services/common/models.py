"""
Pydantic models for BayanLab Community Data Backbone
"""
from datetime import datetime
from typing import Optional, Literal
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, HttpUrl, field_validator
from decimal import Decimal


# Enums
EventSource = Literal["ics", "csv"]
BusinessSource = Literal["osm", "certifier", "csv"]
BusinessCategory = Literal["restaurant", "service", "retail", "grocery", "butcher", "other"]


# Common models
class Address(BaseModel):
    """Address model"""
    street: Optional[str] = None
    city: str
    state: str
    zip: Optional[str] = Field(None, alias="zip_code")

    class Config:
        populate_by_name = True


class Venue(BaseModel):
    """Venue model for events"""
    name: str
    address: Address
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None


class Organizer(BaseModel):
    """Organizer model for events"""
    name: Optional[str] = None
    contact: Optional[str] = None


# Event models
class EventBase(BaseModel):
    """Base event model"""
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    venue_name: str
    address_street: Optional[str] = None
    address_city: str
    address_state: str
    address_zip: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    url: Optional[HttpUrl] = None
    organizer_name: Optional[str] = None
    organizer_contact: Optional[str] = None
    source: EventSource
    source_ref: Optional[str] = None
    region: str

    @field_validator('end_time')
    @classmethod
    def end_after_start(cls, v, info):
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time must be after start_time')
        return v


class EventCanonical(EventBase):
    """Canonical event model (from database)"""
    event_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EventAPI(BaseModel):
    """Event model for API responses"""
    event_id: UUID
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool
    venue: Venue
    url: Optional[HttpUrl] = None
    organizer: Organizer
    source: EventSource
    source_ref: Optional[str] = None
    region: str
    updated_at: datetime


# Business models
class BusinessBase(BaseModel):
    """Base business model"""
    name: str = Field(..., min_length=1, max_length=300)
    category: BusinessCategory
    address_street: Optional[str] = None
    address_city: str
    address_state: str
    address_zip: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    website: Optional[HttpUrl] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    self_identified_muslim_owned: bool = False
    halal_certified: bool = False
    certifier_name: Optional[str] = None
    certifier_ref: Optional[str] = None
    placekey: Optional[str] = None
    source: BusinessSource
    source_ref: Optional[str] = None
    region: str


class BusinessCanonical(BusinessBase):
    """Canonical business model (from database)"""
    business_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BusinessAPI(BaseModel):
    """Business model for API responses"""
    business_id: UUID
    name: str
    category: BusinessCategory
    address: Address
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    website: Optional[HttpUrl] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    self_identified_muslim_owned: bool
    halal_certified: bool
    certifier_name: Optional[str] = None
    certifier_ref: Optional[str] = None
    placekey: Optional[str] = None
    source: BusinessSource
    source_ref: Optional[str] = None
    region: str
    updated_at: datetime


# API response models
class EventsResponse(BaseModel):
    """Events API response"""
    version: str = "1.0"
    region: str
    count: int
    items: list[EventAPI]


class BusinessesResponse(BaseModel):
    """Businesses API response"""
    version: str = "1.0"
    region: str
    count: int
    items: list[BusinessAPI]


class MetricsResponse(BaseModel):
    """Metrics API response"""
    events_count: int
    businesses_count: int
    cities_covered: int
    last_build_at: Optional[datetime] = None


# Staging models
class StagingEvent(BaseModel):
    """Staging event model"""
    staging_id: UUID
    ingest_run_id: UUID
    source: EventSource
    source_ref: Optional[str] = None
    raw_payload: dict
    ingested_at: datetime
    processed: bool = False
    error_message: Optional[str] = None


class StagingBusiness(BaseModel):
    """Staging business model"""
    staging_id: UUID
    ingest_run_id: UUID
    source: BusinessSource
    source_ref: Optional[str] = None
    raw_payload: dict
    ingested_at: datetime
    processed: bool = False
    error_message: Optional[str] = None

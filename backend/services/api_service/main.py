"""
FastAPI service for BayanLab Community Data Backbone
"""
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from pydantic import BaseModel, EmailStr
from pathlib import Path
import uvicorn
import os

from ..common.database import get_db
from ..common.config import get_settings
from ..common.logger import get_logger
from ..common.models import EventsResponse, BusinessesResponse, MetricsResponse, EventAPI, BusinessAPI, Address, Venue, Organizer
from .email_service import email_service
import re
import phonenumbers
from phonenumbers import NumberParseException

settings = get_settings()
logger = get_logger("api_service")


def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """
    Normalize and validate phone number to US format (10 digits)
    - Uses Google's phonenumbers library for robust validation
    - Accepts any US phone format: (970) 231-0576, +1-970-231-0576, etc.
    - Returns 10-digit US phone number or None if invalid
    """
    if not phone:
        return None

    try:
        # Parse as US phone number
        parsed = phonenumbers.parse(phone, "US")

        # Validate it's a valid number
        if not phonenumbers.is_valid_number(parsed):
            logger.warning(f"Invalid phone number: {phone}")
            return None

        # Format as national number (10 digits only)
        national_number = str(parsed.national_number)

        # Ensure it's exactly 10 digits
        if len(national_number) != 10:
            logger.warning(f"Phone number not 10 digits: {national_number} (original: {phone})")
            return None

        return national_number

    except NumberParseException as e:
        logger.warning(f"Failed to parse phone number '{phone}': {e}")
        return None


# Pydantic models for business claim
class BusinessClaimRequest(BaseModel):
    owner_name: str
    owner_email: EmailStr
    owner_phone: Optional[str] = None
    business_name: str
    business_city: str
    business_state: str
    business_street_address: Optional[str] = None
    business_zip: Optional[str] = None
    business_industry: Optional[str] = None
    business_industry_other: Optional[str] = None  # NEW: Specify industry if "Other"
    business_website: Optional[str] = None
    business_phone: Optional[str] = None
    business_whatsapp: Optional[str] = None
    business_description: Optional[str] = None
    muslim_owned: bool = False
    submitted_from: str = "web"


class BusinessClaimResponse(BaseModel):
    claim_id: str
    message: str


class BusinessSyncData(BaseModel):
    business_id: str
    business_name: str
    business_industry: Optional[str] = None
    business_industry_other: Optional[str] = None  # Specified industry if "Other"
    business_description: Optional[str] = None
    business_website: Optional[str] = None
    business_address: Optional[str] = None  # Street address only
    business_city: str
    business_state: str
    business_zip: Optional[str] = None
    business_phone: Optional[str] = None
    business_whatsapp: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    owner_name: str
    owner_email: str
    owner_phone: Optional[str] = None
    muslim_owned: bool = False
    google_place_id: Optional[str] = None
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None
    business_hours: Optional[Dict[str, str]] = None
    photos: Optional[List[str]] = None
    status: str
    updated_at: str


# Pydantic models for halal eateries
class HalalEateryAPI(BaseModel):
    eatery_id: str
    name: str
    cuisine_style: Optional[str] = None
    address: Address
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours_raw: Optional[str] = None
    google_rating: Optional[float] = None
    halal_status: str  # 'validated', 'likely_halal', 'unverified'
    is_favorite: bool = False
    is_food_truck: bool = False
    is_carry_out_only: bool = False
    is_cafe_bakery: bool = False
    has_many_locations: bool = False
    source: str
    google_place_id: Optional[str] = None
    updated_at: datetime


class HalalEateriesResponse(BaseModel):
    version: str = "1.0"
    region: str
    count: int
    total: Optional[int] = None  # Total available (shown in demo mode)
    access_tier: str = "full"  # "demo" or "full"
    items: List[HalalEateryAPI]


# Pydantic models for halal markets
class HalalMarketAPI(BaseModel):
    market_id: str
    name: str
    category: str  # 'grocery', 'butcher', 'wholesale'
    address: Address
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours_raw: Optional[str] = None
    google_rating: Optional[float] = None
    halal_status: str = "validated"
    has_butcher: bool = False
    has_deli: bool = False
    sells_turkey: bool = False
    source: str
    google_place_id: Optional[str] = None
    updated_at: datetime


class HalalMarketsResponse(BaseModel):
    version: str = "1.0"
    region: str
    count: int
    total: Optional[int] = None
    access_tier: str = "full"
    items: List[HalalMarketAPI]


# Combined halal places (eateries + markets)
class HalalPlaceAPI(BaseModel):
    place_id: str
    place_type: str  # 'eatery' or 'market'
    name: str
    category: Optional[str] = None  # cuisine_style for eateries, category for markets
    address: Address
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    hours_raw: Optional[str] = None
    google_rating: Optional[float] = None
    halal_status: str
    source: str
    google_place_id: Optional[str] = None
    updated_at: datetime


class HalalPlacesResponse(BaseModel):
    version: str = "1.0"
    region: str
    count: int
    total: Optional[int] = None
    access_tier: str = "full"
    eateries_count: int = 0
    markets_count: int = 0
    items: List[HalalPlaceAPI]


# Masajid (Mosques) models
class MasjidAPI(BaseModel):
    masjid_id: str
    name: str
    address: Address
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    email: Optional[str] = None
    languages: Optional[str] = None
    has_womens_section: bool = True
    has_parking: bool = True
    has_wudu_facilities: bool = True
    offers_jumah: bool = True
    offers_daily_prayers: bool = True
    offers_quran_classes: Optional[bool] = None
    offers_weekend_school: Optional[bool] = None
    verification_status: str = "unverified"
    source: str
    updated_at: datetime


class MasajidResponse(BaseModel):
    version: str = "1.0"
    region: str
    count: int
    total: Optional[int] = None
    access_tier: str = "full"
    items: List[MasjidAPI]


class BusinessSyncResponse(BaseModel):
    businesses: List[BusinessSyncData]
    pagination: Dict[str, Any]


# Initialize FastAPI
app = FastAPI(
    title="BayanLab Community Data Backbone API",
    description="""
Read-only API for community events, Muslim-owned businesses, and halal eateries.

## Endpoints

- **Events**: Community events from masjids and Islamic centers
- **Businesses**: Muslim-owned businesses (ProWasl integration)
- **Halal Eateries**: Halal restaurants, cafes, and food trucks

## Authentication

Most endpoints are public. Business sync requires API key authentication.
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {"name": "Events", "description": "Community events from masjids"},
        {"name": "Businesses", "description": "Muslim-owned businesses for ProWasl"},
        {"name": "Halal Eateries", "description": "Halal restaurants and food establishments"},
        {"name": "Metrics", "description": "Platform metrics and counters"},
    ]
)

# Mount static files (for claim form)
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """
    Root endpoint - serve claim form directly
    """
    static_path = Path(__file__).parent / "static" / "claim.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Claim form not found")
    return FileResponse(str(static_path))


@app.get("/favicon.ico")
@app.get("/favicon.png")
async def favicon():
    """
    Serve favicon with cache control headers
    """
    favicon_path = Path(__file__).parent / "static" / "favicon.png"
    if favicon_path.exists():
        return FileResponse(
            str(favicon_path),
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour instead of forever
                "ETag": str(favicon_path.stat().st_mtime)  # Use file modification time as ETag
            }
        )
    # Return 204 No Content if favicon doesn't exist
    return JSONResponse(status_code=204, content=None)


@app.get("/healthz")
async def healthz(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint with database connectivity test
    Returns 200 if healthy, 503 if unhealthy
    """
    try:
        # Check database connectivity
        result = await db.execute(text("SELECT 1"))
        result.scalar()

        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "service": "bayan_backbone_api",
                "version": "1.0.0",
                "database": "connected",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "bayan_backbone_api",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


@app.get("/metrics")
async def metrics(db: AsyncSession = Depends(get_db)):
    """
    Prometheus-compatible metrics endpoint
    Returns metrics in Prometheus text format
    """
    try:
        # Query database metrics
        events_result = await db.execute(text("SELECT COUNT(*) FROM event_canonical"))
        businesses_result = await db.execute(text("SELECT COUNT(*) FROM business_canonical"))
        events_by_region = await db.execute(text("""
            SELECT region, COUNT(*) FROM event_canonical GROUP BY region
        """))
        businesses_by_region = await db.execute(text("""
            SELECT region, COUNT(*) FROM business_canonical GROUP BY region
        """))

        events_count = events_result.scalar() or 0
        businesses_count = businesses_result.scalar() or 0

        # Build Prometheus metrics format
        metrics_text = f"""# HELP bayanlab_events_total Total number of events in database
# TYPE bayanlab_events_total gauge
bayanlab_events_total {events_count}

# HELP bayanlab_businesses_total Total number of businesses in database
# TYPE bayanlab_businesses_total gauge
bayanlab_businesses_total {businesses_count}

# HELP bayanlab_events_by_region Events count by region
# TYPE bayanlab_events_by_region gauge
"""
        for row in events_by_region.fetchall():
            region, count = row
            metrics_text += f'bayanlab_events_by_region{{region="{region}"}} {count}\n'

        metrics_text += """
# HELP bayanlab_businesses_by_region Businesses count by region
# TYPE bayanlab_businesses_by_region gauge
"""
        for row in businesses_by_region.fetchall():
            region, count = row
            metrics_text += f'bayanlab_businesses_by_region{{region="{region}"}} {count}\n'

        return JSONResponse(
            content=metrics_text,
            media_type="text/plain; version=0.0.4"
        )

    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return JSONResponse(
            status_code=503,
            content="# Metrics unavailable\n",
            media_type="text/plain"
        )


@app.get("/v1/events", response_model=EventsResponse, tags=["Events"])
@limiter.limit("100/minute")
async def get_events(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO, US-CA, MY)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    updated_since: Optional[datetime] = Query(None, description="Return events updated since this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get events for a region
    """
    try:
        # Build query
        query_sql = """
        SELECT
            event_id, title, description, start_time, end_time, all_day,
            venue_name, address_street, address_city, address_state, address_zip,
            latitude, longitude, url, organizer_name, organizer_contact,
            source, source_ref, region, updated_at
        FROM event_canonical
        WHERE region = :region
        """

        params = {'region': region, 'limit': limit, 'offset': offset}

        if city:
            query_sql += " AND LOWER(address_city) = LOWER(:city)"
            params['city'] = city

        if updated_since:
            query_sql += " AND updated_at >= :updated_since"
            params['updated_since'] = updated_since

        query_sql += " ORDER BY updated_at DESC, event_id LIMIT :limit OFFSET :offset"

        # Execute query
        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        # Build response
        items = []
        for row in rows:
            (event_id, title, description, start_time, end_time, all_day,
             venue_name, address_street, address_city, address_state, address_zip,
             latitude, longitude, url, organizer_name, organizer_contact,
             source, source_ref, region, updated_at) = row

            event = EventAPI(
                event_id=event_id,
                title=title,
                description=description,
                start_time=start_time,
                end_time=end_time,
                all_day=all_day,
                venue=Venue(
                    name=venue_name,
                    address=Address(
                        street=address_street,
                        city=address_city,
                        state=address_state,
                        zip=address_zip
                    ),
                    latitude=latitude,
                    longitude=longitude
                ),
                url=url,
                organizer=Organizer(
                    name=organizer_name,
                    contact=organizer_contact
                ),
                source=source,
                source_ref=source_ref,
                region=region,
                updated_at=updated_at
            )
            items.append(event)

        response = EventsResponse(
            version="1.0",
            region=region,
            count=len(items),
            items=items
        )

        logger.info(f"Served {len(items)} events for region {region}")
        return response

    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/businesses", tags=["Businesses"])
@limiter.limit("100/minute")
async def get_businesses(
    request: Request,
    region: str = Query("CO", description="Region/state code (e.g., CO)"),
    category: Optional[str] = Query(None, description="Filter by industry/category"),
    city: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get Muslim-owned businesses for a region.

    Returns approved business claims from claim.prowasl.com.

    **Access Tiers:**
    - **Demo (no API key)**: 5 sample rows, redacted contact info
    - **Full (with API key)**: All data, full contact details
    """
    try:
        # Check API key for tiered access
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key
        is_demo_mode = not api_key or api_key != expected_key
        DEMO_LIMIT = 5

        # Get total count
        count_sql = """
        SELECT COUNT(*) FROM business_claim_submissions
        WHERE status = 'approved' AND business_state = :region
        """
        count_params = {'region': region}
        if city:
            count_sql += " AND LOWER(business_city) = LOWER(:city)"
            count_params['city'] = city
        if category:
            count_sql += " AND business_industry = :category"
            count_params['category'] = category

        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar() or 0

        # Build query for approved claims
        query_sql = """
        SELECT
            claim_id, business_name, business_industry, business_industry_other,
            business_street_address, business_city, business_state, business_zip,
            latitude, longitude, business_phone, business_whatsapp, business_website,
            business_description, muslim_owned, submitted_at
        FROM business_claim_submissions
        WHERE status = 'approved' AND business_state = :region
        """

        params = {'region': region}

        if city:
            query_sql += " AND LOWER(business_city) = LOWER(:city)"
            params['city'] = city

        if category:
            query_sql += " AND business_industry = :category"
            params['category'] = category

        query_sql += " ORDER BY submitted_at DESC"

        # Apply limits based on access tier
        if is_demo_mode:
            query_sql += f" LIMIT {DEMO_LIMIT}"
        else:
            query_sql += " LIMIT :limit OFFSET :offset"
            params['limit'] = limit
            params['offset'] = offset

        # Execute query
        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        # Build response
        items = []
        for row in rows:
            (claim_id, name, industry, industry_other,
             street, city_name, state, zip_code,
             lat, lng, phone, whatsapp, website,
             description, muslim_owned, submitted_at) = row

            # Redact contact info in demo mode
            if is_demo_mode:
                phone = None
                whatsapp = None
                website = None

            # Use industry_other if industry is "Other"
            display_category = industry_other if industry == "Other" and industry_other else industry

            items.append({
                "business_id": str(claim_id),
                "name": name,
                "category": display_category,
                "address": {
                    "street": street,
                    "city": city_name,
                    "state": state,
                    "zip_code": zip_code
                },
                "latitude": float(lat) if lat else None,
                "longitude": float(lng) if lng else None,
                "phone": phone,
                "whatsapp": whatsapp,
                "website": website,
                "description": description,
                "muslim_owned": muslim_owned,
                "updated_at": submitted_at.isoformat() if submitted_at else None
            })

        # Only show total if there's more data than what we're showing (teaser)
        show_total = is_demo_mode and total_count > len(items)

        response = {
            "version": "1.0",
            "region": region,
            "count": len(items),
            "total": total_count if show_total else None,
            "access_tier": "demo" if is_demo_mode else "full",
            "items": items
        }

        logger.info(f"Served {len(items)} businesses for region {region} (demo={is_demo_mode})")
        return JSONResponse(content=response)

    except Exception as e:
        logger.error(f"Error fetching businesses: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/metrics", response_model=MetricsResponse, tags=["Metrics"])
@limiter.limit("100/minute")
async def get_metrics(
    request: Request,
    region: Optional[str] = Query(None, description="Filter by region"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get metrics for the data backbone
    """
    try:
        # Build queries
        events_query = "SELECT COUNT(*) FROM event_canonical"
        businesses_query = "SELECT COUNT(*) FROM business_canonical"
        cities_query = """
        SELECT COUNT(DISTINCT address_city)
        FROM (
            SELECT address_city FROM event_canonical
            UNION
            SELECT address_city FROM business_canonical
        ) AS cities
        """

        params = {}

        if region:
            events_query += " WHERE region = :region"
            businesses_query += " WHERE region = :region"
            cities_query = f"""
            SELECT COUNT(DISTINCT address_city)
            FROM (
                SELECT address_city FROM event_canonical WHERE region = :region
                UNION
                SELECT address_city FROM business_canonical WHERE region = :region
            ) AS cities
            """
            params['region'] = region

        # Execute queries
        events_result = await db.execute(text(events_query), params)
        businesses_result = await db.execute(text(businesses_query), params)
        cities_result = await db.execute(text(cities_query), params)

        events_count = events_result.scalar()
        businesses_count = businesses_result.scalar()
        cities_covered = cities_result.scalar()

        # Get last build time
        build_query = """
        SELECT MAX(completed_at)
        FROM build_metadata
        WHERE status = 'success'
        """
        build_result = await db.execute(text(build_query))
        last_build_at = build_result.scalar()

        response = MetricsResponse(
            events_count=events_count or 0,
            businesses_count=businesses_count or 0,
            cities_covered=cities_covered or 0,
            last_build_at=last_build_at
        )

        logger.info("Served metrics")
        return response

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/claim")
async def serve_claim_form():
    """
    Serve the business claim form
    """
    static_path = Path(__file__).parent / "static" / "claim.html"
    if not static_path.exists():
        raise HTTPException(status_code=404, detail="Claim form not found")
    return FileResponse(str(static_path))


@app.post("/v1/businesses/claim", response_model=BusinessClaimResponse, tags=["Businesses"])
@limiter.limit("10/minute")
async def submit_business_claim(
    request: Request,
    claim: BusinessClaimRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a business claim/registration
    Allows business owners to add their business to the directory
    """
    try:
        # Validate phone numbers before processing
        normalized_owner_phone = normalize_phone(claim.owner_phone)
        normalized_business_phone = normalize_phone(claim.business_phone)
        normalized_business_whatsapp = normalize_phone(claim.business_whatsapp)

        # If a phone was provided but failed validation, reject it
        if claim.owner_phone and not normalized_owner_phone:
            raise HTTPException(
                status_code=400,
                detail="Invalid owner phone number. Please enter a valid 10-digit US phone number."
            )
        if claim.business_phone and not normalized_business_phone:
            raise HTTPException(
                status_code=400,
                detail="Invalid business phone number. Please enter a valid 10-digit US phone number."
            )
        if claim.business_whatsapp and not normalized_business_whatsapp:
            raise HTTPException(
                status_code=400,
                detail="Invalid WhatsApp number. Please enter a valid 10-digit US phone number."
            )

        # Insert claim into database
        insert_query = text("""
            INSERT INTO business_claim_submissions (
                owner_name, owner_email, owner_phone,
                business_name, business_city, business_state,
                business_street_address, business_zip,
                business_industry, business_industry_other, business_website,
                business_phone, business_whatsapp,
                business_description,
                muslim_owned, submitted_from, submitted_at, status
            )
            VALUES (
                :owner_name, :owner_email, :owner_phone,
                :business_name, :business_city, :business_state,
                :business_street_address, :business_zip,
                :business_industry, :business_industry_other, :business_website,
                :business_phone, :business_whatsapp,
                :business_description,
                :muslim_owned, :submitted_from, NOW(), 'pending'
            )
            RETURNING claim_id, short_claim_id
        """)

        # Insert with already-normalized phone numbers
        result = await db.execute(insert_query, {
            'owner_name': claim.owner_name,
            'owner_email': claim.owner_email,
            'owner_phone': normalized_owner_phone,
            'business_name': claim.business_name,
            'business_city': claim.business_city,
            'business_state': claim.business_state.upper(),
            'business_street_address': claim.business_street_address,
            'business_zip': claim.business_zip,
            'business_industry': claim.business_industry,
            'business_industry_other': claim.business_industry_other,
            'business_website': claim.business_website,
            'business_phone': normalized_business_phone,
            'business_whatsapp': normalized_business_whatsapp,
            'business_description': claim.business_description,
            'muslim_owned': claim.muslim_owned,
            'submitted_from': claim.submitted_from
        })

        await db.commit()

        row = result.first()
        claim_id = row[0]
        short_claim_id = row[1]

        logger.info(f"Business claim submitted: {short_claim_id} ({claim_id}) - {claim.business_name} by {claim.owner_email}")

        # Send confirmation email (non-blocking - don't fail if email fails)
        email_sent = False
        try:
            email_sent = await email_service.send_claim_confirmation(
                to_email=claim.owner_email,
                owner_name=claim.owner_name,
                business_name=claim.business_name,
                claim_id=short_claim_id
            )

            # Mark email as sent if successful
            if email_sent:
                update_query = text("""
                    UPDATE business_claim_submissions
                    SET confirmation_email_sent = TRUE,
                        confirmation_email_sent_at = NOW()
                    WHERE claim_id = :claim_id
                """)
                await db.execute(update_query, {'claim_id': claim_id})
                await db.commit()

        except Exception as email_error:
            logger.error(f"Failed to send confirmation email: {email_error}")
            # Continue anyway - don't fail the claim submission if email fails

        # Send admin notification (non-blocking - don't fail if email fails)
        try:
            await email_service.send_admin_notification(
                business_name=claim.business_name,
                owner_name=claim.owner_name,
                owner_email=claim.owner_email,
                city=claim.business_city,
                state=claim.business_state,
                claim_id=short_claim_id
            )
        except Exception as admin_email_error:
            logger.error(f"Failed to send admin notification: {admin_email_error}")
            # Continue anyway - don't fail the claim submission if admin email fails

        return BusinessClaimResponse(
            claim_id=short_claim_id,
            message="Thank you! Your business has been submitted for review."
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error submitting business claim: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit claim. Please try again.")


class BusinessCounterResponse(BaseModel):
    count: int
    goal: int
    percentage: float
    title: str
    message: str
    subtitle: str


@app.get("/v1/businesses/counter", response_model=BusinessCounterResponse, tags=["Businesses"])
@limiter.limit("120/minute")
async def get_business_counter(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Get live business counter with dynamic goal scaling

    Goal doubles automatically: 10 → 20 → 40 → 80 → 160
    Returns current count, goal, percentage, and display message
    """
    try:
        # Count approved businesses
        count_query = """
            SELECT COUNT(*) as count
            FROM business_claim_submissions
            WHERE status = 'approved'
        """

        result = await db.execute(text(count_query))
        count_row = result.fetchone()
        count = count_row.count if count_row else 0

        # Dynamic goal scaling with custom milestones
        # 10 → 25 → 50 → 100 → 200 → 400...
        if count < 10:
            goal = 10
            title = "🚀 Founding 10 Businesses"
            message = f"{count} / {goal} listed"
            subtitle = "Join the early cohort before we open public search."
        elif count < 25:
            goal = 25
            title = "🚀 Founding 25 Businesses"
            message = f"{count} / {goal} listed"
            subtitle = "Join the early cohort before we open public search."
        elif count < 50:
            goal = 50
            title = "🌐 Colorado Launch Group — 50 Listings"
            message = f"{count} / {goal} listed"
            subtitle = "Launching Colorado local search soon. Add your business to be included."
        elif count < 100:
            goal = 100
            title = "🌙 Ramadan Discovery Wave — 100+ Listings"
            message = f"{count} / {goal} listed"
            subtitle = "Building a nationwide list of trusted Muslim-owned & halal-friendly services for Ramadan."
        else:
            # After 100, double each time: 200, 400, 800...
            goal = 100
            while count >= goal:
                goal *= 2
            title = "🌍 Nationwide Directory"
            message = f"{count} / {goal} businesses listed"
            subtitle = "Growing the largest directory of Muslim-owned businesses."

        # Calculate percentage
        percentage = round((count / goal) * 100, 1) if goal > 0 else 0

        logger.info(f"Business counter: {count}/{goal} ({percentage}%) - {title}")

        return BusinessCounterResponse(
            count=count,
            goal=goal,
            percentage=percentage,
            title=title,
            message=message,
            subtitle=subtitle
        )

    except Exception as e:
        logger.error(f"Error in business counter endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch business counter")


@app.get("/v1/businesses/sync", response_model=BusinessSyncResponse, tags=["Businesses"])
@limiter.limit("60/minute")
async def sync_businesses(
    request: Request,
    updated_since: Optional[str] = Query(None, description="ISO8601 datetime - only return businesses updated after this timestamp"),
    state: Optional[str] = Query(None, description="Filter by state code (e.g., CO, TX)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync endpoint for ProWasl directory

    Returns approved businesses from business_claim_submissions table.
    Requires X-API-Key header for authentication.
    """
    try:
        # Verify API key
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key

        if not expected_key:
            logger.error("PROWASL_API_KEY not configured in environment")
            raise HTTPException(status_code=500, detail="Sync endpoint not configured")

        if api_key != expected_key:
            logger.warning(f"Invalid API key attempt from {get_remote_address(request)}")
            raise HTTPException(status_code=401, detail="Invalid API key")

        # Build query to fetch approved business claims
        query = """
            SELECT
                claim_id::text as business_id,
                business_name,
                business_industry,
                business_industry_other,
                business_description,
                business_website,
                business_street_address as business_address,
                business_city,
                business_state,
                business_zip,
                business_phone,
                business_whatsapp,
                latitude,
                longitude,
                owner_name,
                owner_email,
                owner_phone,
                muslim_owned,
                NULL::text as google_place_id,
                NULL::numeric as google_rating,
                NULL::int as google_review_count,
                NULL::jsonb as business_hours,
                ARRAY[]::text[] as photos,
                status,
                submitted_at::text as updated_at
            FROM business_claim_submissions
            WHERE status = 'approved'
        """

        params = {}

        # Add filters
        if updated_since:
            try:
                # Parse ISO8601 datetime string
                from dateutil import parser
                updated_dt = parser.isoparse(updated_since)
                query += " AND submitted_at > :updated_since"
                params['updated_since'] = updated_dt
            except Exception as e:
                logger.warning(f"Invalid updated_since format: {updated_since}, error: {e}")
                # Skip this filter if invalid format

        if state:
            query += " AND business_state = :state"
            params['state'] = state.upper()

        # Count total matching records
        count_query = f"SELECT COUNT(*) FROM ({query}) AS t"
        count_result = await db.execute(text(count_query), params)
        total = count_result.scalar() or 0

        # Add pagination
        query += " ORDER BY submitted_at DESC LIMIT :limit OFFSET :offset"
        params['limit'] = limit
        params['offset'] = offset

        # Execute query
        result = await db.execute(text(query), params)
        rows = result.fetchall()

        # Convert to list of dicts
        businesses = []
        for row in rows:
            businesses.append({
                'business_id': row.business_id,
                'business_name': row.business_name,
                'business_industry': row.business_industry,
                'business_industry_other': row.business_industry_other,
                'business_description': row.business_description,
                'business_website': row.business_website,
                'business_address': row.business_address,
                'business_city': row.business_city,
                'business_state': row.business_state,
                'business_zip': row.business_zip,
                'business_phone': row.business_phone,
                'business_whatsapp': row.business_whatsapp,
                'latitude': float(row.latitude) if row.latitude else None,
                'longitude': float(row.longitude) if row.longitude else None,
                'owner_name': row.owner_name,
                'owner_email': row.owner_email,
                'owner_phone': row.owner_phone,
                'muslim_owned': row.muslim_owned,
                'google_place_id': row.google_place_id,
                'google_rating': float(row.google_rating) if row.google_rating else None,
                'google_review_count': row.google_review_count,
                'business_hours': row.business_hours,
                'photos': list(row.photos) if row.photos else [],
                'status': row.status,
                'updated_at': row.updated_at
            })

        logger.info(f"Sync request: returned {len(businesses)} businesses (total: {total}, offset: {offset})")

        return BusinessSyncResponse(
            businesses=businesses,
            pagination={
                'total': total,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(businesses) < total
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sync failed. Please try again.")


# =============================================================================
# Halal Eateries API (Discovery data for Ummah App)
# =============================================================================

@app.get("/v1/halal-eateries", response_model=HalalEateriesResponse, tags=["Halal Eateries"])
@limiter.limit("100/minute")
async def get_halal_eateries(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    cuisine: Optional[str] = Query(None, description="Filter by cuisine style"),
    halal_status: Optional[str] = Query(None, description="Filter by halal status: validated, likely_halal, unverified"),
    favorites_only: bool = Query(False, description="Return only community favorites"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get halal eateries for a region.

    Discovery API for established halal restaurants, cafes, and food trucks.
    Data sourced from community directories (Colorado Halal, Zabihah, etc.)

    **Access Tiers:**
    - **Demo (no API key)**: 5 sample rows, redacted contact info (phone/website hidden)
    - **Full (with API key)**: All data, full contact details

    **Halal Status:**
    - `validated`: Confirmed halal by community directory
    - `likely_halal`: AI-identified, not yet confirmed
    - `unverified`: Listed but not verified

    **Filters:**
    - `city`: Filter by city name (case-insensitive)
    - `cuisine`: Filter by cuisine style (e.g., "Mediterranean", "Pakistani")
    - `halal_status`: Filter by verification status
    - `favorites_only`: Return only community favorites
    """
    try:
        # Check API key for tiered access
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key  # Reuse existing key for now
        is_demo_mode = not api_key or api_key != expected_key

        # Demo mode limits (like Enigma: 20 preview rows)
        DEMO_LIMIT = 10

        # First, get total count for the query (before pagination)
        count_sql = """
        SELECT COUNT(*) FROM halal_eateries WHERE region = :region
        """
        count_params = {'region': region}

        if city:
            count_sql += " AND LOWER(address_city) = LOWER(:city)"
            count_params['city'] = city
        if cuisine:
            count_sql += " AND LOWER(cuisine_style) LIKE LOWER(:cuisine)"
            count_params['cuisine'] = f"%{cuisine}%"
        if halal_status:
            count_sql += " AND halal_status = :halal_status"
            count_params['halal_status'] = halal_status
        if favorites_only:
            count_sql += " AND is_favorite = true"

        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar() or 0

        # Build main query
        query_sql = """
        SELECT
            eatery_id, name, cuisine_style,
            address_street, address_city, address_state, address_zip,
            latitude, longitude, phone, website, hours_raw, google_rating,
            halal_status, is_favorite, is_food_truck, is_carry_out_only,
            is_cafe_bakery, has_many_locations, source, google_place_id, updated_at
        FROM halal_eateries
        WHERE region = :region
        """

        # In demo mode: ignore pagination params, force limit to DEMO_LIMIT
        if is_demo_mode:
            effective_limit = DEMO_LIMIT
            effective_offset = 0
        else:
            effective_limit = limit
            effective_offset = offset

        params = {'region': region, 'limit': effective_limit, 'offset': effective_offset}

        if city:
            query_sql += " AND LOWER(address_city) = LOWER(:city)"
            params['city'] = city

        if cuisine:
            query_sql += " AND LOWER(cuisine_style) LIKE LOWER(:cuisine)"
            params['cuisine'] = f"%{cuisine}%"

        if halal_status:
            query_sql += " AND halal_status = :halal_status"
            params['halal_status'] = halal_status

        if favorites_only:
            query_sql += " AND is_favorite = true"

        query_sql += " ORDER BY is_favorite DESC, google_rating DESC NULLS LAST, name ASC LIMIT :limit OFFSET :offset"

        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        items = []
        for row in rows:
            (eatery_id, name, cuisine_style,
             address_street, address_city, address_state, address_zip,
             latitude, longitude, phone, website, hours_raw, google_rating,
             halal_status_val, is_favorite, is_food_truck, is_carry_out_only,
             is_cafe_bakery, has_many_locations, source, google_place_id, updated_at) = row

            # In demo mode: redact contact info and operational details (like Enigma)
            if is_demo_mode:
                phone = None
                website = None
                hours_raw = None
                google_place_id = None

            eatery = HalalEateryAPI(
                eatery_id=str(eatery_id),
                name=name,
                cuisine_style=cuisine_style,
                address=Address(
                    street=address_street,
                    city=address_city,
                    state=address_state,
                    zip=address_zip
                ),
                latitude=float(latitude) if latitude else None,
                longitude=float(longitude) if longitude else None,
                phone=phone,
                website=website,
                hours_raw=hours_raw,
                google_rating=float(google_rating) if google_rating else None,
                halal_status=halal_status_val,
                is_favorite=is_favorite,
                is_food_truck=is_food_truck,
                is_carry_out_only=is_carry_out_only,
                is_cafe_bakery=is_cafe_bakery,
                has_many_locations=has_many_locations,
                source=source,
                google_place_id=google_place_id,
                updated_at=updated_at
            )
            items.append(eatery)

        access_tier = "demo" if is_demo_mode else "full"
        # Only show total if there's more data than what we're showing (teaser)
        show_total = is_demo_mode and total_count > len(items)
        logger.info(f"Served {len(items)} halal eateries for region {region} (tier: {access_tier}, total: {total_count})")

        return HalalEateriesResponse(
            version="1.0",
            region=region,
            count=len(items),
            total=total_count if show_total else None,
            access_tier=access_tier,
            items=items
        )

    except Exception as e:
        logger.error(f"Error fetching halal eateries: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# Halal Markets API (Grocery stores, butchers, wholesale)
# =============================================================================

@app.get("/v1/halal-markets", response_model=HalalMarketsResponse, tags=["Halal Eateries"])
@limiter.limit("100/minute")
async def get_halal_markets(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    category: Optional[str] = Query(None, description="Filter by category: grocery, butcher, wholesale"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get halal markets for a region.

    Grocery stores, butcher shops, and wholesale suppliers with halal products.

    **Categories:**
    - `grocery`: General halal grocery stores
    - `butcher`: Halal meat shops
    - `wholesale`: Wholesale suppliers (e.g., Restaurant Depot)

    **Access Tiers:**
    - **Demo (no API key)**: 5 sample rows, redacted contact info
    - **Full (with API key)**: All data, full contact details
    """
    try:
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key
        is_demo_mode = not api_key or api_key != expected_key
        DEMO_LIMIT = 5

        # Get total count
        count_sql = "SELECT COUNT(*) FROM halal_markets WHERE region = :region"
        count_params = {'region': region}
        if city:
            count_sql += " AND LOWER(address_city) = LOWER(:city)"
            count_params['city'] = city
        if category:
            count_sql += " AND category = :category"
            count_params['category'] = category

        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar() or 0

        # Build query
        query_sql = """
        SELECT market_id, name, category, address_street, address_city, address_state, address_zip,
               latitude, longitude, phone, website, hours_raw, google_rating, halal_status,
               has_butcher, has_deli, sells_turkey, source, google_place_id, updated_at
        FROM halal_markets WHERE region = :region
        """

        if is_demo_mode:
            effective_limit = DEMO_LIMIT
            effective_offset = 0
        else:
            effective_limit = limit
            effective_offset = offset

        params = {'region': region, 'limit': effective_limit, 'offset': effective_offset}

        if city:
            query_sql += " AND LOWER(address_city) = LOWER(:city)"
            params['city'] = city
        if category:
            query_sql += " AND category = :category"
            params['category'] = category

        query_sql += " ORDER BY google_rating DESC NULLS LAST, name ASC LIMIT :limit OFFSET :offset"

        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        items = []
        for row in rows:
            (market_id, name, cat, street, mcity, state, zip_code, lat, lng, phone, website,
             hours, rating, status, has_butcher, has_deli, sells_turkey, source, gplace, updated) = row

            if is_demo_mode:
                phone, website, hours, gplace = None, None, None, None

            items.append(HalalMarketAPI(
                market_id=str(market_id),
                name=name,
                category=cat,
                address=Address(street=street, city=mcity, state=state, zip=zip_code),
                latitude=float(lat) if lat else None,
                longitude=float(lng) if lng else None,
                phone=phone,
                website=website,
                hours_raw=hours,
                google_rating=float(rating) if rating else None,
                halal_status=status,
                has_butcher=has_butcher or False,
                has_deli=has_deli or False,
                sells_turkey=sells_turkey or False,
                source=source,
                google_place_id=gplace,
                updated_at=updated
            ))

        access_tier = "demo" if is_demo_mode else "full"
        # Only show total if there's more data than what we're showing (teaser)
        show_total = is_demo_mode and total_count > len(items)
        logger.info(f"Served {len(items)} halal markets for region {region} (tier: {access_tier}, total: {total_count})")

        return HalalMarketsResponse(
            version="1.0",
            region=region,
            count=len(items),
            total=total_count if show_total else None,
            access_tier=access_tier,
            items=items
        )

    except Exception as e:
        logger.error(f"Error fetching halal markets: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# Halal Places API (Combined: Eateries + Markets for apps like Ummah)
# =============================================================================

@app.get("/v1/halal-places", response_model=HalalPlacesResponse, tags=["Halal Eateries"])
@limiter.limit("100/minute")
async def get_halal_places(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    place_type: Optional[str] = Query(None, description="Filter by type: eatery, market, or all (default)"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get all halal places (eateries + markets) for a region.

    Combined API for apps that need both restaurants and grocery stores.
    Ideal for apps like Ummah that show all halal food sources.

    **Place Types:**
    - `eatery`: Restaurants, cafes, food trucks
    - `market`: Grocery stores, butchers, wholesale

    **Access Tiers:**
    - **Demo (no API key)**: 10 sample rows, redacted contact info
    - **Full (with API key)**: All data, full contact details
    """
    try:
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key
        is_demo_mode = not api_key or api_key != expected_key
        DEMO_LIMIT = 10

        items = []
        eateries_count = 0
        markets_count = 0

        # Query eateries
        if not place_type or place_type in ('eatery', 'all'):
            eatery_sql = """
            SELECT eatery_id, name, cuisine_style, address_street, address_city, address_state, address_zip,
                   latitude, longitude, phone, website, hours_raw, google_rating, halal_status, source, google_place_id, updated_at
            FROM halal_eateries WHERE region = :region
            """
            eatery_params = {'region': region}
            if city:
                eatery_sql += " AND LOWER(address_city) = LOWER(:city)"
                eatery_params['city'] = city
            eatery_sql += " ORDER BY google_rating DESC NULLS LAST"

            result = await db.execute(text(eatery_sql), eatery_params)
            for row in result.fetchall():
                (eid, name, cuisine, street, ecity, state, zip_code, lat, lng, phone, website, hours, rating, status, source, gplace, updated) = row
                if is_demo_mode:
                    phone, website, hours, gplace = None, None, None, None
                items.append(HalalPlaceAPI(
                    place_id=str(eid), place_type="eatery", name=name, category=cuisine,
                    address=Address(street=street, city=ecity, state=state, zip=zip_code),
                    latitude=float(lat) if lat else None, longitude=float(lng) if lng else None,
                    phone=phone, website=website, hours_raw=hours,
                    google_rating=float(rating) if rating else None, halal_status=status,
                    source=source, google_place_id=gplace, updated_at=updated
                ))
            eateries_count = len(items)

        # Query markets
        if not place_type or place_type in ('market', 'all'):
            market_sql = """
            SELECT market_id, name, category, address_street, address_city, address_state, address_zip,
                   latitude, longitude, phone, website, hours_raw, google_rating, halal_status, source, google_place_id, updated_at
            FROM halal_markets WHERE region = :region
            """
            market_params = {'region': region}
            if city:
                market_sql += " AND LOWER(address_city) = LOWER(:city)"
                market_params['city'] = city
            market_sql += " ORDER BY google_rating DESC NULLS LAST"

            result = await db.execute(text(market_sql), market_params)
            for row in result.fetchall():
                (mid, name, cat, street, mcity, state, zip_code, lat, lng, phone, website, hours, rating, status, source, gplace, updated) = row
                if is_demo_mode:
                    phone, website, hours, gplace = None, None, None, None
                items.append(HalalPlaceAPI(
                    place_id=str(mid), place_type="market", name=name, category=cat,
                    address=Address(street=street, city=mcity, state=state, zip=zip_code),
                    latitude=float(lat) if lat else None, longitude=float(lng) if lng else None,
                    phone=phone, website=website, hours_raw=hours,
                    google_rating=float(rating) if rating else None, halal_status=status,
                    source=source, google_place_id=gplace, updated_at=updated
                ))
            markets_count = len(items) - eateries_count

        # Sort combined by rating
        items.sort(key=lambda x: (x.google_rating or 0), reverse=True)
        total_count = len(items)

        # Apply demo limit or pagination
        if is_demo_mode:
            items = items[:DEMO_LIMIT]
        else:
            items = items[offset:offset + limit]

        access_tier = "demo" if is_demo_mode else "full"
        # Only show total if there's more data than what we're showing (teaser)
        show_total = is_demo_mode and total_count > len(items)
        logger.info(f"Served {len(items)} halal places for region {region} (tier: {access_tier}, eateries: {eateries_count}, markets: {markets_count})")

        return HalalPlacesResponse(
            version="1.0",
            region=region,
            count=len(items),
            total=total_count if show_total else None,
            access_tier=access_tier,
            eateries_count=eateries_count,
            markets_count=markets_count,
            items=items
        )

    except Exception as e:
        logger.error(f"Error fetching halal places: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# =============================================================================
# Masajid (Mosques) API
# =============================================================================

@app.get("/v1/masajid", response_model=MasajidResponse, tags=["Masajid"])
@limiter.limit("100/minute")
async def get_masajid(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO)"),
    city: Optional[str] = Query(None, description="Filter by city"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get masajid (mosques) for a region.

    Returns Islamic centers and mosques with details about facilities and services.

    **Access Tiers:**
    - **Demo (no API key)**: 5 sample rows, redacted contact info
    - **Full (with API key)**: All data, full contact details
    """
    try:
        api_key = request.headers.get("X-API-Key")
        expected_key = settings.prowasl_api_key
        is_demo_mode = not api_key or api_key != expected_key
        DEMO_LIMIT = 5

        # Get total count - only verified masajid
        count_sql = "SELECT COUNT(*) FROM masajid WHERE region = :region AND verification_status = 'verified'"
        count_params = {'region': region}
        if city:
            count_sql += " AND LOWER(address_city) = LOWER(:city)"
            count_params['city'] = city

        count_result = await db.execute(text(count_sql), count_params)
        total_count = count_result.scalar() or 0

        # Build query - only verified masajid (excludes unverified entries without standalone locations)
        query_sql = """
        SELECT masjid_id, name, address_street, address_city, address_state, address_zip,
               latitude, longitude, phone, website, email, languages,
               has_womens_section, has_parking, has_wudu_facilities,
               offers_jumah, offers_daily_prayers, offers_quran_classes, offers_weekend_school,
               verification_status, source, updated_at
        FROM masajid WHERE region = :region AND verification_status = 'verified'
        """

        if is_demo_mode:
            effective_limit = DEMO_LIMIT
            effective_offset = 0
        else:
            effective_limit = limit
            effective_offset = offset

        params = {'region': region, 'limit': effective_limit, 'offset': effective_offset}

        if city:
            query_sql += " AND LOWER(address_city) = LOWER(:city)"
            params['city'] = city

        query_sql += " ORDER BY name ASC LIMIT :limit OFFSET :offset"

        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        items = []
        for row in rows:
            (masjid_id, name, street, mcity, state, zip_code, lat, lng, phone, website, email,
             denomination, languages, has_womens, has_parking, has_wudu,
             offers_jumah, offers_daily, offers_quran, offers_school,
             verification, source, updated) = row

            if is_demo_mode:
                phone, website, email = None, None, None

            items.append(MasjidAPI(
                masjid_id=str(masjid_id),
                name=name,
                address=Address(street=street, city=mcity, state=state, zip=zip_code),
                latitude=float(lat) if lat else None,
                longitude=float(lng) if lng else None,
                phone=phone,
                website=website,
                email=email,
                denomination=denomination,
                languages=languages,
                has_womens_section=has_womens if has_womens is not None else True,
                has_parking=has_parking if has_parking is not None else True,
                has_wudu_facilities=has_wudu if has_wudu is not None else True,
                offers_jumah=offers_jumah if offers_jumah is not None else True,
                offers_daily_prayers=offers_daily if offers_daily is not None else True,
                offers_quran_classes=offers_quran,
                offers_weekend_school=offers_school,
                verification_status=verification or "unverified",
                source=source,
                updated_at=updated
            ))

        access_tier = "demo" if is_demo_mode else "full"
        # Only show total if there's more data than what we're showing (teaser)
        show_total = is_demo_mode and total_count > len(items)
        logger.info(f"Served {len(items)} masajid for region {region} (tier: {access_tier}, total: {total_count})")

        return MasajidResponse(
            version="1.0",
            region=region,
            count=len(items),
            total=total_count if show_total else None,
            access_tier=access_tier,
            items=items
        )

    except Exception as e:
        logger.error(f"Error fetching masajid: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(
        "backend.services.api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower()
    )

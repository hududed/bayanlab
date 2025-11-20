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


class BusinessSyncResponse(BaseModel):
    businesses: List[BusinessSyncData]
    pagination: Dict[str, Any]


# Initialize FastAPI
app = FastAPI(
    title="BayanLab Community Data Backbone API",
    description="Read-only API for community events and Muslim-owned/halal businesses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
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


@app.get("/v1/events", response_model=EventsResponse)
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


@app.get("/v1/businesses", response_model=BusinessesResponse)
@limiter.limit("100/minute")
async def get_businesses(
    request: Request,
    region: str = Query("CO", description="Region code (e.g., CO, US-CA, MY)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    city: Optional[str] = Query(None, description="Filter by city"),
    updated_since: Optional[datetime] = Query(None, description="Return businesses updated since this timestamp"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get businesses for a region
    """
    try:
        # Build query
        query_sql = """
        SELECT
            business_id, name, category,
            address_street, address_city, address_state, address_zip,
            latitude, longitude, website, phone, email,
            self_identified_muslim_owned, halal_certified, certifier_name, certifier_ref,
            placekey, source, source_ref, region, updated_at
        FROM business_canonical
        WHERE region = :region
        """

        params = {'region': region, 'limit': limit, 'offset': offset}

        if category:
            query_sql += " AND category = :category"
            params['category'] = category

        if city:
            query_sql += " AND LOWER(address_city) = LOWER(:city)"
            params['city'] = city

        if updated_since:
            query_sql += " AND updated_at >= :updated_since"
            params['updated_since'] = updated_since

        query_sql += " ORDER BY updated_at DESC, business_id LIMIT :limit OFFSET :offset"

        # Execute query
        result = await db.execute(text(query_sql), params)
        rows = result.fetchall()

        # Build response
        items = []
        for row in rows:
            (business_id, name, category,
             address_street, address_city, address_state, address_zip,
             latitude, longitude, website, phone, email,
             self_identified_muslim_owned, halal_certified, certifier_name, certifier_ref,
             placekey, source, source_ref, region, updated_at) = row

            business = BusinessAPI(
                business_id=business_id,
                name=name,
                category=category,
                address=Address(
                    street=address_street,
                    city=address_city,
                    state=address_state,
                    zip=address_zip
                ),
                latitude=latitude,
                longitude=longitude,
                website=website,
                phone=phone,
                email=email,
                self_identified_muslim_owned=self_identified_muslim_owned,
                halal_certified=halal_certified,
                certifier_name=certifier_name,
                certifier_ref=certifier_ref,
                placekey=placekey,
                source=source,
                source_ref=source_ref,
                region=region,
                updated_at=updated_at
            )
            items.append(business)

        response = BusinessesResponse(
            version="1.0",
            region=region,
            count=len(items),
            items=items
        )

        logger.info(f"Served {len(items)} businesses for region {region}")
        return response

    except Exception as e:
        logger.error(f"Error fetching businesses: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/v1/metrics", response_model=MetricsResponse)
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


@app.post("/v1/businesses/claim", response_model=BusinessClaimResponse)
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
        # Validate state (for now, allow CO and common states)
        valid_states = ['CO', 'TX', 'CA', 'NY', 'IL', 'MI', 'FL', 'WA', 'AZ', 'GA']
        if claim.business_state.upper() not in valid_states:
            raise HTTPException(
                status_code=400,
                detail=f"State must be one of: {', '.join(valid_states)}"
            )

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


@app.get("/v1/businesses/counter", response_model=BusinessCounterResponse)
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
        # 25 → 50 → 100 → 200 → 400...
        if count < 25:
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


@app.get("/v1/businesses/sync", response_model=BusinessSyncResponse)
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


if __name__ == "__main__":
    uvicorn.run(
        "backend.services.api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower()
    )

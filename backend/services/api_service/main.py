"""
FastAPI service for BayanLab Community Data Backbone
"""
from fastapi import FastAPI, Depends, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timezone
import uvicorn

from ..common.database import get_db
from ..common.config import get_settings
from ..common.logger import get_logger
from ..common.models import EventsResponse, BusinessesResponse, MetricsResponse, EventAPI, BusinessAPI, Address, Venue, Organizer

settings = get_settings()
logger = get_logger("api_service")

# Initialize FastAPI
app = FastAPI(
    title="BayanLab Community Data Backbone API",
    description="Read-only API for community events and Muslim-owned/halal businesses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

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


if __name__ == "__main__":
    uvicorn.run(
        "backend.services.api_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        log_level=settings.log_level.lower()
    )

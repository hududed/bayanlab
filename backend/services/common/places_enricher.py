"""
Places Enricher - Unified utility for validating/enriching entity data via Google Places API (New).

Consolidates enrichment logic used by:
- Halal eateries (scripts/enrich_halal_eateries.py)
- Halal markets (scripts/enrich_halal_markets.py)
- Masajid (scripts/enrich_masajid.py)
- Future entity types

Pattern:
1. Search Google Places API (New) by name + location
2. Parse address components into structured fields
3. Extract phone, website, rating, lat/lng
4. Fallback to OSM for geocoding if Google fails (optional)

Usage:
    from backend.services.common.places_enricher import PlacesEnricher

    enricher = PlacesEnricher(api_key="...")
    result = enricher.enrich("Islamic Center of Fort Collins", city="Fort Collins", state="CO")
    # Returns: EnrichmentResult with validated address, lat/lng, phone, etc.
"""
import os
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable

import httpx
from dotenv import load_dotenv

# Load .env if running standalone
load_dotenv()


@dataclass
class ParsedAddress:
    """Structured address components from Google Places."""
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    full: Optional[str] = None


@dataclass
class EnrichmentResult:
    """Result of enriching an entity via Places API."""
    # Status
    status: str = "not_found"  # success, partial, not_found, error
    source: str = "unknown"  # google_places_new, osm

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Address
    address: ParsedAddress = field(default_factory=ParsedAddress)

    # Contact
    phone: Optional[str] = None
    website: Optional[str] = None

    # Google-specific
    google_place_id: Optional[str] = None
    google_name: Optional[str] = None
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None
    google_maps_uri: Optional[str] = None

    # Error details
    error: Optional[str] = None


class PlacesEnricher:
    """
    Unified enricher using Google Places API (New) with optional OSM fallback.

    Supports entity-specific search query building via query_builder callback.
    """

    GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
    OSM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"

    # Default field mask for Google Places API
    DEFAULT_FIELD_MASK = ",".join([
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.addressComponents",
        "places.location",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.googleMapsUri",
    ])

    # Colorado bounding box for location bias
    COLORADO_BBOX = {
        "rectangle": {
            "low": {"latitude": 36.9, "longitude": -109.1},   # SW Colorado
            "high": {"latitude": 41.1, "longitude": -102.0}   # NE Colorado
        }
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        use_osm_fallback: bool = True,
        location_bias: Optional[Dict] = None,
        rate_limit_ms: int = 200,
    ):
        """
        Initialize the enricher.

        Args:
            api_key: Google Places API key (falls back to GOOGLE_PLACES_API_KEY env var)
            use_osm_fallback: Whether to fall back to OSM if Google fails
            location_bias: Custom location bias for Google search (defaults to Colorado bbox)
            rate_limit_ms: Milliseconds between API calls (default 200ms = 5 req/sec)
        """
        self.api_key = api_key or os.getenv("GOOGLE_PLACES_API_KEY")
        self.use_osm_fallback = use_osm_fallback
        self.location_bias = location_bias or self.COLORADO_BBOX
        self.rate_limit_ms = rate_limit_ms
        self._last_call_time = 0

    def _rate_limit(self, source: str = "google"):
        """Enforce rate limiting between API calls."""
        elapsed = (time.time() - self._last_call_time) * 1000
        wait_time = self.rate_limit_ms if source == "google" else 1100  # OSM requires 1 req/sec

        if elapsed < wait_time:
            time.sleep((wait_time - elapsed) / 1000)

        self._last_call_time = time.time()

    def enrich(
        self,
        name: str,
        city: str,
        state: str = "CO",
        query_suffix: str = "",
        osm_only: bool = False,
    ) -> EnrichmentResult:
        """
        Enrich an entity by searching Google Places (New) and extracting data.

        Args:
            name: Entity name (e.g., "Islamic Center of Fort Collins")
            city: City name
            state: State code (default: CO)
            query_suffix: Additional text to append to search query (e.g., "mosque", "halal restaurant")
            osm_only: Skip Google and use OSM only (free, geocoding only)

        Returns:
            EnrichmentResult with enriched data or error status
        """
        # Try Google first (unless osm_only)
        if not osm_only and self.api_key:
            result = self._search_google(name, city, state, query_suffix)
            if result.status == "success":
                return result

        # Fallback to OSM
        if self.use_osm_fallback or osm_only:
            return self._search_osm(name, city, state)

        return EnrichmentResult(status="not_found", error="Google failed, OSM fallback disabled")

    def _search_google(self, name: str, city: str, state: str, query_suffix: str) -> EnrichmentResult:
        """Search using Google Places API (New)."""
        self._rate_limit("google")

        query = f"{name} {city} {state}"
        if query_suffix:
            query = f"{query} {query_suffix}"

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": self.DEFAULT_FIELD_MASK,
        }

        payload = {
            "textQuery": query,
            "maxResultCount": 1,
            "locationBias": self.location_bias,
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self.GOOGLE_TEXT_SEARCH_URL, headers=headers, json=payload)

                if response.status_code != 200:
                    return EnrichmentResult(
                        status="error",
                        source="google_places_new",
                        error=f"HTTP {response.status_code}: {response.text[:100]}"
                    )

                data = response.json()

                if not data.get("places"):
                    return EnrichmentResult(status="not_found", source="google_places_new")

                place = data["places"][0]
                return self._parse_google_result(place)

        except Exception as e:
            return EnrichmentResult(status="error", source="google_places_new", error=str(e))

    def _parse_google_result(self, place: Dict) -> EnrichmentResult:
        """Parse a Google Places API result into EnrichmentResult."""
        address = self._parse_address_components(place.get("addressComponents", []))
        address.full = place.get("formattedAddress")

        location = place.get("location", {})

        return EnrichmentResult(
            status="success",
            source="google_places_new",
            latitude=location.get("latitude"),
            longitude=location.get("longitude"),
            address=address,
            phone=place.get("nationalPhoneNumber"),
            website=place.get("websiteUri"),
            google_place_id=place.get("id"),
            google_name=place.get("displayName", {}).get("text"),
            google_rating=place.get("rating"),
            google_review_count=place.get("userRatingCount"),
            google_maps_uri=place.get("googleMapsUri"),
        )

    def _parse_address_components(self, components: List[Dict]) -> ParsedAddress:
        """Parse Google address_components into structured address."""
        street_number = None
        route = None
        city = None
        state = None
        zip_code = None

        for comp in components:
            types = comp.get("types", [])
            text = comp.get("longText", "")
            short_text = comp.get("shortText", "")

            if "street_number" in types:
                street_number = text
            elif "route" in types:
                route = text
            elif "locality" in types:
                city = text
            elif "administrative_area_level_1" in types:
                state = short_text  # CO not Colorado
            elif "postal_code" in types:
                zip_code = text

        # Build street address
        street = None
        if street_number and route:
            street = f"{street_number} {route}"
        elif route:
            street = route

        return ParsedAddress(street=street, city=city, state=state, zip=zip_code)

    def _search_osm(self, name: str, city: str, state: str) -> EnrichmentResult:
        """Search using OpenStreetMap Nominatim (free, geocoding only)."""
        self._rate_limit("osm")

        query = f"{name}, {city}, {state}, USA"

        params = {
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        }

        headers = {"User-Agent": "BayanLab/1.0 (places-enricher)"}

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.OSM_SEARCH_URL, params=params, headers=headers)

                if response.status_code != 200:
                    return EnrichmentResult(
                        status="error",
                        source="osm",
                        error=f"HTTP {response.status_code}"
                    )

                data = response.json()

                if not data:
                    return EnrichmentResult(status="not_found", source="osm")

                result = data[0]
                osm_address = result.get("address", {})

                # Build street address
                house_number = osm_address.get("house_number", "")
                road = osm_address.get("road", "")
                street = f"{house_number} {road}".strip() if house_number or road else None

                address = ParsedAddress(
                    street=street,
                    city=osm_address.get("city") or osm_address.get("town") or osm_address.get("village"),
                    state=osm_address.get("state"),
                    zip=osm_address.get("postcode"),
                    full=result.get("display_name"),
                )

                return EnrichmentResult(
                    status="success",
                    source="osm",
                    latitude=float(result.get("lat")),
                    longitude=float(result.get("lon")),
                    address=address,
                    # OSM doesn't have phone/website/rating
                )

        except Exception as e:
            return EnrichmentResult(status="error", source="osm", error=str(e))


# Convenience function for scripts
def get_places_enricher(
    api_key: Optional[str] = None,
    use_osm_fallback: bool = True,
) -> PlacesEnricher:
    """
    Factory function to get a PlacesEnricher.

    Uses GOOGLE_PLACES_API_KEY from environment if api_key not provided.
    """
    return PlacesEnricher(api_key=api_key, use_osm_fallback=use_osm_fallback)

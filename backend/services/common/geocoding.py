"""
Geocoding service with provider abstraction

Easy migration path:
- Default: OpenStreetMap (FREE, no API key)
- Optional: Google Geocoding API (best accuracy, requires billing)
- Switch via GEOCODING_PROVIDER env var
"""
import os
import httpx
from typing import Optional, Tuple
from .logger import get_logger

logger = get_logger("geocoding")


class GeocodingProvider:
    """Base class for geocoding providers"""

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        """Returns (latitude, longitude) or None"""
        raise NotImplementedError


class OpenStreetMapGeocoder(GeocodingProvider):
    """
    OpenStreetMap Nominatim geocoding (FREE)
    - No API key required
    - Rate limit: 1 request/second
    - Accuracy: Within 10-50m of Google for US addresses
    """

    def __init__(self, user_agent: str = "BayanLab/1.0"):
        self.user_agent = user_agent
        self.url = "https://nominatim.openstreetmap.org/search"

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": self.user_agent
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.url,
                    params=params,
                    headers=headers,
                    timeout=10.0
                )
                data = response.json()

                if len(data) > 0:
                    result = data[0]
                    lat = float(result["lat"])
                    lng = float(result["lon"])
                    logger.info(f"OSM geocoded: {address} → ({lat}, {lng})")
                    return (lat, lng)

                logger.warning(f"OSM: No results for {address}")
                return None

            except Exception as e:
                logger.error(f"OSM geocoding failed for {address}: {e}")
                return None


class GoogleGeocoder(GeocodingProvider):
    """
    Google Geocoding API (requires billing)
    - Best accuracy
    - Rate limit: 50 requests/second
    - Cost: $5 per 1,000 requests
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://maps.googleapis.com/maps/api/geocode/json"

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        params = {
            "address": address,
            "key": self.api_key
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.url,
                    params=params,
                    timeout=10.0
                )
                data = response.json()

                if data.get("status") == "OK" and len(data.get("results", [])) > 0:
                    location = data["results"][0]["geometry"]["location"]
                    lat = location["lat"]
                    lng = location["lng"]
                    logger.info(f"Google geocoded: {address} → ({lat}, {lng})")
                    return (lat, lng)

                logger.warning(f"Google: {data.get('status')} for {address}")
                return None

            except Exception as e:
                logger.error(f"Google geocoding failed for {address}: {e}")
                return None


class HybridGeocoder(GeocodingProvider):
    """
    Try Google first (if available), fallback to OSM
    Best of both worlds: accuracy + reliability
    """

    def __init__(self, google_api_key: Optional[str] = None, user_agent: str = "BayanLab/1.0"):
        self.google = GoogleGeocoder(google_api_key) if google_api_key else None
        self.osm = OpenStreetMapGeocoder(user_agent)

    async def geocode(self, address: str) -> Optional[Tuple[float, float]]:
        # Try Google first (best accuracy)
        if self.google:
            result = await self.google.geocode(address)
            if result:
                return result
            logger.info(f"Google failed for {address}, trying OSM...")

        # Fallback to OSM (free + reliable)
        return await self.osm.geocode(address)


def get_geocoder() -> GeocodingProvider:
    """
    Factory function to get geocoder based on environment

    Environment variables:
    - GEOCODING_PROVIDER: "osm", "google", or "hybrid" (default: "osm")
    - GOOGLE_GEOCODING_API_KEY: Required for "google" or "hybrid"
    - GEOCODER_USER_AGENT: Custom user agent for OSM

    Migration path:
    1. Default: OSM (FREE)
    2. When ready: Set GEOCODING_PROVIDER=hybrid (tries Google, falls back to OSM)
    3. Later: Set GEOCODING_PROVIDER=google (Google only)
    """
    provider = os.getenv("GEOCODING_PROVIDER", "osm").lower()
    google_key = os.getenv("GOOGLE_GEOCODING_API_KEY") or os.getenv("GOOGLE_PLACES_API_KEY")
    user_agent = os.getenv("GEOCODER_USER_AGENT", "BayanLab/1.0")

    if provider == "google":
        if not google_key:
            logger.warning("GOOGLE_GEOCODING_API_KEY not set, falling back to OSM")
            return OpenStreetMapGeocoder(user_agent)
        logger.info("Using Google Geocoding API")
        return GoogleGeocoder(google_key)

    elif provider == "hybrid":
        logger.info("Using Hybrid geocoding (Google → OSM fallback)")
        return HybridGeocoder(google_key, user_agent)

    else:  # Default to OSM
        logger.info("Using OpenStreetMap geocoding (FREE)")
        return OpenStreetMapGeocoder(user_agent)

"""
Geocoder - fill missing coordinates using Nominatim
"""
import uuid
import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from ...common.logger import get_logger
from ...common.config import get_settings
from ...common.database import get_sync_session
from sqlalchemy import text

logger = get_logger("geocoder")


class Geocoder:
    """Geocode addresses to fill missing coordinates"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.settings = get_settings()
        self.geolocator = Nominatim(user_agent=self.settings.geocoder_user_agent)

    def geocode_address(self, street: str, city: str, state: str, zip_code: str = None) -> tuple:
        """Geocode an address to lat/lon"""
        # Build address string
        parts = [p for p in [street, city, state, zip_code] if p]
        address = ", ".join(parts)

        try:
            location = self.geolocator.geocode(address, timeout=10)
            if location:
                return location.latitude, location.longitude
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logger.warning(f"Geocoding failed for {address}: {e}")

        return None, None

    def geocode_events(self) -> int:
        """Geocode events missing coordinates"""
        logger.info("Geocoding events", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get events without coordinates
            result = session.execute(
                text("""
                SELECT event_id, address_street, address_city, address_state, address_zip
                FROM event_canonical
                WHERE latitude IS NULL OR longitude IS NULL
                LIMIT 100
                """)
            )

            count = 0
            for row in result:
                event_id, street, city, state, zip_code = row

                lat, lon = self.geocode_address(street, city, state, zip_code)

                if lat and lon:
                    session.execute(
                        text("""
                        UPDATE event_canonical
                        SET latitude = :lat, longitude = :lon,
                            geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            updated_at = NOW()
                        WHERE event_id = :id
                        """),
                        {'id': event_id, 'lat': lat, 'lon': lon}
                    )
                    count += 1

                # Rate limiting
                time.sleep(self.settings.geocoder_rate_limit)

            session.commit()

        logger.info(f"Geocoded {count} events", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': count
        })

        return count

    def geocode_businesses(self) -> int:
        """Geocode businesses missing coordinates"""
        logger.info("Geocoding businesses", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get businesses without coordinates
            result = session.execute(
                text("""
                SELECT business_id, address_street, address_city, address_state, address_zip
                FROM business_canonical
                WHERE latitude IS NULL OR longitude IS NULL
                LIMIT 100
                """)
            )

            count = 0
            for row in result:
                business_id, street, city, state, zip_code = row

                lat, lon = self.geocode_address(street, city, state, zip_code)

                if lat and lon:
                    session.execute(
                        text("""
                        UPDATE business_canonical
                        SET latitude = :lat, longitude = :lon,
                            geom = ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            updated_at = NOW()
                        WHERE business_id = :id
                        """),
                        {'id': business_id, 'lat': lat, 'lon': lon}
                    )
                    count += 1

                # Rate limiting
                time.sleep(self.settings.geocoder_rate_limit)

            session.commit()

        logger.info(f"Geocoded {count} businesses", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': count
        })

        return count

    def run(self) -> tuple[int, int]:
        """Run geocoder for both events and businesses"""
        logger.info("Starting geocoder", extra={'ingest_run_id': self.ingest_run_id})

        events_count = self.geocode_events()
        businesses_count = self.geocode_businesses()

        logger.info("Geocoder completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'events': events_count,
            'businesses': businesses_count
        })

        return events_count, businesses_count


if __name__ == "__main__":
    geocoder = Geocoder()
    geocoder.run()

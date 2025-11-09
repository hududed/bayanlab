"""
Normalizer - convert staging data to canonical format
"""
import uuid
import json
from datetime import datetime
from typing import Dict, Any
from ...common.logger import get_logger
from ...common.database import get_sync_session
from ...common.config import get_region_timezone
import pytz
from sqlalchemy import text
logger = get_logger("normalizer")


class Normalizer:
    """Normalize staging data to canonical format"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()

    def normalize_events(self) -> int:
        """Normalize events from staging to canonical"""
        logger.info("Normalizing events", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get unprocessed staging events
            result = session.execute(
                text("""
                SELECT staging_id, raw_payload
                FROM staging_events
                WHERE ingest_run_id = :ingest_run_id AND processed = false
                """),
                {'ingest_run_id': str(self.ingest_run_id)}
            )

            count = 0
            for row in result:
                staging_id, raw_payload = row
                try:
                    # Parse JSON payload
                    if isinstance(raw_payload, str):
                        payload = json.loads(raw_payload)
                    else:
                        payload = raw_payload

                    # Insert into canonical
                    session.execute(
                        text("""
                        INSERT INTO event_canonical (
                            event_id, title, description, start_time, end_time, all_day,
                            venue_name, address_street, address_city, address_state, address_zip,
                            latitude, longitude, geom, url, organizer_name, organizer_contact,
                            source, source_ref, region, updated_at
                        ) VALUES (
                            gen_random_uuid(), :title, :description, :start_time, :end_time, :all_day,
                            :venue_name, :address_street, :address_city, :address_state, :address_zip,
                            :latitude, :longitude,
                            CASE WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                                THEN ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                                ELSE NULL END,
                            :url, :organizer_name, :organizer_contact,
                            :source, :source_ref, :region, NOW()
                        )
                        ON CONFLICT (event_id) DO UPDATE SET
                            title = EXCLUDED.title,
                            description = EXCLUDED.description,
                            updated_at = NOW()
                        """),
                        {
                            'title': payload.get('title'),
                            'description': payload.get('description'),
                            'start_time': payload.get('start_time'),
                            'end_time': payload.get('end_time'),
                            'all_day': payload.get('all_day', False),
                            'venue_name': payload.get('venue_name'),
                            'address_street': payload.get('address_street'),
                            'address_city': payload.get('address_city'),
                            'address_state': payload.get('address_state', 'CO'),
                            'address_zip': payload.get('address_zip'),
                            'latitude': payload.get('latitude'),
                            'longitude': payload.get('longitude'),
                            'url': payload.get('url'),
                            'organizer_name': payload.get('organizer_name'),
                            'organizer_contact': payload.get('organizer_contact'),
                            'source': payload.get('source', 'csv'),
                            'source_ref': payload.get('source_ref'),
                            'region': payload.get('region', 'CO'),
                        }
                    )

                    # Mark as processed
                    session.execute(
                        text("UPDATE staging_events SET processed = true WHERE staging_id = :id"),
                        {'id': staging_id}
                    )

                    count += 1

                except Exception as e:
                    logger.error(f"Failed to normalize event {staging_id}: {e}")
                    session.execute(
                        text("UPDATE staging_events SET error_message = :error WHERE staging_id = :id"),
                        {'id': staging_id, 'error': str(e)}
                    )

            session.commit()

        logger.info(f"Normalized {count} events", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': count
        })

        return count

    def normalize_businesses(self) -> int:
        """Normalize businesses from staging to canonical"""
        logger.info("Normalizing businesses", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get unprocessed staging businesses
            result = session.execute(
                text("""
                SELECT staging_id, raw_payload
                FROM staging_businesses
                WHERE ingest_run_id = :ingest_run_id AND processed = false
                """),
                {'ingest_run_id': str(self.ingest_run_id)}
            )

            count = 0
            for row in result:
                staging_id, raw_payload = row
                try:
                    # Parse JSON payload
                    if isinstance(raw_payload, str):
                        payload = json.loads(raw_payload)
                    else:
                        payload = raw_payload

                    # Insert into canonical
                    session.execute(
                        text("""
                        INSERT INTO business_canonical (
                            business_id, name, category,
                            address_street, address_city, address_state, address_zip,
                            latitude, longitude, geom, website, phone, email,
                            self_identified_muslim_owned, halal_certified, certifier_name, certifier_ref,
                            placekey, source, source_ref, region, updated_at
                        ) VALUES (
                            gen_random_uuid(), :name, :category,
                            :address_street, :address_city, :address_state, :address_zip,
                            :latitude, :longitude,
                            CASE WHEN :latitude IS NOT NULL AND :longitude IS NOT NULL
                                THEN ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography
                                ELSE NULL END,
                            :website, :phone, :email,
                            :self_identified_muslim_owned, :halal_certified, :certifier_name, :certifier_ref,
                            :placekey, :source, :source_ref, :region, NOW()
                        )
                        ON CONFLICT (business_id) DO UPDATE SET
                            name = EXCLUDED.name,
                            category = EXCLUDED.category,
                            updated_at = NOW()
                        """),
                        {
                            'name': payload.get('name'),
                            'category': payload.get('category', 'other'),
                            'address_street': payload.get('address_street'),
                            'address_city': payload.get('address_city'),
                            'address_state': payload.get('address_state', 'CO'),
                            'address_zip': payload.get('address_zip'),
                            'latitude': payload.get('latitude'),
                            'longitude': payload.get('longitude'),
                            'website': payload.get('website'),
                            'phone': payload.get('phone'),
                            'email': payload.get('email'),
                            'self_identified_muslim_owned': payload.get('self_identified_muslim_owned', False),
                            'halal_certified': payload.get('halal_certified', False),
                            'certifier_name': payload.get('certifier_name'),
                            'certifier_ref': payload.get('certifier_ref'),
                            'placekey': payload.get('placekey'),
                            'source': payload.get('source', 'csv'),
                            'source_ref': payload.get('source_ref'),
                            'region': payload.get('region', 'CO'),
                        }
                    )

                    # Mark as processed
                    session.execute(
                        text("UPDATE staging_businesses SET processed = true WHERE staging_id = :id"),
                        {'id': staging_id}
                    )

                    count += 1

                except Exception as e:
                    logger.error(f"Failed to normalize business {staging_id}: {e}")
                    session.execute(
                        text("UPDATE staging_businesses SET error_message = :error WHERE staging_id = :id"),
                        {'id': staging_id, 'error': str(e)}
                    )

            session.commit()

        logger.info(f"Normalized {count} businesses", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': count
        })

        return count

    def run(self) -> tuple[int, int]:
        """Run normalizer for both events and businesses"""
        logger.info("Starting normalizer", extra={'ingest_run_id': self.ingest_run_id})

        events_count = self.normalize_events()
        businesses_count = self.normalize_businesses()

        logger.info("Normalizer completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'events': events_count,
            'businesses': businesses_count
        })

        return events_count, businesses_count


if __name__ == "__main__":
    normalizer = Normalizer()
    normalizer.run()

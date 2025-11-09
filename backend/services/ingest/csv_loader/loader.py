"""
CSV loader for events and businesses
"""
import csv
import uuid
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from ...common.logger import get_logger
from ...common.config import get_settings, get_sources_config
from ...common.database import get_sync_session
from sqlalchemy import text
logger = get_logger("csv_loader")


class CSVLoader:
    """Load events and businesses from CSV files"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.settings = get_settings()
        self.sources_config = get_sources_config()

    def load_events_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """Load events from CSV file"""
        events = []
        full_path = self.settings.seed_dir / csv_path

        if not full_path.exists():
            logger.warning(f"CSV file not found: {full_path}")
            return events

        with open(full_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                event = {
                    'title': row.get('title', '').strip(),
                    'description': row.get('description', '').strip() or None,
                    'start_time': row.get('start_time', '').strip(),
                    'end_time': row.get('end_time', '').strip(),
                    'all_day': row.get('all_day', 'false').lower() == 'true',
                    'venue_name': row.get('venue_name', '').strip(),
                    'address_street': row.get('address_street', '').strip() or None,
                    'address_city': row.get('address_city', '').strip(),
                    'address_state': row.get('address_state', 'CO').strip(),
                    'address_zip': row.get('address_zip', '').strip() or None,
                    'latitude': float(row['latitude']) if row.get('latitude') else None,
                    'longitude': float(row['longitude']) if row.get('longitude') else None,
                    'url': row.get('url', '').strip() or None,
                    'organizer_name': row.get('organizer_name', '').strip() or None,
                    'organizer_contact': row.get('organizer_contact', '').strip() or None,
                    'source': 'csv',
                    'source_ref': row.get('id', '') or f"csv_{len(events)}",
                }
                events.append(event)

        return events

    def load_businesses_csv(self, csv_path: str) -> List[Dict[str, Any]]:
        """Load businesses from CSV file"""
        businesses = []
        full_path = self.settings.seed_dir / csv_path

        if not full_path.exists():
            logger.warning(f"CSV file not found: {full_path}")
            return businesses

        with open(full_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                business = {
                    'name': (row.get('name') or '').strip(),
                    'category': (row.get('category') or 'other').strip(),
                    'address_street': (row.get('address_street') or '').strip() or None,
                    'address_city': (row.get('address_city') or '').strip(),
                    'address_state': (row.get('address_state') or 'CO').strip(),
                    'address_zip': (row.get('address_zip') or '').strip() or None,
                    'latitude': float(row['latitude']) if row.get('latitude') else None,
                    'longitude': float(row['longitude']) if row.get('longitude') else None,
                    'website': (row.get('website') or '').strip() or None,
                    'phone': (row.get('phone') or '').strip() or None,
                    'email': (row.get('email') or '').strip() or None,
                    'self_identified_muslim_owned': (row.get('self_identified_muslim_owned') or 'false').lower() == 'true',
                    'halal_certified': (row.get('halal_certified') or 'false').lower() == 'true',
                    'certifier_name': (row.get('certifier_name') or '').strip() or None,
                    'certifier_ref': (row.get('certifier_ref') or '').strip() or None,
                    'source': 'csv',
                    'source_ref': (row.get('id') or f"csv_{len(businesses)}"),
                }
                businesses.append(business)

        return businesses

    def ingest_events(self) -> int:
        """Ingest all events from CSV sources"""
        logger.info("Ingesting events from CSV", extra={'ingest_run_id': self.ingest_run_id})

        sources = self.sources_config.get('csv_sources', {}).get('events', [])
        total_events = 0

        for source in sources:
            if not source.get('enabled', True):
                continue

            csv_path = source.get('path')
            events = self.load_events_csv(csv_path)

            # Insert into staging
            with get_sync_session() as session:
                for event_data in events:
                    query = text("""
                    INSERT INTO staging_events (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, 'csv', :source_ref, CAST(:raw_payload AS jsonb))
                    """)
                    session.execute(
                        query,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source_ref': event_data.get('source_ref'),
                            'raw_payload': json.dumps(event_data)
                        }
                    )

            total_events += len(events)
            logger.info(f"Loaded {len(events)} events from {csv_path}")

        logger.info(f"CSV events ingestion completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': total_events
        })

        return total_events

    def ingest_businesses(self) -> int:
        """Ingest all businesses from CSV sources"""
        logger.info("Ingesting businesses from CSV", extra={'ingest_run_id': self.ingest_run_id})

        sources = self.sources_config.get('csv_sources', {}).get('businesses', [])
        total_businesses = 0

        for source in sources:
            if not source.get('enabled', True):
                continue

            csv_path = source.get('path')
            businesses = self.load_businesses_csv(csv_path)

            # Insert into staging
            with get_sync_session() as session:
                for business_data in businesses:
                    query = text("""
                    INSERT INTO staging_businesses (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, 'csv', :source_ref, CAST(:raw_payload AS jsonb))
                    """)
                    session.execute(
                        query,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source_ref': business_data.get('source_ref'),
                            'raw_payload': json.dumps(business_data)
                        }
                    )

            total_businesses += len(businesses)
            logger.info(f"Loaded {len(businesses)} businesses from {csv_path}")

        logger.info(f"CSV businesses ingestion completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': total_businesses
        })

        return total_businesses

    def run(self) -> tuple[int, int]:
        """Run CSV loader for both events and businesses"""
        logger.info("Starting CSV loader", extra={'ingest_run_id': self.ingest_run_id})

        events_count = self.ingest_events()
        businesses_count = self.ingest_businesses()

        logger.info("CSV loader completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'events': events_count,
            'businesses': businesses_count
        })

        return events_count, businesses_count


if __name__ == "__main__":
    loader = CSVLoader()
    loader.run()

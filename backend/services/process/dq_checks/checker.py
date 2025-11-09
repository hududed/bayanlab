"""
Data Quality Checker - validate data against DQ rules
"""
import uuid
import sys
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from ...common.logger import get_logger
from ...common.config import get_dq_rules_config, get_region_bbox
from ...common.database import get_sync_session
from sqlalchemy import text

logger = get_logger("dq_checks")


class DQChecker:
    """Data quality checker"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.dq_config = get_dq_rules_config()
        self.errors = []
        self.warnings = []

    def check_bbox(self, lat: float, lon: float, region: str) -> bool:
        """Check if coordinates are inside region bounding box"""
        try:
            bbox = get_region_bbox(region)
            return (bbox['west'] <= lon <= bbox['east'] and
                    bbox['south'] <= lat <= bbox['north'])
        except Exception:
            return True  # Skip check if bbox not configured

    def check_events(self) -> bool:
        """Check event data quality"""
        logger.info("Checking event data quality", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get all events
            result = session.execute(
                text("SELECT event_id, title, start_time, end_time, address_city, address_state, latitude, longitude, region FROM event_canonical")
            )

            for row in result:
                event_id, title, start_time, end_time, city, state, lat, lon, region = row

                # Required fields
                if not title or not city or not state:
                    self.errors.append(f"Event {event_id}: Missing required fields")

                # Times
                if start_time and end_time:
                    if start_time >= end_time:
                        self.errors.append(f"Event {event_id}: start_time >= end_time")

                    # Check not too old
                    if start_time < datetime.now(timezone.utc) - timedelta(days=30):
                        self.warnings.append(f"Event {event_id}: Event is more than 30 days old")

                # Region/state check
                if region != state:
                    # For V1, region should match state for CO
                    if region == 'CO' and state != 'CO':
                        self.errors.append(f"Event {event_id}: Region/state mismatch")

                # Coordinates bounds check
                if lat and lon:
                    if not self.check_bbox(lat, lon, region):
                        self.errors.append(f"Event {event_id}: Coordinates outside region bbox")

        logger.info(f"Event DQ checks: {len(self.errors)} errors, {len(self.warnings)} warnings")
        return len(self.errors) == 0

    def check_businesses(self) -> bool:
        """Check business data quality"""
        logger.info("Checking business data quality", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Get all businesses
            result = session.execute(
                text("SELECT business_id, name, category, address_city, address_state, latitude, longitude, region, phone, website FROM business_canonical")
            )

            for row in result:
                business_id, name, category, city, state, lat, lon, region, phone, website = row

                # Required fields
                if not name or not category or not city or not state:
                    self.errors.append(f"Business {business_id}: Missing required fields")

                # Category validation
                valid_categories = ['restaurant', 'service', 'retail', 'grocery', 'butcher', 'other']
                if category not in valid_categories:
                    self.errors.append(f"Business {business_id}: Invalid category {category}")

                # Region/state check
                if region != state:
                    if region == 'CO' and state != 'CO':
                        self.errors.append(f"Business {business_id}: Region/state mismatch")

                # Coordinates bounds check
                if lat and lon:
                    if not self.check_bbox(lat, lon, region):
                        self.errors.append(f"Business {business_id}: Coordinates outside region bbox")

                # Phone format (basic check)
                if phone:
                    phone_pattern = r'^\+?1?[-.]?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})$'
                    if not re.match(phone_pattern, phone.replace(' ', '')):
                        self.warnings.append(f"Business {business_id}: Invalid phone format")

        logger.info(f"Business DQ checks: {len(self.errors)} errors, {len(self.warnings)} warnings")
        return len(self.errors) == 0

    def check_duplicates(self) -> bool:
        """Check for duplicate IDs"""
        logger.info("Checking for duplicates", extra={'ingest_run_id': self.ingest_run_id})

        with get_sync_session() as session:
            # Check duplicate event IDs
            result = session.execute(
                text("""
                SELECT event_id, COUNT(*)
                FROM event_canonical
                GROUP BY event_id
                HAVING COUNT(*) > 1
                """)
            )

            for row in result:
                event_id, count = row
                self.errors.append(f"Duplicate event_id: {event_id} ({count} occurrences)")

            # Check duplicate business IDs
            result = session.execute(
                text("""
                SELECT business_id, COUNT(*)
                FROM business_canonical
                GROUP BY business_id
                HAVING COUNT(*) > 1
                """)
            )

            for row in result:
                business_id, count = row
                self.errors.append(f"Duplicate business_id: {business_id} ({count} occurrences)")

        return len(self.errors) == 0

    def run(self) -> bool:
        """Run all DQ checks"""
        logger.info("Starting DQ checks", extra={'ingest_run_id': self.ingest_run_id})

        events_ok = self.check_events()
        businesses_ok = self.check_businesses()
        no_dupes = self.check_duplicates()

        all_ok = events_ok and businesses_ok and no_dupes

        # Log results
        if self.errors:
            for error in self.errors:
                logger.error(error, extra={'ingest_run_id': self.ingest_run_id})

        if self.warnings:
            for warning in self.warnings:
                logger.warning(warning, extra={'ingest_run_id': self.ingest_run_id})

        # Check if we should fail
        fail_on_error = self.dq_config.get('pipeline', {}).get('fail_on_error', True)
        fail_on_warning = self.dq_config.get('pipeline', {}).get('fail_on_warning', False)

        should_fail = (fail_on_error and len(self.errors) > 0) or (fail_on_warning and len(self.warnings) > 0)

        logger.info(f"DQ checks completed: {len(self.errors)} errors, {len(self.warnings)} warnings", extra={
            'ingest_run_id': self.ingest_run_id,
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'passed': not should_fail
        })

        if should_fail:
            sys.exit(1)

        return not should_fail


if __name__ == "__main__":
    checker = DQChecker()
    success = checker.run()
    sys.exit(0 if success else 1)

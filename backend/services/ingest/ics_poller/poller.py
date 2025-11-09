"""
ICS/iCalendar poller for event ingestion
"""
import httpx
import uuid
from datetime import datetime, timezone
from icalendar import Calendar
from typing import List, Dict, Any
from ...common.logger import get_logger
from ...common.config import get_sources_config
from ...common.database import get_sync_session

logger = get_logger("ics_poller")


class ICSPoller:
    """Poll ICS feeds and ingest events"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.sources_config = get_sources_config()

    def fetch_ics(self, url: str) -> str:
        """Fetch ICS content from URL"""
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch ICS from {url}: {e}")
            raise

    def parse_ics(self, ics_content: str, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse ICS content and extract events"""
        events = []

        try:
            cal = Calendar.from_ical(ics_content)

            for component in cal.walk('VEVENT'):
                try:
                    event = self._extract_event(component, source_info)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to parse event: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to parse ICS calendar: {e}")
            raise

        return events

    def _extract_event(self, component, source_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract event data from iCalendar component"""
        # Get basic fields
        uid = str(component.get('UID', ''))
        summary = str(component.get('SUMMARY', ''))
        description = str(component.get('DESCRIPTION', '')) if component.get('DESCRIPTION') else None

        # Parse dates
        dtstart = component.get('DTSTART')
        dtend = component.get('DTEND')

        if not dtstart:
            return None

        start_dt = dtstart.dt
        end_dt = dtend.dt if dtend else start_dt

        # Check if all-day event
        all_day = not hasattr(start_dt, 'hour')

        # Convert to datetime with timezone
        if all_day:
            start_dt = datetime.combine(start_dt, datetime.min.time()).replace(tzinfo=timezone.utc)
            end_dt = datetime.combine(end_dt, datetime.min.time()).replace(tzinfo=timezone.utc)
        elif start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)
            end_dt = end_dt.replace(tzinfo=timezone.utc)

        # Get location
        location = str(component.get('LOCATION', '')) if component.get('LOCATION') else None
        url_str = str(component.get('URL', '')) if component.get('URL') else None

        # Build raw payload
        raw_payload = {
            'title': summary,
            'description': description,
            'start_time': start_dt.isoformat(),
            'end_time': end_dt.isoformat(),
            'all_day': all_day,
            'venue_name': source_info.get('venue_name', ''),
            'address_city': source_info.get('city', ''),
            'address_state': 'CO',  # Default for V1
            'location': location,
            'url': url_str,
            'source': 'ics',
            'source_ref': uid,
        }

        return raw_payload

    def ingest_source(self, source: Dict[str, Any]) -> int:
        """Ingest events from a single ICS source"""
        source_id = source.get('id')
        url = source.get('url')

        logger.info(f"Ingesting ICS source: {source_id}", extra={
            'ingest_run_id': self.ingest_run_id,
            'source_id': source_id
        })

        try:
            # Fetch and parse
            ics_content = self.fetch_ics(url)
            events = self.parse_ics(ics_content, source)

            # Insert into staging
            with get_sync_session() as session:
                for event_data in events:
                    query = """
                    INSERT INTO staging_events (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, 'ics', :source_ref, :raw_payload)
                    """
                    session.execute(
                        query,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source_ref': event_data.get('source_ref'),
                            'raw_payload': event_data
                        }
                    )

            logger.info(f"Ingested {len(events)} events from {source_id}", extra={
                'ingest_run_id': self.ingest_run_id,
                'count_in': len(events)
            })

            return len(events)

        except Exception as e:
            logger.error(f"Failed to ingest source {source_id}: {e}", extra={
                'ingest_run_id': self.ingest_run_id,
                'errors': str(e)
            })
            raise

    def run(self) -> int:
        """Run ICS poller for all enabled sources"""
        logger.info("Starting ICS poller", extra={'ingest_run_id': self.ingest_run_id})

        sources = self.sources_config.get('ics_sources', [])
        enabled_sources = [s for s in sources if s.get('enabled', True)]

        total_events = 0
        for source in enabled_sources:
            try:
                count = self.ingest_source(source)
                total_events += count
            except Exception as e:
                logger.error(f"Source {source.get('id')} failed: {e}")
                continue

        logger.info(f"ICS poller completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': total_events
        })

        return total_events


if __name__ == "__main__":
    poller = ICSPoller()
    poller.run()

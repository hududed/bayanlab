"""
ICS/iCalendar poller for event ingestion
Supports both ICS URLs and Google Calendar API
"""
import httpx
import uuid
import os
import json
from datetime import datetime, timezone
from icalendar import Calendar
from typing import List, Dict, Any, Optional
from pathlib import Path
from sqlalchemy import text
from ...common.logger import get_logger
from ...common.config import get_sources_config
from ...common.database import get_sync_session

# Google Calendar API imports (optional)
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

logger = get_logger("ics_poller")


class ICSPoller:
    """Poll ICS feeds and ingest events (ICS URLs or Google Calendar API)"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.sources_config = get_sources_config()
        self.calendar_service = None

        # Initialize Google Calendar API if credentials available
        if GOOGLE_API_AVAILABLE:
            self._init_calendar_service()

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

    def _init_calendar_service(self):
        """Initialize Google Calendar API service with service account credentials"""
        try:
            creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
            if not creds_path or not Path(creds_path).exists():
                logger.warning("Google Calendar credentials not found, API access disabled")
                return

            credentials = service_account.Credentials.from_service_account_file(
                creds_path,
                scopes=['https://www.googleapis.com/auth/calendar.readonly']
            )

            self.calendar_service = build('calendar', 'v3', credentials=credentials)
            logger.info("Google Calendar API initialized successfully")

        except Exception as e:
            logger.warning(f"Failed to initialize Google Calendar API: {e}")
            self.calendar_service = None

    def fetch_calendar_api(self, calendar_id: str, source_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch events from Google Calendar API"""
        if not self.calendar_service:
            raise Exception("Google Calendar API not initialized")

        events = []
        try:
            # Get events from now onwards (future events only)
            now = datetime.now(timezone.utc).isoformat()

            events_result = self.calendar_service.events().list(
                calendarId=calendar_id,
                timeMin=now,
                maxResults=250,  # Fetch up to 250 upcoming events
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            calendar_events = events_result.get('items', [])

            for event in calendar_events:
                try:
                    parsed_event = self._parse_calendar_api_event(event, source_info)
                    if parsed_event:
                        events.append(parsed_event)
                except Exception as e:
                    logger.warning(f"Failed to parse Calendar API event: {e}")
                    continue

            logger.info(f"Fetched {len(events)} events from Calendar API: {calendar_id}")

        except HttpError as e:
            logger.error(f"Google Calendar API error for {calendar_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to fetch from Calendar API {calendar_id}: {e}")
            raise

        return events

    def _parse_calendar_api_event(self, event: Dict[str, Any], source_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse event from Google Calendar API format"""
        # Event ID
        event_id = event.get('id', '')

        # Title and description
        summary = event.get('summary', 'Untitled Event')
        description = event.get('description')

        # Start and end times
        start = event.get('start', {})
        end = event.get('end', {})

        # Check if all-day event
        all_day = 'date' in start

        if all_day:
            # All-day event (date only)
            start_dt = datetime.fromisoformat(start['date']).replace(tzinfo=timezone.utc)
            end_dt = datetime.fromisoformat(end['date']).replace(tzinfo=timezone.utc)
        else:
            # Time-specific event
            start_dt = datetime.fromisoformat(start['dateTime'])
            end_dt = datetime.fromisoformat(end['dateTime'])

            # Ensure timezone aware
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

        # Location
        location = event.get('location')
        url_str = event.get('htmlLink')

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
            'source': 'ics',  # Use 'ics' for both Calendar API and ICS URL
            'source_ref': event_id,
        }

        return raw_payload

    def ingest_source(self, source: Dict[str, Any]) -> int:
        """Ingest events from a single source (ICS URL or Calendar API)"""
        source_id = source.get('id')
        url = source.get('url')
        calendar_id = source.get('calendar_id')

        logger.info(f"Ingesting source: {source_id}", extra={
            'ingest_run_id': self.ingest_run_id,
            'source_id': source_id
        })

        try:
            # Determine source type and fetch events
            if calendar_id and self.calendar_service:
                # Use Google Calendar API
                logger.info(f"Using Google Calendar API for {source_id}")
                events = self.fetch_calendar_api(calendar_id, source)
                source_type = 'ics'  # Use 'ics' for both (calendar events)
            elif url:
                # Fall back to ICS URL
                logger.info(f"Using ICS URL for {source_id}")
                ics_content = self.fetch_ics(url)
                events = self.parse_ics(ics_content, source)
                source_type = 'ics'
            else:
                raise ValueError(f"Source {source_id} has neither calendar_id nor url")

            # Insert into staging
            with get_sync_session() as session:
                for event_data in events:
                    query = text("""
                    INSERT INTO staging_events (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, :source, :source_ref, CAST(:raw_payload AS jsonb))
                    """)
                    session.execute(
                        query,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source': source_type,
                            'source_ref': event_data.get('source_ref'),
                            'raw_payload': json.dumps(event_data)
                        }
                    )
                session.commit()  # Explicitly commit

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

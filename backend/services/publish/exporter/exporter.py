"""
Exporter - export canonical data to static JSON files
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy import text
from ...common.logger import get_logger
from ...common.config import get_settings
from ...common.database import get_sync_session

logger = get_logger("exporter")


class Exporter:
    """Export canonical data to JSON files"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.settings = get_settings()

    def export_events(self, region: str = "CO") -> Dict[str, Any]:
        """Export events to JSON"""
        logger.info(f"Exporting events for region {region}", extra={
            'ingest_run_id': self.ingest_run_id,
            'region': region
        })

        with get_sync_session() as session:
            result = session.execute(
                text("""
                SELECT
                    event_id, title, description, start_time, end_time, all_day,
                    venue_name, address_street, address_city, address_state, address_zip,
                    latitude, longitude, url, organizer_name, organizer_contact,
                    source, source_ref, region, updated_at
                FROM event_canonical
                WHERE region = :region
                ORDER BY updated_at DESC, event_id
                """),
                {'region': region}
            )

            items = []
            for row in result:
                (event_id, title, description, start_time, end_time, all_day,
                 venue_name, address_street, address_city, address_state, address_zip,
                 latitude, longitude, url, organizer_name, organizer_contact,
                 source, source_ref, region, updated_at) = row

                item = {
                    "event_id": str(event_id),
                    "title": title,
                    "description": description,
                    "start_time": start_time.isoformat() if start_time else None,
                    "end_time": end_time.isoformat() if end_time else None,
                    "all_day": all_day,
                    "venue": {
                        "name": venue_name,
                        "address": {
                            "street": address_street,
                            "city": address_city,
                            "state": address_state,
                            "zip": address_zip
                        },
                        "latitude": float(latitude) if latitude else None,
                        "longitude": float(longitude) if longitude else None
                    },
                    "url": str(url) if url else None,
                    "organizer": {
                        "name": organizer_name,
                        "contact": organizer_contact
                    },
                    "source": source,
                    "source_ref": source_ref,
                    "region": region,
                    "updated_at": updated_at.isoformat() if updated_at else None
                }
                items.append(item)

        export_data = {
            "version": "1.0",
            "region": region,
            "count": len(items),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "items": items
        }

        # Write to file
        output_path = self.settings.exports_dir / f"{region}-events.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(items)} events to {output_path}", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': len(items),
            'region': region
        })

        return export_data

    def export_businesses(self, region: str = "CO") -> Dict[str, Any]:
        """Export businesses to JSON"""
        logger.info(f"Exporting businesses for region {region}", extra={
            'ingest_run_id': self.ingest_run_id,
            'region': region
        })

        with get_sync_session() as session:
            result = session.execute(
                text("""
                SELECT
                    business_id, name, category,
                    address_street, address_city, address_state, address_zip,
                    latitude, longitude, website, phone, email,
                    self_identified_muslim_owned, halal_certified, certifier_name, certifier_ref,
                    placekey, source, source_ref, region, updated_at
                FROM business_canonical
                WHERE region = :region
                ORDER BY updated_at DESC, business_id
                """),
                {'region': region}
            )

            items = []
            for row in result:
                (business_id, name, category,
                 address_street, address_city, address_state, address_zip,
                 latitude, longitude, website, phone, email,
                 self_identified_muslim_owned, halal_certified, certifier_name, certifier_ref,
                 placekey, source, source_ref, region, updated_at) = row

                item = {
                    "business_id": str(business_id),
                    "name": name,
                    "category": category,
                    "address": {
                        "street": address_street,
                        "city": address_city,
                        "state": address_state,
                        "zip": address_zip
                    },
                    "latitude": float(latitude) if latitude else None,
                    "longitude": float(longitude) if longitude else None,
                    "website": str(website) if website else None,
                    "phone": phone,
                    "email": email,
                    "self_identified_muslim_owned": self_identified_muslim_owned,
                    "halal_certified": halal_certified,
                    "certifier_name": certifier_name,
                    "certifier_ref": certifier_ref,
                    "placekey": placekey,
                    "source": source,
                    "source_ref": source_ref,
                    "region": region,
                    "updated_at": updated_at.isoformat() if updated_at else None
                }
                items.append(item)

        export_data = {
            "version": "1.0",
            "region": region,
            "count": len(items),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "items": items
        }

        # Write to file
        output_path = self.settings.exports_dir / f"{region}-businesses.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Exported {len(items)} businesses to {output_path}", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': len(items),
            'region': region
        })

        return export_data

    def run(self, region: str = "CO") -> tuple[int, int]:
        """Run exporter for both events and businesses"""
        logger.info("Starting exporter", extra={
            'ingest_run_id': self.ingest_run_id,
            'region': region
        })

        events_data = self.export_events(region)
        businesses_data = self.export_businesses(region)

        logger.info("Exporter completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'events': events_data['count'],
            'businesses': businesses_data['count'],
            'region': region
        })

        return events_data['count'], businesses_data['count']


if __name__ == "__main__":
    exporter = Exporter()
    exporter.run()

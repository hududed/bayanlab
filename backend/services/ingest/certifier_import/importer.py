"""
Halal certifier CSV importer
"""
import csv
import uuid
import json
from pathlib import Path
from typing import List, Dict, Any
from ...common.logger import get_logger
from ...common.config import get_settings, get_sources_config
from ...common.database import get_sync_session
from sqlalchemy import text
logger = get_logger("certifier_import")


class CertifierImporter:
    """Import halal-certified businesses from certifier CSVs"""

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.settings = get_settings()
        self.sources_config = get_sources_config()

    def load_certifier_csv(self, csv_path: str, certifier_name: str) -> List[Dict[str, Any]]:
        """Load businesses from certifier CSV file"""
        businesses = []
        full_path = self.settings.seed_dir / csv_path

        if not full_path.exists():
            logger.warning(f"Certifier CSV file not found: {full_path}")
            return businesses

        with open(full_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                business = {
                    'name': row.get('name', '').strip(),
                    'category': row.get('category', 'restaurant').strip(),
                    'address_street': row.get('address_street', '').strip() or None,
                    'address_city': row.get('address_city', '').strip(),
                    'address_state': row.get('address_state', 'CO').strip(),
                    'address_zip': row.get('address_zip', '').strip() or None,
                    'latitude': float(row['latitude']) if row.get('latitude') else None,
                    'longitude': float(row['longitude']) if row.get('longitude') else None,
                    'website': row.get('website', '').strip() or None,
                    'phone': row.get('phone', '').strip() or None,
                    'email': row.get('email', '').strip() or None,
                    'self_identified_muslim_owned': False,  # Unknown from certifier
                    'halal_certified': True,  # This is from a certifier
                    'certifier_name': certifier_name,
                    'certifier_ref': row.get('cert_id', '') or row.get('id', ''),
                    'source': 'certifier',
                    'source_ref': f"{certifier_name}_{row.get('cert_id', '')}",
                }
                businesses.append(business)

        return businesses

    def ingest_certifier(self, certifier_config: Dict[str, Any]) -> int:
        """Ingest businesses from a single certifier"""
        certifier_id = certifier_config.get('id')
        certifier_name = certifier_config.get('name')
        csv_path = certifier_config.get('path')

        logger.info(f"Ingesting certifier: {certifier_id}", extra={
            'ingest_run_id': self.ingest_run_id,
            'certifier_id': certifier_id
        })

        try:
            businesses = self.load_certifier_csv(csv_path, certifier_name)

            # Insert into staging
            with get_sync_session() as session:
                for business_data in businesses:
                    query = text("""
                    INSERT INTO staging_businesses (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, 'certifier', :source_ref, CAST(:raw_payload AS jsonb))
                    """)
                    session.execute(
                        query,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source_ref': business_data.get('source_ref'),
                            'raw_payload': json.dumps(business_data)
                        }
                    )

            logger.info(f"Ingested {len(businesses)} businesses from certifier {certifier_id}", extra={
                'ingest_run_id': self.ingest_run_id,
                'count_in': len(businesses)
            })

            return len(businesses)

        except Exception as e:
            logger.error(f"Failed to ingest certifier {certifier_id}: {e}", extra={
                'ingest_run_id': self.ingest_run_id,
                'errors': str(e)
            })
            raise

    def run(self) -> int:
        """Run certifier importer for all enabled certifiers"""
        logger.info("Starting certifier importer", extra={'ingest_run_id': self.ingest_run_id})

        certifiers = self.sources_config.get('certifier_feeds', [])
        enabled_certifiers = [c for c in certifiers if c.get('enabled', True)]

        total_businesses = 0
        for certifier in enabled_certifiers:
            try:
                count = self.ingest_certifier(certifier)
                total_businesses += count
            except Exception as e:
                logger.error(f"Certifier {certifier.get('id')} failed: {e}")
                continue

        logger.info(f"Certifier importer completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': total_businesses
        })

        return total_businesses


if __name__ == "__main__":
    importer = CertifierImporter()
    importer.run()

"""
OpenStreetMap Overpass API importer for businesses
"""
import httpx
import uuid
import json
from typing import List, Dict, Any
from ...common.logger import get_logger
from ...common.config import get_sources_config
from ...common.database import get_sync_session
from sqlalchemy import text
logger = get_logger("osm_import")


class OSMImporter:
    """Import businesses from OpenStreetMap via Overpass API"""

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, ingest_run_id: uuid.UUID = None):
        self.ingest_run_id = ingest_run_id or uuid.uuid4()
        self.sources_config = get_sources_config()

    def build_query(self, query_config: Dict[str, Any]) -> str:
        """Build Overpass QL query from config"""
        template = query_config.get('query_template', '')
        bbox = query_config.get('bbox', [])

        # Format bbox as south,west,north,east for Overpass
        bbox_str = f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"

        query = template.replace('{{bbox}}', bbox_str)
        return query

    def fetch_osm_data(self, query: str) -> Dict[str, Any]:
        """Fetch data from Overpass API"""
        try:
            response = httpx.post(
                self.OVERPASS_URL,
                data={'data': query},
                timeout=60.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch OSM data: {e}")
            raise

    def parse_osm_element(self, element: Dict[str, Any], region: str) -> Dict[str, Any]:
        """Parse OSM element to business format"""
        tags = element.get('tags', {})

        # Determine category - map to enum values: restaurant, service, retail, grocery, butcher, other
        amenity = tags.get('amenity', '')
        shop = tags.get('shop', '')

        if amenity == 'restaurant':
            category = 'restaurant'
        elif shop == 'butcher':
            category = 'butcher'
        elif shop in ['supermarket', 'convenience', 'grocery']:
            category = 'grocery'
        elif shop:
            category = 'retail'
        else:
            category = 'other'

        # Get coordinates
        if element.get('type') == 'node':
            lat = element.get('lat')
            lon = element.get('lon')
        elif element.get('center'):
            lat = element['center'].get('lat')
            lon = element['center'].get('lon')
        else:
            lat, lon = None, None

        # Build business data
        business = {
            'name': tags.get('name', 'Unknown'),
            'category': category,
            'address_street': tags.get('addr:street', ''),
            'address_city': tags.get('addr:city', ''),
            'address_state': tags.get('addr:state', 'CO'),
            'address_zip': tags.get('addr:postcode', ''),
            'latitude': lat,
            'longitude': lon,
            'website': tags.get('website', '') or tags.get('contact:website', ''),
            'phone': tags.get('phone', '') or tags.get('contact:phone', ''),
            'halal_certified': tags.get('diet:halal') == 'yes' or 'halal' in tags.get('cuisine', '').lower(),
            'source': 'osm',
            'source_ref': f"osm_{element.get('type')}_{element.get('id')}",
            'region': region,
        }

        return business

    def ingest_query(self, query_config: Dict[str, Any]) -> int:
        """Ingest businesses from a single OSM query"""
        query_id = query_config.get('id')
        region = query_config.get('region', 'CO')

        logger.info(f"Ingesting OSM query: {query_id}", extra={
            'ingest_run_id': self.ingest_run_id,
            'query_id': query_id
        })

        try:
            # Build and execute query
            query = self.build_query(query_config)
            data = self.fetch_osm_data(query)

            # Parse elements
            elements = data.get('elements', [])
            businesses = []

            for element in elements:
                try:
                    business = self.parse_osm_element(element, region)
                    if business.get('name') != 'Unknown':
                        businesses.append(business)
                except Exception as e:
                    logger.warning(f"Failed to parse OSM element: {e}")
                    continue

            # Insert into staging
            with get_sync_session() as session:
                for business_data in businesses:
                    query_sql = text("""
                    INSERT INTO staging_businesses (staging_id, ingest_run_id, source, source_ref, raw_payload)
                    VALUES (gen_random_uuid(), :ingest_run_id, 'osm', :source_ref, CAST(:raw_payload AS jsonb))
                    """)
                    session.execute(
                        query_sql,
                        {
                            'ingest_run_id': str(self.ingest_run_id),
                            'source_ref': business_data.get('source_ref'),
                            'raw_payload': json.dumps(business_data)
                        }
                    )

            logger.info(f"Ingested {len(businesses)} businesses from OSM query {query_id}", extra={
                'ingest_run_id': self.ingest_run_id,
                'count_in': len(businesses)
            })

            return len(businesses)

        except Exception as e:
            logger.error(f"Failed to ingest OSM query {query_id}: {e}", extra={
                'ingest_run_id': self.ingest_run_id,
                'errors': str(e)
            })
            raise

    def run(self) -> int:
        """Run OSM importer for all configured queries"""
        logger.info("Starting OSM importer", extra={'ingest_run_id': self.ingest_run_id})

        queries = self.sources_config.get('osm_queries', [])
        total_businesses = 0

        for query_config in queries:
            try:
                count = self.ingest_query(query_config)
                total_businesses += count
            except Exception as e:
                logger.error(f"OSM query {query_config.get('id')} failed: {e}")
                continue

        logger.info(f"OSM importer completed", extra={
            'ingest_run_id': self.ingest_run_id,
            'count_out': total_businesses
        })

        return total_businesses


if __name__ == "__main__":
    importer = OSMImporter()
    importer.run()

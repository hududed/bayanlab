#!/usr/bin/env python3
"""
Pipeline runner - orchestrates the full data pipeline
"""
import uuid
import sys
from datetime import datetime
from sqlalchemy import text
from backend.services.common.logger import get_logger
from backend.services.common.database import get_sync_session
from backend.services.ingest.ics_poller import ICSPoller
from backend.services.ingest.csv_loader import CSVLoader
from backend.services.ingest.osm_import import OSMImporter
from backend.services.ingest.certifier_import import CertifierImporter
from backend.services.process.normalizer import Normalizer
from backend.services.process.geocoder import Geocoder
from backend.services.process.placekeyer import Placekeyer
from backend.services.process.dq_checks import DQChecker
from backend.services.publish.exporter import Exporter

logger = get_logger("pipeline_runner")


def record_build_start(ingest_run_id: uuid.UUID, build_type: str):
    """Record pipeline build start"""
    with get_sync_session() as session:
        session.execute(
            text("""
            INSERT INTO build_metadata (ingest_run_id, build_type, started_at, status)
            VALUES (:run_id, :build_type, NOW(), 'running')
            """),
            {'run_id': str(ingest_run_id), 'build_type': build_type}
        )
        session.commit()


def record_build_complete(ingest_run_id: uuid.UUID, build_type: str, records_processed: int, success: bool, error_log: str = None):
    """Record pipeline build completion"""
    with get_sync_session() as session:
        session.execute(
            text("""
            UPDATE build_metadata
            SET completed_at = NOW(), status = :status, records_processed = :records, error_log = :error_log
            WHERE ingest_run_id = :run_id AND build_type = :build_type
            """),
            {
                'run_id': str(ingest_run_id),
                'build_type': build_type,
                'status': 'success' if success else 'failed',
                'records': records_processed,
                'error_log': error_log
            }
        )
        session.commit()


def run_events_pipeline():
    """Run events pipeline"""
    ingest_run_id = uuid.uuid4()
    logger.info(f"Starting events pipeline", extra={'ingest_run_id': ingest_run_id})

    record_build_start(ingest_run_id, 'events')

    try:
        # Ingest
        ics_poller = ICSPoller(ingest_run_id)
        ics_count = ics_poller.run()

        csv_loader = CSVLoader(ingest_run_id)
        events_count, _ = csv_loader.run()

        total_ingested = ics_count + events_count

        # Process
        normalizer = Normalizer(ingest_run_id)
        normalized_count, _ = normalizer.run()

        geocoder = Geocoder(ingest_run_id)
        geocoded_count, _ = geocoder.run()

        # DQ Checks
        dq_checker = DQChecker(ingest_run_id)
        dq_passed = dq_checker.run()

        if not dq_passed:
            logger.error("DQ checks failed for events pipeline")
            record_build_complete(ingest_run_id, 'events', normalized_count, False, "DQ checks failed")
            return False

        # Export
        exporter = Exporter(ingest_run_id)
        exported_count, _ = exporter.run()

        record_build_complete(ingest_run_id, 'events', exported_count, True)

        logger.info(f"Events pipeline completed successfully", extra={
            'ingest_run_id': ingest_run_id,
            'ingested': total_ingested,
            'normalized': normalized_count,
            'exported': exported_count
        })

        return True

    except Exception as e:
        logger.error(f"Events pipeline failed: {e}", extra={'ingest_run_id': ingest_run_id})
        record_build_complete(ingest_run_id, 'events', 0, False, str(e))
        return False


def run_businesses_pipeline():
    """Run businesses pipeline"""
    ingest_run_id = uuid.uuid4()
    logger.info(f"Starting businesses pipeline", extra={'ingest_run_id': ingest_run_id})

    record_build_start(ingest_run_id, 'businesses')

    try:
        # Ingest
        csv_loader = CSVLoader(ingest_run_id)
        _, businesses_count = csv_loader.run()

        osm_importer = OSMImporter(ingest_run_id)
        osm_count = osm_importer.run()

        certifier_importer = CertifierImporter(ingest_run_id)
        certifier_count = certifier_importer.run()

        total_ingested = businesses_count + osm_count + certifier_count

        # Process
        normalizer = Normalizer(ingest_run_id)
        _, normalized_count = normalizer.run()

        geocoder = Geocoder(ingest_run_id)
        _, geocoded_count = geocoder.run()

        placekeyer = Placekeyer(ingest_run_id)
        placekeyer.run()

        # DQ Checks
        dq_checker = DQChecker(ingest_run_id)
        dq_passed = dq_checker.run()

        if not dq_passed:
            logger.error("DQ checks failed for businesses pipeline")
            record_build_complete(ingest_run_id, 'businesses', normalized_count, False, "DQ checks failed")
            return False

        # Export
        exporter = Exporter(ingest_run_id)
        _, exported_count = exporter.run()

        record_build_complete(ingest_run_id, 'businesses', exported_count, True)

        logger.info(f"Businesses pipeline completed successfully", extra={
            'ingest_run_id': ingest_run_id,
            'ingested': total_ingested,
            'normalized': normalized_count,
            'exported': exported_count
        })

        return True

    except Exception as e:
        logger.error(f"Businesses pipeline failed: {e}", extra={'ingest_run_id': ingest_run_id})
        record_build_complete(ingest_run_id, 'businesses', 0, False, str(e))
        return False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="BayanLab Data Pipeline Runner")
    parser.add_argument('--pipeline', choices=['events', 'businesses', 'all'], default='all',
                        help="Which pipeline to run")
    args = parser.parse_args()

    success = True

    if args.pipeline in ['events', 'all']:
        success = run_events_pipeline() and success

    if args.pipeline in ['businesses', 'all']:
        success = run_businesses_pipeline() and success

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

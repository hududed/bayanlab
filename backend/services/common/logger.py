"""
Structured logging for BayanLab Community Data Backbone
"""
import logging
import json
import sys
from datetime import datetime
from typing import Any
from uuid import UUID


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": getattr(record, "service", "unknown"),
            "message": record.getMessage(),
        }

        # Add extra fields
        for key in ["ingest_run_id", "count_in", "count_out", "errors", "region"]:
            if hasattr(record, key):
                value = getattr(record, key)
                # Handle UUID serialization
                if isinstance(value, UUID):
                    value = str(value)
                log_data[key] = value

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(service: str) -> logging.Logger:
    """Get a logger for a service"""
    logger = logging.getLogger(service)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # Add service name to all log records
    old_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.service = service
        return record

    logging.setLogRecordFactory(record_factory)

    return logger

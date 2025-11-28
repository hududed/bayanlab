# Changelog

All notable changes to the BayanLab Community Data Backbone project.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Google Calendar API integration for private calendar access
- Dual-mode ICS poller (supports both public ICS URLs and Calendar API)
- Masjid onboarding documentation
- Service account setup guide
- Data migration scripts for organizing `business_claim_submissions`
  - `migrate_masajid.py` - Move mosques/Islamic centers to `masajid` table
  - `migrate_food.py` - Move halal eateries/markets to specialized tables
- `nonprofits` table for non-business organizations (CAIR, MSAs, foundations, food pantries)
- Address/city cleaning in geocoding for improved results (suite number removal, city normalization)
- Discovery email system for notifying imported businesses

### Changed
- Repository structure consolidated from `backbone/` to `backend/`
- All imports updated to use `backend.services` namespace
- Docker configuration updated for new structure
- Consolidated geocoding scripts into single `geocode_staging.py`
- Archived one-time migration scripts to `scripts/archive/`
- API response models no longer include `count` field (breaking change)

### Fixed
- SQL queries wrapped with `text()` for SQLAlchemy 2.0 compatibility
- Pydantic validation errors for Settings model
- Switched from Google Geocoding to OSM Nominatim (free, no API key required)

### Security
- Removed hardcoded database credentials from migration scripts
- Migration scripts now require environment variables (no fallback credentials)
- Added `scripts/migrate_*.py` to `.gitignore` to prevent credential exposure

## [0.1.0] - 2025-11-09

### Added
- Initial V1 implementation (Colorado region)
- Events pipeline (ICS poller, CSV loader)
- Businesses pipeline (CSV loader, OSM importer, certifier importer)
- Data processing services (normalizer, geocoder, placekeyer, DQ checker)
- Publishing services (API, static exports)
- PostgreSQL + PostGIS database schema
- FastAPI read-only API with filtering and pagination
- Static JSON exports for CDN distribution
- Docker Compose setup for local development
- Comprehensive documentation and QA checklist

### Technical Stack
- Python 3.11+ with uv package manager
- PostgreSQL 15 + PostGIS 3.3
- FastAPI for API layer
- SQLAlchemy 2.0 for ORM
- Docker + Docker Compose for containers

---

**Legend:**
- `Added` - New features
- `Changed` - Changes to existing functionality
- `Deprecated` - Soon-to-be removed features
- `Removed` - Removed features
- `Fixed` - Bug fixes
- `Security` - Security fixes

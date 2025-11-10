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

### Changed
- Repository structure consolidated from `backbone/` to `backend/`
- All imports updated to use `backend.services` namespace
- Docker configuration updated for new structure

### Fixed
- SQL queries wrapped with `text()` for SQLAlchemy 2.0 compatibility
- Pydantic validation errors for Settings model

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

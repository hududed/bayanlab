# Architectural Decision Records (ADRs)

Key technical decisions for BayanLab Backbone.

**Format:** Context → Decision → Consequences

---

## ADR-001: Regional Data Model
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Single PostgreSQL database with region column for V1.

**Rationale:** Simpler for V1, easier cross-region queries, can shard later.

**Consequences:**  
✅ Simple deployment  
❌ Single point of failure (mitigated by replicas)

---

## ADR-002: Staging + Canonical Tables
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Two-stage data model: staging (raw JSONB) → canonical (validated schema).

**Rationale:** Preserves original data, allows reprocessing without re-fetching.

**Consequences:**  
✅ Can replay pipeline, debug easily  
❌ Doubles storage (purge old staging after 90 days)

---

## ADR-003: FastAPI for API
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** FastAPI with async PostgreSQL (asyncpg).

**Rationale:** Auto-generated docs, fast (~10ms latency), type hints.

**Consequences:**  
✅ Great DX, fast enough for V1  
❌ Not as fast as Go/Rust

---

## ADR-004: Nominatim Geocoding
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Use Nominatim (OpenStreetMap) for geocoding.

**Rationale:** Free, good US accuracy, no vendor lock-in.

**Consequences:**  
✅ Free, no vendor lock-in  
❌ Rate limited (1 req/sec) - cache aggressively

---

## ADR-005: Static JSON Exports
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Generate static JSON files per region after each pipeline run.

**Rationale:** Fast (CDN), offline-friendly, no rate limits.

**Consequences:**  
✅ Blazing fast, simple  
❌ Stale data (4-hour refresh)

---

## ADR-006: Python + uv
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Use uv (Rust-based Python package manager).

**Rationale:** 10-100x faster than pip, lock files, simple config.

**Consequences:**  
✅ Fast, great for monorepos  
❌ Newer tool (less mature)

---

## ADR-007: SQLAlchemy 2.0
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Wrap raw SQL with `text()` for SQLAlchemy 2.0.

**Rationale:** Future-proof, safer (prevents SQL injection), async support.

**Consequences:**  
✅ Future-proof, safer  
❌ More verbose

---

## ADR-008: Docker Compose (DB Only)
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Docker for PostgreSQL only. Run pipeline/API natively.

**Rationale:** Fast iteration (hot reload), consistent DB version.

**Consequences:**  
✅ Fast iteration  
❌ Need Python 3.11+ on host

---

## ADR-009: Google Calendar Dual-Mode
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Try Calendar API first, fall back to ICS URL.

**Rationale:** Supports private calendars, graceful degradation.

**Consequences:**  
✅ Privacy-first, flexible  
❌ More complex (two code paths)

---

## ADR-010: Placekey (Optional)
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Use Placekey API for business deduplication (optional).

**Rationale:** High accuracy, industry standard, low cost.

**Consequences:**  
✅ Accurate deduplication  
❌ Requires API key (skip if missing)

---

## ADR-011: JSONB for Staging
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Store raw data as JSONB in staging tables.

**Rationale:** Flexible, indexed, native PostgreSQL support.

**Consequences:**  
✅ Flexible, fast  
❌ No schema validation at storage

---

## ADR-012: No Auth (V1)
**Date:** Nov 2025 | **Status:** Accepted (Temporary)

**Decision:** No authentication for V1 read-only API.

**Security:** Rate limiting (100 req/min), CORS enabled, HTTPS-only, no writes.

**Consequences:**  
✅ Simple integration  
❌ No usage tracking (add API keys Phase 2)

---

## ADR-013: PostgreSQL + PostGIS
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** PostgreSQL + PostGIS for database.

**Rationale:** ACID, spatial queries, JSONB support, mature.

**Consequences:**  
✅ Reliable, great for structured + spatial data  
❌ Vertical scaling limits (read replicas mitigate)

---

**Maintained by:** BayanLab Engineering

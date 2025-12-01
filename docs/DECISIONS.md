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

## ADR-004: Geocoding Provider Abstraction
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Use provider abstraction with three options: OpenStreetMap (default), Google, or Hybrid.

**Rationale:**
- OpenStreetMap Nominatim is free, good US accuracy (10-50m of Google), no API key needed
- Google Geocoding API offers best accuracy but requires billing ($5/1000 requests)
- Hybrid approach tries Google first, falls back to OSM for reliability
- Easy migration via `GEOCODING_PROVIDER` environment variable

**Implementation:**
- Location: `backend/services/common/geocoding.py`
- Providers: `OpenStreetMapGeocoder`, `GoogleGeocoder`, `HybridGeocoder`
- Factory: `get_geocoder()` controlled by env var
- Migration path: `osm` (default) → `hybrid` → `google`

**Consequences:**
✅ Free default (OSM), no vendor lock-in
✅ Easy migration to Google when billing enabled
✅ Hybrid mode provides best of both worlds
❌ OSM rate limited (1 req/sec) - cache aggressively
❌ Google requires billing setup

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

## ADR-014: Cron for Scheduling
**Date:** Nov 2025 | **Status:** Accepted

**Decision:** Use cron for pipeline scheduling instead of APScheduler.

**Rationale:** Simpler, more reliable, standard Unix tool, better process isolation.

**Consequences:**
✅ Simple, reliable, no Python dependencies
✅ Better process isolation (each run is independent)
✅ Easy to monitor with standard tools
❌ Less flexible than APScheduler (no dynamic scheduling)

---

## ADR-015: Hybrid Enrichment Pipeline (Google Places + Crawl4AI)
**Date:** Nov 2025 | **Status:** Accepted

**Context:** ProWasl business directory needs enriched data (location, services, contact info) for 197+ Muslim-owned businesses from Muslim Professionals network. Initial CSV has no location data.

**Decision:** Use hybrid enrichment pipeline:
1. **Google Places API** for location/contact data (address, phone, website)
2. **Crawl4AI + LLM** for deep website scraping (services, about, team size)
3. **Manual QA** for final verification

**Alternatives Considered:**
- LinkedIn scraping: Fragile, ToS violations, account bans, manual effort
- Manual enrichment: 8-16 hours for 197 businesses
- Pure web scraping: Fragile CSS selectors, anti-bot detection
- Crawl4AI only: Less reliable for location data than Places API

**Rationale:**
- Google Places API is free (under $200/month limit), official, 90% success rate
- Crawl4AI uses LLM to understand any website structure (no brittle selectors)
- Combination is fast (2-3 hours), cheap ($0-1), and reliable
- Scalable to 1,000s of businesses for national expansion

**Consequences:**
✅ Fast enrichment (30 min for 197 businesses)
✅ High success rate (~90% for location, ~70% for website data)
✅ Low cost ($0 for Places API, $0.20 for LLM extraction)
✅ No ToS violations (official APIs only)
✅ Scalable architecture
❌ Requires Google Cloud account setup (one-time, 10 min)
❌ Depends on external APIs (fallback: manual enrichment)

**Fallback Strategy:**
If Google Places API unavailable:
- Option A: Crawl4AI scrapes Google search results (slower, less reliable)
- Option B: Manual LinkedIn enrichment via LinkedIn Helper
- Option C: Hire VA on Fiverr ($50-100 for 197 businesses)

---

## ADR-016: Enigma-Inspired Entity Model Evolution
**Date:** Nov 2025 | **Status:** Accepted

**Context:** Current `business_canonical` table is flat and limited. To build a commercial-grade business data API (like Enigma.com) serving multiple apps (ProWasl, The Ummah), need richer entity model with relationships, certifications, and Muslim-specific attributes.

**Decision:** Evolve database schema to match Enigma's entity model, with Muslim-focused extensions:

**Entity Types:**
1. **business_brands** - Customer-facing business identities (name, logo, website)
2. **business_locations** - Physical operating locations (address, hours, status)
3. **legal_entities** - Legal business structures (LLC, Corp, registrations)
4. **industries** - Hierarchical industry classification (Halal Food → Restaurants → Fast Casual)
5. **brand_certifications** - Halal certifications (ISNA, IFANCA, HMA), expiration tracking
6. **brand_owners** - Business owners (opt-in, privacy-conscious)

**Muslim-Specific Attributes:**
- `muslim_owned` (boolean)
- `verified_muslim_owner` (boolean, community-verified)
- `halal_certified` (boolean)
- `prayer_space_available` (boolean)
- `wudu_facilities` (boolean)
- `hijab_friendly` (boolean)
- `ramadan_hours` (JSONB, special operating hours)
- `supports_masjid` (boolean, donates to masjids)
- `zakat_friendly` (boolean, accepts Zakat payments)

**API Evolution:**
- Phase 1-3: REST API (current)
- Phase 4+: GraphQL API with Relay pagination (like Enigma)
- Advanced filters: halal, Muslim-owned, prayer space, certifications
- Aggregation queries (business stats, trends)

**Alternatives Considered:**
- Keep flat `business_canonical` table: Simple but limits scalability and API richness
- Build custom model from scratch: Reinventing the wheel, Enigma already proved this works
- Copy Enigma exactly: Miss Muslim-specific needs (halal, prayer accommodations)

**Rationale:**
- Enigma's model is proven for commercial business data APIs
- Separation of Brand/Location/Legal Entity enables rich relationships and queries
- Muslim-specific attributes differentiate BayanLab from general business directories
- GraphQL API enables flexible queries for diverse app needs
- Scalable to 100,000+ businesses nationally/internationally

**Consequences:**
✅ Commercial-grade data model matching industry standards (Enigma)
✅ Rich API capabilities (filters, relationships, aggregations)
✅ Muslim-specific features competitors can't match
✅ Scalable to national/international expansion
✅ Supports revenue model (API pricing tiers, premium features)
❌ Breaking change: Must migrate existing data from `business_canonical`
❌ More complex schema: Higher development/maintenance effort
❌ GraphQL adds API surface area to maintain

**Migration Strategy:**
- Phase 1 (Q1 2026): Build new tables alongside `business_canonical`
- Phase 2 (Q2 2026): Migrate existing data, dual-write to both schemas
- Phase 3 (Q3 2026): Deprecate `business_canonical`, GraphQL API launch
- Phase 4 (Q4 2026): Remove old schema

**Revenue Model (Waqf-First):**
- Free tier: Non-profits, masjids, students (1,000 API calls/month)
- Paid tiers: $99 → $499 → $2,500/month (10K → 100K → 1M calls)
- **50% of all revenue donated to masjids** (ongoing sadaqah jariyah)

**See:** [ENIGMA_INSPIRED_ROADMAP.md](ENIGMA_INSPIRED_ROADMAP.md) for complete technical specification

---

## ADR-017: Short Claim IDs
**Date:** Nov 2025 | **Status:** Accepted

**Context:** Business claim submissions need user-friendly identifiers for emails and communication. Full UUIDs are too long and difficult to communicate.

**Decision:** Implement short claim ID system with format `PRW-XXXXX`:
- Prefix: `PRW` (ProWasl)
- 5-character random suffix (uppercase alphanumeric)
- Excludes confusing characters (0, O, I, 1)
- Collision detection with retry logic

**Implementation:**
- Added `short_claim_id` column to `business_claim_submissions`
- Generated on claim submission
- Used in email templates and admin interface
- Examples: `PRW-HB2DL`, `PRW-CYMH6`, `PRW-6WSYE`

**Consequences:**
✅ User-friendly identifiers for support and communication
✅ Short enough for emails and verbal communication
✅ Collision-resistant (36^5 = 60M+ combinations)
❌ Not globally unique (prefix tied to ProWasl project)

---

## ADR-018: SendGrid Email Integration
**Date:** Nov 2025 | **Status:** Accepted

**Context:** Business claim portal needs professional email confirmations for submissions.

**Decision:** Integrate SendGrid for transactional emails:
- Confirmation email on claim submission
- Dynamic templates for professional formatting
- Sender: `noreply@prowasl.com`

**Implementation:**
- Configuration: `SENDGRID_API_KEY` environment variable
- Template management: SendGrid dashboard
- Email includes: business name, short claim ID, submission details

**Consequences:**
✅ Professional email confirmations
✅ Reliable delivery tracking
✅ Template management via SendGrid UI
❌ Dependency on external service
❌ Cost scales with volume (free tier: 100 emails/day)

---

## ADR-019: Phone Number Normalization
**Date:** Nov 2025 | **Status:** Accepted

**Context:** Business submissions have inconsistent phone number formats, making validation and storage difficult.

**Decision:** Normalize all phone numbers to E.164 format before storage:
- Strip all non-digit characters
- Add `+1` prefix for US numbers (10 digits)
- Validate length before storage

**Implementation:**
Applied to fields:
- `business_phone`
- `business_whatsapp`
- `owner_phone`

**Consequences:**
✅ Consistent storage format
✅ Easy validation and comparison
✅ Ready for international expansion
❌ Assumes US numbers (+1) by default

---

## ADR-020: External Business Discovery & Import
**Date:** Nov 2025 | **Status:** Accepted

**Context:** To bootstrap ProWasl directory, we need to import businesses from external Muslim business directories (e.g., Muslim Business Central).

**Decision:** Create import pipeline with discovery email workflow:
1. **Scrape** external directories → JSON files (stored locally, not committed)
2. **Import** to `business_claim_submissions` with `status=staging`
3. **Gradual approval** via cron (5/week for organic growth)
4. **Discovery emails** sent to businesses with real emails after approval

**Implementation:**
- Scripts in `scripts/` (gitignored - contain scraping logic)
- Cron job on Raspberry Pi: `cron_approve_and_notify.py`
- Discovery email tracking: `discovery_email_sent`, `discovery_email_sent_at` columns
- `submitted_from` field tracks how data entered the system (see ADR-021)

**Email Flow:**
- Web submissions → immediate confirmation email
- External imports → discovery email only after approval (if real email exists)
- No email if `owner_email = 'import@bayanlab.com'` (placeholder)

**Consequences:**
✅ Bootstraps directory with validated businesses
✅ Organic growth appearance (not all at once)
✅ Notifies real business owners of their listing
✅ Easy opt-out (reply to remove)
❌ Scrape scripts not version controlled (intentional)
❌ Dependent on external directory availability

---

## ADR-021: Standardized submitted_from Values
**Date:** Nov 2025 | **Status:** Accepted

**Context:** The `submitted_from` column was being used inconsistently across tables. In some cases it duplicated the `source` column (e.g., `mbc_import`, `muslimlistings_import`), making it redundant.

**Decision:** Standardize `submitted_from` to track HOW data entered the system, not WHERE it came from:

| Value | Meaning | Used By |
|-------|---------|---------|
| `scraper` | Automated scraper ingestion | unified_ingest.py |
| `claim_portal` | User self-submitted claim | claim.prowasl.com |
| `admin_manual` | Admin added manually | validation.html |

**Distinction from `source` column:**
- `source` (enum): WHERE data originated (e.g., `mda_import`, `muslimlistings_import`, `claim_approved`)
- `submitted_from` (varchar): HOW it entered the system (e.g., `scraper`, `claim_portal`, `admin_manual`)

**Migration Applied:**
```sql
-- business_claim_submissions
UPDATE business_claim_submissions SET submitted_from = 'claim_portal' WHERE submitted_from = 'web';
UPDATE business_claim_submissions SET submitted_from = 'admin_manual' WHERE submitted_from = 'facebook_group';

-- business_canonical
UPDATE business_canonical SET submitted_from = 'claim_portal' WHERE submitted_from = 'web';
UPDATE business_canonical SET submitted_from = 'admin_manual' WHERE submitted_from = 'facebook_group';
UPDATE business_canonical SET submitted_from = 'scraper' WHERE submitted_from LIKE '%_import';
```

**Consequences:**
✅ Clear separation of concerns (source vs entry method)
✅ Useful for analytics (how are businesses entering the system?)
✅ Generic values work across all sites/apps
❌ Required one-time migration of existing data

---

**Maintained by:** BayanLab Engineering

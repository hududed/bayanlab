# BayanLab Backbone - Product Roadmap

Strategic product direction and long-term goals.

**Last Updated:** November 10, 2025

---

## Vision

Build a scalable, multi-region data backbone that aggregates Muslim community events and halal businesses across the United States and internationally, serving mobile apps and community platforms with high-quality, up-to-date data.

## Guiding Principles

1. **Regional Architecture** - Design for multi-region from day one
2. **Data Quality First** - Validation, deduplication, and source tracking
3. **Privacy Conscious** - Respect calendar privacy, support both public and private data sharing
4. **Simple Onboarding** - Make it easy for masjids and businesses to share data
5. **API-First** - Everything accessible via clean REST APIs

---

## Phase 1: Colorado MVP ✅ (Complete)

**Goal:** Prove the concept with Colorado as the pilot region

### Completed
- [x] PostgreSQL + PostGIS database schema
- [x] Events pipeline (ICS/CSV ingestion)
- [x] Businesses pipeline (CSV/OSM/Certifier ingestion)
- [x] Data processing (normalize, geocode, DQ checks)
- [x] FastAPI read-only endpoints
- [x] Static JSON exports
- [x] Docker setup for local development
- [x] Google Calendar API integration
- [x] Masjid onboarding documentation

### Metrics
- 5+ events from seed data
- 10+ businesses from OSM + CSV + certifiers
- API response time < 100ms
- Zero breaking changes in data schema

---

## Phase 2: Production Hardening 🚧 (In Progress)

**Status:** 30% complete | **Target:** December 2025

**Goal:** Make the system production-ready for The Ummah and ProWasl apps

### Current Sprint: Calendar Integration ⏳
- [x] Dual-mode ICS poller (URL + Calendar API)
- [x] Service account setup guide
- [x] Masjid onboarding documentation
- [ ] Onboard first production masjid (blocked by org permissions)
- [ ] Test with personal test calendar

**Blocker:** ICFC calendar sharing restricted by Google Workspace admin

### Infrastructure
- [ ] Automated scheduling (APScheduler for 4-hour rebuilds)
- [ ] Health checks (`/healthz`, `/metrics` Prometheus)
- [ ] Rate limiting (100 req/min per IP)
- [ ] Error alerting (email on pipeline failures)
- [ ] Database backups (daily, 30-day retention)
- [ ] CDN for static exports

### Testing & Quality
- [ ] E2E test suite
- [ ] Integration tests for all services
- [ ] Load testing (100 RPS sustained)
- [ ] Partner validation (masjids verify events)
- [ ] 80% test coverage

### Deployment
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Blue-green deployment
- [ ] Production environment setup
- [ ] Rollback procedures

**Success Criteria:**
- 99.5% uptime for 30 days
- API latency < 100ms (p95)
- 20+ masjid calendars integrated
- 100+ businesses listed

---

## Phase 3: Colorado Expansion

**Goal:** Onboard 20+ Colorado masjids and 50+ halal businesses

### Partnerships
- [ ] Outreach to Denver-area masjids (DMA, MCA, ICNC, etc.)
- [ ] Outreach to Colorado Springs Islamic Center
- [ ] Outreach to Fort Collins ICFC
- [ ] Outreach to Boulder Islamic Center
- [ ] Partner with halal certifiers (ISNA, IFANCA)

### Features
- [ ] Email notifications for calendar sync issues
- [ ] Admin dashboard for monitoring data sources
- [ ] Self-service calendar onboarding (web form)
- [ ] Business claim system (businesses verify their info)

### Data Sources
- [ ] 20+ masjid Google Calendars
- [ ] 50+ verified halal businesses
- [ ] Real-time OSM updates (weekly refresh)

**Target:** Q1 2026

---

## Phase 4: Multi-State Expansion

**Goal:** Expand to 5 US states with high Muslim populations

### Target States
1. **Texas** (Houston, Dallas, Austin)
2. **California** (LA, Bay Area, San Diego)
3. **Illinois** (Chicago metro)
4. **Michigan** (Detroit, Dearborn)
5. **New York** (NYC, Buffalo)

### Technical Requirements
- [ ] Region management dashboard
- [ ] State-specific data quality rules
- [ ] Timezone handling for multi-region queries
- [ ] Regional API endpoints (`/v1/US-TX/events`)

### Data Goals per State
- 30+ masjid calendars
- 100+ halal businesses
- 500+ monthly events

**Target:** Q2-Q3 2026

---

## Phase 5: National Coverage

**Goal:** Cover all 50 US states

### Scale
- 500+ masjids nationally
- 2,000+ halal businesses
- 10,000+ monthly events

### Features
- [ ] Federated data model (regional instances)
- [ ] Search API (full-text search across all regions)
- [ ] Analytics dashboard (usage metrics, popular events)
- [ ] Mobile SDK for app developers

**Target:** Q4 2026

---

## Phase 6: International Expansion

**Goal:** Expand to Canada, UK, and Middle East

### Target Regions
- **Canada** (Toronto, Montreal, Vancouver)
- **UK** (London, Birmingham, Manchester)
- **UAE** (Dubai, Abu Dhabi)
- **Saudi Arabia** (Riyadh, Jeddah, Makkah/Madinah)

### Technical Challenges
- [ ] Multi-language support (Arabic, Urdu, French)
- [ ] Hijri calendar integration
- [ ] Prayer time APIs (for salah events)
- [ ] International address geocoding

**Target:** 2027

---

## Future Ideas (Backlog)

- **Recurring events intelligence** - Detect patterns in one-off events, suggest recurring templates
- **Event categories** - Auto-classify events (educational, social, worship, sports)
- **Waitlist system** - For events with limited capacity
- **Business reviews** - Community ratings for halal businesses
- **Prayer time integration** - Auto-generate salah times per masjid
- **Donation platform** - Help masjids fundraise through the platform
- **Volunteer coordination** - Match volunteers with community needs

---

## Metrics and KPIs

### V1 Success Criteria (Colorado)
- ✅ 5+ masjid calendars integrated
- ✅ 50+ halal businesses listed
- ✅ API uptime > 99%
- ✅ Pipeline runtime < 5 minutes

### Phase 2 Success Criteria
- [ ] 20+ masjid calendars
- [ ] 100+ halal businesses
- [ ] API latency < 50ms (p95)
- [ ] Zero data loss incidents
- [ ] 2 regional consumers (The Ummah, ProWasl)

### Long-Term North Star Metrics
- **Coverage:** 80% of US masjids with public calendars integrated
- **Accuracy:** 95% of events have correct time/location
- **Freshness:** Data updated within 6 hours of source changes
- **Adoption:** 10+ apps/platforms consuming the API

---

## Decision Framework

When evaluating new features, consider:

1. **Does it improve data quality?** (accuracy, freshness, completeness)
2. **Does it reduce manual work?** (for masjids, for BayanLab team)
3. **Does it enable new use cases?** (new apps, new platforms)
4. **Is it scalable?** (works for 10 regions? 50 regions?)
5. **Does it align with our mission?** (clarity, community service)

---

**Maintained by:** BayanLab Team
**Review Cadence:** Quarterly

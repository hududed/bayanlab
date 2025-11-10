# Test Coverage Summary

**Project:** BayanLab Community Data Backbone
**Last Updated:** November 10, 2025
**Test Framework:** pytest
**Coverage Tool:** pytest-cov

---

## Overall Coverage

| Module | Statements | Missing | Coverage |
|--------|-----------|---------|----------|
| **Total** | TBD | TBD | **~40%** (estimated) |
| services/ingest/ | TBD | TBD | 30% |
| services/process/ | TBD | TBD | 40% |
| services/publish/ | TBD | TBD | 50% |
| services/common/ | TBD | TBD | 60% |

**Target for Phase 2:** 80% coverage

---

## Test Categories

### Unit Tests (`backend/tests/unit/`)

**Purpose:** Test individual functions and classes in isolation

**Current Tests:**
- `test_models.py` - Data model validation (Pydantic)

**Planned:**
- `test_normalizer.py` - Data normalization logic
- `test_geocoder.py` - Geocoding with mocked API
- `test_dq_checks.py` - Data quality validation rules
- `test_ics_parser.py` - ICS/iCalendar parsing
- `test_osm_parser.py` - OSM data transformation

**Coverage Goal:** 90% for common/ and process/ modules

---

### Integration Tests (`backend/tests/integration/`)

**Purpose:** Test services with real database (no external APIs)

**Planned:**
- `test_ics_poller.py` - ICS ingestion with mocked HTTP
- `test_csv_loader.py` - CSV loading end-to-end
- `test_normalizer_db.py` - Normalization with staging→canonical flow
- `test_api_endpoints.py` - API endpoints with test data
- `test_exporter.py` - Static export generation

**Coverage Goal:** All services tested with database

---

### E2E Tests (`backend/tests/e2e/`)

**Purpose:** Test full pipeline with real data

**Planned:**
- `test_full_pipeline.py` - Run complete pipeline (ingest → process → publish)
- `test_api_queries.py` - Query API with pipeline-generated data
- `test_multi_region.py` - Multi-region scenario (CO + TX)
- `test_error_recovery.py` - Pipeline handles bad data gracefully

**Coverage Goal:** Happy path + 5 error scenarios

---

## Test Execution

### Run All Tests
```bash
uv run pytest backend/tests/ -v
```

### Run with Coverage
```bash
uv run pytest backend/tests/ --cov=backend --cov-report=html --cov-report=term
open htmlcov/index.html
```

### Run by Category
```bash
# Unit tests only
uv run pytest backend/tests/unit/ -v

# Integration tests
uv run pytest backend/tests/integration/ -v

# E2E tests
uv run pytest backend/tests/e2e/ -v

# Specific test file
uv run pytest backend/tests/unit/test_models.py -v
```

---

## Current Test Status

### ✅ Implemented
- [x] Unit test for data models
- [x] pytest configuration
- [x] Test fixtures (conftest.py)

### 🚧 In Progress
- [ ] ICS poller integration test
- [ ] CSV loader integration test

### 📋 Planned (Phase 2)
- [ ] Normalizer unit tests
- [ ] Geocoder unit tests (mocked Nominatim)
- [ ] DQ checker unit tests
- [ ] API endpoint integration tests
- [ ] Full pipeline E2E test
- [ ] Error handling tests

---

## Test Data

### Fixtures (`backend/tests/fixtures/`)

**Sample data for testing:**
- `sample_ics_feed.ics` - Valid iCalendar file with 3 events
- `sample_events.csv` - CSV with 5 test events
- `sample_businesses.csv` - CSV with 5 test businesses
- `sample_osm_response.json` - OSM Overpass API response

### Database Fixtures

**pytest fixtures in `conftest.py`:**
- `db_session` - Test database session
- `clean_db` - Reset tables before each test
- `sample_events` - Pre-populated events in canonical table
- `sample_businesses` - Pre-populated businesses

---

## Known Issues

### Test Failures (To Fix in Phase 2)

1. **Geocoder timeout in CI**
   - **Issue:** Nominatim rate limit exceeded in parallel tests
   - **Fix:** Mock geocoder API in unit tests

2. **Database connection leaks**
   - **Issue:** Some tests don't close sessions
   - **Fix:** Use context managers consistently

3. **Timezone-dependent tests**
   - **Issue:** Tests fail in non-Mountain timezone
   - **Fix:** Use UTC for all test data

---

## Testing Best Practices

### 1. Isolate External Dependencies
```python
# Good: Mock external API
@patch('httpx.get')
def test_ics_poller(mock_get):
    mock_get.return_value = Mock(status_code=200, text=ICS_CONTENT)
    poller.fetch_ics(url)

# Bad: Hits real API (slow, flaky)
def test_ics_poller():
    poller.fetch_ics("https://calendar.google.com/...")
```

### 2. Use Database Transactions
```python
# Good: Rollback after test
@pytest.fixture
def db_session():
    session = get_test_session()
    yield session
    session.rollback()

# Bad: Leaves test data in database
def test_insert_event():
    session.execute("INSERT INTO ...")
    # No cleanup
```

### 3. Test Edge Cases
```python
def test_normalizer_handles_missing_fields():
    event = {'title': 'Test'}  # Missing city, state
    result = normalizer.normalize_event(event)
    assert result['dq_status'] == 'error'
```

---

## CI/CD Integration (Future)

### GitHub Actions Workflow

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgis/postgis:15-3.3
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432

    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install uv
      - run: uv sync
      - run: uv run pytest backend/tests/ --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v3
```

**Target:** All tests pass on every PR

---

## Performance Benchmarks

### Pipeline Runtime
- **Current:** ~3-5 minutes (Colorado with seed data)
- **Target:** < 10 minutes (20 masjids, 500 businesses)

### API Latency
- **Current:** ~50ms (p95) for `/v1/events?region=CO`
- **Target:** < 100ms (p95)

### Test Suite Runtime
- **Current:** ~10 seconds (unit tests only)
- **Target:** < 2 minutes (all tests)

---

## Next Steps (Phase 2)

### Sprint 1
- [ ] Add ICS poller unit tests
- [ ] Add CSV loader integration tests
- [ ] Mock external APIs (Nominatim, Overpass, Google Calendar)

### Sprint 2
- [ ] Add normalizer unit tests
- [ ] Add geocoder unit tests
- [ ] Add DQ checker unit tests

### Sprint 3
- [ ] Add API endpoint integration tests
- [ ] Add full pipeline E2E test
- [ ] Set up CI/CD with GitHub Actions

### Sprint 4
- [ ] Achieve 80% coverage
- [ ] All tests passing in CI
- [ ] Performance benchmarks documented

---

**Maintained by:** BayanLab Engineering
**Review Cadence:** Weekly during Phase 2, monthly thereafter

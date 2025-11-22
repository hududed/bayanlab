#!/bin/bash
# Quick QA Test Script for BayanLab Backbone
# Run this after making changes to verify everything works

set -e  # Exit on error

echo "🧪 BayanLab Backbone - Quick QA Test"
echo "===================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper function
test_command() {
    local name="$1"
    shift
    echo -n "Testing: $name... "
    if "$@" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 1. Environment checks
echo "1. Environment Checks"
echo "--------------------"
test_command "Python 3.11+" python -c "import sys; assert sys.version_info >= (3, 11)"
test_command "uv installed" uv --version
test_command "Docker running" docker ps
echo ""

# 2. Database checks
echo "2. Database Checks"
echo "------------------"
test_command "PostgreSQL running" docker ps | grep -q postgres
test_command "Database connection" PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT 1"
test_command "PostGIS extension" PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "SELECT PostGIS_Version()"
echo ""

# 3. File structure checks
echo "3. File Structure"
echo "-----------------"
test_command ".env exists" test -f .env
test_command "backend/ directory" test -d backend
test_command "seed/ at root" test -d seed
test_command "infra/ at root" test -d infra
test_command "No backend/.gitignore" test ! -f backend/.gitignore
test_command "No backend/pyproject.toml" test ! -f backend/pyproject.toml
echo ""

# 4. Data checks
echo "4. Data Verification"
echo "--------------------"
EVENT_COUNT=$(PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -t -c "SELECT COUNT(*) FROM event_canonical;")
BUSINESS_COUNT=$(PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -t -c "SELECT COUNT(*) FROM business_canonical;")

echo -n "Events in database: "
if [ "$EVENT_COUNT" -ge 5 ]; then
    echo -e "${GREEN}$EVENT_COUNT ✓${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}$EVENT_COUNT (expected >= 5) ✗${NC}"
    ((TESTS_FAILED++))
fi

echo -n "Businesses in database: "
if [ "$BUSINESS_COUNT" -ge 10 ]; then
    echo -e "${GREEN}$BUSINESS_COUNT ✓${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}$BUSINESS_COUNT (expected >= 10) ✗${NC}"
    ((TESTS_FAILED++))
fi

test_command "Export files exist" test -f exports/CO-events.json -a -f exports/CO-businesses.json
echo ""

# 5. Code quality checks
echo "5. Code Quality"
echo "---------------"
OLD_IMPORTS=$(grep -r "from services\." backend/services/ 2>/dev/null | wc -l | tr -d ' ')
echo -n "Old imports (from services.): "
if [ "$OLD_IMPORTS" -eq 0 ]; then
    echo -e "${GREEN}$OLD_IMPORTS ✓${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${RED}$OLD_IMPORTS found (should be 0) ✗${NC}"
    ((TESTS_FAILED++))
fi

NEW_IMPORTS=$(grep -r "from backend.services" backend/services/ 2>/dev/null | wc -l | tr -d ' ')
echo -n "New imports (from backend.services): "
if [ "$NEW_IMPORTS" -gt 0 ]; then
    echo -e "${GREEN}$NEW_IMPORTS ✓${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}$NEW_IMPORTS (expected > 0) ⚠${NC}"
fi

TEXT_WRAPPERS=$(grep -r "session.execute(text(" backend/services/ 2>/dev/null | wc -l | tr -d ' ')
echo -n "SQL text() wrappers: "
if [ "$TEXT_WRAPPERS" -gt 0 ]; then
    echo -e "${GREEN}$TEXT_WRAPPERS ✓${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}$TEXT_WRAPPERS (expected > 0) ⚠${NC}"
fi
echo ""

# 6. Pipeline test
echo "6. Pipeline Test"
echo "----------------"
echo "Running pipeline... (this may take 30 seconds)"
if uv run python run_pipeline.py --pipeline all > /tmp/pipeline_test.log 2>&1; then
    echo -e "${GREEN}Pipeline completed successfully ✓${NC}"
    ((TESTS_PASSED++))

    # Check for expected output
    if grep -q "Loaded 5 events from events.csv" /tmp/pipeline_test.log; then
        echo -e "${GREEN}CSV events loaded ✓${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${RED}CSV events not loaded ✗${NC}"
        ((TESTS_FAILED++))
    fi

    if grep -q "Ingested.*businesses from OSM" /tmp/pipeline_test.log; then
        echo -e "${GREEN}OSM businesses imported ✓${NC}"
        ((TESTS_PASSED++))
    else
        echo -e "${YELLOW}OSM businesses not imported ⚠${NC}"
    fi
else
    echo -e "${RED}Pipeline failed ✗${NC}"
    echo "Last 10 lines of output:"
    tail -10 /tmp/pipeline_test.log
    ((TESTS_FAILED++))
fi
echo ""

# Summary
echo "========================================"
echo "Summary"
echo "========================================"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All critical tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Start API: uv run uvicorn backend.services.api_service.main:app --reload"
    echo "  2. Test API: curl http://localhost:8000/v1/metrics"
    echo "  3. View docs: open http://localhost:8000/docs"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please review the output above.${NC}"
    echo ""
    echo "Common fixes:"
    echo "  - Database: cd infra/docker && docker-compose up -d db"
    echo "  - Dependencies: uv sync"
    echo "  - See QA_CHECKLIST.md for detailed troubleshooting"
    exit 1
fi

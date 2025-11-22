# Business Claim Portal - Deployment Guide

**Created**: November 12, 2025 @ 6:20 PM MST
**For**: Saturday Open House (Nov 15, 2025)
**Status**: ✅ Ready to deploy

---

## What Was Built

A **1-2 minute business claim form** that fits into your existing BayanLab FastAPI architecture:

- ✅ Simple, professional web form
- ✅ Minimal fields (owner info + business essentials)
- ✅ Saves to PostgreSQL database
- ✅ Rate-limited API endpoint (10 submissions/min)
- ✅ Mobile-responsive design
- ✅ No separate frontend repo needed

---

## Files Created/Modified

### New Files
1. **[backend/sql/025_business_claims.sql](backend/sql/025_business_claims.sql)** - Database table for submissions
2. **[backend/services/api_service/static/claim.html](backend/services/api_service/static/claim.html)** - Claim form (gradient purple design)

### Modified Files
1. **[backend/services/api_service/main.py](backend/services/api_service/main.py)**
   - Added `POST /v1/businesses/claim` endpoint
   - Added `GET /claim` to serve the form
   - Rate limiting: 10 submissions/minute per IP

2. **[backend/services/common/config.py](backend/services/common/config.py)**
   - Added Google API keys to Settings model

---

## Form Fields (1-2 min to complete)

### Required
- Owner Name
- Owner Email
- Business Name
- City
- State

### Optional
- Owner Phone
- Business Website
- Services/Description

---

## Local Testing ✅ Complete

```bash
# API is running on:
http://localhost:8000

# Form accessible at:
http://localhost:8000/claim

# Test submission:
curl -X POST http://localhost:8000/v1/businesses/claim \
  -H "Content-Type: application/json" \
  -d '{
    "owner_name": "John Smith",
    "owner_email": "john@example.com",
    "business_name": "ABC Construction",
    "business_city": "Denver",
    "business_state": "CO",
    "submitted_from": "open_house"
  }'
```

---

## Deployment Options

### Option 1: Saturday Quick Deploy (ngrok - Temporary)

**Use for**: Saturday open house only
**Time**: 2 minutes
**Cost**: Free

```bash
./deploy-ngrok.sh
```

You'll get a URL like: `https://abc123.ngrok.io`
Form will be at: `https://abc123.ngrok.io/claim`

**Pros**: Works immediately, no setup
**Cons**: Temporary URL, laptop must stay on

---

### Option 2: Production Deploy (Vercel + Neon - Permanent)

**Use for**: Long-term production
**Time**: 20 minutes
**Cost**: $0/month (free forever)

```bash
./deploy-vercel.sh
```

Then configure custom domain: `claim.prowasl.com`

**See**: [VERCEL_NEON_DEPLOY.md](VERCEL_NEON_DEPLOY.md) for full guide

---

## For Saturday Open House

### 1. Test Form (NOW)
Open http://localhost:8000/claim in your browser and submit a test business.

### 2. Expose API (Thursday/Friday)
```bash
# Option A: ngrok (easiest)
ngrok http 8000

# Option B: localtunnel
npx localtunnel --port 8000
```

### 3. Create QR Code (Friday)
1. Get your public URL (from ngrok/localtunnel)
2. Generate QR code: https://www.qr-code-generator.com/
3. QR code should point to: `https://YOUR_URL/claim`
4. Print multiple copies (tablefront, handouts)

### 4. Saturday Setup
- **Laptop**: Keep API running on your laptop
- **WiFi**: Ensure stable connection at venue
- **Backup**: Have Google Form as backup if API goes down

---

## View Submissions

### During Event (CLI)
```bash
# View all submissions
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone \
  -c "SELECT owner_name, business_name, business_city, submitted_at FROM business_claim_submissions ORDER BY submitted_at DESC;"

# Count submissions
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone \
  -c "SELECT COUNT(*) FROM business_claim_submissions;"
```

### After Event (Export to CSV)
```bash
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone \
  -c "\copy (SELECT * FROM business_claim_submissions) TO 'open_house_submissions.csv' CSV HEADER"
```

---

## Database Schema

Table: `business_claim_submissions`

| Column | Type | Description |
|--------|------|-------------|
| claim_id | UUID | Unique submission ID |
| owner_name | VARCHAR(300) | Owner's full name |
| owner_email | VARCHAR(255) | Owner's email |
| owner_phone | VARCHAR(50) | Owner's phone (optional) |
| business_name | VARCHAR(300) | Business name |
| business_city | VARCHAR(100) | City |
| business_state | VARCHAR(2) | State code (CO, TX, etc.) |
| business_website | VARCHAR(1000) | Website URL (optional) |
| business_description | TEXT | Services offered (optional) |
| submitted_at | TIMESTAMPTZ | Submission timestamp |
| submitted_from | VARCHAR(50) | Source: 'web', 'open_house', etc. |
| status | VARCHAR(50) | 'pending', 'approved', 'imported' |

---

## API Endpoints

### GET /claim
Serves the HTML form

### POST /v1/businesses/claim
Submit a business claim

**Request Body:**
```json
{
  "owner_name": "John Smith",
  "owner_email": "john@example.com",
  "owner_phone": "(303) 555-1234",
  "business_name": "ABC Construction",
  "business_city": "Denver",
  "business_state": "CO",
  "business_website": "https://example.com",
  "business_description": "Home remodeling, kitchen renovations",
  "submitted_from": "open_house"
}
```

**Response:**
```json
{
  "claim_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Thank you! Your business has been submitted for review."
}
```

**Rate Limit**: 10 requests per minute per IP

---

## Troubleshooting

### Form won't load
```bash
# Check if API is running
curl http://localhost:8000/healthz

# Restart API
kill $(lsof -ti:8000)
DATABASE_URL="postgresql+asyncpg://bayan:bayan@localhost:5433/bayan_backbone" \
DATABASE_URL_SYNC="postgresql://bayan:bayan@localhost:5433/bayan_backbone" \
uv run uvicorn backend.services.api_service.main:app --host 0.0.0.0 --port 8000
```

### Database connection error
```bash
# Check if database is running
docker ps | grep postgres

# If not running on 5433, check port 5432
PGPASSWORD=bayan psql -h localhost -p 5432 -U bayan -d bayan_backbone -c "SELECT 1"
```

### Form submits but doesn't save
```bash
# Check database table exists
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c "\dt business_claim*"

# If table missing, run migration
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -f backend/sql/025_business_claims.sql
```

---

## Post-Event Workflow

### 1. Export Submissions
```bash
PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone \
  -c "\copy (SELECT * FROM business_claim_submissions WHERE submitted_from='open_house') TO 'open_house_nov15.csv' CSV HEADER"
```

### 2. Review & Approve
- Open CSV in Excel/Google Sheets
- Remove duplicates/spam
- Verify email addresses

### 3. Enrich with Google Places API
```bash
uv run python scripts/verify_and_enrich.py \
  --input open_house_nov15.csv \
  --output open_house_enriched.csv
```

### 4. Import to Business Canonical
```sql
-- After enrichment, import approved businesses
INSERT INTO business_canonical (
  name, category, address_city, address_state,
  website, phone, email, source, region
)
SELECT
  business_name,
  'service'::business_category,
  business_city,
  business_state,
  business_website,
  owner_phone,
  owner_email,
  'claim_submission'::business_source,
  'CO'
FROM business_claim_submissions
WHERE status = 'approved' AND business_id IS NULL;
```

---

## Future Enhancements (Post-Saturday)

### Week of Nov 18-22
- [ ] Deploy to production (Railway/Fly.io)
- [ ] Configure custom domain (`claim.prowasl.com`)
- [ ] Add email confirmation for submissions
- [ ] Build admin dashboard to review submissions

### December
- [ ] Add photo upload for business logo
- [ ] Add "claim existing business" flow
- [ ] Integrate with ProWasl app API

---

## Quick Reference

| What | URL/Command |
|------|-------------|
| **Form (local)** | http://localhost:8000/claim |
| **API health** | http://localhost:8000/healthz |
| **API docs** | http://localhost:8000/docs |
| **View submissions** | `psql ... -c "SELECT * FROM business_claim_submissions;"` |
| **Export CSV** | `psql ... -c "\copy (...) TO 'file.csv' CSV HEADER"` |
| **Restart API** | `kill $(lsof -ti:8000) && uv run uvicorn ...` |

---

## Support

- **Code**: `/Users/hfox/Developments/bayanlab`
- **Database**: Port 5433, user `bayan`, pass `bayan`, db `bayan_backbone`
- **Logs**: API logs print to terminal when running

---

**Ready to go for Saturday!** 🚀

Test the form now, set up ngrok tomorrow, print QR codes Friday.

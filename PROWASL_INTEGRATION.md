# BayanLab → ProWasl Integration Guide

**Last Updated:** November 13, 2025

## Purpose

This document defines how **BayanLab** (community data backbone) feeds business data to **ProWasl** (consumer marketplace). BayanLab remains the authoritative source for business data collection, enrichment, and analytics. ProWasl consumes this data to power its directory and marketplace features.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        BayanLab                             │
│  (Data Collection, Enrichment, Analytics)                   │
│                                                             │
│  ┌─────────────────┐      ┌──────────────────┐            │
│  │ Claim Portal    │      │ Enrichment       │            │
│  │ claim.prowasl   │─────▶│ Pipeline         │            │
│  │ .com            │      │ (Google Places,  │            │
│  └─────────────────┘      │  Custom Search)  │            │
│                            └──────────────────┘            │
│                                     │                       │
│                            ┌────────▼─────────┐            │
│                            │ business_        │            │
│                            │ canonical        │            │
│                            │ (Neon PostgreSQL)│            │
│                            └────────┬─────────┘            │
│                                     │                       │
│                            ┌────────▼─────────┐            │
│                            │ Sync API         │            │
│                            │ /v1/businesses   │            │
│                            │ /sync            │            │
│                            └────────┬─────────┘            │
└─────────────────────────────────────┼───────────────────────┘
                                      │
                                      │ HTTPS/Webhooks
                                      │
┌─────────────────────────────────────▼───────────────────────┐
│                        ProWasl                              │
│  (Consumer Directory, Quotes, Reviews, Marketplace)         │
│                                                             │
│  ┌──────────────────┐      ┌──────────────────┐           │
│  │ Sync Worker      │      │ provider_        │           │
│  │ (Supabase Edge   │─────▶│ listings         │           │
│  │  Function)       │      │ (Supabase)       │           │
│  └──────────────────┘      └──────────────────┘           │
│                                     │                       │
│                            ┌────────▼─────────┐            │
│                            │ Next.js App      │            │
│                            │ - Directory      │            │
│                            │ - Quotes         │            │
│                            │ - Reviews        │            │
│                            └──────────────────┘            │
└─────────────────────────────────────────────────────────────┘
```

---

## Integration Options

### Option 1: Real-Time API Sync (Recommended for MVP)
**How it works:**
- BayanLab exposes read-only API: `GET /v1/businesses/sync`
- ProWasl calls this API periodically (every 5 minutes via cron)
- ProWasl Supabase Edge Function syncs to `provider_listings` table

**Pros:**
- ✅ Simple to implement
- ✅ BayanLab stays authoritative
- ✅ No database coupling
- ✅ Easy to debug

**Cons:**
- ❌ 5-minute delay for new listings
- ❌ API rate limits needed

**Implementation Time:** 2-3 hours

### Option 2: Webhook Push (Real-Time)
**How it works:**
- When BayanLab approves a business, it POSTs to ProWasl webhook
- ProWasl receives webhook → upserts to `provider_listings`
- Webhook includes signature for security

**Pros:**
- ✅ Real-time updates (instant)
- ✅ No polling overhead
- ✅ Event-driven

**Cons:**
- ❌ More complex (webhook verification, retry logic)
- ❌ Requires both systems online

**Implementation Time:** 4-5 hours

### Option 3: Shared Database View (Advanced)
**How it works:**
- ProWasl connects to BayanLab's Neon database (read-only)
- ProWasl reads directly from `business_canonical` view
- No data duplication

**Pros:**
- ✅ Always in sync (no delay)
- ✅ No API needed

**Cons:**
- ❌ Tight coupling (database schema changes break ProWasl)
- ❌ Security risk (need read-only user)
- ❌ Can't customize ProWasl schema easily

**Implementation Time:** 1-2 hours (but risky)

---

## Recommended Approach: Option 1 (API Sync)

Start with **Option 1** for Saturday's launch, then upgrade to **Option 2** (webhooks) later when you have more businesses.

---

## Data Mapping

### BayanLab Schema → ProWasl Schema

| BayanLab (`business_canonical`) | ProWasl (`provider_listings`) | Notes |
|--------------------------------|------------------------------|-------|
| `business_id` (UUID) | `bayanlab_id` (UUID) | Foreign key reference |
| `business_name` | `business_name` | Direct copy |
| `business_city` | Extract from `address` | Parse city from address |
| `business_state` | Extract from `address` | Parse state |
| `business_industry` | Map to `categories[]` | See industry mapping below |
| `business_website` | `website` | Direct copy |
| `business_description` | `about` | Direct copy |
| `owner_email` | Link to `profiles.id` | Create auth user if needed |
| `owner_phone` | `phone` | Direct copy |
| `muslim_owned` | `badges.muslim_owned` | Boolean → JSONB |
| `latitude`, `longitude` | `geom` (PostGIS Point) | `ST_MakePoint(lon, lat)` |
| `google_place_id` | `metadata.google_place_id` | Store in JSONB |
| N/A | `owner_id` (UUID) | Create/link Supabase auth user |
| N/A | `status` | Set to `'approved'` (pre-vetted) |
| N/A | `service_radius_km` | Default to `15` |
| N/A | `mosque_ids[]` | Assign based on city/state |

### Industry → Category Mapping

BayanLab captures free-form `business_industry`. ProWasl uses predefined categories for filtering.

| BayanLab Industry | ProWasl Categories |
|-------------------|-------------------|
| Construction & Home Services | `['Construction', 'Home Services']` |
| Consulting | `['Consulting']` |
| Real Estate | `['Real Estate']` |
| Healthcare | `['Healthcare']` |
| Legal Services | `['Legal']` |
| Finance & Accounting | `['Finance', 'Accounting']` |
| Food & Restaurant | `['Food & Dining', 'Catering']` |
| Retail & E-commerce | `['Retail', 'E-commerce']` |
| Technology & IT | `['Technology', 'IT Services']` |
| Education & Tutoring | `['Education', 'Tutoring']` |
| Marketing & Design | `['Marketing', 'Design']` |
| Other | `['General Services']` |

---

## API Specification

### Endpoint: `GET /v1/businesses/sync`

**Purpose:** Fetch businesses for ProWasl directory sync.

**Query Parameters:**
- `updated_since` (optional, ISO8601 datetime): Only return businesses updated after this timestamp
- `state` (optional, string): Filter by state code (e.g., `CO`, `TX`)
- `limit` (optional, int, default=100): Max records per request
- `offset` (optional, int, default=0): Pagination offset

**Response Format:**
```json
{
  "businesses": [
    {
      "business_id": "550e8400-e29b-41d4-a716-446655440000",
      "business_name": "Halal Corner Market",
      "business_industry": "Food & Restaurant",
      "business_description": "Grocery store specializing in halal meat and Middle Eastern products",
      "business_website": "https://halalcorner.com",
      "business_city": "Denver",
      "business_state": "CO",
      "business_address": "1234 Main St, Denver, CO 80202",
      "latitude": 39.7392,
      "longitude": -104.9903,
      "owner_name": "Ahmed Hassan",
      "owner_email": "ahmed@halalcorner.com",
      "owner_phone": "+1-303-555-0123",
      "muslim_owned": true,
      "google_place_id": "ChIJxxxxxx",
      "google_rating": 4.5,
      "google_review_count": 127,
      "business_hours": {
        "monday": "9:00-21:00",
        "tuesday": "9:00-21:00",
        "wednesday": "9:00-21:00",
        "thursday": "9:00-21:00",
        "friday": "9:00-22:00",
        "saturday": "9:00-22:00",
        "sunday": "10:00-20:00"
      },
      "photos": [
        "https://storage.example.com/businesses/550e8400.../photo1.jpg"
      ],
      "status": "approved",
      "updated_at": "2025-11-13T10:30:00Z"
    }
  ],
  "pagination": {
    "total": 250,
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

**Authentication:**
- API Key in header: `X-API-Key: <prowasl_api_key>`
- Rate limit: 60 requests/minute

**Implementation in BayanLab:**
```python
# backend/services/api_service/main.py

@app.get("/v1/businesses/sync")
@limiter.limit("60/minute")
async def sync_businesses(
    request: Request,
    updated_since: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync endpoint for ProWasl directory

    Returns approved businesses from business_canonical table
    """
    # Verify API key
    api_key = request.headers.get("X-API-Key")
    if api_key != os.getenv("PROWASL_API_KEY"):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Build query
    query = """
        SELECT
            business_id,
            business_name,
            business_industry,
            business_description,
            business_website,
            business_city,
            business_state,
            business_address,
            latitude,
            longitude,
            owner_name,
            owner_email,
            owner_phone,
            muslim_owned,
            google_place_id,
            google_rating,
            google_review_count,
            business_hours,
            photos,
            status,
            updated_at
        FROM business_canonical
        WHERE status = 'approved'
    """

    params = {}

    if updated_since:
        query += " AND updated_at > :updated_since"
        params['updated_since'] = updated_since

    if state:
        query += " AND business_state = :state"
        params['state'] = state.upper()

    # Count total
    count_query = f"SELECT COUNT(*) FROM ({query}) AS t"
    count_result = await db.execute(text(count_query), params)
    total = count_result.scalar()

    # Paginate
    query += " ORDER BY updated_at DESC LIMIT :limit OFFSET :offset"
    params['limit'] = limit
    params['offset'] = offset

    result = await db.execute(text(query), params)
    businesses = [dict(row._mapping) for row in result]

    return {
        "businesses": businesses,
        "pagination": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(businesses) < total
        }
    }
```

---

## ProWasl Implementation

### Step 1: Create Supabase Edge Function

**File:** `supabase/functions/sync-bayanlab/index.ts`

```typescript
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const BAYANLAB_API = 'https://claim.prowasl.com'
const BAYANLAB_API_KEY = Deno.env.get('BAYANLAB_API_KEY')!

interface BayanlabBusiness {
  business_id: string
  business_name: string
  business_industry: string
  business_description: string | null
  business_website: string | null
  business_city: string
  business_state: string
  business_address: string | null
  latitude: number | null
  longitude: number | null
  owner_email: string
  owner_phone: string | null
  muslim_owned: boolean
  google_place_id: string | null
  status: string
  updated_at: string
}

function mapIndustryToCategories(industry: string | null): string[] {
  const mapping: Record<string, string[]> = {
    'Construction & Home Services': ['Construction', 'Home Services'],
    'Consulting': ['Consulting'],
    'Real Estate': ['Real Estate'],
    'Healthcare': ['Healthcare'],
    'Legal Services': ['Legal'],
    'Finance & Accounting': ['Finance', 'Accounting'],
    'Food & Restaurant': ['Food & Dining', 'Catering'],
    'Retail & E-commerce': ['Retail', 'E-commerce'],
    'Technology & IT': ['Technology', 'IT Services'],
    'Education & Tutoring': ['Education', 'Tutoring'],
    'Marketing & Design': ['Marketing', 'Design'],
  }

  return mapping[industry || ''] || ['General Services']
}

Deno.serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  // Fetch latest sync timestamp
  const { data: lastSync } = await supabase
    .from('sync_log')
    .select('synced_at')
    .order('synced_at', { ascending: false })
    .limit(1)
    .single()

  const updatedSince = lastSync?.synced_at || '2025-01-01T00:00:00Z'

  // Fetch from BayanLab
  const response = await fetch(
    `${BAYANLAB_API}/v1/businesses/sync?updated_since=${updatedSince}&limit=100`,
    {
      headers: { 'X-API-Key': BAYANLAB_API_KEY }
    }
  )

  if (!response.ok) {
    return new Response(`BayanLab API error: ${response.status}`, { status: 500 })
  }

  const data = await response.json()
  const businesses: BayanlabBusiness[] = data.businesses

  let synced = 0
  let errors = 0

  for (const biz of businesses) {
    try {
      // Find or create owner profile
      let ownerId: string | null = null

      const { data: existingProfile } = await supabase
        .from('profiles')
        .select('id')
        .eq('email', biz.owner_email)
        .single()

      if (existingProfile) {
        ownerId = existingProfile.id
      } else {
        // Create auth user (email only, no password - they'll reset on first login)
        const { data: authUser, error: authError } = await supabase.auth.admin.createUser({
          email: biz.owner_email,
          email_confirm: true,
          user_metadata: {
            full_name: biz.owner_name || '',
            phone: biz.owner_phone || ''
          }
        })

        if (authError) {
          console.error(`Failed to create user for ${biz.owner_email}:`, authError)
          errors++
          continue
        }

        ownerId = authUser.user.id

        // Create profile
        await supabase.from('profiles').insert({
          id: ownerId,
          role: 'provider',
          full_name: biz.owner_name || '',
          phone: biz.owner_phone || ''
        })
      }

      // Upsert provider listing
      const geom = (biz.latitude && biz.longitude)
        ? `SRID=4326;POINT(${biz.longitude} ${biz.latitude})`
        : null

      const { error: upsertError } = await supabase
        .from('provider_listings')
        .upsert({
          bayanlab_id: biz.business_id,
          owner_id: ownerId,
          business_name: biz.business_name,
          categories: mapIndustryToCategories(biz.business_industry),
          about: biz.business_description,
          website: biz.business_website,
          phone: biz.owner_phone,
          address: biz.business_address,
          geom: geom,
          badges: {
            muslim_owned: biz.muslim_owned,
            community_verified: false,
            licensed: false
          },
          status: 'approved', // Pre-vetted by BayanLab
          service_radius_km: 15,
          metadata: {
            google_place_id: biz.google_place_id,
            bayanlab_synced_at: new Date().toISOString()
          }
        }, {
          onConflict: 'bayanlab_id'
        })

      if (upsertError) {
        console.error(`Failed to upsert listing ${biz.business_id}:`, upsertError)
        errors++
      } else {
        synced++
      }
    } catch (err) {
      console.error(`Error processing ${biz.business_id}:`, err)
      errors++
    }
  }

  // Log sync
  await supabase.from('sync_log').insert({
    synced_at: new Date().toISOString(),
    businesses_synced: synced,
    errors: errors
  })

  return new Response(
    JSON.stringify({ synced, errors, total: businesses.length }),
    { headers: { 'Content-Type': 'application/json' } }
  )
})
```

### Step 2: Add Database Migration

**File:** `supabase/migrations/004_bayanlab_sync.sql`

```sql
-- Add bayanlab_id column to provider_listings
ALTER TABLE provider_listings
  ADD COLUMN IF NOT EXISTS bayanlab_id UUID UNIQUE,
  ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

-- Create sync log table
CREATE TABLE IF NOT EXISTS sync_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  synced_at TIMESTAMPTZ NOT NULL,
  businesses_synced INT DEFAULT 0,
  errors INT DEFAULT 0
);

CREATE INDEX idx_sync_log_time ON sync_log(synced_at DESC);

-- Add email to profiles for lookup
ALTER TABLE profiles
  ADD COLUMN IF NOT EXISTS email TEXT;

CREATE INDEX idx_profiles_email ON profiles(email);
```

### Step 3: Add Cron Job (Supabase pg_cron)

**File:** `supabase/migrations/005_sync_cron.sql`

```sql
-- Enable pg_cron extension
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule sync every 5 minutes
SELECT cron.schedule(
  'sync-bayanlab',
  '*/5 * * * *', -- Every 5 minutes
  $$
    SELECT net.http_post(
      url := 'https://your-project.supabase.co/functions/v1/sync-bayanlab',
      headers := jsonb_build_object(
        'Authorization', 'Bearer ' || current_setting('app.service_role_key')
      )
    );
  $$
);
```

### Step 4: Environment Variables

**Add to ProWasl `.env.local`:**
```bash
BAYANLAB_API_KEY=your_secret_api_key_here
```

**Add to BayanLab `.env`:**
```bash
PROWASL_API_KEY=your_secret_api_key_here
```

---

## Testing the Integration

### 1. Test BayanLab API Endpoint
```bash
curl -H "X-API-Key: your_api_key" \
  "https://claim.prowasl.com/v1/businesses/sync?limit=5"
```

### 2. Test ProWasl Edge Function
```bash
supabase functions deploy sync-bayanlab

supabase functions invoke sync-bayanlab --env-file ./supabase/.env
```

### 3. Verify Data Sync
```sql
-- In ProWasl Supabase SQL Editor
SELECT
  business_name,
  categories,
  bayanlab_id,
  metadata->>'bayanlab_synced_at' AS last_sync
FROM provider_listings
WHERE bayanlab_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 10;
```

---

## Saturday Event Workflow

1. **Saturday (Nov 15):** Businesses fill out claim.prowasl.com form
2. **Saturday evening:** You review submissions in BayanLab, approve good ones
3. **Automatic (every 5 min):** ProWasl syncs approved businesses
4. **Sunday morning:** Businesses appear in ProWasl directory automatically
5. **Email notification:** Send email to business owners: "Your listing is live at prowasl.com/provider/{id}"

---

## Future Enhancements

### Phase 2: Webhook Push (Real-Time)
When you have 100+ businesses, upgrade to webhooks for instant sync.

**BayanLab webhook trigger:**
```python
# After approving a business
async def approve_business(business_id: str):
    # ... update status to 'approved' ...

    # Send webhook to ProWasl
    webhook_url = os.getenv("PROWASL_WEBHOOK_URL")
    payload = {
        "event": "business.approved",
        "business_id": business_id,
        "timestamp": datetime.utcnow().isoformat()
    }

    signature = hmac.new(
        os.getenv("WEBHOOK_SECRET").encode(),
        json.dumps(payload).encode(),
        hashlib.sha256
    ).hexdigest()

    await httpx.post(
        webhook_url,
        json=payload,
        headers={"X-Webhook-Signature": signature}
    )
```

### Phase 3: Two-Way Sync
- Business updates their profile in ProWasl → syncs back to BayanLab
- Reviews/ratings in ProWasl → stored in BayanLab for analytics

### Phase 4: Real-Time Analytics API
- ProWasl calls BayanLab for: `GET /v1/analytics/city/{city}/trends`
- BayanLab provides insights: growth trends, popular categories, etc.

---

## Questions for LLM in ProWasl Repo

When you open this document in the ProWasl repo, ask the LLM:

> "Read PROWASL_INTEGRATION.md and implement **Option 1: API Sync** for me.
>
> Specifically:
> 1. Create the Supabase Edge Function `sync-bayanlab`
> 2. Add the database migration for `bayanlab_id` and `sync_log`
> 3. Test the sync with mock data
> 4. Set up the cron job to run every 5 minutes
>
> I already have the BayanLab API running at `https://claim.prowasl.com`. The API key is in my `.env.local` file as `BAYANLAB_API_KEY`.
>
> Let me know if you need any clarification on the data mapping or schema."

---

## Support

- **BayanLab repo:** `/Users/hfox/Developments/bayanlab`
- **ProWasl repo:** `/Users/hfox/Developments/prowasl`
- **BayanLab API docs:** This file + `backend/services/api_service/main.py`
- **ProWasl schema:** `supabase/migrations/001_ddl.sql`

---

**Next Steps:**
1. ✅ Copy this file to ProWasl repo: `cp PROWASL_INTEGRATION.md /Users/hfox/Developments/prowasl/docs/`
2. Open ProWasl repo in new terminal
3. Ask LLM to implement Option 1 (API Sync)
4. Test sync with Saturday's claim submissions

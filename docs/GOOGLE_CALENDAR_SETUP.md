# Google Calendar API Setup Guide

This guide walks you through setting up Google Calendar API access for BayanLab Backbone using a service account. This allows masjids to share their private Google Calendars with BayanLab without making them public.

## Why Use Google Calendar API?

**Advantages over public ICS URLs:**
- ✅ **Privacy**: Calendars remain private, not publicly searchable
- ✅ **Reliability**: Direct API access, more stable than ICS feeds
- ✅ **Control**: Masjid can revoke access anytime
- ✅ **Better data**: Richer event metadata from API

**When to use public ICS instead:**
- Masjid is comfortable with public calendar
- Simpler setup (no Google Cloud configuration)
- One-time or testing scenarios

## Prerequisites

- Google Cloud account (free)
- Access to Google Cloud Console
- 10 minutes

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a Project"** → **"New Project"**
3. Enter project details:
   - **Project name**: `BayanLab Calendar Access`
   - **Organization**: (leave as-is if personal account)
4. Click **"Create"**
5. Wait for project creation (10-30 seconds)

## Step 2: Enable Google Calendar API

1. In Google Cloud Console, select your new project
2. Go to **APIs & Services** → **Library**
3. Search for **"Google Calendar API"**
4. Click on it, then click **"Enable"**
5. Wait for API to be enabled (5-10 seconds)

## Step 3: Create Service Account

1. Go to **APIs & Services** → **Credentials**
2. Click **"Create Credentials"** → **"Service Account"**
3. Fill in service account details:
   - **Service account name**: `bayanlab-calendar`
   - **Service account ID**: `bayanlab-calendar` (auto-filled)
   - **Description**: `Service account for reading shared masjid calendars`
4. Click **"Create and Continue"**
5. **Skip** role assignment (click "Continue")
6. **Skip** user access (click "Done")

## Step 4: Create and Download Service Account Key

1. On the **Credentials** page, find your new service account
2. Click on the service account email (e.g., `bayanlab-calendar@project-id.iam.gserviceaccount.com`)
3. Go to the **Keys** tab
4. Click **"Add Key"** → **"Create new key"**
5. Select **JSON** format
6. Click **"Create"**
7. **Save the downloaded JSON file securely!** This is your only copy.

**IMPORTANT**:
- Keep this file secret (never commit to git!)
- Name it something recognizable: `bayanlab-calendar-credentials.json`
- Store it outside your repository or in `.gitignore`

## Step 5: Configure BayanLab Backbone

### Option A: Local Development

```bash
# 1. Move credentials to a secure location
mv ~/Downloads/bayanlab-*.json ~/.config/bayanlab/calendar-credentials.json

# 2. Update .env file
echo "GOOGLE_APPLICATION_CREDENTIALS=$HOME/.config/bayanlab/calendar-credentials.json" >> .env

# 3. Verify configuration
cat .env | grep GOOGLE_APPLICATION_CREDENTIALS
```

### Option B: Docker/Production

```bash
# 1. Copy credentials to project
mkdir -p infra/secrets
cp ~/Downloads/bayanlab-*.json infra/secrets/calendar-credentials.json

# 2. Update .env
echo "GOOGLE_APPLICATION_CREDENTIALS=/app/infra/secrets/calendar-credentials.json" >> .env

# 3. Mount secrets in docker-compose.yml
# Add this to the pipeline and api services:
#   volumes:
#     - ../infra/secrets:/app/infra/secrets:ro
```

## Step 6: Copy Service Account Email

You'll need to share this email with masjid administrators:

```bash
# Find your service account email in the JSON file
grep "client_email" ~/.config/bayanlab/calendar-credentials.json

# Example output:
# "client_email": "bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com"
```

**Save this email!** You'll give it to masjids so they can share their calendars.

## Step 7: Test the Setup

```bash
# Run pipeline to verify Google Calendar API is initialized
uv run python run_pipeline.py --pipeline events

# Look for this log line:
# {"level": "INFO", "message": "Google Calendar API initialized successfully"}
```

If you see warnings about credentials not found, double-check your `GOOGLE_APPLICATION_CREDENTIALS` path.

## Onboarding a Masjid Calendar

Once setup is complete, you can onboard masjid calendars:

1. **Get the service account email** (from Step 6)
2. **Ask masjid admin** to share their Google Calendar:
   - Open Google Calendar settings
   - Find the calendar to share
   - Click "Share with specific people"
   - Add: `bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com`
   - Permission: **"See all event details"** (read-only)
   - Click "Send"

3. **Add to sources.yaml**:
```yaml
ics_sources:
  - id: "masjid_name"
    calendar_id: "masjidcalendar@gmail.com"  # The calendar email
    venue_name: "Masjid Al-Noor"
    city: "Denver"
    enabled: true
```

4. **Run pipeline**:
```bash
uv run python run_pipeline.py --pipeline events
```

## Troubleshooting

### "Google Calendar API not initialized"
**Cause**: Credentials file not found or invalid path

**Fix**:
```bash
# Check if file exists
ls -la $GOOGLE_APPLICATION_CREDENTIALS

# Check if path is correct in .env
cat .env | grep GOOGLE_APPLICATION_CREDENTIALS

# Verify JSON is valid
python -c "import json; json.load(open('path/to/credentials.json'))"
```

### "Calendar not found" or "403 Forbidden"
**Cause**: Calendar not shared with service account

**Fix**:
1. Verify the calendar is shared with the exact service account email
2. Check permission is "See all event details" (not "See only free/busy")
3. Wait 1-2 minutes after sharing (Google needs time to propagate)

### "importerror: No module named google.oauth2"
**Cause**: Google Calendar API dependencies not installed

**Fix**:
```bash
uv sync
```

## Security Best Practices

1. **Never commit credentials to git**:
```bash
# Add to .gitignore
echo "infra/secrets/" >> .gitignore
echo "*-credentials.json" >> .gitignore
```

2. **Rotate keys periodically**:
- Delete old service account keys every 90 days
- Create new keys in Google Cloud Console
- Update `GOOGLE_APPLICATION_CREDENTIALS` path

3. **Limit access**:
- Only grant read-only calendar access
- Use separate service accounts for production/staging if needed

4. **Monitor usage**:
- Check Google Cloud Console → APIs & Services → Dashboard
- Review Calendar API quota usage monthly

## Next Steps

- See [MASJID_ONBOARDING.md](MASJID_ONBOARDING.md) for masjid-facing documentation
- Review [sources.yaml](../backend/configs/sources.yaml) for configuration examples
- Check [QUICKSTART.md](../QUICKSTART.md) for running the pipeline

---

**Note**: Service accounts do NOT require OAuth user consent or verification for read-only Calendar API access. Setup takes effect immediately.

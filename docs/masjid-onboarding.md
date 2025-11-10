# Masjid Calendar Onboarding Guide

**For Masjid Administrators and Event Coordinators**

Welcome! This guide explains how to share your Google Calendar with BayanLab so your community events can appear in The Ummah app and other community platforms.

## What is BayanLab?

BayanLab (*BAYĀN = clarity*) aggregates Muslim community events and halal businesses across Colorado and beyond. We collect event data from masjid calendars and make it available through:
- **The Ummah** mobile app (events)
- **ProWasl** (halal businesses)
- Public API for other community tools

## Your Privacy Matters

🔒 **Your calendar stays private.** We don't make your calendar public. You simply share it with our service account (like sharing with a specific person). You can:
- ✅ Revoke access anytime
- ✅ Control what we see (only shared calendars, not your entire account)
- ✅ Keep your calendar private from public search engines

## Two Ways to Share Your Calendar

### Option 1: Share with Service Account (Recommended)

**Best for:**
- Masjids who want to keep calendars private
- Organizations with Google Workspace accounts
- Better reliability and data quality

**Steps:**

1. **Open Google Calendar**
   - Go to [calendar.google.com](https://calendar.google.com)
   - Sign in with the account that manages your masjid calendar

2. **Find the calendar to share**
   - In the left sidebar, find your masjid's calendar
   - Hover over it and click the three dots (**⋮**)
   - Select **"Settings and sharing"**

3. **Share with BayanLab**
   - Scroll down to **"Share with specific people or groups"**
   - Click **"Add people and groups"**
   - Enter this email address:
     ```
     bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com
     ```
   - Set permission to: **"See all event details"**
   - Click **"Send"**

4. **Confirm your calendar ID**
   - Scroll down to **"Integrate calendar"**
   - Find the **"Calendar ID"** (looks like an email address)
   - Copy it (e.g., `masjiddenver@gmail.com` or `randomstring@group.calendar.google.com`)
   - Send it to BayanLab via email: `info@bayanlab.com`

5. **Done!**
   - Your events will appear in The Ummah app within 2-6 hours
   - You'll receive a confirmation email from BayanLab

### Option 2: Make Calendar Public (Alternative)

**Best for:**
- Masjids comfortable with public calendars
- Simpler setup (no service account sharing)
- One-time or testing scenarios

**Steps:**

1. **Open Google Calendar settings**
   - Go to your calendar's **"Settings and sharing"**

2. **Make calendar public**
   - Check **"Make available to public"**
   - Ensure **"See all event details"** is selected

3. **Get the public URL**
   - Scroll to **"Integrate calendar"**
   - Copy the **"Public address in iCal format"** URL
   - Send it to BayanLab via email: `info@bayanlab.com`

**Note**: This makes your calendar searchable by anyone. We recommend Option 1 for privacy.

## What Information Do We Collect?

From your shared calendar, we collect:
- ✅ Event title
- ✅ Event description (if provided)
- ✅ Start and end times
- ✅ Location/venue information
- ✅ Event URL (if provided)

We **DO NOT** collect:
- ❌ Attendee information
- ❌ Email addresses
- ❌ Private event notes
- ❌ Other calendars you haven't shared

## Event Best Practices

To help your events display well in the app:

### 1. Use Clear Event Titles
✅ **Good**: "Jumu'ah Prayer - Second Khutbah"
❌ **Avoid**: "Friday thing"

### 2. Include Location Details
✅ **Good**: Add full masjid address in location field
❌ **Avoid**: Just "Main Hall"

### 3. Add Descriptions
✅ **Good**: Brief description, speaker name, registration link
❌ **Avoid**: Leaving description empty

### 4. Set Correct Times
✅ **Good**: Use actual event times (e.g., 1:30 PM - 2:00 PM for Khutbah)
❌ **Avoid**: All-day events for specific-time activities

### 5. Recurring Events
✅ **Good**: Use Google Calendar's recurring event feature
❌ **Avoid**: Creating individual events for every recurrence

## Sample Event

**Title**: Jumu'ah (Friday Prayer) - Second Khutbah

**Time**: Every Friday, 1:30 PM - 2:00 PM (Mountain Time)

**Location**: Islamic Center of Northern Colorado, 2555 S Shields St, Fort Collins, CO 80526

**Description**: Join us for Friday congregational prayer. Khutbah in English and Arabic. Brothers and sisters sections available. Wudu facilities on-site.

**URL**: https://icnoco.org/jumah

## Revoking Access

If you need to stop sharing your calendar:

1. Go to Google Calendar → Your calendar's **"Settings and sharing"**
2. Under **"Share with specific people"**, find:
   ```
   bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com
   ```
3. Click the **X** to remove access
4. Email us at `info@bayanlab.com` to confirm removal

Your events will be removed from our system within 72 hours.

## Frequently Asked Questions

### Do I need a paid Google Workspace account?
No! Free Gmail accounts work fine.

### How often do you check for updates?
We refresh event calendars every 2-6 hours. Updates typically appear within that timeframe.

### Can I share multiple calendars?
Yes! Just repeat the sharing process for each calendar. Each calendar will need its own entry in our system.

### What if I have events in both English and Arabic?
Perfect! Include both languages in the event title and description. Our app supports multilingual content.

### Do you support recurring events?
Yes! Google Calendar's recurring events work automatically. Create the recurrence pattern in Google Calendar and we'll fetch all instances.

### What if I don't use Google Calendar?
We're working on support for other platforms. For now:
- **Apple Calendar/iCloud**: Export to .ics and share the public URL
- **Outlook**: Export to .ics and email it to us monthly
- **Manual entry**: Email us your events and we'll add them

### Can I see my events in your system?
Yes! Check The Ummah app or visit our public API:
```
https://api.bayanlab.com/v1/events?region=CO&city=Denver
```

### How do I update or cancel an event?
Just update or delete it in your Google Calendar. Changes sync automatically within 2-6 hours.

### Is this service free?
Yes! BayanLab is a community service funded by donations.

## Need Help?

**Email**: info@bayanlab.com
**Subject line**: "Calendar Sharing - [Your Masjid Name]"

Please include:
- Your masjid name
- Your calendar ID (if Option 1)
- Your public ICS URL (if Option 2)
- Best contact email for confirmations

We typically respond within 1-2 business days.

## Example Email to BayanLab

```
Subject: Calendar Sharing - Masjid Al-Noor

Hi BayanLab team,

I'd like to share our calendar with your platform.

Masjid Name: Masjid Al-Noor
City: Denver, CO
Calendar ID: masjidalnoordenver@gmail.com
Contact Email: admin@masjidalnoor.org

I've already shared the calendar with:
bayanlab-calendar@bayanlab-477720.iam.gserviceaccount.com

Please confirm once our events are live.

JazakAllah khair,
[Your Name]
Event Coordinator, Masjid Al-Noor
```

---

**JazakAllah Khair** for helping make our community events more accessible!

*Last updated: November 9, 2025*

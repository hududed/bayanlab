# Business Validation Tool - Team Guide

Internal tool for the ProWasl team to validate and add Muslim-owned businesses.

## Access

**URL**: `https://claim.prowasl.com/validate?key=YOUR_TEAM_KEY`

Bookmark this URL - the key is required to access the tool.

## Overview

The validation tool has two workflows:

### Track 1: Validate Imported Businesses
Businesses imported from spreadsheets (MBC, MDA, etc.) start as **unverified**.
- Review the business info, website, contact details
- Click **OK** to move to staging, or **Reject** if not valid

### Track 2: Add New Discoveries
Businesses found on Facebook, LinkedIn, etc. can be added directly.
- Fill out the form with business details
- Click **Add to Staging** - they go directly to staging queue

### Final Approval (Admin Only)
Only admins can approve businesses from staging to approved.
- Select businesses in the staging queue
- Enter admin password when prompted
- Approved businesses get a discovery email sent automatically

## UI Sections

### 1. Add New Discovery Form
Use this when you find a new business on social media.

**Required fields:**
- Business Name
- City
- State (defaults to CO)
- Discovery Source (Facebook, LinkedIn, etc.)

**Optional but helpful:**
- Contact Name & Email
- Business Phone
- Website
- Street Address & ZIP
- Industry
- Source URL (link to FB post, etc.)
- Business Description (copy/paste from FB)

### 2. All Businesses (Dedup Check)
Search existing businesses to avoid duplicates.
- Search by name
- Filter by status (approved, staging, unverified)
- Hover over rows to see more details

### 3. Unverified Queue
Imported businesses that need validation.
- Check if website works
- Verify business is real
- **OK** = move to staging
- **Reject** = mark as rejected

### 4. Staging Queue (Admin Section)
Businesses ready for final approval.
- Only visible/actionable by admin
- Batch select and approve
- Discovery emails sent automatically on approval

## Workflow Diagram

```
New Discovery (FB/LinkedIn)     Imported Data (CSV)
         |                              |
         v                              v
    [Add Form]                    [Unverified Queue]
         |                              |
         |                         Team validates
         |                              |
         v                              v
    +---------+                   +---------+
    | STAGING | <-----------------| STAGING |
    +---------+                   +---------+
         |
    Admin approves
         |
         v
    +----------+
    | APPROVED | --> Discovery Email Sent
    +----------+
```

## Tips

1. **Always search first** - Check the dedup table before adding a new business
2. **Include source URL** - Helps with future verification
3. **Business phone vs Owner phone** - Use business phone for FB discoveries
4. **Muslim-owned is default** - All manual discoveries default to muslim_owned=true

## Troubleshooting

**Can't access the tool?**
- Make sure you have the correct URL with `?key=` parameter
- The key is case-sensitive

**Can't approve businesses?**
- Approval requires the admin password
- Contact your admin if you need approval access

**Added a duplicate?**
- Duplicates can be rejected from the staging queue
- Search for the business to find the duplicate entry

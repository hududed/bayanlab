# Security Configuration

Last updated: November 2025

## Overview

Security hardening for BayanLab infrastructure covering prowasl.com and bayanlab.com.

---

## prowasl.com

### HTTP Security Headers
Configured in `prowasl/web/next.config.mjs`:

| Header | Value | Purpose |
|--------|-------|---------|
| X-Frame-Options | DENY | Prevents clickjacking |
| X-Content-Type-Options | nosniff | Prevents MIME sniffing |
| Referrer-Policy | strict-origin-when-cross-origin | Controls referrer info |
| Permissions-Policy | geolocation=(), microphone=(), camera=() | Restricts browser APIs |

### Cloudflare Protection
- **Rate Limiting:** 20 requests/10 seconds on `/directory` and `/provider/*`
- **Bot Fight Mode:** Enabled - challenges suspicious traffic
- **AI Labyrinth:** Enabled - traps scraper bots in honeypot maze
- **SSL/TLS:** Full mode

### robots.txt
```
User-Agent: *
Allow: /
Allow: /directory
Allow: /provider/*
Disallow: /admin/
Disallow: /steward/
Disallow: /api/
Disallow: /login
```

### Forms (Future)
- Contact form on `/provider/*` pages - no CAPTCHA yet
- Service request form at `/request/new` - no CAPTCHA yet
- Consider adding Cloudflare Turnstile or honeypot fields if spam occurs

---

## bayanlab.com

### HTTP Security Headers
Configured in `bayanlab-web/next.config.mjs`:

| Header | Value | Purpose |
|--------|-------|---------|
| X-Frame-Options | DENY | Prevents clickjacking |
| X-Content-Type-Options | nosniff | Prevents MIME sniffing |
| Referrer-Policy | strict-origin-when-cross-origin | Controls referrer info |
| Permissions-Policy | geolocation=(), microphone=(), camera=() | Restricts browser APIs |

### Cloudflare Protection
- **Rate Limiting:** 20 requests/10 seconds on `/directory` and `/docs`
- **Bot Fight Mode:** Enabled
- **AI Labyrinth:** Enabled
- **SSL/TLS:** Full mode

---

## claim.prowasl.com

Hosted on Render. Security headers should be added to the claim portal.

**TODO:** Add security headers to claim portal

---

## API Security (api.bayanlab.com)

The FastAPI backend has separate security considerations:

- **Rate Limiting:** Not implemented (relies on Cloudflare)
- **Authentication:** No auth for V1 read-only API (see ADR-012)
- **CORS:** Enabled for allowed origins
- **Input Validation:** Pydantic models validate all inputs

**TODO:** Add security headers to FastAPI responses

---

## Verification Commands

Test security headers:
```bash
# prowasl.com
curl -sI https://prowasl.com | grep -iE "x-frame|x-content|referrer|permissions"

# bayanlab.com
curl -sI https://bayanlab.com | grep -iE "x-frame|x-content|referrer|permissions"
```

Test rate limiting (will get blocked after ~20 rapid requests):
```bash
for i in {1..30}; do curl -s -o /dev/null -w "%{http_code} " https://prowasl.com/directory; done
```

---

## Known Limitations (Free Cloudflare Plan)

- Rate limit block duration: 10 seconds max (Pro plan allows longer)
- No advanced WAF rules
- No custom bot management

---

## Incident Response

If you notice scraping or abuse:

1. Check Cloudflare Analytics → Security → Events
2. Block specific IPs: Security → WAF → Tools → IP Access Rules
3. Temporarily enable "Under Attack Mode" if severe: Overview → Quick Actions

---

## Future Improvements

- [ ] Add Cloudflare Turnstile CAPTCHA to forms if spam occurs
- [ ] Add honeypot fields to contact forms
- [ ] Add security headers to claim.prowasl.com
- [ ] Add security headers to FastAPI (api.bayanlab.com)
- [ ] Consider upgrading to Cloudflare Pro if rate limiting needs improvement

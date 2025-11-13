# Render + Neon Deployment (Alternative to Vercel)

**Issue**: Vercel serverless functions have a 250 MB limit, which FastAPI + dependencies exceed.

**Solution**: Use Render (Docker-based) + Neon (PostgreSQL)

**Cost**: $0/month (truly free)
**Time**: 15 minutes

---

## Why Render Instead of Vercel?

| Feature | Render | Vercel |
|---------|--------|--------|
| **Deployment** | Docker container | Serverless function |
| **Size limit** | No limit | 250 MB (hit limit ❌) |
| **Free tier** | ✅ 750 hours/month | ✅ Unlimited |
| **Custom domain** | ✅ Free SSL | ✅ Free SSL |
| **PostgreSQL** | Use Neon (free) | Use Neon (free) |
| **Best for** | Full FastAPI apps | Lightweight APIs |

---

## Step 1: Push Code to GitHub

Make sure your latest code is on GitHub:

```bash
git add .
git commit -m "Add Render deployment config"
git push
```

---

## Step 2: Deploy to Render (10 min)

### 2.1 Create Render Account
1. Go to: https://render.com
2. Sign up with GitHub (easiest)

### 2.2 Create New Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository: `hududed/bayanlab`
3. Render will auto-detect `render.yaml`

### 2.3 Configure Service
Render reads from `render.yaml` (already created ✅), but verify:

- **Name**: bayanlab-claim-portal
- **Region**: Oregon (closest to Denver)
- **Runtime**: Docker
- **Plan**: Free
- **Dockerfile Path**: `./infra/docker/Dockerfile`

### 2.4 Add Environment Variables
In Render dashboard, add these environment variables:

1. `DATABASE_URL` = `postgresql+asyncpg://[your-neon-url]`
2. `DATABASE_URL_SYNC` = `postgresql://[your-neon-url]`
3. `API_HOST` = `0.0.0.0`
4. `API_PORT` = `8000`
5. `LOG_LEVEL` = `INFO`

### 2.5 Deploy
Click "Create Web Service"

Render will:
1. Clone your repo
2. Build Docker image
3. Deploy to https://bayanlab-claim-portal.onrender.com
4. Run health checks

**⏳ First deploy takes ~5-10 minutes**

---

## Step 3: Add Custom Domain (5 min)

### 3.1 Add Domain in Render
1. Go to your service dashboard
2. Settings → Custom Domain
3. Add: `claim.prowasl.com`

### 3.2 Update DNS
Render will provide a CNAME target. Add this to your DNS:

```
Type: CNAME
Name: claim
Value: bayanlab-claim-portal.onrender.com
TTL: 3600
```

### 3.3 Verify SSL
Render automatically provisions SSL certificate (takes ~5 min)

---

## Step 4: Test Deployment

### Health Check
```bash
curl https://claim.prowasl.com/healthz
```

Expected:
```json
{
  "status": "healthy",
  "service": "bayan_backbone_api",
  "version": "1.0.0",
  "database": "connected"
}
```

### Test Claim Form
https://claim.prowasl.com/claim

---

## Render Free Tier Limits

| Resource | Limit | Notes |
|----------|-------|-------|
| **Hours** | 750/month | 24/7 uptime possible |
| **RAM** | 512 MB | Sufficient for API |
| **CPU** | Shared | No limit on compute time |
| **Build time** | 500 min/month | More than enough |
| **Bandwidth** | 100 GB/month | ~1M requests |
| **Sleep after** | 15 min inactivity | Wakes on first request (~30s) |

**For claim portal**: Free tier is perfect. 750 hours = 31 days of uptime.

---

## Auto-Deploy from GitHub

Render automatically deploys when you push to `main`:

```bash
git add .
git commit -m "Update claim form"
git push
```

Render will:
1. Detect changes
2. Build new Docker image
3. Deploy with zero downtime

---

## Troubleshooting

### Build fails
Check build logs in Render dashboard:
- Common issue: Missing dependencies
- Solution: Verify `requirements.txt` is correct

### Service won't start
Check logs for errors:
- Common issue: Database connection
- Verify `DATABASE_URL` is set correctly

### Slow to wake from sleep
- Free tier services sleep after 15 min inactivity
- First request after sleep takes ~30 seconds
- Subsequent requests are instant
- **Solution**: Upgrade to paid tier ($7/month) for always-on

---

## Cost Comparison

| Platform | Free Tier | Paid Tier |
|----------|-----------|-----------|
| **Render + Neon** | $0/month (750 hours) | $7/month (always-on) + $0 (Neon) |
| **Vercel + Neon** | ❌ Doesn't work (size limit) | N/A |
| **Railway** | ❌ No free tier anymore | $5/month + usage |
| **Fly.io** | ~$2/month (minimal usage) | $10-20/month |

---

## Quick Deploy Commands

```bash
# 1. Push to GitHub
git add .
git commit -m "Deploy to Render"
git push

# 2. Go to Render dashboard
open https://dashboard.render.com

# 3. Create new web service from GitHub repo

# 4. Add environment variables (Neon connection strings)

# 5. Deploy!
```

---

## Monitoring

### Render Dashboard
- Real-time logs
- Metrics (CPU, RAM, bandwidth)
- Deploy history
- Health check status

### View Logs
```bash
# In Render dashboard:
# Your Service → Logs (real-time stream)
```

---

## Advantages of Render

✅ **Docker support** - No size limits
✅ **Free tier** - 750 hours/month
✅ **Auto-deploy** - Push to GitHub = auto deploy
✅ **Custom domains** - Free SSL
✅ **Zero config** - `render.yaml` handles everything
✅ **Neon compatible** - Works perfectly with Neon Postgres

---

## Files Created

- ✅ `render.yaml` - Render configuration
- ✅ `RENDER_NEON_DEPLOY.md` - This guide
- ✅ Dockerfile already exists at `infra/docker/Dockerfile`

---

## ✅ Ready to Deploy

Your Neon database is already set up with all migrations ✅

Next step: Go to https://render.com and create a new web service!


# Deploying Baton

Baton uses **Socket Mode** — it connects outbound to Slack via WebSocket, so you don't need to expose a public URL or configure SSL. This makes deployment simple.

## Option 1: Railway (Recommended — Free Tier)

### Step 1: Push to GitHub
```bash
git add .
git commit -m "Production-ready Baton agent"
git push origin main
```

### Step 2: Create Railway Project
1. Go to [railway.app](https://railway.app) and sign in with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your `StackBuilder` repository

### Step 3: Set Environment Variables
In the Railway dashboard → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `SLACK_BOT_TOKEN` | `xoxb-...` |
| `SLACK_SIGNING_SECRET` | Your signing secret |
| `SLACK_APP_TOKEN` | `xapp-...` |
| `GROQ_API_KEY` | `gsk_...` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` (optional) |

### Step 4: Deploy
Railway auto-deploys on push. Check the **Deployments** tab for logs.

The `railway.json` config auto-restarts on failure (up to 10 retries).

---

## Option 2: Render (Free Tier)

### Step 1: Push to GitHub (same as above)

### Step 2: Create Render Service
1. Go to [render.com](https://render.com) and sign in
2. Click **"New +"** → **"Background Worker"** (NOT Web Service — Socket Mode doesn't need a port)
3. Connect your GitHub repo
4. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`

### Step 3: Set Environment Variables
Same as Railway (add all 4 required variables in Render's Environment tab).

---

## Option 3: Docker (Self-Hosted / VPS)

### Build and Run
```bash
docker build -t baton .
docker run -d --name baton \
  -e SLACK_BOT_TOKEN=xoxb-... \
  -e SLACK_SIGNING_SECRET=... \
  -e SLACK_APP_TOKEN=xapp-... \
  -e GROQ_API_KEY=gsk_... \
  --restart unless-stopped \
  baton
```

### Check Logs
```bash
docker logs -f baton
```

---

## Verification

After deployment, check:
1. **Railway/Render logs** show: `Starting Baton in Socket Mode…` and `Bolt app is running!`
2. In Slack, open a new assistant thread with Baton
3. Ask: *"How do we book the community centre?"*
4. Verify you get a cited answer with a permalink

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Missing required environment variables` | Check all 4 env vars are set in the dashboard |
| `invalid_auth` | Regenerate your `SLACK_BOT_TOKEN` in Slack app settings |
| `connection_refused` | Ensure `SLACK_APP_TOKEN` starts with `xapp-` |
| App crashes and restarts | Check logs for the specific error; Railway auto-restarts up to 10 times |

# Railway Deployment Guide

## Prerequisites

- Railway CLI installed (`npm install -g @railway/cli`) or Railway dashboard access
- Supabase project already provisioned with migrations 001–019 applied
- GWDG API key available

---

## 1. Railway Project Setup

### Option A — Railway CLI (local deploy, no GitHub required)

```sh
railway login
railway init          # create new project
railway up            # deploy from local repo
```

### Option B — GitHub-connected (requires private repo)

> This private dev tree is never pushed publicly. If using GitHub-connected deploys,
> push to a **private** GitHub repo first. Do not use the public `mhju1988/job-agent-whs`.

Create two services in the Railway dashboard:
- **api**: root directory = `/` (repo root), Dockerfile = `Dockerfile`
- **web**: root directory = `frontend/`, Dockerfile = `Dockerfile`

`railway.json` at the repo root configures both services automatically.

---

## 2. Backend Environment Variables (`api` service)

Set these in Railway → api service → Variables:

| Variable | Required | Default / Notes |
|---|---|---|
| `GWDG_API_KEY` | ✅ | Your GWDG LLM key |
| `GWDG_API_BASE` | optional | `https://chat-ai.academiccloud.de/v1` |
| `GWDG_MODEL` | optional | `apertus-70b-instruct-2509` |
| `GWDG_EMBED_MODEL` | optional | `multilingual-e5-large-instruct` |
| `GWDG_TIMEOUT` | optional | `120` (seconds) |
| `SUPABASE_URL` | ✅ | Your Supabase project URL |
| `SUPABASE_KEY` | ✅ | Service-role key (bypasses RLS — keep secret) |
| `SUPABASE_ANON_KEY` | ✅ | Anon/publishable key (RLS-bound) |
| `SUPABASE_JWT_SECRET` | optional | Only if project signs HS256 tokens |
| `CORS_ORIGINS` | ✅ | Deployed frontend URL (see step 5) |
| `NIM_API_KEY` | optional | Leave blank to disable NVIDIA NIM |
| `NIM_API_BASE` | optional | `https://integrate.api.nvidia.com/v1` |
| `NIM_MODEL` | optional | `meta/llama-3.1-70b-instruct` |
| `NIM_TIMEOUT` | optional | `30` |
| `NIM_HEALTH_INTERVAL_S` | optional | `60` |
| `RAPIDAPI_KEY` | optional | Leave blank to disable JSearch |
| `MATCHER_MAX_CONCURRENCY` | optional | `4` |
| `LOG_LEVEL` | optional | `INFO` |
| `ARTIFACTS_DIR` | optional | `./artifacts` — see persistence note below |
| `PORT` | auto | Injected by Railway — do not set manually |

**Artifact persistence note:** Generated CVs and cover letters are written to `ARTIFACTS_DIR`
on the container's local filesystem, which is **ephemeral** — files are lost on restart or
redeploy. For a demo this is acceptable (downloads work within a container's lifetime). For
durability: attach a Railway volume mounted at the `ARTIFACTS_DIR` path, or migrate exports
to Supabase Storage.

---

## 3. Frontend Environment Variables (`web` service — build-time)

These are **baked into the Next.js bundle at build time**. Set them as build-time variables
in Railway → web service → Variables before deploying:

| Variable | Required | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Same as `SUPABASE_URL` above |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Anon key (safe to expose in browser) |
| `NEXT_PUBLIC_API_BASE_URL` | ✅ | Backend public domain (see step 5) |

> **Important:** Changing `NEXT_PUBLIC_API_BASE_URL` (e.g. if the backend domain changes)
> requires a **frontend redeploy** — the value is baked into the bundle, not read at runtime.

---

## 4. First Deploy

Deploy the `api` service first (to get its public domain), then the `web` service:

```sh
# CLI
railway up --service api
# note the api public domain printed in output

railway up --service web
# note the web public domain
```

---

## 5. Chicken-and-Egg Domain Wiring

Both services need each other's public domain. The flow:

1. Deploy both services once (they won't fully work yet — CORS will block, API URL unknown)
2. In Railway dashboard, copy the **public domain** for each service
3. Set on `api` service: `CORS_ORIGINS=https://<web-domain>.up.railway.app`
4. Set on `web` service (build-time): `NEXT_PUBLIC_API_BASE_URL=https://<api-domain>.up.railway.app`
5. **Redeploy both services** — this is required for the frontend to bake in the correct API URL

---

## 6. Supabase Auth Configuration

After you have the deployed frontend URL, update the Supabase dashboard:

1. Go to **Authentication → URL Configuration**
2. Set **Site URL** to `https://<web-domain>.up.railway.app`
3. Add the same URL to **Redirect URLs**

This is required for Supabase Auth email magic links and OAuth redirects to work from the
deployed app.

---

## 7. SSE / Long-Running Requests

The Matcher agent runs use Server-Sent Events and can stay open for several minutes.

- Check Railway's **request timeout** setting for the `api` service — set it generously
  (e.g. 300–600 seconds) to avoid premature stream termination
- Railway's HTTP proxy may buffer SSE responses; confirm the event stream is not
  buffered by testing a live Matcher run in the deployed app

---

## 8. Healthchecks

| Service | Healthcheck path | Expected |
|---|---|---|
| `api` | `/api/health` | `200 OK` |
| `web` | `/` | `200 OK` |

---

## 9. Rollback

Via Railway CLI:
```sh
railway rollback --service api
railway rollback --service web
```

Via dashboard: Railway → service → Deployments → click a prior deployment → Rollback.

---

## 10. Logs

```sh
railway logs --service api
railway logs --service web
```

Or view in Railway dashboard → service → Logs.

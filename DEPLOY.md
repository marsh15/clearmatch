# Deploying ClearMatch

Backend + Postgres on **Render**, frontend on **Vercel**.
Repo: https://github.com/marsh15/clearmatch — both platforms deploy from `main`.

## 1 · Backend → Render

The repo ships a blueprint (`render.yaml`): API web service + free Postgres.

1. Render dashboard → **New → Blueprint** → connect this repo.
2. It provisions `clearmatch-api` (root `backend/`, health check `/api/health`)
   and `clearmatch-db` (free Postgres; auto-expires 30 days after last use —
   fine for the case-study window).
3. When asked for `OPENAI_API_KEY`, paste yours (sync: false — never in repo).
4. `RESET_TOKEN` is auto-generated; read it from the dashboard (Environment).

Smoke check: `https://<render-domain>/api/health` → `{"status":"ok"}`

Free-tier note: the service spins down after ~15 min idle; first request takes
~30–60 s to wake. Ping `/api/health` before the interview.

## 2 · Frontend → Vercel

```bash
cd frontend
vercel login                              # browser auth (once)
vercel link --project clearmatch
vercel env add NEXT_PUBLIC_API_URL production
#   value: https://<render-domain>        (no trailing slash)
vercel --prod
```

Smoke check: open the Vercel URL → Run page loads → click **Happy path** →
stages stream → decision card appears.

## 3 · Before the interview

- Ping the Vercel URL and `/api/health` 10 minutes early (cold starts).
- Reset demo state: `POST /api/seed/reset` with header
  `X-Reset-Token: <RESET_TOKEN from Render env>`.
- Keep a local instance running as backup (`localhost:3000`).

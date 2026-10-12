# ClearMatch frontend

Next.js app (App Router, TypeScript, Tailwind) for ClearMatch: the run page,
the dashboard, and the run detail view.

Pages:

- `/` run page: drag-drop an invoice PDF or click a preset button; the seven
  pipeline stages stream in live over SSE as the backend works.
- `/dashboard`: every run with its decision chip, confidence, and reason
  codes, plus a decision-mix summary.
- `/runs/[id]`: the invoice-vs-PO comparison side by side, the plain-English
  explanation, the recommended next action, and the full stage timeline.

## Develop

```bash
npm install
npm run dev        # http://localhost:3000
```

The API base is resolved at runtime from the `/api-base` route
(`src/app/api-base/route.ts`), which returns `API_BASE_URL` and defaults to
`http://localhost:8000`. To point at a different backend:

```bash
API_BASE_URL=https://your-backend npm run dev
```

## Build and lint

```bash
npm run build && npm start
npm run lint
```

## Deploy

Production runs on Vercel. The full flow (linking the project, setting
`API_BASE_URL` to the Render backend, shipping with `vercel --prod`) is in
[../DEPLOY.md](../DEPLOY.md).

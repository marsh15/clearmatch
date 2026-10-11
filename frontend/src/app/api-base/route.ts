// Runtime API-base resolver: the backend URL lives in a Vercel env var
// (API_BASE_URL) and is read per-invocation, so repointing the frontend to a
// different backend never requires a rebuild.
export const dynamic = "force-dynamic";

export async function GET() {
  return Response.json({ api: (process.env.API_BASE_URL ?? "http://localhost:8000").trim() });
}

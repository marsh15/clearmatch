export type Decision = "AUTO-APPROVE" | "NEEDS REVIEW" | "REJECT" | "PENDING";

// Resolved once at runtime from /api-base (same-origin), so the deployed
// frontend can be repointed to any backend without a rebuild.
let resolvedBase: string | null = null;

export async function apiBase(): Promise<string> {
  if (resolvedBase) return resolvedBase;
  try {
    const res = await fetch("/api-base", { cache: "no-store" });
    resolvedBase = (await res.json()).api as string;
  } catch {
    resolvedBase = "http://localhost:8000";
  }
  return resolvedBase;
}

export interface RunSummary {
  id: number;
  filename: string;
  decision: Decision;
  confidence: number;
  reason_codes: string[];
  po_number: string | null;
  duration_ms: number;
  created_at: string | null;
}

export interface StageEvent {
  id: number;
  stage: string;
  status: "start" | "ok" | "warn" | "error";
  message: string;
  data: Record<string, unknown>;
  ts: string | null;
}

export interface LineItem {
  description: string;
  qty: number | null;
  unit_price: number | null;
  amount: number | null;
}

export interface Extraction {
  vendor_name?: string | null;
  invoice_number?: string | null;
  invoice_date?: string | null;
  po_number?: string | null;
  line_items?: LineItem[];
  subtotal?: number | null;
  tax?: number | null;
  total?: number | null;
}

export interface MatchResult {
  po_number: string | null;
  method: string;
  invoice_total: number | null;
  po_remaining: number | null;
  delta_abs: number | null;
  delta_pct: number | null;
  line_diffs: { description: string; po_unit_price: number | null;
                invoice_unit_price: number | null; price_deviation_pct: number | null }[];
}

export interface RunDetail extends RunSummary {
  sha256: string;
  size: number;
  explanation: string;
  next_action: string;
  extraction: Extraction | null;
  extraction_source: string | null;
  match: MatchResult | null;
  events: StageEvent[];
}

export const money = (v: number | null | undefined) =>
  v == null ? "-" : `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export async function getJSON<T>(path: string): Promise<T> {
  const base = await apiBase();
  const res = await fetch(`${base}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export async function startRun(body: FormData): Promise<{ run_id: number }> {
  const base = await apiBase();
  const res = await fetch(`${base}/api/runs`, { method: "POST", body });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

export async function startPreset(preset: string): Promise<{ run_id: number }> {
  const base = await apiBase();
  const res = await fetch(`${base}/api/runs/preset/${preset}`, { method: "POST" });
  if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
  return res.json();
}

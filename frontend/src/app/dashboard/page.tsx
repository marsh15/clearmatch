"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import CodeChip from "@/components/CodeChip";
import ConfidenceBar from "@/components/ConfidenceBar";
import DecisionChip from "@/components/DecisionChip";
import { getJSON, isLocalDev, offlineMessage, type Decision, type RunSummary } from "@/lib/api";

interface Stats {
  total_runs: number;
  decision_mix: Record<string, number>;
  avg_duration_ms: number;
}

export default function DashboardPage() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getJSON<RunSummary[]>("/api/runs"), getJSON<Stats>("/api/stats")])
      .then(([r, s]) => { setRuns(r); setStats(s); })
      .catch(async (e) => {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg.includes("Failed to fetch") ? offlineMessage(await isLocalDev()) : msg);
      });
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500">Every run, its decision, and why.</p>
        </div>
        <Link
          href="/"
          className="pressable rounded-lg bg-blue-700 px-4 py-2.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-blue-800 focus-visible:outline-2 focus-visible:outline-blue-600"
        >
          + New run
        </Link>
      </div>

      {error && (
        <p role="alert" className="enter rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {stats && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Runs" value={String(stats.total_runs)} delay={0} />
          <StatCard label="Auto-approved" value={String(stats.decision_mix["AUTO-APPROVE"] ?? 0)} tone="emerald" delay={40} />
          <StatCard label="Needs review" value={String(stats.decision_mix["NEEDS REVIEW"] ?? 0)} tone="amber" delay={80} />
          <StatCard label="Rejected" value={String(stats.decision_mix["REJECT"] ?? 0)} tone="red" delay={120} />
        </div>
      )}

      {runs === null && !error && <TableSkeleton />}

      {runs !== null && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Run</th>
                <th className="px-4 py-3">Decision</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">PO</th>
                <th className="hidden px-4 py-3 md:table-cell">Reason codes</th>
                <th className="px-4 py-3 text-right">When</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((r) => (
                <tr key={r.id} className="transition-colors duration-150 hover:bg-blue-50/40">
                  <td className="px-4 py-3">
                    <Link href={`/runs/${r.id}`} className="rounded-sm font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
                      #{r.id}
                    </Link>
                    <span className="ml-2 text-slate-600">{r.filename}</span>
                  </td>
                  <td className="px-4 py-3"><DecisionChip decision={r.decision as Decision} /></td>
                  <td className="px-4 py-3"><ConfidenceBar value={r.confidence} /></td>
                  <td className="num px-4 py-3 text-slate-600">{r.po_number ?? "-"}</td>
                  <td className="hidden max-w-xs px-4 py-3 md:table-cell">
                    <div className="flex flex-wrap gap-1">
                      {r.reason_codes.slice(0, 3).map((c) => <CodeChip key={c} code={c} />)}
                      {r.reason_codes.length > 3 && <span className="text-[11px] text-slate-500">+{r.reason_codes.length - 3}</span>}
                    </div>
                  </td>
                  <td className="num px-4 py-3 text-right text-xs text-slate-500">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : "-"}
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12">
                    <div className="flex flex-col items-center gap-2 text-center">
                      <p className="text-sm font-medium text-slate-700">No runs yet</p>
                      <p className="max-w-xs text-xs text-slate-500">
                        Run an invoice from the Run page; every decision lands here with its full reasoning.
                      </p>
                      <Link href="/" className="mt-1 rounded-sm text-sm font-medium text-blue-700 hover:underline">
                        Run the happy path first →
                      </Link>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, tone, delay }: { label: string; value: string; tone?: string; delay: number }) {
  const color = tone === "emerald" ? "text-emerald-700" : tone === "amber" ? "text-amber-700" : tone === "red" ? "text-red-700" : "text-slate-900";
  return (
    <div className="enter rounded-2xl border border-slate-200 bg-white p-4 shadow-sm" style={{ animationDelay: `${delay}ms` }}>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`num mt-1 text-2xl font-bold ${color}`}>{value}</p>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm" aria-label="Loading runs">
      <div className="divide-y divide-slate-100">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="skeleton flex items-center gap-6 px-4 py-4">
            <div className="h-3.5 w-40 rounded bg-slate-200" />
            <div className="h-3.5 w-24 rounded bg-slate-200" />
            <div className="h-3.5 w-32 rounded bg-slate-200" />
            <div className="ml-auto h-3.5 w-28 rounded bg-slate-200" />
          </div>
        ))}
      </div>
    </div>
  );
}

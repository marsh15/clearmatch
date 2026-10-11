"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import CodeChip from "@/components/CodeChip";
import ConfidenceBar from "@/components/ConfidenceBar";
import DecisionChip from "@/components/DecisionChip";
import { getJSON, money, type LineItem, type RunDetail } from "@/lib/api";

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (params?.id) getJSON<RunDetail>(`/api/runs/${params.id}`).then(setRun).catch((e) => setError(e.message));
  }, [params?.id]);

  if (error) return <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>;
  if (!run) return <DetailSkeleton />;

  const e = run.extraction;
  const m = run.match;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">
            Run #{run.id} <span className="font-normal text-slate-500">· {run.filename}</span>
          </h1>
          <p className="num text-xs text-slate-500">
            {run.created_at ? new Date(run.created_at).toLocaleString() : ""} · {run.size.toLocaleString()} bytes ·
            sha256 {run.sha256.slice(0, 12)} · {run.duration_ms} ms
          </p>
        </div>
        <div className="flex items-center gap-4">
          <ConfidenceBar value={run.confidence} />
          <DecisionChip decision={run.decision} large />
        </div>
      </div>

      <div className="enter rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-wrap gap-1.5">
          {run.reason_codes.map((c) => <CodeChip key={c} code={c} />)}
        </div>
        <p className="pretty mt-3 text-sm leading-relaxed text-slate-700">{run.explanation}</p>
        <p className="pretty mt-3 rounded-lg bg-blue-50 px-3 py-2 text-sm text-blue-900">
          <span className="font-semibold">Recommended next action: </span>{run.next_action}
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Extracted invoice" tag={run.extraction_source ?? ""}>
          <Field label="Vendor" value={e?.vendor_name} />
          <Field label="Invoice no." value={e?.invoice_number} />
          <Field label="Date" value={e?.invoice_date} />
          <Field label="PO reference" value={e?.po_number} />
          <div className="mt-3 overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-slate-500">
                <tr><th className="py-1 text-left">Line</th><th className="text-right">Qty</th><th className="text-right">Unit</th><th className="text-right">Amount</th></tr>
              </thead>
              <tbody className="num divide-y divide-slate-100">
                {(e?.line_items ?? []).map((li: LineItem, i) => (
                  <tr key={i}>
                    <td className="py-1.5 pr-2 font-sans text-slate-700">{li.description || "-"}</td>
                    <td className="text-right">{li.qty ?? "-"}</td>
                    <td className="text-right">{money(li.unit_price)}</td>
                    <td className="text-right">{money(li.amount)}</td>
                  </tr>
                ))}
                {(e?.line_items ?? []).length === 0 && (
                  <tr><td colSpan={4} className="py-3 text-center font-sans text-slate-500">No line items extracted</td></tr>
                )}
              </tbody>
            </table>
          </div>
          <dl className="num mt-3 space-y-1 border-t border-slate-100 pt-2 text-sm">
            <Row label="Subtotal" value={money(e?.subtotal)} />
            <Row label="Tax" value={money(e?.tax)} />
            <Row label="Total" value={money(e?.total)} bold />
          </dl>
        </Panel>

        <Panel title="PO match" tag={m?.method ?? "none"}>
          {m?.po_number ? (
            <>
              <Field label="PO" value={m.po_number} />
              <Field label="Match method" value={m.method} />
              <dl className="num mt-3 space-y-1 text-sm">
                <Row label="Invoice total" value={money(m.invoice_total)} />
                <Row label="PO remaining balance" value={money(m.po_remaining)} />
                <Row label="Delta (invoice - remaining)" value={money(m.delta_abs)} bold
                     warn={m.delta_abs != null && m.delta_abs > 0} />
                {m.delta_pct != null && <Row label="Delta %" value={`${(m.delta_pct * 100).toFixed(1)}%`} />}
              </dl>
              {m.line_diffs.length > 0 && (
                <div className="mt-3 rounded-lg bg-amber-50 p-3">
                  <p className="text-xs font-semibold text-amber-800">Line price deviations</p>
                  <ul className="num mt-1 space-y-1 text-xs text-amber-900">
                    {m.line_diffs.map((d, i) => (
                      <li key={i}>
                        {d.description}: PO {money(d.po_unit_price)} vs invoice {money(d.invoice_unit_price)}
                        <span className="font-semibold"> ({d.price_deviation_pct}%)</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-500">No purchase order was matched to this invoice.</p>
          )}
        </Panel>
      </div>

      <Panel title="Stage timeline">
        <ol className="space-y-1">
          {run.events.map((ev) => (
            <li key={ev.id} className="flex items-baseline gap-3 text-xs">
              <span className="num w-24 shrink-0 text-slate-500">{ev.ts ? ev.ts.slice(11, 23) : ""}</span>
              <span className="flex w-16 shrink-0 items-baseline gap-1 font-medium text-slate-700">
                {ev.stage}
                {ev.status === "warn" && <span className="text-[10px] font-semibold text-amber-600">warn</span>}
              </span>
              <span className={ev.status === "warn" ? "text-amber-700" : "text-slate-600"}>{ev.message}</span>
            </li>
          ))}
        </ol>
      </Panel>

      <Link href="/dashboard" className="inline-block rounded-sm text-sm font-medium text-blue-700 hover:underline">
        ← Back to dashboard
      </Link>
    </div>
  );
}

function Panel({ title, tag, children }: { title: string; tag?: string; children: React.ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-semibold text-slate-800">{title}</h2>
        {tag && <span className="rounded-md bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-600">{tag}</span>}
      </div>
      {children}
    </section>
  );
}

function Field({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex justify-between border-b border-slate-100 py-1.5 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-800">{value ?? "-"}</span>
    </div>
  );
}

function Row({ label, value, bold, warn }: { label: string; value: string; bold?: boolean; warn?: boolean }) {
  return (
    <div className="flex justify-between">
      <dt className={warn ? "text-amber-800" : "text-slate-500"}>{label}</dt>
      <dd className={`${bold ? "font-semibold" : ""} ${warn ? "text-amber-800" : "text-slate-800"}`}>{value}</dd>
    </div>
  );
}

function DetailSkeleton() {
  return (
    <div className="space-y-6" aria-label="Loading run">
      <div className="skeleton h-8 w-64 rounded bg-slate-200" />
      <div className="skeleton h-28 rounded-2xl bg-slate-200/70" />
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="skeleton h-72 rounded-2xl bg-slate-200/70" />
        <div className="skeleton h-72 rounded-2xl bg-slate-200/70" />
      </div>
    </div>
  );
}

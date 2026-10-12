"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import CodeChip from "@/components/CodeChip";
import ConfidenceBar from "@/components/ConfidenceBar";
import DecisionChip from "@/components/DecisionChip";
import { apiBase, getJSON, isLocalDev, money, offlineMessage, startPreset, startRun, type RunDetail, type StageEvent } from "@/lib/api";

const PRESETS = [
  { key: "happy", label: "Happy path", hint: "clean PDF, exact PO match" },
  { key: "scanned", label: "E1 · Scanned", hint: "image-only PDF, OCR path" },
  { key: "duplicate", label: "E2 · Duplicate", hint: "resubmitted invoice number" },
  { key: "split_a", label: "E3 · Split A", hint: "first half of a PO" },
  { key: "split_b", label: "E3 · Split B", hint: "matches remaining balance" },
  { key: "breach", label: "E4 · Breach", hint: "4% over PO" },
  { key: "missing", label: "B1 · Missing", hint: "no invoice number / PO ref" },
  { key: "linemismatch", label: "B2 · Line delta", hint: "totals agree, prices don't" },
];

const STAGE_ORDER = ["receive", "classify", "extract", "validate", "match", "decide", "report"];

const STAGE_LABELS: Record<string, string> = {
  receive: "1 · Receive", classify: "2 · Classify", extract: "3 · Extract",
  validate: "4 · Validate", match: "5 · Match", decide: "6 · Decide", report: "7 · Report",
};

const STATUS_DOT: Record<string, string> = {
  start: "bg-blue-500 animate-pulse", ok: "bg-emerald-500", warn: "bg-amber-500", error: "bg-red-500",
};

export default function RunPage() {
  const [events, setEvents] = useState<StageEvent[]>([]);
  const [runId, setRunId] = useState<number | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [waking, setWaking] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const eventSource = useRef<EventSource | null>(null);

  useEffect(() => () => eventSource.current?.close(), []);

  const reset = () => {
    eventSource.current?.close();
    setEvents([]); setRunId(null); setDetail(null); setError(null);
  };

  const watch = useCallback(async (id: number) => {
    setRunId(id);
    eventSource.current?.close();
    const es = new EventSource(`${await apiBase()}/api/runs/${id}/events`);
    eventSource.current = es;
    es.addEventListener("stage", (e) => {
      const ev: StageEvent = JSON.parse((e as MessageEvent).data);
      setEvents((prev) => [...prev, ev]);
      if (ev.stage === "report" && ev.status === "ok") {
        es.close();
        getJSON<RunDetail>(`/api/runs/${id}`).then(setDetail).catch(() => {});
      }
    });
    es.onerror = () => {
      es.close();
      setError("Live stream interrupted. Open the run from the dashboard to see its result.");
    };
  }, []);

  const launch = async (fn: () => Promise<{ run_id: number }>) => {
    if (busy) return;
    reset(); setBusy(true);
    const slowTimer = setTimeout(() => setWaking(true), 3000);
    try {
      const { run_id } = await fn();
      clearTimeout(slowTimer); setWaking(false);
      await watch(run_id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg.includes("Failed to fetch") ? offlineMessage(await isLocalDev()) : msg);
    } finally {
      clearTimeout(slowTimer); setWaking(false); setBusy(false);
    }
  };

  const onUpload = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    await launch(() => startRun(fd));
  };

  const latestByStage = new Map(events.map((e) => [e.stage, e]));
  const currentStage = events[events.length - 1]?.stage;
  const finished = events.some((e) => e.stage === "report" && e.status === "ok");

  return (
    <div className="grid gap-6 lg:grid-cols-[380px_1fr]">
      {/* ---- left: inputs ---- */}
      <section className="space-y-6">
        <div>
          <h2 className="text-sm font-semibold text-slate-500">Run an invoice</h2>
          <button
            type="button"
            onClick={() => fileInput.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) void onUpload(f); }}
            className="pressable mt-2 flex w-full cursor-pointer flex-col items-center rounded-xl border-2 border-dashed border-slate-300 bg-white px-6 py-6 text-center transition-colors duration-150 hover:border-blue-500 hover:bg-blue-50/40 focus-visible:outline-2 focus-visible:outline-blue-600"
          >
            <p className="text-sm font-medium text-slate-700">Drop an invoice PDF, or click to choose</p>
            <p className="mt-1 text-xs text-slate-500">PDF only · max 10 MB</p>
          </button>
          <input
            ref={fileInput} type="file" accept="application/pdf" className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void onUpload(f); e.target.value = ""; }}
          />
          {waking && !error && (
            <p role="status" className="enter mt-2 rounded-md bg-blue-50 px-3 py-2 text-xs text-blue-800">
              Waking the API. The free tier sleeps when idle; the first request can take up to a minute.
            </p>
          )}
          {error && (
            <p role="alert" className="enter mt-2 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p>
          )}
        </div>

        <div>
          <h2 className="text-sm font-semibold text-slate-500">Demo presets</h2>
          <p className="text-xs text-slate-500">One click: the exact rehearsed inputs.</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.key}
                disabled={busy}
                onClick={() => void launch(() => startPreset(p.key))}
                className="pressable min-h-14 rounded-lg border border-slate-200 bg-white px-3 py-2 text-left transition-colors duration-150 hover:border-blue-400 hover:shadow-sm focus-visible:outline-2 focus-visible:outline-blue-600 disabled:opacity-50"
              >
                <span className="block text-sm font-medium text-slate-800">{p.label}</span>
                <span className="block text-[11px] text-slate-500">{p.hint}</span>
              </button>
            ))}
          </div>
        </div>

        {detail && (
          <div className="enter rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <DecisionChip decision={detail.decision} large />
              <ConfidenceBar value={detail.confidence} />
            </div>
            <p className="pretty mt-3 text-sm leading-relaxed text-slate-700">{detail.explanation}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {detail.reason_codes.map((c) => <CodeChip key={c} code={c} />)}
            </div>
            <p className="pretty mt-3 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-900">
              <span className="font-semibold">Next action: </span>{detail.next_action}
            </p>
            <Link href={`/runs/${detail.id}`} className="mt-3 inline-block rounded-sm text-sm font-medium text-blue-700 hover:underline focus-visible:outline-2 focus-visible:outline-blue-600">
              View full run detail →
            </Link>
          </div>
        )}
      </section>

      {/* ---- right: live stages ---- */}
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-slate-800">Live run</h2>
          {runId && <span className="num text-xs text-slate-500">run #{runId}</span>}
        </div>

        {!runId && (
          <div className="mt-16 flex flex-col items-center gap-2 text-center">
            <p className="text-sm font-medium text-slate-600">{waking ? "Starting the run…" : "Nothing running yet"}</p>
            <p className="max-w-xs text-xs text-slate-500">
              {waking
                ? "The API is waking from idle. This can take up to a minute on the free tier."
                : "Pick a preset or drop a PDF. Each of the seven stages lights up as it executes."}
            </p>
          </div>
        )}

        <ol className="mt-4 space-y-1">
          {STAGE_ORDER.map((stage) => {
            const ev = latestByStage.get(stage);
            const running = !finished && stage === currentStage && ev?.status === "start";
            return (
              <li
                key={stage}
                className={`flex gap-3 rounded-lg px-3 py-2 transition-colors duration-150
                  ${ev ? "enter bg-slate-50" : "opacity-40"}
                  ${running ? "ring-1 ring-inset ring-blue-300" : ""}`}
              >
                <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${ev ? STATUS_DOT[ev.status] : "bg-slate-300"}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-medium text-slate-800">{STAGE_LABELS[stage]}</span>
                    {ev?.status === "warn" && <span className="text-[11px] font-semibold text-amber-600">warn</span>}
                    {running && <span className="text-[11px] font-semibold text-blue-600">running</span>}
                  </div>
                  <p className="num truncate text-xs text-slate-600">{ev?.message ?? "waiting"}</p>
                  {ev?.stage === "extract" && ev.status === "ok" && ev.data?.vendor_name != null && (
                    <p className="num mt-1 text-[11px] text-slate-500">
                      {String(ev.data.vendor_name)} · lines {Array.isArray(ev.data.line_items) ? ev.data.line_items.length : 0} · total {money(ev.data.total as number)}
                    </p>
                  )}
                  {ev?.stage === "match" && ev.status === "ok" && ev.data?.po_number != null && (
                    <p className="num mt-1 text-[11px] text-slate-500">
                      {String(ev.data.po_number)} · remaining {money(ev.data.po_remaining as number)} · delta {money(ev.data.delta_abs as number)}
                    </p>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

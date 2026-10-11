import type { Decision } from "@/lib/api";

const STYLES: Record<string, string> = {
  "AUTO-APPROVE": "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
  "NEEDS REVIEW": "bg-amber-100 text-amber-800 ring-amber-600/20",
  "REJECT": "bg-red-100 text-red-800 ring-red-600/20",
  "PENDING": "bg-slate-100 text-slate-600 ring-slate-500/20",
};

export default function DecisionChip({ decision, large }: { decision: Decision; large?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full font-semibold ring-1 ring-inset
        ${STYLES[decision] ?? STYLES.PENDING} ${large ? "px-4 py-1.5 text-base" : "px-2.5 py-0.5 text-xs"}`}
    >
      {decision}
    </span>
  );
}

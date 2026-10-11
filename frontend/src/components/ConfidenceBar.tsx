export default function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 85 ? "bg-emerald-600" : pct >= 60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div
        role="img"
        aria-label={`Confidence ${pct}%`}
        className="h-2 w-32 overflow-hidden rounded-full bg-slate-200"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="num text-xs text-slate-600">{pct}%</span>
    </div>
  );
}

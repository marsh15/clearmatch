export default function CodeChip({ code }: { code: string }) {
  return (
    <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 font-mono text-[11px] text-slate-700 ring-1 ring-inset ring-slate-200">
      {code}
    </span>
  );
}

interface Props {
  conviction: number;
}

export default function ConvictionBadge({ conviction }: Props) {
  const pct = Math.round(conviction * 100);
  const color =
    pct >= 60
      ? 'bg-emerald-900/50 text-emerald-400 ring-emerald-500/30'
      : pct >= 40
        ? 'bg-amber-900/50 text-amber-400 ring-amber-500/30'
        : 'bg-red-900/50 text-red-400 ring-red-500/30';

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${color}`}
      title={`Conviction: ${pct}% \u2014 measures indicator agreement, not predicted return`}
    >
      {pct}%
    </span>
  );
}

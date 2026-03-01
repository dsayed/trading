import type { Signal } from '../types/api';
import ConvictionBadge from './ConvictionBadge';

interface Props {
  signals: Signal[];
  onSelect?: (signal: Signal) => void;
}

export default function SignalTable({ signals, onSelect }: Props) {
  if (signals.length === 0) {
    return (
      <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-500">
        No actionable signals found.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-zinc-800">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
            <th className="px-4 py-3">Action</th>
            <th className="px-4 py-3">Symbol</th>
            <th className="px-4 py-3">Conviction</th>
            <th className="px-4 py-3">Qty</th>
            <th className="px-4 py-3">Limit Price</th>
            <th className="px-4 py-3">Strategy</th>
            <th className="px-4 py-3">Summary</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-zinc-800/50">
          {signals.map((s, i) => {
            const dirColor =
              s.direction === 'long'
                ? 'text-emerald-400'
                : s.direction === 'close'
                  ? 'text-red-400'
                  : 'text-amber-400';
            return (
              <tr
                key={`${s.symbol}-${i}`}
                className={`transition-colors ${onSelect ? 'cursor-pointer hover:bg-zinc-900/50' : ''}`}
                onClick={() => onSelect?.(s)}
              >
                <td className={`px-4 py-3 font-semibold uppercase ${dirColor}`}>
                  {s.direction}
                </td>
                <td className="px-4 py-3 font-mono font-medium text-zinc-200">
                  {s.symbol}
                </td>
                <td className="px-4 py-3">
                  <ConvictionBadge conviction={s.conviction} />
                </td>
                <td className="px-4 py-3 text-zinc-300">{s.quantity}</td>
                <td className="px-4 py-3 font-mono text-zinc-300">
                  {s.limit_price ? `$${s.limit_price.toFixed(2)}` : '—'}
                </td>
                <td className="px-4 py-3 text-zinc-400">{s.strategy_name}</td>
                <td className="max-w-xs truncate px-4 py-3 text-zinc-400">
                  {s.rationale}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

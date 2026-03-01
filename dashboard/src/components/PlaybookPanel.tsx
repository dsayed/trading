import type { Signal } from '../types/api';
import ConvictionBadge from './ConvictionBadge';

interface Props {
  signal: Signal;
  onClose: () => void;
}

export default function PlaybookPanel({ signal, onClose }: Props) {
  const dirColor =
    signal.direction === 'long'
      ? 'border-emerald-500/40 bg-emerald-950/20'
      : 'border-red-500/40 bg-red-950/20';

  return (
    <div className={`rounded-lg border ${dirColor} p-6`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span
            className={`text-lg font-bold uppercase ${
              signal.direction === 'long' ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            {signal.direction} {signal.symbol}
          </span>
          <ConvictionBadge conviction={signal.conviction} />
          <span className="text-sm text-zinc-500">{signal.strategy_name}</span>
        </div>
        <button
          onClick={onClose}
          className="rounded-md px-2 py-1 text-sm text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
        >
          Close
        </button>
      </div>

      <div className="mb-4">
        <h3 className="mb-1 text-xs font-medium uppercase tracking-wider text-zinc-500">
          Rationale
        </h3>
        <p className="text-sm leading-relaxed text-zinc-300">{signal.rationale}</p>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-4">
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Quantity</div>
          <div className="text-lg font-semibold text-zinc-200">
            {signal.quantity}
          </div>
        </div>
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Limit Price</div>
          <div className="font-mono text-lg font-semibold text-zinc-200">
            {signal.limit_price ? `$${signal.limit_price.toFixed(2)}` : '—'}
          </div>
        </div>
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Stop Loss</div>
          <div className="font-mono text-lg font-semibold text-zinc-200">
            {signal.stop_price ? `$${signal.stop_price.toFixed(2)}` : '—'}
          </div>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          Action Playbook
        </h3>
        <pre className="whitespace-pre-wrap rounded-md bg-zinc-900 p-4 font-mono text-sm leading-relaxed text-zinc-300">
          {signal.playbook}
        </pre>
      </div>
    </div>
  );
}

import { useState } from 'react';
import type { Signal } from '../types/api';
import { fmt, fmtInt } from '../utils/format';
import ConvictionBadge from './ConvictionBadge';

interface Props {
  signal: Signal;
  onClose: () => void;
}

const DIRECTION_LABELS: Record<string, string> = {
  long: 'Buy',
  short: 'Sell Short',
  close: 'Sell',
};

const STRATEGY_LABELS: Record<string, string> = {
  momentum: 'Momentum',
  mean_reversion: 'Mean Reversion',
  income: 'Income',
};

export default function PlaybookPanel({ signal, onClose }: Props) {
  const [showTechnical, setShowTechnical] = useState(false);

  const dirLabel = DIRECTION_LABELS[signal.direction] ?? signal.direction;
  const isBuy = signal.direction === 'long';
  const dirColor = isBuy
    ? 'border-emerald-500/40 bg-emerald-950/20'
    : 'border-red-500/40 bg-red-950/20';
  const dirTextColor = isBuy ? 'text-emerald-400' : 'text-red-400';

  return (
    <div className={`rounded-lg border ${dirColor} p-6`}>
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-lg font-bold ${dirTextColor}`}>
            {dirLabel} {signal.symbol}
          </span>
          {signal.company_name && (
            <span className="text-sm text-zinc-500">{signal.company_name}</span>
          )}
          <ConvictionBadge conviction={signal.conviction} />
          <span className="text-sm text-zinc-500">
            {STRATEGY_LABELS[signal.strategy_name] ?? signal.strategy_name}
          </span>
        </div>
        <button
          onClick={onClose}
          className="rounded-md px-2 py-1 text-sm text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
        >
          Close
        </button>
      </div>

      {/* Key numbers */}
      <div className="mb-4 grid grid-cols-3 gap-4">
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Shares</div>
          <div className="text-lg font-semibold text-zinc-200">
            {fmtInt(signal.quantity)}
          </div>
        </div>
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Price</div>
          <div className="font-mono text-lg font-semibold text-zinc-200">
            {signal.limit_price ? fmt(signal.limit_price) : '\u2014'}
          </div>
        </div>
        <div className="rounded-md bg-zinc-900/50 p-3">
          <div className="text-xs text-zinc-500">Stop Loss</div>
          <div className="font-mono text-lg font-semibold text-zinc-200">
            {signal.stop_price ? fmt(signal.stop_price) : '\u2014'}
          </div>
        </div>
      </div>

      {/* Technical rationale — collapsible */}
      <div className="mb-4">
        <button
          onClick={() => setShowTechnical(!showTechnical)}
          className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-zinc-500 hover:text-zinc-400"
        >
          <span
            className="inline-block transition-transform"
            style={{ transform: showTechnical ? 'rotate(90deg)' : 'rotate(0deg)' }}
          >
            &#9656;
          </span>
          Technical Details
        </button>
        {showTechnical && (
          <p className="mt-2 rounded-md bg-zinc-900/50 p-3 text-sm leading-relaxed text-zinc-400">
            {signal.rationale}
          </p>
        )}
      </div>

      {/* Playbook */}
      <div>
        <h3 className="mb-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
          Action Plan
        </h3>
        <pre className="whitespace-pre-wrap rounded-md bg-zinc-900 p-4 font-mono text-sm leading-relaxed text-zinc-300">
          {signal.playbook}
        </pre>
      </div>
    </div>
  );
}

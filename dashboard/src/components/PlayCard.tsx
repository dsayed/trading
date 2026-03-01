import { useState } from 'react';
import type { Play } from '../types/api';

const TYPE_COLORS: Record<string, string> = {
  covered_call: 'bg-blue-900/50 text-blue-300 border-blue-800',
  protective_put: 'bg-purple-900/50 text-purple-300 border-purple-800',
  stop_loss: 'bg-red-900/50 text-red-300 border-red-800',
  trim: 'bg-amber-900/50 text-amber-300 border-amber-800',
  add: 'bg-emerald-900/50 text-emerald-300 border-emerald-800',
  hold: 'bg-zinc-800/50 text-zinc-400 border-zinc-700',
};

const TYPE_LABELS: Record<string, string> = {
  covered_call: 'Covered Call',
  protective_put: 'Protective Put',
  stop_loss: 'Stop Loss',
  trim: 'Trim',
  add: 'Add',
  hold: 'Hold',
};

function ConvictionBar({ conviction }: { conviction: number }) {
  const pct = Math.round(conviction * 100);
  const color =
    pct >= 70 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-zinc-600';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-zinc-500">{pct}%</span>
    </div>
  );
}

export default function PlayCard({ play }: { play: Play }) {
  const [expanded, setExpanded] = useState(false);
  const badgeClass = TYPE_COLORS[play.play_type] || TYPE_COLORS.hold;
  const label = TYPE_LABELS[play.play_type] || play.play_type;

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900/30 p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className={`rounded-md border px-2 py-0.5 text-xs font-medium ${badgeClass}`}>
            {label}
          </span>
          <h3 className="text-sm font-medium text-zinc-200">{play.title}</h3>
        </div>
        <ConvictionBar conviction={play.conviction} />
      </div>

      <p className="mb-3 text-xs text-zinc-400">{play.rationale}</p>

      {/* Key metrics */}
      <div className="mb-3 flex flex-wrap gap-4 text-xs">
        {play.option_contract && (
          <>
            <span className="text-zinc-500">
              Strike: <span className="text-zinc-300">${play.option_contract.strike}</span>
            </span>
            <span className="text-zinc-500">
              Exp: <span className="text-zinc-300">{play.option_contract.expiration}</span>
            </span>
            <span className="text-zinc-500">
              Mid: <span className="text-zinc-300">${play.option_contract.mid_price.toFixed(2)}</span>
            </span>
          </>
        )}
        {play.contracts > 0 && (
          <span className="text-zinc-500">
            Contracts: <span className="text-zinc-300">{play.contracts}</span>
          </span>
        )}
        {play.premium > 0 && (
          <span className="text-zinc-500">
            Premium: <span className="text-zinc-300">${play.premium.toFixed(2)}</span>
          </span>
        )}
        {play.max_profit != null && (
          <span className="text-zinc-500">
            Max Profit: <span className="text-emerald-400">${play.max_profit.toFixed(2)}</span>
          </span>
        )}
        {play.max_loss != null && (
          <span className="text-zinc-500">
            Max Loss: <span className="text-red-400">${play.max_loss.toFixed(2)}</span>
          </span>
        )}
        {play.breakeven != null && (
          <span className="text-zinc-500">
            Breakeven: <span className="text-zinc-300">${play.breakeven.toFixed(2)}</span>
          </span>
        )}
      </div>

      {/* Tax note */}
      {play.tax_note && (
        <div className="mb-3 rounded-md border border-amber-900/50 bg-amber-950/20 px-3 py-2 text-xs text-amber-400">
          {play.tax_note}
        </div>
      )}

      {/* Expandable playbook */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-emerald-400 hover:text-emerald-300"
      >
        {expanded ? 'Hide playbook ▴' : 'Show playbook ▾'}
      </button>
      {expanded && (
        <pre className="mt-2 whitespace-pre-wrap rounded-md bg-zinc-900 p-3 text-xs text-zinc-300">
          {play.playbook}
        </pre>
      )}
    </div>
  );
}

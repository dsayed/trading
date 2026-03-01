import { useState } from 'react';
import PlayCard from '../components/PlayCard';
import { useRunAdvise } from '../hooks/useAdvise';
import { usePositions } from '../hooks/usePositions';
import type { AdviseResponse } from '../types/api';

export default function PlaysPage() {
  const { data: positions, isLoading } = usePositions();
  const runAdvise = useRunAdvise();

  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [results, setResults] = useState<AdviseResponse | null>(null);

  function togglePosition(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    if (!positions) return;
    if (selected.size === positions.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(positions.map((p) => p.id)));
    }
  }

  function handleGetPlays() {
    const ids = selected.size > 0 ? Array.from(selected) : undefined;
    runAdvise.mutate(
      { position_ids: ids },
      { onSuccess: (data) => setResults(data) },
    );
  }

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Plays</h1>

      {/* Position selector */}
      {positions && positions.length > 0 ? (
        <div className="mb-6 rounded-lg border border-zinc-800 p-4">
          <div className="mb-3 flex items-center justify-between">
            <label className="text-sm font-medium text-zinc-400">
              Select positions to analyze
            </label>
            <button
              onClick={selectAll}
              className="text-xs text-emerald-400 hover:text-emerald-300"
            >
              {selected.size === positions.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          <div className="mb-4 flex flex-wrap gap-2">
            {positions.map((pos) => (
              <button
                key={pos.id}
                onClick={() => togglePosition(pos.id)}
                className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                  selected.has(pos.id)
                    ? 'border-emerald-500/50 bg-emerald-900/30 text-emerald-300'
                    : 'border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300'
                }`}
              >
                {pos.symbol}{' '}
                <span className="text-xs opacity-70">({pos.total_quantity})</span>
              </button>
            ))}
          </div>
          <button
            onClick={handleGetPlays}
            disabled={runAdvise.isPending}
            className="rounded-md bg-emerald-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
          >
            {runAdvise.isPending ? 'Analyzing...' : 'Get Plays'}
          </button>
        </div>
      ) : (
        <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-600">
          No positions yet. Add positions first to get play recommendations.
        </div>
      )}

      {/* Loading */}
      {runAdvise.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 p-8 text-zinc-400">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
          Running advisors on your positions...
        </div>
      )}

      {/* Error */}
      {runAdvise.isError && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {runAdvise.error.message}
        </div>
      )}

      {/* Results */}
      {results && !runAdvise.isPending && (
        <div className="space-y-6">
          {results.positions.map((posAdvice) => (
            <div key={posAdvice.symbol}>
              {/* Position header */}
              <div className="mb-3 flex items-baseline gap-4 border-b border-zinc-800 pb-2">
                <h2 className="text-lg font-semibold text-zinc-200">
                  {posAdvice.symbol}
                </h2>
                <span className="text-sm text-zinc-400">
                  {posAdvice.total_quantity} shares @ ${posAdvice.average_cost.toFixed(2)}
                </span>
                <span className="text-sm text-zinc-500">
                  Current: ${posAdvice.current_price.toFixed(2)}
                </span>
                <span
                  className={`text-sm font-medium ${
                    posAdvice.unrealized_pnl >= 0
                      ? 'text-emerald-400'
                      : 'text-red-400'
                  }`}
                >
                  {posAdvice.unrealized_pnl >= 0 ? '+' : ''}$
                  {posAdvice.unrealized_pnl.toFixed(2)}
                </span>
              </div>

              {/* Play cards */}
              <div className="space-y-3">
                {posAdvice.plays.length > 0 ? (
                  posAdvice.plays.map((play, i) => (
                    <PlayCard key={i} play={play} />
                  ))
                ) : (
                  <div className="rounded-lg border border-zinc-800 p-4 text-sm text-zinc-500">
                    No plays recommended for this position.
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import { useRef, useState } from 'react';
import ConvictionBadge from '../components/ConvictionBadge';
import PlaybookPanel from '../components/PlaybookPanel';
import { useRunScannerStream } from '../hooks/useScanner';
import { useUpdateWatchlist, useWatchlists } from '../hooks/useWatchlists';
import type { ScannerResponse, Signal } from '../types/api';

const UNIVERSE_OPTIONS = [
  { value: 'sp500', label: 'S&P 500', group: 'predefined' },
  { value: 'nasdaq100', label: 'NASDAQ 100', group: 'predefined' },
  { value: 'forex_majors', label: 'Forex Majors', group: 'predefined' },
  { value: 'gainers', label: 'Top Gainers', group: 'dynamic' },
  { value: 'losers', label: 'Top Losers', group: 'dynamic' },
  { value: 'most_active', label: 'Most Active', group: 'dynamic' },
  { value: 'custom', label: 'Custom Symbols', group: 'custom' },
] as const;

const STRATEGY_OPTIONS = [
  { value: 'momentum', label: 'Momentum' },
  { value: 'mean_reversion', label: 'Mean Reversion' },
  { value: 'income', label: 'Income' },
] as const;

export default function ScannerPage() {
  const runScanner = useRunScannerStream();
  const { data: watchlists } = useWatchlists();
  const updateWatchlist = useUpdateWatchlist();

  const [universe, setUniverse] = useState('sp500');
  const [customSymbols, setCustomSymbols] = useState('');
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([
    'momentum',
    'mean_reversion',
    'income',
  ]);
  const [maxResults, setMaxResults] = useState(20);
  const [lastResult, setLastResult] = useState<ScannerResponse | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [addingToWatchlist, setAddingToWatchlist] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  function toggleStrategy(name: string) {
    setSelectedStrategies((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    );
  }

  function handleScan() {
    const req: Record<string, unknown> = {
      strategies: selectedStrategies.length > 0 ? selectedStrategies : undefined,
      max_results: maxResults,
    };
    if (universe === 'custom') {
      const symbols = customSymbols
        .split(/[,\s]+/)
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      if (symbols.length === 0) return;
      req.symbols = symbols;
    } else {
      req.universe = universe;
    }
    setProgressLog([]);
    runScanner.mutate(
      {
        data: req as any,
        onProgress: (msg: string) => {
          setProgressLog((prev) => [...prev, msg]);
          // Auto-scroll log
          requestAnimationFrame(() => {
            logRef.current?.scrollTo(0, logRef.current.scrollHeight);
          });
        },
      },
      {
        onSuccess: (data) => {
          setLastResult(data);
          setSelectedSignal(null);
        },
      },
    );
  }

  function handleAddToWatchlist(symbol: string, watchlistId: number) {
    const wl = watchlists?.find((w) => w.id === watchlistId);
    if (!wl) return;
    if (wl.symbols.includes(symbol)) return;
    updateWatchlist.mutate(
      { id: watchlistId, data: { symbols: [...wl.symbols, symbol] } },
      { onSuccess: () => setAddingToWatchlist(null) },
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Scanner</h1>

      {/* Controls */}
      <div className="mb-6 space-y-4 rounded-lg border border-zinc-800 p-4">
        <div className="flex flex-wrap items-end gap-4">
          {/* Universe */}
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-sm font-medium text-zinc-400">Universe</label>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
            >
              <optgroup label="Predefined">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'predefined').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Dynamic">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'dynamic').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Custom">
                <option value="custom">Custom Symbols</option>
              </optgroup>
            </select>
          </div>

          {/* Custom symbols input */}
          {universe === 'custom' && (
            <div className="min-w-[300px] flex-1">
              <label className="mb-1 block text-sm font-medium text-zinc-400">Symbols</label>
              <input
                type="text"
                value={customSymbols}
                onChange={(e) => setCustomSymbols(e.target.value)}
                placeholder="AAPL, MSFT, GOOG"
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50"
              />
            </div>
          )}

          {/* Max results */}
          <div className="w-32">
            <label className="mb-1 block text-sm font-medium text-zinc-400">
              Max Results: {maxResults}
            </label>
            <input
              type="range"
              min={5}
              max={50}
              step={5}
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
              className="w-full accent-emerald-500"
            />
          </div>

          {/* Scan button */}
          <button
            onClick={handleScan}
            disabled={runScanner.isPending || selectedStrategies.length === 0}
            className="rounded-md bg-emerald-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
          >
            {runScanner.isPending ? 'Scanning...' : 'Scan'}
          </button>
        </div>

        {/* Strategy checkboxes */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-400">Strategies</label>
          <div className="flex gap-4">
            {STRATEGY_OPTIONS.map((s) => (
              <label key={s.value} className="flex items-center gap-2 text-sm text-zinc-300">
                <input
                  type="checkbox"
                  checked={selectedStrategies.includes(s.value)}
                  onChange={() => toggleStrategy(s.value)}
                  className="rounded border-zinc-600 bg-zinc-800 text-emerald-500 accent-emerald-500"
                />
                {s.label}
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Progress log */}
      {runScanner.isPending && (
        <div className="mb-4 rounded-lg border border-zinc-800 p-4">
          <div className="mb-2 flex items-center gap-2 text-sm text-zinc-400">
            <div className="h-3 w-3 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
            Scanning...
          </div>
          <div
            ref={logRef}
            className="max-h-48 overflow-y-auto rounded bg-zinc-900/50 p-3 font-mono text-xs leading-relaxed text-zinc-500"
          >
            {progressLog.length === 0 ? (
              <span className="text-zinc-600">Resolving universe...</span>
            ) : (
              progressLog.map((msg, i) => {
                const isError = msg.toLowerCase().includes('failed');
                const isDone = msg.toLowerCase().startsWith('done');
                return (
                  <div
                    key={i}
                    className={
                      isError
                        ? 'text-amber-500'
                        : isDone
                          ? 'text-emerald-400'
                          : 'text-zinc-500'
                    }
                  >
                    {msg}
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {runScanner.isError && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {runScanner.error.message}
        </div>
      )}

      {/* Results */}
      {lastResult && !runScanner.isPending && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm text-zinc-500">
            <span>
              {lastResult.signal_count} signal{lastResult.signal_count !== 1 ? 's' : ''} found
            </span>
            {lastResult.universe && (
              <>
                <span>&middot;</span>
                <span>Universe: {lastResult.universe}</span>
              </>
            )}
            <span>&middot;</span>
            <span>{new Date(lastResult.ran_at + 'Z').toLocaleString()}</span>
          </div>

          {selectedSignal ? (
            <PlaybookPanel signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
          ) : lastResult.signals.length === 0 ? (
            <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-500">
              No actionable signals found.
            </div>
          ) : (
            <div className="overflow-hidden rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-900/50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <th className="px-4 py-3 w-12">#</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Symbol</th>
                    <th className="px-4 py-3">Conviction</th>
                    <th className="px-4 py-3">Qty</th>
                    <th className="px-4 py-3">Strategy</th>
                    <th className="px-4 py-3">Summary</th>
                    <th className="px-4 py-3 w-24"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {lastResult.signals.map((s, i) => {
                    const dirLabel =
                      s.direction === 'long'
                        ? 'Buy'
                        : s.direction === 'close'
                          ? 'Sell'
                          : 'Sell Short';
                    const dirColor =
                      s.direction === 'long'
                        ? 'text-emerald-400'
                        : s.direction === 'close'
                          ? 'text-red-400'
                          : 'text-amber-400';
                    return (
                      <tr
                        key={`${s.symbol}-${i}`}
                        className="cursor-pointer transition-colors hover:bg-zinc-900/50"
                        onClick={() => setSelectedSignal(s)}
                      >
                        <td className="px-4 py-3 text-zinc-600">{i + 1}</td>
                        <td className={`px-4 py-3 font-semibold ${dirColor}`}>
                          {dirLabel}
                        </td>
                        <td className="px-4 py-3 font-mono font-medium text-zinc-200">
                          {s.symbol}
                        </td>
                        <td className="px-4 py-3">
                          <ConvictionBadge conviction={s.conviction} />
                        </td>
                        <td className="px-4 py-3 text-zinc-300">{s.quantity}</td>
                        <td className="px-4 py-3 text-zinc-400">{s.strategy_name}</td>
                        <td className="max-w-xs truncate px-4 py-3 text-zinc-400">
                          {s.rationale}
                        </td>
                        <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                          {/* Add to Watchlist dropdown */}
                          <div className="relative">
                            <button
                              onClick={() =>
                                setAddingToWatchlist(
                                  addingToWatchlist === s.symbol ? null : s.symbol,
                                )
                              }
                              className="rounded px-2 py-1 text-xs text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                              title="Add to watchlist"
                            >
                              + List
                            </button>
                            {addingToWatchlist === s.symbol && watchlists && (
                              <div className="absolute right-0 top-8 z-10 min-w-[160px] rounded-md border border-zinc-700 bg-zinc-900 py-1 shadow-lg">
                                {watchlists.map((wl) => (
                                  <button
                                    key={wl.id}
                                    onClick={() => handleAddToWatchlist(s.symbol, wl.id)}
                                    className="block w-full px-3 py-1.5 text-left text-xs text-zinc-300 hover:bg-zinc-800"
                                  >
                                    {wl.name}
                                    {wl.symbols.includes(s.symbol) && (
                                      <span className="ml-1 text-zinc-600">(added)</span>
                                    )}
                                  </button>
                                ))}
                                {watchlists.length === 0 && (
                                  <span className="block px-3 py-1.5 text-xs text-zinc-500">
                                    No watchlists
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!lastResult && !runScanner.isPending && (
        <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-600">
          Select a universe, choose strategies, and scan to discover opportunities.
        </div>
      )}
    </div>
  );
}

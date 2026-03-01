import { useEffect, useRef, useState } from 'react';
import ConvictionBadge from '../components/ConvictionBadge';
import PlaybookPanel from '../components/PlaybookPanel';
import { useConfig, useUpdateConfig } from '../hooks/useConfig';
import { useRunScannerStream } from '../hooks/useScanner';
import { useUpdateWatchlist, useWatchlists } from '../hooks/useWatchlists';
import { usePositions } from '../hooks/usePositions';
import type { ScannerResponse, Signal } from '../types/api';
import { fmt, fmtInt } from '../utils/format';

const UNIVERSE_OPTIONS = [
  // Indices
  { value: 'sp500', label: 'S&P 500 \u2014 500 largest US companies', group: 'indices' },
  { value: 'nasdaq100', label: 'NASDAQ 100 \u2014 Top tech & growth stocks', group: 'indices' },
  { value: 'dow30', label: 'Dow 30 \u2014 30 blue-chip industrials', group: 'indices' },
  { value: 'smallcap100', label: 'Small-Cap 100 \u2014 Top liquid small caps', group: 'indices' },
  // Sectors
  { value: 'technology', label: 'Technology \u2014 Software, semiconductors, hardware', group: 'sectors' },
  { value: 'healthcare', label: 'Healthcare \u2014 Pharma, biotech, med devices', group: 'sectors' },
  { value: 'financials', label: 'Financials \u2014 Banks, insurance, asset mgmt', group: 'sectors' },
  { value: 'consumer_discretionary', label: 'Consumer Discretionary \u2014 Retail, auto, leisure', group: 'sectors' },
  { value: 'communication_services', label: 'Communication Services \u2014 Media, telecom, social', group: 'sectors' },
  { value: 'industrials', label: 'Industrials \u2014 Aerospace, machinery, transport', group: 'sectors' },
  { value: 'consumer_staples', label: 'Consumer Staples \u2014 Food, beverage, household', group: 'sectors' },
  { value: 'energy', label: 'Energy \u2014 Oil, gas, renewables', group: 'sectors' },
  { value: 'utilities', label: 'Utilities \u2014 Electric, gas, water', group: 'sectors' },
  { value: 'real_estate', label: 'Real Estate \u2014 REITs, property, data centers', group: 'sectors' },
  { value: 'materials', label: 'Materials \u2014 Chemicals, metals, packaging', group: 'sectors' },
  // Forex
  { value: 'forex_majors', label: 'Forex Majors \u2014 EUR, GBP, JPY, etc.', group: 'forex' },
  // Trending
  { value: 'gainers', label: 'Top Gainers \u2014 Biggest risers today', group: 'trending' },
  { value: 'losers', label: 'Top Losers \u2014 Biggest drops today', group: 'trending' },
  { value: 'most_active', label: 'Most Active \u2014 Highest volume today', group: 'trending' },
  // Custom
  { value: 'custom', label: 'Custom Symbols \u2014 Enter your own', group: 'custom' },
] as const;

const STRATEGY_OPTIONS = [
  {
    value: 'momentum',
    label: 'Momentum',
    description: 'Finds stocks trending upward \u2014 rising moving averages + strong volume. Best for riding existing trends.',
  },
  {
    value: 'mean_reversion',
    label: 'Mean Reversion',
    description: 'Finds stocks that dropped too far too fast \u2014 oversold on RSI, near Bollinger Band lows. Best for bounce-back trades.',
  },
  {
    value: 'income',
    label: 'Income',
    description: 'Finds stocks with high volatility suitable for selling options (covered calls, cash-secured puts). Best for generating premium income.',
  },
  {
    value: 'macd_divergence',
    label: 'MACD Divergence',
    description: 'Spots when price and MACD disagree \u2014 price makes new lows but momentum is rising (or vice versa). Best for catching reversals early.',
  },
  {
    value: 'intermarket',
    label: 'Global Macro',
    description: 'Compares each stock to SPY, dollar, bonds, and gold trends. Favors stocks aligned with the current market regime. Best for macro-aware positioning.',
  },
] as const;

const HOLDING_PERIODS = [
  { value: 'swing', label: 'Swing', description: '2\u20134 weeks' },
  { value: 'position', label: 'Position', description: '1\u20133 months' },
  { value: 'longterm', label: 'Long-term', description: '3+ months' },
] as const;

const LOOKBACK_STEPS = [30, 60, 90, 120, 180, 365];

const CONVICTION_INFO_KEY = 'scanner_conviction_info_dismissed';

type SortCol = 'symbol' | 'conviction' | 'strategy' | 'quantity' | 'entry' | 'risk' | 'reward';
type SortDir = 'asc' | 'desc';

function sortSignals(signals: Signal[], col: SortCol, dir: SortDir): Signal[] {
  const sorted = Array.from(signals);
  const mult = dir === 'asc' ? 1 : -1;
  sorted.sort((a, b) => {
    let av: number | string;
    let bv: number | string;
    switch (col) {
      case 'symbol':
        return mult * a.symbol.localeCompare(b.symbol);
      case 'conviction':
        return mult * (a.conviction - b.conviction);
      case 'strategy':
        return mult * a.strategy_name.localeCompare(b.strategy_name);
      case 'quantity':
        return mult * (a.quantity - b.quantity);
      case 'entry':
        av = a.limit_price ?? 0;
        bv = b.limit_price ?? 0;
        return mult * ((av as number) - (bv as number));
      case 'risk':
        av = a.risk_amount ?? 0;
        bv = b.risk_amount ?? 0;
        return mult * ((av as number) - (bv as number));
      case 'reward':
        av = a.reward_amount ?? 0;
        bv = b.reward_amount ?? 0;
        return mult * ((av as number) - (bv as number));
      default:
        return 0;
    }
  });
  return sorted;
}

export default function ScannerPage() {
  const runScanner = useRunScannerStream();
  const { data: watchlists } = useWatchlists();
  const updateWatchlist = useUpdateWatchlist();
  const { data: positions } = usePositions();
  const { data: config } = useConfig();
  const updateConfig = useUpdateConfig();

  const [universe, setUniverse] = useState('sp500');
  const [customSymbols, setCustomSymbols] = useState('');
  const [selectedStrategies, setSelectedStrategies] = useState<string[]>([
    'momentum',
    'mean_reversion',
    'income',
    'macd_divergence',
    'intermarket',
  ]);
  const [maxResults, setMaxResults] = useState(20);
  const [lookbackDays, setLookbackDays] = useState(120);
  const [holdingPeriod, setHoldingPeriod] = useState<string | null>(null);
  const [minConviction, setMinConviction] = useState(0);
  const [lastResult, setLastResult] = useState<ScannerResponse | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);
  const [addingToWatchlist, setAddingToWatchlist] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<string[]>([]);
  const [infoDismissed, setInfoDismissed] = useState(
    () => localStorage.getItem(CONVICTION_INFO_KEY) === '1',
  );
  const logRef = useRef<HTMLDivElement>(null);

  // Sort state
  const [sortCol, setSortCol] = useState<SortCol>('conviction');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Position modeler state — initialized from config
  const [stake, setStake] = useState<number | null>(null);
  const [maxPositionPct, setMaxPositionPct] = useState<number | null>(null);
  const [stopLossPct, setStopLossPct] = useState<number | null>(null);
  const [modelerOpen, setModelerOpen] = useState(false);

  useEffect(() => {
    if (config && stake === null) {
      setStake(config.stake);
      setMaxPositionPct(Math.round(config.max_position_pct * 100));
      setStopLossPct(Math.round(config.stop_loss_pct * 100));
    }
  }, [config, stake]);

  function toggleSort(col: SortCol) {
    if (sortCol === col) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortCol(col);
      setSortDir(col === 'symbol' || col === 'strategy' ? 'asc' : 'desc');
    }
  }

  function SortHeader({ col, label, className }: { col: SortCol; label: string; className?: string }) {
    const active = sortCol === col;
    const arrow = active ? (sortDir === 'asc' ? ' \u25B2' : ' \u25BC') : '';
    return (
      <th
        className={`px-4 py-3 cursor-pointer select-none transition-colors hover:text-zinc-300 ${active ? 'text-zinc-300' : ''} ${className ?? ''}`}
        onClick={() => toggleSort(col)}
      >
        {label}{arrow}
      </th>
    );
  }

  function toggleStrategy(name: string) {
    setSelectedStrategies((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    );
  }

  function handleModelerSave() {
    if (stake == null || maxPositionPct == null || stopLossPct == null) return;
    updateConfig.mutate({
      stake,
      max_position_pct: maxPositionPct / 100,
      stop_loss_pct: stopLossPct / 100,
    });
  }

  function handleScan() {
    const req: Record<string, unknown> = {
      strategies: selectedStrategies.length > 0 ? selectedStrategies : undefined,
      max_results: maxResults,
      lookback_days: lookbackDays,
      holding_period: holdingPeriod ?? undefined,
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

  function dismissInfo() {
    localStorage.setItem(CONVICTION_INFO_KEY, '1');
    setInfoDismissed(true);
  }

  // Client-side conviction filter
  const filteredSignals = lastResult?.signals.filter(
    (s) => Math.round(s.conviction * 100) >= minConviction,
  );

  // Apply sorting
  const sortedSignals = filteredSignals ? sortSignals(filteredSignals, sortCol, sortDir) : undefined;

  // Check if user has positions matching any scanner results
  const ownedSymbols = positions?.map((p) => p.symbol) ?? [];
  const ownedInResults =
    sortedSignals?.filter((s) => ownedSymbols.includes(s.symbol)) ?? [];

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Scanner</h1>

      {/* Conviction info banner */}
      {!infoDismissed && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-blue-900/40 bg-blue-950/20 p-4 text-sm text-blue-300">
          <span className="mt-0.5 shrink-0 text-blue-400">i</span>
          <p className="flex-1">
            Conviction measures how many technical indicators agree on a signal &mdash;
            higher means stronger alignment. It is not a guarantee of profit. Past patterns
            don&apos;t always repeat. Use signals as a starting point for your own research.
          </p>
          <button
            onClick={dismissInfo}
            className="shrink-0 rounded px-1.5 py-0.5 text-xs text-blue-400 hover:bg-blue-900/30 hover:text-blue-300"
          >
            &times;
          </button>
        </div>
      )}

      {/* Controls */}
      <div className="mb-6 space-y-4 rounded-lg border border-zinc-800 p-4">
        {/* Position Sizing Modeler */}
        <details
          open={modelerOpen}
          onToggle={(e) => setModelerOpen((e.target as HTMLDetailsElement).open)}
        >
          <summary className="cursor-pointer text-sm font-medium text-zinc-400 hover:text-zinc-300">
            Position Sizing
            {stake != null && (
              <span className="ml-2 font-normal text-zinc-600">
                {fmt(stake)} stake &middot; {maxPositionPct}% max &middot; {stopLossPct}% stop
              </span>
            )}
          </summary>
          <div className="mt-3 flex flex-wrap items-end gap-4">
            <div className="w-40">
              <label className="mb-1 block text-xs font-medium text-zinc-500">Stake ($)</label>
              <input
                type="number"
                value={stake ?? ''}
                onChange={(e) => setStake(Number(e.target.value))}
                className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-zinc-200 outline-none focus:border-emerald-500/50"
              />
              <p className="mt-0.5 text-xs text-zinc-600">Total capital to deploy</p>
            </div>
            <div className="w-40">
              <label className="mb-1 block text-xs font-medium text-zinc-500">
                Max Position: {maxPositionPct ?? 0}%
              </label>
              <input
                type="range"
                min={5}
                max={100}
                step={5}
                value={maxPositionPct ?? 10}
                onChange={(e) => setMaxPositionPct(Number(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <p className="mt-0.5 text-xs text-zinc-600">Max % of stake per position</p>
            </div>
            <div className="w-40">
              <label className="mb-1 block text-xs font-medium text-zinc-500">
                Stop Loss: {stopLossPct ?? 0}%
              </label>
              <input
                type="range"
                min={1}
                max={20}
                step={1}
                value={stopLossPct ?? 5}
                onChange={(e) => setStopLossPct(Number(e.target.value))}
                className="w-full accent-emerald-500"
              />
              <p className="mt-0.5 text-xs text-zinc-600">Stop distance from entry</p>
            </div>
            <button
              onClick={handleModelerSave}
              disabled={updateConfig.isPending}
              className="rounded-md bg-zinc-700 px-4 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-zinc-600 disabled:opacity-50"
            >
              {updateConfig.isPending ? 'Saving...' : 'Apply'}
            </button>
            {updateConfig.isSuccess && (
              <span className="text-xs text-emerald-400">Saved</span>
            )}
          </div>
        </details>

        {/* Holding period toggle */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-400">Holding Period</label>
          <div className="flex gap-2">
            {HOLDING_PERIODS.map((hp) => (
              <button
                key={hp.value}
                onClick={() => setHoldingPeriod(holdingPeriod === hp.value ? null : hp.value)}
                className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                  holdingPeriod === hp.value
                    ? 'border-emerald-500/50 bg-emerald-900/30 text-emerald-300'
                    : 'border-zinc-700 text-zinc-400 hover:border-zinc-600 hover:text-zinc-300'
                }`}
              >
                {hp.label}
                <span className="ml-1.5 text-xs opacity-60">{hp.description}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          {/* Search In (was Universe) */}
          <div className="min-w-[200px] flex-1">
            <label className="mb-1 block text-sm font-medium text-zinc-400">Search In</label>
            <select
              value={universe}
              onChange={(e) => setUniverse(e.target.value)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
            >
              <optgroup label="Indices">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'indices').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Sectors">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'sectors').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Forex">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'forex').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Trending Today">
                {UNIVERSE_OPTIONS.filter((o) => o.group === 'trending').map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </optgroup>
              <optgroup label="Custom">
                <option value="custom">Custom Symbols &mdash; Enter your own</option>
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

          {/* Lookback */}
          <div className="w-36">
            <label className="mb-1 block text-sm font-medium text-zinc-400">
              Lookback: {lookbackDays}d
            </label>
            <input
              type="range"
              min={0}
              max={LOOKBACK_STEPS.length - 1}
              step={1}
              value={LOOKBACK_STEPS.indexOf(lookbackDays)}
              onChange={(e) => setLookbackDays(LOOKBACK_STEPS[Number(e.target.value)])}
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

        {/* Strategy checkboxes with descriptions */}
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-400">
            Strategies <span className="font-normal text-zinc-600">(5 included)</span>
          </label>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {STRATEGY_OPTIONS.map((s) => (
              <label
                key={s.value}
                className={`flex cursor-pointer items-start gap-2 rounded-lg border p-3 transition-colors ${
                  selectedStrategies.includes(s.value)
                    ? 'border-emerald-500/40 bg-emerald-950/10'
                    : 'border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedStrategies.includes(s.value)}
                  onChange={() => toggleStrategy(s.value)}
                  className="mt-0.5 rounded border-zinc-600 bg-zinc-800 text-emerald-500 accent-emerald-500"
                />
                <div>
                  <span className="text-sm font-medium text-zinc-200">{s.label}</span>
                  <p className="mt-0.5 text-xs text-zinc-500">{s.description}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Min conviction (opportunity filter) */}
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-zinc-400">
            Opportunity Filter: {minConviction}%+
          </label>
          <input
            type="range"
            min={0}
            max={80}
            step={5}
            value={minConviction}
            onChange={(e) => setMinConviction(Number(e.target.value))}
            className="w-40 accent-emerald-500"
          />
          <span className="text-xs text-zinc-600">
            {minConviction === 0 ? 'Show all' : 'Higher = stronger setups only'}
          </span>
        </div>
      </div>

      {/* Progress log — visible during scan */}
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
                const isError = msg.toLowerCase().includes('error') || msg.toLowerCase().includes('failed');
                const isSkipped = msg.toLowerCase().includes('skipped');
                const isDone = msg.toLowerCase().startsWith('done');
                const isInfo = msg.toLowerCase().startsWith('provider:');
                return (
                  <div
                    key={i}
                    className={
                      isError
                        ? 'text-red-400'
                        : isSkipped
                          ? 'text-amber-500'
                          : isDone
                            ? 'text-emerald-400'
                            : isInfo
                              ? 'text-blue-400'
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

      {/* Collapsible progress log after scan completes */}
      {!runScanner.isPending && progressLog.length > 0 && (
        <details className="mb-4 rounded-lg border border-zinc-800">
          <summary className="cursor-pointer px-4 py-2 text-xs text-zinc-500 hover:text-zinc-400">
            Scan log ({progressLog.length} messages)
          </summary>
          <div className="max-h-48 overflow-y-auto border-t border-zinc-800 p-3 font-mono text-xs leading-relaxed">
            {progressLog.map((msg, i) => {
              const isError = msg.toLowerCase().includes('error') || msg.toLowerCase().includes('failed');
              const isSkipped = msg.toLowerCase().includes('skipped');
              const isDone = msg.toLowerCase().startsWith('done');
              const isInfo = msg.toLowerCase().startsWith('provider:');
              return (
                <div
                  key={i}
                  className={
                    isError
                      ? 'text-red-400'
                      : isSkipped
                        ? 'text-amber-500'
                        : isDone
                          ? 'text-emerald-400'
                          : isInfo
                            ? 'text-blue-400'
                            : 'text-zinc-500'
                  }
                >
                  {msg}
                </div>
              );
            })}
          </div>
        </details>
      )}

      {/* Error */}
      {runScanner.isError && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {runScanner.error.message}
        </div>
      )}

      {/* Owned stocks banner */}
      {ownedInResults.length > 0 && !selectedSignal && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-purple-900/40 bg-purple-950/20 px-4 py-2.5 text-sm text-purple-300">
          <span>Own {ownedInResults.map((s) => s.symbol).join(', ')}?</span>
          <a
            href="/plays"
            className="font-medium text-purple-400 hover:text-purple-300 hover:underline"
          >
            Check Options & Plays for income strategies &rarr;
          </a>
        </div>
      )}

      {/* Results */}
      {lastResult && !runScanner.isPending && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm text-zinc-500">
            <span>
              {sortedSignals?.length ?? 0} signal{(sortedSignals?.length ?? 0) !== 1 ? 's' : ''}{' '}
              {minConviction > 0 && `(${lastResult.signal_count} total, filtered to ${minConviction}%+)`}
            </span>
            {lastResult.universe && (
              <>
                <span>&middot;</span>
                <span>{lastResult.universe}</span>
              </>
            )}
            <span>&middot;</span>
            <span>{new Date(lastResult.ran_at + 'Z').toLocaleString()}</span>
          </div>

          {selectedSignal ? (
            <PlaybookPanel signal={selectedSignal} onClose={() => setSelectedSignal(null)} />
          ) : !sortedSignals || sortedSignals.length === 0 ? (
            <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-500">
              No actionable signals found.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-zinc-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 bg-zinc-900/50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                    <th className="px-4 py-3 w-12">#</th>
                    <th className="px-4 py-3">Action</th>
                    <SortHeader col="symbol" label="Symbol" />
                    <SortHeader col="conviction" label="Conviction" />
                    <SortHeader col="entry" label="Entry" />
                    <SortHeader col="risk" label="Risk" />
                    <SortHeader col="reward" label="Reward" />
                    <SortHeader col="quantity" label="Qty" />
                    <SortHeader col="strategy" label="Strategy" />
                    <th className="px-4 py-3">Summary</th>
                    <th className="px-4 py-3 w-24"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/50">
                  {sortedSignals.map((s, i) => {
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
                        <td className="px-4 py-3">
                          <div className="font-mono font-medium text-zinc-200">{s.symbol}</div>
                          {s.company_name && (
                            <div className="text-xs text-zinc-500">{s.company_name}</div>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <ConvictionBadge conviction={s.conviction} />
                        </td>
                        <td className="px-4 py-3 font-mono text-zinc-300">
                          {s.limit_price != null ? fmt(s.limit_price) : '\u2014'}
                        </td>
                        <td className="px-4 py-3 font-mono text-red-400">
                          {s.risk_amount != null ? fmt(s.risk_amount) : '\u2014'}
                        </td>
                        <td className="px-4 py-3 font-mono text-emerald-400">
                          {s.reward_amount != null ? fmt(s.reward_amount) : '\u2014'}
                        </td>
                        <td className="px-4 py-3 text-zinc-300">{fmtInt(s.quantity)}</td>
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
          Select a market, choose strategies, and scan to discover opportunities.
        </div>
      )}
    </div>
  );
}

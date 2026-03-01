import { useState } from 'react';
import PlaybookPanel from '../components/PlaybookPanel';
import SignalTable from '../components/SignalTable';
import { useRunScan } from '../hooks/useScans';
import { useWatchlists } from '../hooks/useWatchlists';
import type { ScanResponse, Signal } from '../types/api';

export default function ScanPage() {
  const { data: watchlists } = useWatchlists();
  const runScan = useRunScan();

  const [selectedWatchlist, setSelectedWatchlist] = useState<number | ''>('');
  const [lastScan, setLastScan] = useState<ScanResponse | null>(null);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  function handleScan() {
    if (!selectedWatchlist) return;
    runScan.mutate(
      { watchlist_id: Number(selectedWatchlist) },
      {
        onSuccess: (data) => {
          setLastScan(data);
          setSelectedSignal(null);
        },
      },
    );
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Scan</h1>

      {/* Controls */}
      <div className="mb-6 flex items-end gap-4 rounded-lg border border-zinc-800 p-4">
        <div className="flex-1">
          <label className="mb-1 block text-sm font-medium text-zinc-400">
            Watchlist
          </label>
          <select
            value={selectedWatchlist}
            onChange={(e) => setSelectedWatchlist(e.target.value ? Number(e.target.value) : '')}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          >
            <option value="">Select a watchlist...</option>
            {watchlists?.map((wl) => (
              <option key={wl.id} value={wl.id}>
                {wl.name} ({wl.symbols.length} symbols)
              </option>
            ))}
          </select>
        </div>
        <button
          onClick={handleScan}
          disabled={!selectedWatchlist || runScan.isPending}
          className="rounded-md bg-emerald-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
        >
          {runScan.isPending ? 'Scanning...' : 'Run Scan'}
        </button>
      </div>

      {/* Loading */}
      {runScan.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 p-8 text-zinc-400">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
          Scanning symbols...
        </div>
      )}

      {/* Error */}
      {runScan.isError && (
        <div className="rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {runScan.error.message}
        </div>
      )}

      {/* Results */}
      {lastScan && !runScan.isPending && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 text-sm text-zinc-500">
            <span>
              {lastScan.signal_count} signal{lastScan.signal_count !== 1 ? 's' : ''} found
            </span>
            <span>&middot;</span>
            <span>{new Date(lastScan.ran_at + 'Z').toLocaleString()}</span>
          </div>

          {selectedSignal ? (
            <PlaybookPanel
              signal={selectedSignal}
              onClose={() => setSelectedSignal(null)}
            />
          ) : (
            <SignalTable
              signals={lastScan.signals}
              onSelect={setSelectedSignal}
            />
          )}
        </div>
      )}

      {/* Empty state */}
      {!lastScan && !runScan.isPending && (
        <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-600">
          Select a watchlist and run a scan to see signals.
        </div>
      )}
    </div>
  );
}

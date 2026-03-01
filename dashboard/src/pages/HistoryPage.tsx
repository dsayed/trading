import { useState } from 'react';
import PlaybookPanel from '../components/PlaybookPanel';
import SignalTable from '../components/SignalTable';
import { useScan, useScanHistory } from '../hooks/useScans';
import type { Signal } from '../types/api';

export default function HistoryPage() {
  const { data: scans, isLoading } = useScanHistory();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: scanDetail } = useScan(selectedId);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">
        Scan History
      </h1>

      {!selectedId && (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          {scans?.length === 0 ? (
            <div className="p-12 text-center text-sm text-zinc-600">
              No scans yet. Go to Scan to run your first one.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Watchlist</th>
                  <th className="px-4 py-3">Symbols</th>
                  <th className="px-4 py-3">Signals</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {scans?.map((s) => (
                  <tr
                    key={s.id}
                    className="cursor-pointer transition-colors hover:bg-zinc-900/50"
                    onClick={() => {
                      setSelectedId(s.id);
                      setSelectedSignal(null);
                    }}
                  >
                    <td className="px-4 py-3 text-zinc-300">
                      {new Date(s.ran_at + 'Z').toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-zinc-400">
                      {s.watchlist_name || '—'}
                    </td>
                    <td className="px-4 py-3 font-mono text-zinc-400">
                      {s.symbols.join(', ')}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          s.signal_count > 0
                            ? 'bg-emerald-900/50 text-emerald-400'
                            : 'bg-zinc-800 text-zinc-500'
                        }`}
                      >
                        {s.signal_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {selectedId && (
        <div className="space-y-4">
          <button
            onClick={() => {
              setSelectedId(null);
              setSelectedSignal(null);
            }}
            className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
          >
            &larr; Back to history
          </button>

          {scanDetail && (
            <>
              <div className="text-sm text-zinc-500">
                {scanDetail.signal_count} signal
                {scanDetail.signal_count !== 1 ? 's' : ''} &middot;{' '}
                {new Date(scanDetail.ran_at + 'Z').toLocaleString()}
              </div>

              {selectedSignal ? (
                <PlaybookPanel
                  signal={selectedSignal}
                  onClose={() => setSelectedSignal(null)}
                />
              ) : (
                <SignalTable
                  signals={scanDetail.signals}
                  onSelect={setSelectedSignal}
                />
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

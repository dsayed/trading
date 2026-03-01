import { useRef, useState } from 'react';
import { useImportCommit, useImportPreview } from '../hooks/useImport';
import type { ImportPreviewResponse } from '../types/api';

export default function ImportPage() {
  const preview = useImportPreview();
  const commit = useImportCommit();
  const fileRef = useRef<HTMLInputElement>(null);

  const [previewData, setPreviewData] = useState<ImportPreviewResponse | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [committed, setCommitted] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  function handleFile(file: File) {
    setCommitted(false);
    preview.mutate(file, {
      onSuccess: (data) => {
        setPreviewData(data);
        // Pre-select all non-warning positions
        const indices = new Set<number>();
        data.positions.forEach((p, i) => {
          if (p.status !== 'warning') indices.add(i);
        });
        setSelected(indices);
      },
    });
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }

  function toggleSelect(idx: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }

  function selectAll() {
    if (!previewData) return;
    const all = new Set<number>(previewData.positions.map((_, i) => i));
    setSelected(all);
  }

  function deselectAll() {
    setSelected(new Set());
  }

  function handleCommit() {
    if (!previewData) return;
    const toImport = previewData.positions.filter((_, i) => selected.has(i));
    commit.mutate(
      { positions: toImport },
      { onSuccess: () => setCommitted(true) },
    );
  }

  const statusStyle = (status: string) => {
    switch (status) {
      case 'duplicate': return 'bg-amber-950/30 text-amber-400';
      case 'warning': return 'bg-red-950/30 text-red-400';
      default: return 'text-emerald-400';
    }
  };

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Import Positions</h1>

      {/* Upload zone */}
      {!previewData && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-16 transition-colors ${
            dragOver
              ? 'border-emerald-500 bg-emerald-950/10'
              : 'border-zinc-700 hover:border-zinc-600'
          }`}
        >
          <div className="mb-4 text-4xl text-zinc-600">&#8593;</div>
          <p className="mb-2 text-sm text-zinc-400">
            Drag & drop a CSV file, or{' '}
            <button
              onClick={() => fileRef.current?.click()}
              className="text-emerald-400 hover:underline"
            >
              browse
            </button>
          </p>
          <p className="text-xs text-zinc-600">
            Supports Fidelity exports and generic CSV (Symbol, Quantity, Cost Basis)
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>
      )}

      {/* Loading */}
      {preview.isPending && (
        <div className="flex items-center gap-3 rounded-lg border border-zinc-800 p-8 text-zinc-400">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
          Parsing CSV...
        </div>
      )}

      {/* Error */}
      {preview.isError && (
        <div className="mb-4 rounded-lg border border-red-900/50 bg-red-950/20 p-4 text-sm text-red-400">
          {preview.error.message}
        </div>
      )}

      {/* Preview */}
      {previewData && !committed && (
        <div className="space-y-4">
          {/* Header */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-800 p-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-zinc-200">
                Detected: <span className="text-emerald-400">{previewData.broker_detected}</span>
              </p>
              <p className="text-xs text-zinc-500">
                {previewData.summary.new} new &middot;{' '}
                {previewData.summary.duplicates} duplicate{previewData.summary.duplicates !== 1 ? 's' : ''} (will add as tax lots) &middot;{' '}
                {previewData.summary.warnings} warning{previewData.summary.warnings !== 1 ? 's' : ''}
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={selectAll} className="rounded px-3 py-1 text-xs text-zinc-400 hover:bg-zinc-800">
                Select All
              </button>
              <button onClick={deselectAll} className="rounded px-3 py-1 text-xs text-zinc-400 hover:bg-zinc-800">
                Deselect All
              </button>
              <button
                onClick={() => { setPreviewData(null); setSelected(new Set()); }}
                className="rounded px-3 py-1 text-xs text-zinc-400 hover:bg-zinc-800"
              >
                Upload Different File
              </button>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-900/50 text-left text-xs font-medium uppercase tracking-wider text-zinc-500">
                  <th className="px-4 py-3 w-10"></th>
                  <th className="px-4 py-3">Symbol</th>
                  <th className="px-4 py-3">Qty</th>
                  <th className="px-4 py-3">Cost Basis</th>
                  <th className="px-4 py-3">Asset Class</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/50">
                {previewData.positions.map((p, i) => (
                  <tr
                    key={`${p.symbol}-${i}`}
                    className={p.status === 'duplicate' ? 'bg-amber-950/10' : ''}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selected.has(i)}
                        onChange={() => toggleSelect(i)}
                        className="rounded border-zinc-600 bg-zinc-800 accent-emerald-500"
                      />
                    </td>
                    <td className="px-4 py-3 font-mono font-medium text-zinc-200">{p.symbol}</td>
                    <td className="px-4 py-3 text-zinc-300">{p.quantity}</td>
                    <td className="px-4 py-3 font-mono text-zinc-300">${p.cost_basis.toFixed(2)}</td>
                    <td className="px-4 py-3 text-zinc-400">{p.asset_class}</td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${statusStyle(p.status)}`}>
                        {p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-zinc-500">
                      {p.warnings.length > 0 && p.warnings.join(', ')}
                      {p.status === 'duplicate' && 'Will add as new tax lot'}
                      {p.description && !p.warnings.length && p.status !== 'duplicate' && p.description}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Commit button */}
          <div className="flex justify-end">
            <button
              onClick={handleCommit}
              disabled={selected.size === 0 || commit.isPending}
              className="rounded-md bg-emerald-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
            >
              {commit.isPending
                ? 'Importing...'
                : `Import ${selected.size} Position${selected.size !== 1 ? 's' : ''}`}
            </button>
          </div>
        </div>
      )}

      {/* Success */}
      {committed && (
        <div className="rounded-lg border border-emerald-900/50 bg-emerald-950/20 p-8 text-center">
          <p className="text-lg font-medium text-emerald-400">
            Successfully imported {commit.data?.imported} position{commit.data?.imported !== 1 ? 's' : ''}
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            View them on the{' '}
            <a href="/positions" className="text-emerald-400 hover:underline">Positions</a> page.
          </p>
          <button
            onClick={() => {
              setPreviewData(null);
              setSelected(new Set());
              setCommitted(false);
            }}
            className="mt-4 rounded-md border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Import Another File
          </button>
        </div>
      )}
    </div>
  );
}

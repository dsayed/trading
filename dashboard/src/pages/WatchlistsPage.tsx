import { useState } from 'react';
import SymbolInput from '../components/SymbolInput';
import {
  useCreateWatchlist,
  useDeleteWatchlist,
  useUpdateWatchlist,
  useWatchlists,
} from '../hooks/useWatchlists';
import type { Watchlist } from '../types/api';

export default function WatchlistsPage() {
  const { data: watchlists, isLoading } = useWatchlists();
  const createWatchlist = useCreateWatchlist();
  const updateWatchlist = useUpdateWatchlist();
  const deleteWatchlist = useDeleteWatchlist();

  const [selected, setSelected] = useState<Watchlist | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState('');

  function handleCreate() {
    if (!newName.trim()) return;
    createWatchlist.mutate(
      { name: newName.trim(), symbols: [] },
      {
        onSuccess: (wl) => {
          setSelected(wl);
          setIsCreating(false);
          setNewName('');
        },
      },
    );
  }

  function handleUpdateSymbols(symbols: string[]) {
    if (!selected) return;
    updateWatchlist.mutate(
      { id: selected.id, data: { symbols } },
      {
        onSuccess: (wl) => setSelected(wl),
      },
    );
  }

  function handleRename(name: string) {
    if (!selected || !name.trim()) return;
    updateWatchlist.mutate(
      { id: selected.id, data: { name: name.trim() } },
      {
        onSuccess: (wl) => setSelected(wl),
      },
    );
  }

  function handleDelete() {
    if (!selected) return;
    deleteWatchlist.mutate(selected.id, {
      onSuccess: () => setSelected(null),
    });
  }

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-zinc-100">Watchlists</h1>
        <button
          onClick={() => {
            setIsCreating(true);
            setSelected(null);
          }}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
        >
          New Watchlist
        </button>
      </div>

      <div className="flex gap-6">
        {/* List panel */}
        <div className="w-72 flex-shrink-0">
          <div className="space-y-1">
            {watchlists?.map((wl) => (
              <button
                key={wl.id}
                onClick={() => {
                  setSelected(wl);
                  setIsCreating(false);
                }}
                className={`flex w-full items-center justify-between rounded-lg px-4 py-3 text-left text-sm transition-colors ${
                  selected?.id === wl.id
                    ? 'bg-zinc-800 text-zinc-100'
                    : 'text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200'
                }`}
              >
                <span className="font-medium">{wl.name}</span>
                <span className="text-xs text-zinc-600">
                  {wl.symbols.length} symbols
                </span>
              </button>
            ))}
            {watchlists?.length === 0 && !isCreating && (
              <p className="px-4 py-8 text-center text-sm text-zinc-600">
                No watchlists yet. Create one to get started.
              </p>
            )}
          </div>
        </div>

        {/* Detail panel */}
        <div className="flex-1">
          {isCreating && (
            <div className="rounded-lg border border-zinc-800 p-6">
              <h2 className="mb-4 text-lg font-medium text-zinc-200">
                New Watchlist
              </h2>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
                  placeholder="Watchlist name"
                  autoFocus
                  className="flex-1 rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
                />
                <button
                  onClick={handleCreate}
                  disabled={!newName.trim()}
                  className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
                >
                  Create
                </button>
                <button
                  onClick={() => {
                    setIsCreating(false);
                    setNewName('');
                  }}
                  className="rounded-md px-4 py-2 text-sm text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {selected && !isCreating && (
            <div className="rounded-lg border border-zinc-800 p-6">
              <div className="mb-5 flex items-center justify-between">
                <EditableName
                  name={selected.name}
                  onSave={handleRename}
                />
                <button
                  onClick={handleDelete}
                  className="rounded-md px-3 py-1.5 text-sm text-red-400 transition-colors hover:bg-red-950/50"
                >
                  Delete
                </button>
              </div>
              <h3 className="mb-3 text-sm font-medium text-zinc-400">
                Symbols
              </h3>
              <SymbolInput
                symbols={selected.symbols}
                onChange={handleUpdateSymbols}
              />
            </div>
          )}

          {!selected && !isCreating && (
            <div className="flex h-48 items-center justify-center text-sm text-zinc-600">
              Select a watchlist or create a new one
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EditableName({
  name,
  onSave,
}: {
  name: string;
  onSave: (name: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(name);

  if (!editing) {
    return (
      <h2
        className="cursor-pointer text-lg font-medium text-zinc-200 hover:text-emerald-400"
        onClick={() => {
          setValue(name);
          setEditing(true);
        }}
      >
        {name}
      </h2>
    );
  }

  return (
    <input
      type="text"
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => {
        if (value.trim() && value !== name) onSave(value);
        setEditing(false);
      }}
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          if (value.trim() && value !== name) onSave(value);
          setEditing(false);
        }
        if (e.key === 'Escape') setEditing(false);
      }}
      autoFocus
      className="rounded-md border border-emerald-500/50 bg-zinc-900 px-2 py-1 text-lg font-medium text-zinc-200 outline-none"
    />
  );
}

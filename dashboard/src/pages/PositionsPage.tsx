import { useState } from 'react';
import {
  useCreatePosition,
  useAddTaxLot,
  useDeletePosition,
  usePositions,
} from '../hooks/usePositions';
import type { Position } from '../types/api';

export default function PositionsPage() {
  const { data: positions, isLoading } = usePositions();
  const createPosition = useCreatePosition();
  const addTaxLot = useAddTaxLot();
  const deletePosition = useDeletePosition();

  const [isCreating, setIsCreating] = useState(false);
  const [addingLotId, setAddingLotId] = useState<number | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Create form state
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState('');
  const [costBasis, setCostBasis] = useState('');
  const [purchaseDate, setPurchaseDate] = useState('');

  // Add lot form state
  const [lotQty, setLotQty] = useState('');
  const [lotCost, setLotCost] = useState('');
  const [lotDate, setLotDate] = useState('');

  function handleCreate() {
    if (!symbol || !quantity || !costBasis || !purchaseDate) return;
    createPosition.mutate(
      {
        symbol: symbol.toUpperCase(),
        quantity: Number(quantity),
        cost_basis: Number(costBasis),
        purchase_date: purchaseDate,
      },
      {
        onSuccess: () => {
          setIsCreating(false);
          setSymbol('');
          setQuantity('');
          setCostBasis('');
          setPurchaseDate('');
        },
      },
    );
  }

  function handleAddLot(posId: number) {
    if (!lotQty || !lotCost || !lotDate) return;
    addTaxLot.mutate(
      {
        id: posId,
        data: {
          quantity: Number(lotQty),
          cost_basis: Number(lotCost),
          purchase_date: lotDate,
        },
      },
      {
        onSuccess: () => {
          setAddingLotId(null);
          setLotQty('');
          setLotCost('');
          setLotDate('');
        },
      },
    );
  }

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-zinc-100">Positions</h1>
        <button
          onClick={() => setIsCreating(true)}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500"
        >
          Add Position
        </button>
      </div>

      {/* Create form */}
      {isCreating && (
        <div className="mb-6 rounded-lg border border-zinc-800 p-5">
          <h2 className="mb-4 text-lg font-medium text-zinc-200">New Position</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <input
              type="text"
              placeholder="Symbol"
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50"
            />
            <input
              type="number"
              placeholder="Quantity"
              value={quantity}
              onChange={(e) => setQuantity(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50"
            />
            <input
              type="number"
              placeholder="Cost basis"
              step="0.01"
              value={costBasis}
              onChange={(e) => setCostBasis(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50"
            />
            <input
              type="date"
              value={purchaseDate}
              onChange={(e) => setPurchaseDate(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none focus:border-emerald-500/50"
            />
          </div>
          <div className="mt-3 flex gap-2">
            <button
              onClick={handleCreate}
              disabled={!symbol || !quantity || !costBasis || !purchaseDate}
              className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
            >
              Create
            </button>
            <button
              onClick={() => setIsCreating(false)}
              className="rounded-md px-4 py-2 text-sm text-zinc-500 transition-colors hover:bg-zinc-800 hover:text-zinc-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Positions table */}
      {positions && positions.length > 0 ? (
        <div className="overflow-hidden rounded-lg border border-zinc-800">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-zinc-800 bg-zinc-900/50">
              <tr>
                <th className="px-4 py-3 font-medium text-zinc-400">Symbol</th>
                <th className="px-4 py-3 font-medium text-zinc-400">Qty</th>
                <th className="px-4 py-3 font-medium text-zinc-400">Avg Cost</th>
                <th className="px-4 py-3 font-medium text-zinc-400">Tax Lots</th>
                <th className="px-4 py-3 font-medium text-zinc-400">Notes</th>
                <th className="px-4 py-3 font-medium text-zinc-400">Actions</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((pos) => (
                <PositionRow
                  key={pos.id}
                  position={pos}
                  expanded={expandedId === pos.id}
                  onToggleExpand={() =>
                    setExpandedId(expandedId === pos.id ? null : pos.id)
                  }
                  addingLot={addingLotId === pos.id}
                  onStartAddLot={() => {
                    setAddingLotId(pos.id);
                    setLotQty('');
                    setLotCost('');
                    setLotDate('');
                  }}
                  onCancelAddLot={() => setAddingLotId(null)}
                  lotQty={lotQty}
                  lotCost={lotCost}
                  lotDate={lotDate}
                  onLotQtyChange={setLotQty}
                  onLotCostChange={setLotCost}
                  onLotDateChange={setLotDate}
                  onSubmitLot={() => handleAddLot(pos.id)}
                  onDelete={() => deletePosition.mutate(pos.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        !isCreating && (
          <div className="rounded-lg border border-zinc-800 p-12 text-center text-zinc-600">
            No positions yet. Add one to get started.
          </div>
        )
      )}
    </div>
  );
}

function PositionRow({
  position,
  expanded,
  onToggleExpand,
  addingLot,
  onStartAddLot,
  onCancelAddLot,
  lotQty,
  lotCost,
  lotDate,
  onLotQtyChange,
  onLotCostChange,
  onLotDateChange,
  onSubmitLot,
  onDelete,
}: {
  position: Position;
  expanded: boolean;
  onToggleExpand: () => void;
  addingLot: boolean;
  onStartAddLot: () => void;
  onCancelAddLot: () => void;
  lotQty: string;
  lotCost: string;
  lotDate: string;
  onLotQtyChange: (v: string) => void;
  onLotCostChange: (v: string) => void;
  onLotDateChange: (v: string) => void;
  onSubmitLot: () => void;
  onDelete: () => void;
}) {
  return (
    <>
      <tr className="border-b border-zinc-800/50 hover:bg-zinc-900/30">
        <td className="px-4 py-3 font-medium text-zinc-200">{position.symbol}</td>
        <td className="px-4 py-3 text-zinc-300">{position.total_quantity}</td>
        <td className="px-4 py-3 text-zinc-300">${position.average_cost.toFixed(2)}</td>
        <td className="px-4 py-3">
          <button
            onClick={onToggleExpand}
            className="text-xs text-emerald-400 hover:text-emerald-300"
          >
            {position.tax_lots.length} lot{position.tax_lots.length !== 1 ? 's' : ''}{' '}
            {expanded ? '▴' : '▾'}
          </button>
        </td>
        <td className="px-4 py-3 text-xs text-zinc-500">
          {position.notes || '—'}
        </td>
        <td className="px-4 py-3">
          <div className="flex gap-2">
            <button
              onClick={onStartAddLot}
              className="text-xs text-zinc-400 hover:text-zinc-200"
            >
              +Lot
            </button>
            <button
              onClick={onDelete}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Close
            </button>
          </div>
        </td>
      </tr>

      {/* Expanded tax lots */}
      {expanded && (
        <tr>
          <td colSpan={6} className="bg-zinc-900/40 px-8 py-3">
            <div className="space-y-1 text-xs">
              {position.tax_lots.map((lot, i) => (
                <div key={i} className="flex gap-4 text-zinc-400">
                  <span>{lot.quantity} shares @ ${lot.cost_basis.toFixed(2)}</span>
                  <span>Purchased: {lot.purchase_date}</span>
                  <span
                    className={
                      lot.is_long_term ? 'text-emerald-400' : 'text-amber-400'
                    }
                  >
                    {lot.is_long_term
                      ? 'Long-term'
                      : `${lot.days_to_long_term}d to long-term`}
                  </span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}

      {/* Add lot form */}
      {addingLot && (
        <tr>
          <td colSpan={6} className="bg-zinc-900/40 px-8 py-3">
            <div className="flex items-center gap-2">
              <input
                type="number"
                placeholder="Qty"
                value={lotQty}
                onChange={(e) => onLotQtyChange(e.target.value)}
                className="w-20 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-200 outline-none"
              />
              <input
                type="number"
                placeholder="Cost"
                step="0.01"
                value={lotCost}
                onChange={(e) => onLotCostChange(e.target.value)}
                className="w-24 rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-200 outline-none"
              />
              <input
                type="date"
                value={lotDate}
                onChange={(e) => onLotDateChange(e.target.value)}
                className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-200 outline-none"
              />
              <button
                onClick={onSubmitLot}
                disabled={!lotQty || !lotCost || !lotDate}
                className="rounded bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                Add
              </button>
              <button
                onClick={onCancelAddLot}
                className="rounded px-2 py-1 text-xs text-zinc-500 hover:text-zinc-300"
              >
                Cancel
              </button>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

import { useEffect, useState } from 'react';
import { useConfig, useUpdateConfig } from '../hooks/useConfig';

export default function SettingsPage() {
  const { data: config, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();

  const [stake, setStake] = useState('');
  const [maxPosition, setMaxPosition] = useState('');
  const [stopLoss, setStopLoss] = useState('');

  useEffect(() => {
    if (config) {
      setStake(String(config.stake));
      setMaxPosition(String(Math.round(config.max_position_pct * 100)));
      setStopLoss(String(Math.round(config.stop_loss_pct * 100)));
    }
  }, [config]);

  function handleSave() {
    updateConfig.mutate({
      stake: Number(stake),
      max_position_pct: Number(maxPosition) / 100,
      stop_loss_pct: Number(stopLoss) / 100,
    });
  }

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  return (
    <div className="max-w-xl">
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Settings</h1>

      <div className="space-y-5 rounded-lg border border-zinc-800 p-6">
        <div>
          <label className="mb-1 block text-sm font-medium text-zinc-400">
            Stake ($)
          </label>
          <input
            type="number"
            value={stake}
            onChange={(e) => setStake(e.target.value)}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          />
          <p className="mt-1 text-xs text-zinc-600">
            Total capital to deploy across positions
          </p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-zinc-400">
            Max Position (%)
          </label>
          <input
            type="number"
            value={maxPosition}
            onChange={(e) => setMaxPosition(e.target.value)}
            min={1}
            max={100}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          />
          <p className="mt-1 text-xs text-zinc-600">
            Maximum percentage of stake in any single position
          </p>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-zinc-400">
            Stop Loss (%)
          </label>
          <input
            type="number"
            value={stopLoss}
            onChange={(e) => setStopLoss(e.target.value)}
            min={1}
            max={50}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          />
          <p className="mt-1 text-xs text-zinc-600">
            Automatic stop-loss distance from entry price
          </p>
        </div>

        <div className="flex items-center gap-3 pt-2">
          <button
            onClick={handleSave}
            disabled={updateConfig.isPending}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
          >
            {updateConfig.isPending ? 'Saving...' : 'Save'}
          </button>
          {updateConfig.isSuccess && (
            <span className="text-sm text-emerald-400">Saved</span>
          )}
        </div>
      </div>

      <div className="mt-6 rounded-lg border border-zinc-800 p-6">
        <h2 className="mb-3 text-sm font-medium text-zinc-400">Active Plugins</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-zinc-500">Data:</span>{' '}
            <span className="text-zinc-300">{config?.data_provider}</span>
          </div>
          <div>
            <span className="text-zinc-500">Strategy:</span>{' '}
            <span className="text-zinc-300">{config?.strategies.join(', ')}</span>
          </div>
          <div>
            <span className="text-zinc-500">Risk:</span>{' '}
            <span className="text-zinc-300">{config?.risk_manager}</span>
          </div>
          <div>
            <span className="text-zinc-500">Broker:</span>{' '}
            <span className="text-zinc-300">{config?.broker}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

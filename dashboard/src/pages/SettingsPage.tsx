import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { useConfig, useUpdateConfig } from '../hooks/useConfig';
import type { ProviderStatus } from '../types/api';

const PROVIDERS: Record<string, {
  label: string;
  description: string;
  bars: boolean;
  options: boolean;
  discovery: boolean;
  forex: boolean;
  needsKey: boolean;
  keyField?: string;
  keySetField?: string;
  keyHintField?: string;
  signupUrl?: string;
  signupNote?: string;
}> = {
  yahoo: {
    label: 'Yahoo Finance',
    description: 'Free, rate-limited (~360 req/hr). Good for small watchlists.',
    bars: true, options: true, discovery: false, forex: true, needsKey: false,
  },
  polygon: {
    label: 'Polygon.io',
    description: 'Stocks + options + forex + discovery. $29/mo or free (5/min).',
    bars: true, options: true, discovery: true, forex: true, needsKey: true,
    keyField: 'polygon_api_key', keySetField: 'polygon_api_key_set', keyHintField: 'polygon_api_key_hint',
    signupUrl: 'https://polygon.io', signupNote: 'Starter plan ($29/mo) covers stocks, options, and forex.',
  },
  fmp: {
    label: 'Financial Modeling Prep',
    description: 'Best discovery/screening APIs. $22/mo or free (250/day).',
    bars: true, options: false, discovery: true, forex: false, needsKey: true,
    keyField: 'fmp_api_key', keySetField: 'fmp_api_key_set', keyHintField: 'fmp_api_key_hint',
    signupUrl: 'https://financialmodelingprep.com', signupNote: 'Starter plan ($22/mo) has broad coverage.',
  },
  marketdata: {
    label: 'MarketData.app',
    description: 'Best-in-class options with full greeks. $12/mo or free (100/day).',
    bars: true, options: true, discovery: false, forex: false, needsKey: true,
    keyField: 'marketdata_api_key', keySetField: 'marketdata_api_key_set', keyHintField: 'marketdata_api_key_hint',
    signupUrl: 'https://marketdata.app', signupNote: 'Starter plan ($12/mo) for stocks + options.',
  },
  twelvedata: {
    label: 'Twelve Data',
    description: 'Broad global coverage with official SDK. $79/mo or free (8/min).',
    bars: true, options: true, discovery: false, forex: true, needsKey: true,
    keyField: 'twelvedata_api_key', keySetField: 'twelvedata_api_key_set', keyHintField: 'twelvedata_api_key_hint',
    signupUrl: 'https://twelvedata.com', signupNote: 'Free tier has 8 API calls/minute.',
  },
};

const PROVIDER_NAMES = Object.keys(PROVIDERS);

function getActiveProviders(primary: string, options: string | null, discovery: string | null, forex: string | null): Set<string> {
  const active = new Set<string>();
  active.add(primary);
  if (options) active.add(options);
  if (discovery) active.add(discovery);
  if (forex) active.add(forex);
  return active;
}

export default function SettingsPage() {
  const { data: config, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();

  const [dataProvider, setDataProvider] = useState('yahoo');
  const [optionsProvider, setOptionsProvider] = useState<string | null>(null);
  const [discoveryProvider, setDiscoveryProvider] = useState<string | null>(null);
  const [forexProvider, setForexProvider] = useState<string | null>(null);

  // API key state — one per provider that needs a key
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  // Diagnostics state
  const [diagResults, setDiagResults] = useState<ProviderStatus[] | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      setDataProvider(config.data_provider);
      setOptionsProvider(config.options_provider);
      setDiscoveryProvider(config.discovery_provider);
      setForexProvider(config.forex_provider);
      setApiKeys({});
    }
  }, [config]);

  async function handleTestProviders() {
    setDiagLoading(true);
    setDiagError(null);
    try {
      const data = await api.getDiagnostics();
      setDiagResults(data.providers);
    } catch (err) {
      setDiagError(err instanceof Error ? err.message : 'Failed to test providers');
    } finally {
      setDiagLoading(false);
    }
  }

  function handleSave() {
    const update: Record<string, unknown> = {
      data_provider: dataProvider,
      options_provider: optionsProvider,
      discovery_provider: discoveryProvider,
      forex_provider: forexProvider,
    };
    // Include API keys only if user typed a new value
    for (const [provName, prov] of Object.entries(PROVIDERS)) {
      if (prov.keyField && apiKeys[provName]) {
        update[prov.keyField] = apiKeys[provName];
      }
    }
    updateConfig.mutate(update as any);
  }

  if (isLoading) {
    return <div className="text-zinc-500">Loading...</div>;
  }

  const activeProviders = getActiveProviders(dataProvider, optionsProvider, discoveryProvider, forexProvider);
  const providersNeedingKeys = [...activeProviders].filter(p => PROVIDERS[p]?.needsKey);

  return (
    <div className="max-w-xl">
      <h1 className="mb-6 text-2xl font-semibold text-zinc-100">Settings</h1>

      {/* Data Providers */}
      <div className="mt-6 space-y-5 rounded-lg border border-zinc-800 p-6">
        {/* Primary Provider (bars) */}
        <div>
          <h2 className="mb-1 text-sm font-medium text-zinc-300">Primary Provider</h2>
          <p className="mb-3 text-xs text-zinc-600">Used for price bars and as default for all data types</p>
          <div className="space-y-2">
            {PROVIDER_NAMES.map((key) => {
              const p = PROVIDERS[key];
              return (
                <label
                  key={key}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                    dataProvider === key
                      ? 'border-emerald-500/50 bg-emerald-950/10'
                      : 'border-zinc-800 hover:border-zinc-700'
                  }`}
                >
                  <input
                    type="radio"
                    name="dataProvider"
                    value={key}
                    checked={dataProvider === key}
                    onChange={(e) => setDataProvider(e.target.value)}
                    className="mt-0.5 accent-emerald-500"
                  />
                  <div>
                    <span className="text-sm font-medium text-zinc-200">{p.label}</span>
                    <p className="mt-0.5 text-xs text-zinc-500">{p.description}</p>
                  </div>
                </label>
              );
            })}
          </div>
        </div>

        {/* Options Provider Override */}
        <div>
          <h2 className="mb-1 text-sm font-medium text-zinc-300">Options Provider</h2>
          <p className="mb-2 text-xs text-zinc-600">Override for option chains and greeks</p>
          <select
            value={optionsProvider ?? ''}
            onChange={(e) => setOptionsProvider(e.target.value || null)}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          >
            <option value="">Same as primary</option>
            {PROVIDER_NAMES.filter(k => PROVIDERS[k].options).map(key => (
              <option key={key} value={key}>{PROVIDERS[key].label}</option>
            ))}
          </select>
        </div>

        {/* Discovery Provider Override */}
        <div>
          <h2 className="mb-1 text-sm font-medium text-zinc-300">Discovery Provider</h2>
          <p className="mb-2 text-xs text-zinc-600">Override for universe listing and market movers</p>
          <select
            value={discoveryProvider ?? ''}
            onChange={(e) => setDiscoveryProvider(e.target.value || null)}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          >
            <option value="">Same as primary</option>
            {PROVIDER_NAMES.filter(k => PROVIDERS[k].discovery).map(key => (
              <option key={key} value={key}>{PROVIDERS[key].label}</option>
            ))}
          </select>
        </div>

        {/* Forex Provider Override */}
        <div>
          <h2 className="mb-1 text-sm font-medium text-zinc-300">Forex Provider</h2>
          <p className="mb-2 text-xs text-zinc-600">Override for forex pair data (EUR/USD, GBP/USD, etc.)</p>
          <select
            value={forexProvider ?? ''}
            onChange={(e) => setForexProvider(e.target.value || null)}
            className="w-full rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
          >
            <option value="">Same as primary</option>
            {PROVIDER_NAMES.filter(k => PROVIDERS[k].forex).map(key => (
              <option key={key} value={key}>{PROVIDERS[key].label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* API Keys — only show for providers actively in use */}
      {providersNeedingKeys.length > 0 && (
        <div className="mt-6 space-y-4 rounded-lg border border-zinc-800 p-6">
          <h2 className="mb-2 text-sm font-medium text-zinc-300">API Keys</h2>
          <p className="mb-3 text-xs text-zinc-600">
            Only showing keys for providers you have selected above
          </p>

          {providersNeedingKeys.map((provName) => {
            const prov = PROVIDERS[provName];
            const cfgAny = config as unknown as Record<string, unknown>;
            const isSet = cfgAny ? !!cfgAny[prov.keySetField!] : false;
            const hint = cfgAny ? String(cfgAny[prov.keyHintField!] ?? '') : '';

            return (
              <div key={provName} className="space-y-2 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                <label className="mb-1 block text-sm font-medium text-zinc-400">
                  {prov.label} API Key
                </label>
                <div className="relative">
                  <input
                    type={showKeys[provName] ? 'text' : 'password'}
                    value={apiKeys[provName] ?? ''}
                    onChange={(e) => setApiKeys(prev => ({ ...prev, [provName]: e.target.value }))}
                    placeholder={isSet ? `Current: ${hint}` : 'Paste your API key here'}
                    className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 pr-16 text-sm text-zinc-200 outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKeys(prev => ({ ...prev, [provName]: !prev[provName] }))}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded px-2 py-0.5 text-xs text-zinc-500 hover:text-zinc-300"
                  >
                    {showKeys[provName] ? 'Hide' : 'Show'}
                  </button>
                </div>
                {isSet && !apiKeys[provName] && (
                  <p className="text-xs text-emerald-500/70">
                    Key configured. Leave blank to keep current key.
                  </p>
                )}
                {prov.signupUrl && !isSet && (
                  <p className="mt-1 text-xs text-zinc-600">
                    Sign up at{' '}
                    <a
                      href={prov.signupUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-400 hover:underline"
                    >
                      {prov.signupUrl.replace('https://', '')}
                    </a>
                    {prov.signupNote && <> &mdash; {prov.signupNote}</>}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Save */}
      <div className="mt-6 flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={updateConfig.isPending}
          className="rounded-md bg-emerald-600 px-6 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:opacity-50"
        >
          {updateConfig.isPending ? 'Saving...' : 'Save Settings'}
        </button>
        {updateConfig.isSuccess && (
          <span className="text-sm text-emerald-400">Saved</span>
        )}
      </div>

      {/* Active Plugins */}
      <div className="mt-6 rounded-lg border border-zinc-800 p-6">
        <h2 className="mb-3 text-sm font-medium text-zinc-400">Active Plugins</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <span className="text-zinc-500">Data:</span>{' '}
            <span className="text-zinc-300">{config?.data_provider}</span>
          </div>
          <div>
            <span className="text-zinc-500">Options:</span>{' '}
            <span className="text-zinc-300">{config?.options_provider ?? config?.data_provider}</span>
            {!config?.options_provider && <span className="text-zinc-600 text-xs ml-1">(primary)</span>}
          </div>
          <div>
            <span className="text-zinc-500">Discovery:</span>{' '}
            <span className="text-zinc-300">{config?.discovery_provider ?? config?.data_provider}</span>
            {!config?.discovery_provider && <span className="text-zinc-600 text-xs ml-1">(primary)</span>}
          </div>
          <div>
            <span className="text-zinc-500">Forex:</span>{' '}
            <span className="text-zinc-300">{config?.forex_provider ?? config?.data_provider}</span>
            {!config?.forex_provider && <span className="text-zinc-600 text-xs ml-1">(primary)</span>}
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

      {/* Test Providers */}
      <div className="mt-6 rounded-lg border border-zinc-800 p-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-zinc-400">Test Providers</h2>
          <button
            onClick={handleTestProviders}
            disabled={diagLoading}
            className="rounded-md bg-zinc-700 px-4 py-1.5 text-xs font-medium text-zinc-200 transition-colors hover:bg-zinc-600 disabled:opacity-50"
          >
            {diagLoading ? 'Testing...' : 'Run Diagnostics'}
          </button>
        </div>
        <p className="mb-3 text-xs text-zinc-600">
          Tests each active provider by fetching 5 days of AAPL data
        </p>

        {diagError && (
          <div className="rounded-md border border-red-900/50 bg-red-950/20 p-3 text-xs text-red-400">
            {diagError}
          </div>
        )}

        {diagResults && (
          <div className="space-y-2">
            {diagResults.map((p) => (
              <div
                key={p.name}
                className={`flex items-center justify-between rounded-lg border p-3 text-sm ${
                  p.ok
                    ? 'border-emerald-900/50 bg-emerald-950/10'
                    : 'border-red-900/50 bg-red-950/10'
                }`}
              >
                <div>
                  <span className="font-medium text-zinc-200">{p.name}</span>
                  <span className="ml-2 text-xs text-zinc-500">({p.role})</span>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  {p.ok ? (
                    <>
                      <span className="text-emerald-400">{p.bars_returned} bars</span>
                      <span className="text-zinc-500">{Math.round(p.latency_ms)}ms</span>
                    </>
                  ) : (
                    <span className="max-w-xs truncate text-red-400">{p.error}</span>
                  )}
                  <span
                    className={`inline-block h-2 w-2 rounded-full ${
                      p.ok ? 'bg-emerald-400' : 'bg-red-400'
                    }`}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

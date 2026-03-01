import type {
  AddTaxLot,
  AdviseRequest,
  AdviseResponse,
  Config,
  ConfigUpdate,
  ImportCommitRequest,
  ImportCommitResponse,
  ImportPreviewResponse,
  Position,
  PositionCreate,
  ScanRequest,
  ScanResponse,
  ScanSummary,
  ScannerRequest,
  ScannerResponse,
  UniverseResponse,
  Watchlist,
  WatchlistCreate,
  WatchlistUpdate,
} from '../types/api';

const BASE = '/api';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  // Config
  getConfig: () => request<Config>('/config'),
  updateConfig: (data: ConfigUpdate) =>
    request<Config>('/config', { method: 'PUT', body: JSON.stringify(data) }),

  // Watchlists
  getWatchlists: () => request<Watchlist[]>('/watchlists'),
  createWatchlist: (data: WatchlistCreate) =>
    request<Watchlist>('/watchlists', { method: 'POST', body: JSON.stringify(data) }),
  getWatchlist: (id: number) => request<Watchlist>(`/watchlists/${id}`),
  updateWatchlist: (id: number, data: WatchlistUpdate) =>
    request<Watchlist>(`/watchlists/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteWatchlist: (id: number) =>
    request<void>(`/watchlists/${id}`, { method: 'DELETE' }),

  // Scans
  runScan: (data: ScanRequest) =>
    request<ScanResponse>('/scans', { method: 'POST', body: JSON.stringify(data) }),
  getScans: (limit = 20) => request<ScanSummary[]>(`/scans?limit=${limit}`),
  getScan: (id: number) => request<ScanResponse>(`/scans/${id}`),

  // Positions
  getPositions: () => request<Position[]>('/positions'),
  createPosition: (data: PositionCreate) =>
    request<Position>('/positions', { method: 'POST', body: JSON.stringify(data) }),
  getPosition: (id: number) => request<Position>(`/positions/${id}`),
  addTaxLot: (id: number, data: AddTaxLot) =>
    request<Position>(`/positions/${id}/lots`, { method: 'POST', body: JSON.stringify(data) }),
  updatePosition: (id: number, data: { notes?: string }) =>
    request<Position>(`/positions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deletePosition: (id: number) =>
    request<void>(`/positions/${id}`, { method: 'DELETE' }),

  // Advise
  runAdvise: (data: AdviseRequest) =>
    request<AdviseResponse>('/advise', { method: 'POST', body: JSON.stringify(data) }),

  // Scanner
  getUniverses: () => request<UniverseResponse>('/scanner/universes'),
  runScanner: (data: ScannerRequest) =>
    request<ScannerResponse>('/scanner/run', { method: 'POST', body: JSON.stringify(data) }),

  // Import
  previewImport: async (file: File): Promise<ImportPreviewResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch(`${BASE}/import/preview`, {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || 'Upload failed');
    }
    return resp.json();
  },
  commitImport: (data: ImportCommitRequest) =>
    request<ImportCommitResponse>('/import/commit', { method: 'POST', body: JSON.stringify(data) }),
};

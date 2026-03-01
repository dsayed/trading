import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { WatchlistCreate, WatchlistUpdate } from '../types/api';

export function useWatchlists() {
  return useQuery({ queryKey: ['watchlists'], queryFn: api.getWatchlists });
}

export function useWatchlist(id: number | null) {
  return useQuery({
    queryKey: ['watchlists', id],
    queryFn: () => api.getWatchlist(id!),
    enabled: id !== null,
  });
}

export function useCreateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WatchlistCreate) => api.createWatchlist(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  });
}

export function useUpdateWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: WatchlistUpdate }) =>
      api.updateWatchlist(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  });
}

export function useDeleteWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deleteWatchlist(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlists'] }),
  });
}

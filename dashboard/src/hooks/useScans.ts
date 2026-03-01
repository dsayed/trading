import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ScanRequest } from '../types/api';

export function useRunScan() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ScanRequest) => api.runScan(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scans'] }),
  });
}

export function useScanHistory(limit = 20) {
  return useQuery({
    queryKey: ['scans', limit],
    queryFn: () => api.getScans(limit),
  });
}

export function useScan(id: number | null) {
  return useQuery({
    queryKey: ['scans', 'detail', id],
    queryFn: () => api.getScan(id!),
    enabled: id !== null,
  });
}

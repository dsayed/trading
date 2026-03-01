import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ConfigUpdate } from '../types/api';

export function useConfig() {
  return useQuery({ queryKey: ['config'], queryFn: api.getConfig });
}

export function useUpdateConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ConfigUpdate) => api.updateConfig(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['config'] }),
  });
}

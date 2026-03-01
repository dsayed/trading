import { useMutation } from '@tanstack/react-query';
import { api } from '../api/client';
import type { AdviseRequest } from '../types/api';

export function useRunAdvise() {
  return useMutation({
    mutationFn: (data: AdviseRequest) => api.runAdvise(data),
  });
}

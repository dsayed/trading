import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { AddTaxLot, PositionCreate } from '../types/api';

export function usePositions() {
  return useQuery({ queryKey: ['positions'], queryFn: api.getPositions });
}

export function useCreatePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PositionCreate) => api.createPosition(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

export function useAddTaxLot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: AddTaxLot }) =>
      api.addTaxLot(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

export function useDeletePosition() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.deletePosition(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

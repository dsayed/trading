import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ImportCommitRequest } from '../types/api';

export function useImportPreview() {
  return useMutation({
    mutationFn: (file: File) => api.previewImport(file),
  });
}

export function useImportCommit() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ImportCommitRequest) => api.commitImport(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['positions'] }),
  });
}

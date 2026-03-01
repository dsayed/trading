import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../api/client';
import type { ScannerRequest, ScannerResponse } from '../types/api';

export function useUniverses() {
  return useQuery({
    queryKey: ['universes'],
    queryFn: () => api.getUniverses(),
  });
}

export function useRunScanner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ScannerRequest) => api.runScanner(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scans'] }),
  });
}

/**
 * Streaming scanner that reports progress via SSE.
 */
export function useRunScannerStream() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      data,
      onProgress,
    }: {
      data: ScannerRequest;
      onProgress: (msg: string) => void;
    }): Promise<ScannerResponse> => {
      return new Promise((resolve, reject) => {
        fetch('/api/scanner/run-stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(data),
        })
          .then((resp) => {
            if (!resp.ok) {
              resp
                .json()
                .then((err) => reject(new Error(err.detail || 'Scan failed')))
                .catch(() => reject(new Error('Scan failed')));
              return;
            }

            const reader = resp.body?.getReader();
            if (!reader) {
              reject(new Error('No response body'));
              return;
            }

            const decoder = new TextDecoder();
            let buffer = '';

            function processChunk(): void {
              reader!.read().then(({ done, value }) => {
                if (done) {
                  reject(new Error('Stream ended without result'));
                  return;
                }

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() ?? '';

                for (const line of lines) {
                  if (line.startsWith('event:') || line.trim() === '') continue;
                  if (line.startsWith('data: ')) {
                    const payload = line.slice(6);
                    try {
                      const parsed = JSON.parse(payload);
                      if ('message' in parsed) {
                        onProgress(parsed.message);
                      } else if ('id' in parsed) {
                        resolve(parsed as ScannerResponse);
                        return;
                      }
                    } catch {
                      // skip unparseable lines
                    }
                  }
                }

                processChunk();
              });
            }

            processChunk();
          })
          .catch(reject);
      });
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scans'] }),
  });
}

import { useMutation, useQuery, useQueryClient, type UseMutationResult } from '@tanstack/react-query';

import {
  fetchSection16,
  postOverrideUse,
  setRule4Today,
  setTrackAssignment,
} from '@/lib/api/section16';
import type {
  OverrideUseRequest,
  OverrideUseResponse,
  Rule4Request,
  Rule4Response,
  Section16Result,
  TrackAssignmentRequest,
  TrackAssignmentResponse,
} from '@/lib/schemas/section16';

/** No client-side caching of market data — backend re-fetches on every call. */
const STALE_MS = 0;

const QUERY_KEY = (ticker: string): readonly unknown[] => ['section16', ticker.toUpperCase()];

export function useSection16(ticker: string): {
  data: Section16Result | undefined;
  isLoading: boolean;
  isError: boolean;
  error: Error | null;
} {
  return useQuery({
    queryKey: QUERY_KEY(ticker),
    queryFn: () => fetchSection16(ticker),
    enabled: ticker.length > 0,
    staleTime: STALE_MS,
    placeholderData: (prev) => prev,
  });
}

export function useSetTrackAssignment(
  ticker: string,
): UseMutationResult<TrackAssignmentResponse, Error, TrackAssignmentRequest> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: TrackAssignmentRequest) => setTrackAssignment(ticker, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: QUERY_KEY(ticker) });
      const prev = qc.getQueryData<Section16Result>(QUERY_KEY(ticker));
      if (prev) {
        qc.setQueryData<Section16Result>(QUERY_KEY(ticker), { ...prev, track: body.track });
      }
      return { prev };
    },
    onError: (_err, _body, context) => {
      if (context?.prev) {
        qc.setQueryData(QUERY_KEY(ticker), context.prev);
      }
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEY(ticker) });
      void qc.invalidateQueries({ queryKey: ['framework12', ticker.toUpperCase()] });
    },
  });
}

export function useSetRule4Today(
  ticker: string,
): UseMutationResult<Rule4Response, Error, Rule4Request> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Rule4Request) => setRule4Today(ticker, body),
    onMutate: async (body) => {
      await qc.cancelQueries({ queryKey: QUERY_KEY(ticker) });
      const prev = qc.getQueryData<Section16Result>(QUERY_KEY(ticker));
      if (prev) {
        const today = new Date().toISOString().slice(0, 10);
        qc.setQueryData<Section16Result>(QUERY_KEY(ticker), {
          ...prev,
          rule4: prev.rule4
            ? {
                ...prev.rule4,
                fits_portfolio: body.fits_portfolio,
                fit_date: today,
                result: body.fits_portfolio ? 'PASS' : 'FAIL',
              }
            : prev.rule4,
        });
      }
      return { prev };
    },
    onError: (_err, _body, context) => {
      if (context?.prev) {
        qc.setQueryData(QUERY_KEY(ticker), context.prev);
      }
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEY(ticker) });
      void qc.invalidateQueries({ queryKey: ['framework12', ticker.toUpperCase()] });
    },
  });
}

export function useUseOverride(
  ticker: string,
): UseMutationResult<OverrideUseResponse, Error, OverrideUseRequest> {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: OverrideUseRequest) => postOverrideUse(ticker, body),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: QUERY_KEY(ticker) });
      void qc.invalidateQueries({ queryKey: ['framework12', ticker.toUpperCase()] });
    },
  });
}

'use client';

import { useQuery, useMutation, skipToken } from '@tanstack/react-query';
import { apiClient } from './client';
import type { ColdStartRequest } from './schemas';

// Cache timing constants
const MINUTE = 60 * 1000;

export function useTypes() {
  return useQuery({
    queryKey: ['types'],
    queryFn: ({ signal }) => apiClient.getTypes(signal),
    staleTime: 10 * MINUTE,
    gcTime: 30 * MINUTE,
  });
}

export function useUsers(type: string, query?: string) {
  return useQuery({
    queryKey: ['users', type, query || ''],
    queryFn: ({ signal }) => apiClient.getUsers(type, query, signal),
    enabled: Boolean(type),
    staleTime: 5 * MINUTE,
  });
}

export function useUserProfile(type: string, userId?: string) {
  return useQuery({
    queryKey: ['userProfile', type, userId],
    queryFn: userId ? ({ signal }) => apiClient.getUserProfile(type, userId, signal) : skipToken,
    enabled: Boolean(type && userId),
    staleTime: 2 * MINUTE,
  });
}

export function useRecommendations(
  type: string,
  userId?: string,
  k: number = 10,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['recommendations', type, userId, k],
    queryFn: ({ signal }) => apiClient.getRecommendations(type, userId, k, signal),
    enabled: options?.enabled ?? Boolean(type),
    staleTime: 30 * 1000,
  });
}

export function usePopular(type: string, k: number = 10) {
  return useQuery({
    queryKey: ['popular', type, k],
    queryFn: ({ signal }) => apiClient.getPopular(type, k, signal),
    enabled: Boolean(type),
    staleTime: 5 * MINUTE,
  });
}

export function useSimilar(type: string, itemId?: string, k: number = 10) {
  return useQuery({
    queryKey: ['similar', type, itemId, k],
    queryFn: itemId ? ({ signal }) => apiClient.getSimilar(type, itemId, k, signal) : skipToken,
    enabled: Boolean(type && itemId),
    staleTime: 5 * MINUTE,
  });
}

export function useItemDetail(type: string, itemId?: string) {
  return useQuery({
    queryKey: ['itemDetail', type, itemId],
    queryFn: itemId ? ({ signal }) => apiClient.getItemDetail(type, itemId, signal) : skipToken,
    enabled: Boolean(type && itemId),
    staleTime: 10 * MINUTE,
  });
}

export function useItemSearch(type: string, query: string) {
  return useQuery({
    queryKey: ['search', type, query],
    queryFn: ({ signal }) => apiClient.searchItems(type, query, 20, signal),
    enabled: Boolean(type && query.trim().length >= 1),
    staleTime: 1 * MINUTE,
  });
}

export function useColdStartMutation() {
  return useMutation({
    mutationFn: (request: ColdStartRequest) => apiClient.postColdStart(request),
  });
}

export function useColdStart(
  type: string,
  history: Array<{ item_id: string; signal?: number | null }>,
  k: number = 10,
  options?: { enabled?: boolean }
) {
  return useQuery({
    queryKey: ['coldStart', type, history, k],
    queryFn: ({ signal }) => apiClient.postColdStart({ type, history, k, exclude: [] }, signal),
    enabled: options?.enabled !== false && Boolean(type),
    staleTime: 30 * 1000,
  });
}

export function useMetrics(type: string) {
  return useQuery({
    queryKey: ['metrics', type],
    queryFn: ({ signal }) => apiClient.getMetrics(type, signal),
    enabled: Boolean(type),
    staleTime: 10 * MINUTE,
  });
}

export function useAbout() {
  return useQuery({
    queryKey: ['about'],
    queryFn: ({ signal }) => apiClient.getAbout(signal),
    staleTime: Infinity,
  });
}

export function useMoviePoster(title?: string, year?: number | null, enabled: boolean = true) {
  return useQuery({
    queryKey: ['moviePoster', title, year],
    queryFn: async () => {
      if (!title) return null;
      const params = new URLSearchParams({ title });
      if (year) params.set('year', String(year));
      const res = await fetch(`/api/posters/movie?${params.toString()}`);
      if (!res.ok) return null;
      const json = await res.json();
      return (json.poster_url as string | null) || null;
    },
    enabled: enabled && Boolean(title),
    staleTime: Infinity,
    gcTime: Infinity,
  });
}


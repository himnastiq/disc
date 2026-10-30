'use client';

import { useQuery, useMutation } from '@tanstack/react-query';
import { apiClient } from './client';
import type { ColdStartRequest } from './schemas';

// Cache timing constants
const MINUTE = 60 * 1000;

export function useTypes() {
  return useQuery({
    queryKey: ['types'],
    queryFn: () => apiClient.getTypes(),
    staleTime: 10 * MINUTE,
    gcTime: 30 * MINUTE,
  });
}

export function useUsers(type: string, query?: string) {
  return useQuery({
    queryKey: ['users', type, query || ''],
    queryFn: () => apiClient.getUsers(type, query),
    enabled: Boolean(type),
    staleTime: 5 * MINUTE,
  });
}

export function useUserProfile(type: string, userId?: string) {
  return useQuery({
    queryKey: ['userProfile', type, userId],
    queryFn: () => (userId ? apiClient.getUserProfile(type, userId) : null),
    enabled: Boolean(type && userId),
    staleTime: 2 * MINUTE,
  });
}

export function useRecommendations(type: string, userId?: string, k: number = 10) {
  return useQuery({
    queryKey: ['recommendations', type, userId, k],
    queryFn: () => apiClient.getRecommendations(type, userId, k),
    enabled: Boolean(type),
    staleTime: 30 * 1000,
  });
}

export function usePopular(type: string, k: number = 10) {
  return useQuery({
    queryKey: ['popular', type, k],
    queryFn: () => apiClient.getPopular(type, k),
    enabled: Boolean(type),
    staleTime: 5 * MINUTE,
  });
}

export function useSimilar(type: string, itemId?: string, k: number = 10) {
  return useQuery({
    queryKey: ['similar', type, itemId, k],
    queryFn: () => (itemId ? apiClient.getSimilar(type, itemId, k) : null),
    enabled: Boolean(type && itemId),
    staleTime: 5 * MINUTE,
  });
}

export function useItemDetail(type: string, itemId?: string) {
  return useQuery({
    queryKey: ['itemDetail', type, itemId],
    queryFn: () => (itemId ? apiClient.getItemDetail(type, itemId) : null),
    enabled: Boolean(type && itemId),
    staleTime: 10 * MINUTE,
  });
}

export function useItemSearch(type: string, query: string) {
  return useQuery({
    queryKey: ['search', type, query],
    queryFn: () => apiClient.searchItems(type, query),
    enabled: Boolean(type && query.trim().length >= 1),
    staleTime: 1 * MINUTE,
  });
}

export function useColdStartMutation() {
  return useMutation({
    mutationFn: (request: ColdStartRequest) => apiClient.postColdStart(request),
  });
}

export function useMetrics(type: string) {
  return useQuery({
    queryKey: ['metrics', type],
    queryFn: () => apiClient.getMetrics(type),
    enabled: Boolean(type),
    staleTime: 10 * MINUTE,
  });
}

export function useAbout() {
  return useQuery({
    queryKey: ['about'],
    queryFn: () => apiClient.getAbout(),
    staleTime: Infinity,
  });
}


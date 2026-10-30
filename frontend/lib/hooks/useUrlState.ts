'use client';

import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { useCallback, useMemo } from 'react';

export const VALID_TABS = ['for-you', 'compare', 'cold-start', 'evaluation'] as const;
export type TabKey = (typeof VALID_TABS)[number];

export const VALID_TYPES = ['movies', 'products', 'articles'] as const;
export type ContentTypeKey = (typeof VALID_TYPES)[number];

export const DEFAULT_TAB: TabKey = 'for-you';
export const DEFAULT_TYPE: ContentTypeKey = 'movies';
export const DEFAULT_K = 10;

export function normalizeTab(rawTab: string | null | undefined): TabKey {
  if (rawTab && VALID_TABS.includes(rawTab as TabKey)) {
    return rawTab as TabKey;
  }
  return DEFAULT_TAB;
}

export function normalizeType(rawType: string | null | undefined): ContentTypeKey {
  if (rawType && VALID_TYPES.includes(rawType as ContentTypeKey)) {
    return rawType as ContentTypeKey;
  }
  return DEFAULT_TYPE;
}

export function normalizeK(rawK: string | null | undefined): number {
  const parsed = rawK ? parseInt(rawK, 10) : DEFAULT_K;
  if ([5, 10, 20].includes(parsed)) {
    return parsed;
  }
  return DEFAULT_K;
}

export interface UrlStateUpdates {
  type?: string;
  tab?: string;
  user?: string;
  k?: number;
  item?: string | null;
  compareUser?: string | null;
}

export function useUrlState() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const rawType = searchParams.get('type');
  const rawTab = searchParams.get('tab');
  const rawUser = searchParams.get('user');
  const rawK = searchParams.get('k');
  const rawItem = searchParams.get('item');
  const rawCompareUser = searchParams.get('compareUser');

  const currentType = useMemo(() => normalizeType(rawType), [rawType]);
  const currentTab = useMemo(() => normalizeTab(rawTab), [rawTab]);
  const currentUser = rawUser || '1';
  const currentK = useMemo(() => normalizeK(rawK), [rawK]);
  const currentItem = rawItem || null;
  const currentCompareUser = rawCompareUser || null;

  const setUrlState = useCallback(
    (updates: UrlStateUpdates) => {
      const params = new URLSearchParams(searchParams.toString());

      if (updates.type !== undefined) {
        params.set('type', normalizeType(updates.type));
      }
      if (updates.tab !== undefined) {
        params.set('tab', normalizeTab(updates.tab));
      }
      if (updates.user !== undefined) {
        params.set('user', updates.user);
      }
      if (updates.k !== undefined) {
        params.set('k', String(normalizeK(String(updates.k))));
      }
      if (updates.item !== undefined) {
        if (updates.item) {
          params.set('item', updates.item);
        } else {
          params.delete('item');
        }
      }
      if (updates.compareUser !== undefined) {
        if (updates.compareUser) {
          params.set('compareUser', updates.compareUser);
        } else {
          params.delete('compareUser');
        }
      }

      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [searchParams, router, pathname]
  );

  const setType = useCallback((type: string) => setUrlState({ type }), [setUrlState]);
  const setTab = useCallback((tab: string) => setUrlState({ tab }), [setUrlState]);
  const setUser = useCallback((user: string) => setUrlState({ user }), [setUrlState]);
  const setK = useCallback((k: number) => setUrlState({ k }), [setUrlState]);
  const setItem = useCallback((item: string | null) => setUrlState({ item }), [setUrlState]);
  const setCompareUser = useCallback(
    (compareUser: string | null) => setUrlState({ compareUser }),
    [setUrlState]
  );

  const switchType = useCallback(
    (newType: string, defaultUser?: string) => {
      setUrlState({
        type: newType,
        user: defaultUser || '1',
      });
    },
    [setUrlState]
  );

  return {
    type: currentType,
    tab: currentTab,
    user: currentUser,
    k: currentK,
    item: currentItem,
    compareUser: currentCompareUser,
    setType,
    setTab,
    setUser,
    setK,
    setItem,
    setCompareUser,
    switchType,
    setUrlState,
  };
}

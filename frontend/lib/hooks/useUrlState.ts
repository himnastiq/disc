'use client';

import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { useCallback, useMemo } from 'react';

export const VALID_TABS = ['for-you', 'compare', 'cold-start', 'evaluation', 'about'] as const;
export type TabKey = (typeof VALID_TABS)[number];

export const VALID_TYPES = ['movies', 'products', 'articles'] as const;
export type ContentTypeKey = (typeof VALID_TYPES)[number];

export const DEFAULT_TAB: TabKey = 'for-you';
export const DEFAULT_TYPE: ContentTypeKey = 'movies';

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

export function useUrlState() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const rawType = searchParams.get('type');
  const rawTab = searchParams.get('tab');
  const rawUser = searchParams.get('user');

  const currentType = useMemo(() => normalizeType(rawType), [rawType]);
  const currentTab = useMemo(() => normalizeTab(rawTab), [rawTab]);
  const currentUser = rawUser || '1';

  const setUrlState = useCallback(
    (updates: { type?: string; tab?: string; user?: string }) => {
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

      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [searchParams, router, pathname]
  );

  const setType = useCallback((type: string) => setUrlState({ type }), [setUrlState]);
  const setTab = useCallback((tab: string) => setUrlState({ tab }), [setUrlState]);
  const setUser = useCallback((user: string) => setUrlState({ user }), [setUrlState]);

  return {
    type: currentType,
    tab: currentTab,
    user: currentUser,
    setType,
    setTab,
    setUser,
    setUrlState,
  };
}


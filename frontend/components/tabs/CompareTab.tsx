'use client';

import React, { useState, useMemo } from 'react';
import { GitCompare, TrendingUp, User, Sparkles, SlidersHorizontal } from 'lucide-react';
import { usePopular, useRecommendations, useUsers } from '@/lib/api/hooks';
import { RecCard } from '@/components/features/RecCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { ScoredItem } from '@/lib/api/schemas';

export interface CompareTabProps {
  type: string;
  user: string;
  k: number;
  onKChange: (k: number) => void;
  onSelectItem?: (item: ScoredItem) => void;
}

export function computeOverlap(
  listA: Array<{ item_id: string }> = [],
  listB: Array<{ item_id: string }> = []
) {
  const setB = new Set(listB.map((item) => item.item_id));
  const sharedIds = new Set(listA.filter((item) => setB.has(item.item_id)).map((item) => item.item_id));
  const overlapCount = sharedIds.size;
  const denominator = Math.max(listA.length, listB.length, 1);
  const percentage = Math.round((overlapCount / denominator) * 100);

  // Pairwise Jaccard similarity
  const unionCount = new Set([...listA.map((i) => i.item_id), ...listB.map((i) => i.item_id)]).size;
  const jaccard = unionCount > 0 ? (overlapCount / unionCount) : 0;

  return {
    sharedIds,
    overlapCount,
    percentage,
    jaccard: Math.round(jaccard * 100),
  };
}

export function CompareTab({
  type,
  user,
  k,
  onKChange,
  onSelectItem,
}: CompareTabProps) {
  const [compareMode, setCompareMode] = useState<'popular-vs-user' | 'user-vs-user'>('popular-vs-user');
  const [selectedSecondaryUser, setSelectedSecondaryUser] = useState<string | null>(null);

  const { data: usersData } = useUsers(type);
  const availableUsers = useMemo(() => usersData?.users || [], [usersData?.users]);
  const peerUsers = useMemo(() => availableUsers.filter((u) => u.user_id !== user), [availableUsers, user]);

  // Derive active secondaryUser: use user selection if valid for current peers, otherwise default to first peer
  const secondaryUser = useMemo(() => {
    if (selectedSecondaryUser && peerUsers.some((u) => u.user_id === selectedSecondaryUser)) {
      return selectedSecondaryUser;
    }
    if (peerUsers.length > 0) {
      return peerUsers[0].user_id;
    }
    return type === 'movies' ? (user === '1' ? '2' : '1') : '';
  }, [selectedSecondaryUser, peerUsers, type, user]);

  // Mode 1 queries
  const { data: popularData, isLoading: popLoading, isError: popError, refetch: refetchPop } =
    usePopular(type, k);

  const { data: userAData, isLoading: userALoading, isError: userAError, refetch: refetchUserA } =
    useRecommendations(type, user, k);

  // Mode 2 secondary user query: only run when in user-vs-user mode and secondaryUser is a valid peer
  const isSecondaryValid =
    compareMode === 'user-vs-user' &&
    Boolean(secondaryUser) &&
    (availableUsers.length === 0 || availableUsers.some((u) => u.user_id === secondaryUser));

  const { data: userBData, isLoading: userBLoading, isError: userBError, refetch: refetchUserB } =
    useRecommendations(type, isSecondaryValid ? secondaryUser : undefined, k, {
      enabled: isSecondaryValid,
    });

  const cardType = type === 'products' ? 'product' : type === 'articles' ? 'article' : 'movie';

  const overlapInfo = useMemo(() => {
    if (compareMode === 'popular-vs-user') {
      return computeOverlap(popularData?.results, userAData?.results);
    } else {
      return computeOverlap(userAData?.results, userBData?.results);
    }
  }, [compareMode, popularData?.results, userAData?.results, userBData?.results]);

  const isLoading =
    compareMode === 'popular-vs-user'
      ? popLoading || userALoading
      : userALoading || userBLoading;

  const isError =
    compareMode === 'popular-vs-user'
      ? popError || userAError
      : userAError || userBError;

  return (
    <div className="space-y-6">
      {/* 1. Comparison Mode Controls & Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-[var(--color-border)] pb-4">
        {/* Toggle between Popular vs User and User vs User */}
        <div
          role="tablist"
          aria-label="Comparison mode switcher"
          className="inline-flex rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5 text-xs"
        >
          <button
            type="button"
            role="tab"
            aria-selected={compareMode === 'popular-vs-user'}
            onClick={() => setCompareMode('popular-vs-user')}
            className={`px-3 py-1.5 font-medium rounded-[4px] transition-all cursor-pointer flex items-center gap-1.5 ${
              compareMode === 'popular-vs-user'
                ? 'bg-[var(--color-elevated)] text-[var(--color-text)] font-semibold shadow-xs'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            <TrendingUp className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            <span>Popular vs. Personalized</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={compareMode === 'user-vs-user'}
            onClick={() => setCompareMode('user-vs-user')}
            className={`px-3 py-1.5 font-medium rounded-[4px] transition-all cursor-pointer flex items-center gap-1.5 ${
              compareMode === 'user-vs-user'
                ? 'bg-[var(--color-elevated)] text-[var(--color-text)] font-semibold shadow-xs'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
            }`}
          >
            <GitCompare className="h-3.5 w-3.5 text-[var(--color-accent)]" />
            <span>User vs. User</span>
          </button>
        </div>

        {/* k Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
            <SlidersHorizontal className="h-3 w-3" /> k:
          </span>
          <div className="inline-flex rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5 text-xs">
            {[5, 10, 20].map((kVal) => (
              <button
                key={kVal}
                type="button"
                onClick={() => onKChange(kVal)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-[4px] cursor-pointer tabular-nums transition-colors ${
                  k === kVal
                    ? 'bg-[var(--color-elevated)] text-[var(--color-accent-text)]'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                }`}
              >
                {kVal}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* 2. Secondary User Selector (when in user-vs-user mode) */}
      {compareMode === 'user-vs-user' && (
        <div className="flex items-center gap-3 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-xs">
          <span className="font-semibold text-[var(--color-text)] flex items-center gap-1.5">
            <User className="h-3.5 w-3.5 text-[var(--color-accent)]" /> Compare User #{user} with:
          </span>
          <select
            value={secondaryUser}
            onChange={(e) => setSelectedSecondaryUser(e.target.value)}
            className="h-8 rounded-[4px] border border-[var(--color-border)] bg-[var(--color-bg)] px-2.5 text-xs font-medium text-[var(--color-text)] focus:outline-none focus:border-[var(--color-accent-text)]"
          >
            {availableUsers
              .filter((u) => u.user_id !== user)
              .map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  User #{u.user_id} {u.persona ? `· ${u.persona}` : ''}
                </option>
              ))}
          </select>
        </div>
      )}

      {/* 3. Overlap Metrics Banner */}
      {!isLoading && !isError && (
        <div
          role="status"
          aria-label="Overlap analysis summary"
          className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs"
        >
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-[4px] bg-[var(--color-elevated)] border border-[var(--color-border)] flex items-center justify-center font-bold text-sm text-[var(--color-accent)]">
              {overlapInfo.overlapCount}
            </div>
            <div>
              <p className="font-semibold text-[var(--color-text)]">
                {overlapInfo.overlapCount} of {k} items overlap ({overlapInfo.percentage}%)
              </p>
              <p className="text-[11px] text-[var(--color-text-secondary)]">
                {compareMode === 'popular-vs-user'
                  ? `${100 - overlapInfo.percentage}% distinct personalized recommendations beyond the global popularity baseline.`
                  : `Pairwise Jaccard similarity: ${overlapInfo.jaccard}% between personas.`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)]">
            <span className="inline-block h-2.5 w-2.5 rounded-full bg-[var(--color-accent)]" />
            <span>Illuminated cards indicate shared items</span>
          </div>
        </div>
      )}

      {/* 4. Loading State */}
      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-3">
            <Skeleton className="h-6 w-1/3 bg-[var(--color-elevated)]" />
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="aspect-[2/3] bg-[var(--color-elevated)]" />
              ))}
            </div>
          </div>
          <div className="space-y-3">
            <Skeleton className="h-6 w-1/3 bg-[var(--color-elevated)]" />
            <div className="grid grid-cols-2 gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="aspect-[2/3] bg-[var(--color-elevated)]" />
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 5. Error State */}
      {isError && (
        <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
          <ErrorState
            title="Comparison failed"
            message="Unable to retrieve recommendation feeds for both columns."
            onRetry={() => {
              if (compareMode === 'popular-vs-user') {
                refetchPop();
                refetchUserA();
              } else {
                refetchUserA();
                refetchUserB();
              }
            }}
          />
        </div>
      )}

      {/* 6. Side-by-Side Comparison Columns */}
      {!isLoading && !isError && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Column A */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
              <h4 className="font-bold text-sm text-[var(--color-text)] flex items-center gap-1.5">
                {compareMode === 'popular-vs-user' ? (
                  <>
                    <TrendingUp className="h-4 w-4 text-[var(--color-text-muted)]" />
                    <span>Popular for Everyone</span>
                  </>
                ) : (
                  <>
                    <User className="h-4 w-4 text-[var(--color-accent)]" />
                    <span>User #{user}</span>
                  </>
                )}
              </h4>
              <span className="text-xs text-[var(--color-text-muted)] tabular-nums">
                {compareMode === 'popular-vs-user' ? popularData?.results.length : userAData?.results.length} items
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {(compareMode === 'popular-vs-user' ? popularData?.results : userAData?.results)?.map((item) => {
                const isShared = overlapInfo.sharedIds.has(item.item_id);
                return (
                  <div key={item.item_id} className="relative">
                    <RecCard
                      item={item}
                      cardType={cardType}
                      onSelect={onSelectItem}
                      className={isShared ? 'ring-2 ring-[var(--color-accent)] border-[var(--color-accent)]/80' : ''}
                    />
                    {isShared && (
                      <span className="absolute bottom-3 right-3 z-10 rounded-[3px] bg-[var(--color-accent)] px-1.5 py-0.5 text-[9px] font-bold text-white shadow-xs">
                        In both lists
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Column B */}
          <div className="space-y-3">
            <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2">
              <h4 className="font-bold text-sm text-[var(--color-text)] flex items-center gap-1.5">
                {compareMode === 'popular-vs-user' ? (
                  <>
                    <Sparkles className="h-4 w-4 text-[var(--color-accent)]" />
                    <span>Personalized for User #{user}</span>
                  </>
                ) : (
                  <>
                    <User className="h-4 w-4 text-[var(--color-text-secondary)]" />
                    <span>User #{secondaryUser}</span>
                  </>
                )}
              </h4>
              <span className="text-xs text-[var(--color-text-muted)] tabular-nums">
                {compareMode === 'popular-vs-user' ? userAData?.results.length : userBData?.results.length} items
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              {(compareMode === 'popular-vs-user' ? userAData?.results : userBData?.results)?.map((item) => {
                const isShared = overlapInfo.sharedIds.has(item.item_id);
                return (
                  <div key={item.item_id} className="relative">
                    <RecCard
                      item={item}
                      cardType={cardType}
                      onSelect={onSelectItem}
                      className={isShared ? 'ring-2 ring-[var(--color-accent)] border-[var(--color-accent)]/80' : ''}
                    />
                    {isShared && (
                      <span className="absolute bottom-3 right-3 z-10 rounded-[3px] bg-[var(--color-accent)] px-1.5 py-0.5 text-[9px] font-bold text-white shadow-xs">
                        In both lists
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

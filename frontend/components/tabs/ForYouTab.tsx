'use client';

import React from 'react';
import { SlidersHorizontal } from 'lucide-react';
import { useRecommendations } from '@/lib/api/hooks';
import { ProfileCard } from '@/components/features/ProfileCard';
import { RecCard } from '@/components/features/RecCard';
import { ModeBadge } from '@/components/features/ModeBadge';
import { MovieDiscoveryFeed } from '@/components/features/MovieDiscoveryFeed';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import type { ScoredItem } from '@/lib/api/schemas';

export interface ForYouTabProps {
  type: string;
  user: string;
  k: number;
  onKChange: (k: number) => void;
  onSelectItem?: (item: ScoredItem) => void;
}

export function ForYouTab({
  type,
  user,
  k,
  onKChange,
  onSelectItem,
}: ForYouTabProps) {
  const { data: recData, isLoading, isError, refetch } = useRecommendations(type, user, k);

  const cardType: 'movie' | 'product' | 'article' =
    type === 'products' ? 'product' : type === 'articles' ? 'article' : 'movie';

  const kOptions = [5, 10, 20];

  if (isError) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
        <ErrorState
          title="Failed to fetch recommendations"
          message={`Could not load recommendations for User #${user} in ${type}.`}
          onRetry={refetch}
        />
      </div>
    );
  }

  // Consumer Movie Discovery Feed for Movies domain (Option 1)
  if (type === 'movies') {
    return (
      <MovieDiscoveryFeed
        user={user}
        k={k}
        onKChange={onKChange}
        onSelectItem={onSelectItem}
        recData={recData}
        isLoading={isLoading}
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* 1. User Profile Summary (P9.2) */}
      <ProfileCard type={type} userId={user} />

      {/* 2. Personalized Feed Header */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-[var(--color-border)] pb-3">
          <div className="flex items-center gap-2.5">
            <h3 className="text-base sm:text-lg font-bold text-[var(--color-text)]">
              Personalized Recommendations
            </h3>
            {recData && <ModeBadge mode={recData.mode} />}
          </div>

          {/* k Selector (5, 10, 20) */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <SlidersHorizontal className="h-3 w-3" /> Show:
            </span>
            <div
              role="group"
              aria-label="Number of recommendations"
              className="inline-flex rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5 text-xs"
            >
              {kOptions.map((kOpt) => {
                const isActive = k === kOpt;
                return (
                  <button
                    key={kOpt}
                    type="button"
                    onClick={() => onKChange(kOpt)}
                    className={`px-2.5 py-1 text-xs font-semibold rounded-[4px] transition-all cursor-pointer tabular-nums ${
                      isActive
                        ? 'bg-[var(--color-elevated)] text-[var(--color-accent-text)] border border-[var(--color-border)] shadow-xs'
                        : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                    }`}
                  >
                    k={kOpt}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 3. Loading State */}
        {isLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4">
            {Array.from({ length: k }).map((_, i) => (
              <div
                key={i}
                className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 space-y-3"
              >
                <Skeleton className="aspect-[2/3] w-full rounded-[4px] bg-[var(--color-elevated)]" />
                <Skeleton className="h-4 w-4/5 bg-[var(--color-elevated)]" />
                <Skeleton className="h-3 w-1/2 bg-[var(--color-elevated)]" />
              </div>
            ))}
          </div>
        )}

        {/* 4. Empty State */}
        {!isLoading && (!recData || recData.results.length === 0) && (
          <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-8">
            <EmptyState
              title="No recommendations generated"
              description={`The model did not return any recommendations for User #${user} with k=${k}.`}
            />
          </div>
        )}

        {/* 5. Recommendation Cards Grid */}
        {!isLoading && recData && recData.results.length > 0 && (
          <div
            role="region"
            aria-label="Recommendation results"
            className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 sm:gap-4"
          >
            {recData.results.map((item, idx) => (
              <RecCard
                key={item.item_id}
                item={item}
                cardType={cardType}
                onSelect={onSelectItem}
                priority={idx < 4}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

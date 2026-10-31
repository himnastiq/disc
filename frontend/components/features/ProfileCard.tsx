'use client';

import React from 'react';
import { User, Star, Calendar, Clock, BarChart2 } from 'lucide-react';
import { useUserProfile } from '@/lib/api/hooks';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';

export interface ProfileCardProps {
  type: string;
  userId: string;
}

export function formatDateUtc(timestamp: number | string | null | undefined): string {
  if (!timestamp) return 'N/A';
  const num = typeof timestamp === 'string' ? parseInt(timestamp, 10) : timestamp;
  if (isNaN(num)) return 'N/A';
  const d = new Date(num * 1000);
  return d.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  });
}

export function ProfileCard({ type, userId }: ProfileCardProps) {
  const { data: profile, isLoading, isError, refetch } = useUserProfile(type, userId);

  if (isLoading) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
        <div className="flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-full bg-[var(--color-elevated)]" />
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-28 bg-[var(--color-elevated)]" />
            <Skeleton className="h-3 w-40 bg-[var(--color-elevated)]" />
          </div>
        </div>
        <div className="space-y-2 pt-2">
          <Skeleton className="h-3 w-full bg-[var(--color-elevated)]" />
          <Skeleton className="h-3 w-4/5 bg-[var(--color-elevated)]" />
          <Skeleton className="h-3 w-2/3 bg-[var(--color-elevated)]" />
        </div>
      </div>
    );
  }

  if (isError || !profile) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <ErrorState
          title="Could not load profile"
          message={`Unable to retrieve profile records for User #${userId} in ${type}.`}
          onRetry={refetch}
        />
      </div>
    );
  }

  if (profile.interaction_count === 0) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5">
        <EmptyState
          title="No Profile Activity"
          description={`User #${userId} has zero recorded interactions in the ${type} catalogue.`}
        />
      </div>
    );
  }

  return (
    <section
      aria-label={`User Profile #${profile.user_id}`}
      className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-5"
    >
      {/* User Header & Persona */}
      <div className="flex items-start justify-between gap-3 border-b border-[var(--color-border)] pb-4">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-[6px] bg-[var(--color-elevated)] border border-[var(--color-border)] flex items-center justify-center font-bold text-[var(--color-text)] shrink-0">
            <User className="h-5 w-5 text-[var(--color-text-secondary)]" />
          </div>
          <div>
            <h3 className="font-bold text-sm sm:text-base text-[var(--color-text)] flex items-center gap-2">
              <span>User #{profile.user_id}</span>
              {profile.persona && (
                <span className="text-[12px] font-medium text-[var(--color-accent-text)] bg-[var(--color-accent)]/10 px-1.5 py-0.5 rounded-[4px] border border-[var(--color-accent)]/20">
                  {profile.persona}
                </span>
              )}
            </h3>
            <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
              Domain: <span className="capitalize text-[var(--color-text)]">{profile.content_type}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Numerical Stats Grid */}
      <div className="grid grid-cols-2 gap-3 text-xs">
        <div className="rounded-[4px] bg-[var(--color-elevated)]/60 border border-[var(--color-border)] p-2.5">
          <span className="text-[12px] text-[var(--color-text-muted)] block">Total Interactions</span>
          <span className="text-base font-bold text-[var(--color-text)] tabular-nums">
            {profile.interaction_count}
          </span>
        </div>
        <div className="rounded-[4px] bg-[var(--color-elevated)]/60 border border-[var(--color-border)] p-2.5">
          <span className="text-[12px] text-[var(--color-text-muted)] block">Positive Signals</span>
          <span className="text-base font-bold text-[var(--color-success)] tabular-nums">
            {profile.positive_count}
          </span>
        </div>
        <div className="rounded-[4px] bg-[var(--color-elevated)]/60 border border-[var(--color-border)] p-2.5">
          <span className="text-[12px] text-[var(--color-text-muted)] flex items-center gap-1">
            <Calendar className="h-3 w-3" /> First Active
          </span>
          <span className="text-xs font-semibold text-[var(--color-text-secondary)] tabular-nums mt-0.5 block">
            {formatDateUtc(profile.first_activity)}
          </span>
        </div>
        <div className="rounded-[4px] bg-[var(--color-elevated)]/60 border border-[var(--color-border)] p-2.5">
          <span className="text-[12px] text-[var(--color-text-muted)] flex items-center gap-1">
            <Clock className="h-3 w-3" /> Last Active
          </span>
          <span className="text-xs font-semibold text-[var(--color-text-secondary)] tabular-nums mt-0.5 block">
            {formatDateUtc(profile.last_activity)}
          </span>
        </div>
      </div>

      {/* Top Categories Horizontal Bar Chart */}
      {profile.top_categories.length > 0 && (
        <div className="space-y-3 pt-1">
          <h4 className="font-semibold text-xs tracking-wider uppercase text-[var(--color-text-muted)] flex items-center gap-1.5">
            <BarChart2 className="h-3.5 w-3.5 text-[var(--color-accent)]" /> Top Category Affinity
          </h4>

          <div className="space-y-2.5" role="region" aria-label="Top categories horizontal bar chart">
            {profile.top_categories.map((cat) => {
              const pct = Math.round(cat.share * 100);
              return (
                <div key={cat.category} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium text-[var(--color-text)]">
                      {cat.category}
                    </span>
                    <div className="flex items-center gap-2 tabular-nums text-xs">
                      <span className="text-[12px] text-[var(--color-text-muted)]">
                        {cat.count} items
                      </span>
                      <span className="font-semibold text-[var(--color-text)]">
                        {(cat.share * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  {/* Horizontal Bar */}
                  <div
                    role="progressbar"
                    aria-valuenow={pct}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`${cat.category}: ${(cat.share * 100).toFixed(1)}%`}
                    className="h-1.5 w-full bg-[var(--color-elevated)] rounded-full overflow-hidden"
                  >
                    <div
                      className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent Activity List */}
      {profile.recent_items.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-[var(--color-border)]">
          <h4 className="font-semibold text-xs tracking-wider uppercase text-[var(--color-text-muted)] flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5 text-[var(--color-accent)]" /> Recent Activity (Last {profile.recent_items.length})
          </h4>

          <ul className="divide-y divide-[var(--color-border)]">
            {profile.recent_items.map((item) => (
              <li
                key={`${item.item_id}-${item.timestamp || ''}`}
                className="py-2 flex items-start justify-between gap-3 text-xs"
              >
                <div className="min-w-0 pr-2">
                  <p className="font-medium text-[var(--color-text)] truncate">
                    {item.title}
                  </p>
                  <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5 tabular-nums">
                    {formatDateUtc(item.timestamp)}
                  </p>
                </div>

                {item.signal !== null && item.signal !== undefined && (
                  <div className="flex items-center gap-1 text-[var(--color-accent)] font-semibold text-xs shrink-0 tabular-nums">
                    <Star className="h-3.5 w-3.5 fill-current" />
                    <span>{item.signal}</span>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}

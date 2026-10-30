'use client';

import React from 'react';
import { Sparkles, TrendingUp } from 'lucide-react';
import type { RecommendationReason } from '@/lib/api/schemas';

export interface ReasonBadgeProps {
  reason?: RecommendationReason | null;
  className?: string;
}

export function ReasonBadge({ reason, className = '' }: ReasonBadgeProps) {
  if (!reason || !reason.text) {
    return null;
  }

  const isPopular = reason.kind === 'popular' || reason.text.toLowerCase().includes('popular');

  return (
    <div
      title={reason.text}
      className={`flex items-center gap-1.5 text-[11px] text-[var(--color-text-secondary)] overflow-hidden ${className}`}
    >
      {isPopular ? (
        <TrendingUp className="h-3 w-3 shrink-0 text-[var(--color-text-muted)]" />
      ) : (
        <Sparkles className="h-3 w-3 shrink-0 text-[var(--color-accent)]" />
      )}
      <span className="truncate">{reason.text}</span>
    </div>
  );
}

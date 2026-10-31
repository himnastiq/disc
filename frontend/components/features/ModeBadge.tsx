'use client';

import React from 'react';
import { Sparkles, TrendingUp } from 'lucide-react';

export interface ModeBadgeProps {
  mode: 'personalized' | 'popularity';
  className?: string;
}

export function ModeBadge({ mode, className = '' }: ModeBadgeProps) {
  const isPersonalized = mode === 'personalized';

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-[4px] text-[12px] font-semibold tracking-wider uppercase border ${
        isPersonalized
          ? 'bg-[var(--color-accent)]/10 text-[var(--color-accent-text)] border-[var(--color-accent)]/20'
          : 'bg-[var(--color-elevated)] text-[var(--color-text-secondary)] border-[var(--color-border)]'
      } ${className}`}
    >
      {isPersonalized ? (
        <>
          <Sparkles className="h-3 w-3 text-[var(--color-accent)]" />
          <span>Personalized</span>
        </>
      ) : (
        <>
          <TrendingUp className="h-3 w-3 text-[var(--color-text-muted)]" />
          <span>Popularity Fallback</span>
        </>
      )}
    </span>
  );
}

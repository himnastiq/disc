'use client';

import React, { useEffect, useRef } from 'react';
import Image from 'next/image';
import { X, Star, Film, ShoppingBag, Newspaper, Sparkles, Heart, Check } from 'lucide-react';
import { useItemDetail, useSimilar } from '@/lib/api/hooks';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import type { ScoredItem } from '@/lib/api/schemas';

export interface ItemDrawerProps {
  type: string;
  itemId: string | null;
  cardType?: 'movie' | 'product' | 'article';
  onClose: () => void;
  onSelectItem?: (item: ScoredItem) => void;
}

export function ItemDrawer({
  type,
  itemId,
  cardType = 'movie',
  onClose,
  onSelectItem,
}: ItemDrawerProps) {
  const drawerRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedElementRef = useRef<HTMLElement | null>(null);

  const { data: item, isLoading, isError, refetch } = useItemDetail(type, itemId || undefined);
  const { data: similarData, isLoading: similarLoading } = useSimilar(type, itemId || undefined, 6);

  // Store trigger element and restore focus on unmount
  useEffect(() => {
    if (itemId) {
      previouslyFocusedElementRef.current = document.activeElement as HTMLElement;
      // Focus drawer
      setTimeout(() => {
        drawerRef.current?.focus();
      }, 50);
    }

    return () => {
      previouslyFocusedElementRef.current?.focus();
    };
  }, [itemId]);

  // Focus trap & Escape key
  useEffect(() => {
    if (!itemId) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        if (!drawerRef.current) return;
        const focusableElements = drawerRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement?.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement?.focus();
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [itemId, onClose]);

  if (!itemId) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end bg-black/80 backdrop-blur-xs transition-opacity duration-200"
      aria-modal="true"
      role="dialog"
      aria-labelledby="drawer-item-title"
    >
      {/* Backdrop click area */}
      <div
        className="fixed inset-0 cursor-pointer"
        aria-hidden="true"
        onClick={onClose}
      />

      {/* Slide-out Sheet */}
      <div
        ref={drawerRef}
        tabIndex={-1}
        className="relative z-10 flex h-full w-full max-w-lg flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl focus:outline-none overflow-y-auto"
      >
        {/* Sticky Close Header */}
        <div className="sticky top-0 z-20 flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)]/95 px-5 py-3.5 backdrop-blur-sm">
          <span className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
            {cardType === 'movie' && 'Film Details'}
            {cardType === 'product' && 'Product Details'}
            {cardType === 'article' && 'Article Story'}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close item drawer"
            className="rounded-[4px] p-1.5 text-[var(--color-text-secondary)] hover:bg-[var(--color-elevated)] hover:text-[var(--color-text)] transition-colors focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="p-6 space-y-4">
            <Skeleton className="h-64 w-full rounded-[4px] bg-[var(--color-elevated)]" />
            <Skeleton className="h-8 w-3/4 bg-[var(--color-elevated)]" />
            <Skeleton className="h-4 w-1/2 bg-[var(--color-elevated)]" />
            <Skeleton className="h-20 w-full bg-[var(--color-elevated)]" />
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-6">
            <ErrorState
              title="Unable to load item"
              message={`Could not fetch details for item ID ${itemId}.`}
              onRetry={refetch}
            />
          </div>
        )}

        {/* Item Content */}
        {item && (
          <div className="p-6 space-y-6">
            {/* 1. Large Poster / Hero Banner */}
            <div className="relative aspect-[16/9] sm:aspect-[2/1] w-full overflow-hidden rounded-[var(--radius-card)] bg-[var(--color-elevated)] border border-[var(--color-border)]">
              {item.image_url ? (
                <Image
                  src={item.image_url}
                  alt={item.title}
                  fill
                  sizes="500px"
                  className="object-cover"
                />
              ) : (
                <div className="flex h-full w-full flex-col items-center justify-center p-4 text-center text-[var(--color-text-muted)]">
                  {cardType === 'movie' && <Film className="h-12 w-12 opacity-30 text-[var(--color-accent)] mb-2" />}
                  {cardType === 'product' && <ShoppingBag className="h-12 w-12 opacity-30 text-[var(--color-accent)] mb-2" />}
                  {cardType === 'article' && <Newspaper className="h-12 w-12 opacity-30 text-[var(--color-accent)] mb-2" />}
                  <span className="text-xs text-[var(--color-text-secondary)]">Catalogue #{item.item_id}</span>
                </div>
              )}
            </div>

            {/* 2. Title & Metadata Block */}
            <div className="space-y-2">
              <h2
                id="drawer-item-title"
                className="text-2xl sm:text-3xl font-bold tracking-tight text-[var(--color-text)] leading-tight"
              >
                {item.title}
              </h2>

              <div className="flex items-center gap-3 text-xs text-[var(--color-text-secondary)] flex-wrap tabular-nums">
                {item.year && <span className="font-semibold text-[var(--color-text)]">{item.year}</span>}
                {item.subtitle && <span>· {item.subtitle}</span>}
                {item.popularity_rank && (
                  <span className="flex items-center gap-1">
                    · Rank #{item.popularity_rank}
                  </span>
                )}
              </div>

              {/* Categories */}
              {item.categories.length > 0 && (
                <div className="flex items-center gap-1.5 pt-1 flex-wrap">
                  {item.categories.map((cat) => (
                    <Badge
                      key={cat}
                      variant="secondary"
                      className="text-xs px-2 py-0.5 bg-[var(--color-elevated)] text-[var(--color-text-secondary)] border border-[var(--color-border)]"
                    >
                      {cat}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* 3. Action Buttons */}
            <div className="flex items-center gap-2 pt-1 border-y border-[var(--color-border)] py-3">
              <button
                type="button"
                className="flex-1 flex items-center justify-center gap-1.5 rounded-[var(--radius-card)] bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] active:bg-[var(--color-accent-active)] px-4 py-2 text-xs font-bold text-white transition-colors cursor-pointer min-h-[44px]"
              >
                <Check className="h-4 w-4" />
                <span>Mark Watched</span>
              </button>
              <button
                type="button"
                className="flex items-center justify-center gap-1.5 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-transparent hover:bg-[var(--color-elevated)] px-4 py-2 text-xs font-semibold text-[var(--color-text)] transition-colors cursor-pointer min-h-[44px]"
              >
                <Heart className="h-4 w-4" />
                <span>Like</span>
              </button>
            </div>

            {/* 4. Description / Synopsis */}
            {item.text && (
              <div className="space-y-1.5">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)]">
                  Overview
                </h4>
                <p className="text-sm leading-relaxed text-[var(--color-text)] whitespace-pre-line">
                  {item.text}
                </p>
              </div>
            )}

            {/* 5. More Like This Section */}
            <div className="space-y-3 pt-3 border-t border-[var(--color-border)]">
              <h4 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-muted)] flex items-center gap-1.5">
                <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)]" /> More Like This
              </h4>

              {similarLoading ? (
                <div className="grid grid-cols-2 gap-2">
                  <Skeleton className="h-20 bg-[var(--color-elevated)]" />
                  <Skeleton className="h-20 bg-[var(--color-elevated)]" />
                </div>
              ) : similarData && similarData.results.length > 0 ? (
                <div className="grid grid-cols-2 gap-2.5">
                  {similarData.results.map((sim) => (
                    <div
                      key={sim.item_id}
                      role="button"
                      tabIndex={0}
                      onClick={() => onSelectItem?.(sim)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onSelectItem?.(sim);
                        }
                      }}
                      className="group flex flex-col justify-between rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-elevated)]/40 p-2.5 transition-colors hover:border-[#3E3E3E] hover:bg-[var(--color-elevated)] cursor-pointer text-left"
                    >
                      <div>
                        <p className="font-semibold text-xs text-[var(--color-text)] line-clamp-2 group-hover:text-[var(--color-accent-text)]">
                          {sim.title}
                        </p>
                        <p className="text-[11px] text-[var(--color-text-muted)] mt-1 truncate">
                          {sim.categories.slice(0, 2).join(', ')}
                        </p>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-[10px] text-[var(--color-text-secondary)] tabular-nums pt-1 border-t border-[var(--color-border)]/60">
                        <span>Similar item</span>
                        <div className="flex items-center gap-0.5 text-[var(--color-accent)] font-semibold">
                          <Star className="h-2.5 w-2.5 fill-current" />
                          <span>{Math.round(sim.display_score * 100)}%</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--color-text-muted)] italic">
                  No nearest neighbors indexed for this item.
                </p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { Film, ShoppingBag, Newspaper, Star } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { ReasonBadge } from './ReasonBadge';
import { useMoviePoster } from '@/lib/api/hooks';
import type { ScoredItem } from '@/lib/api/schemas';

export interface RecCardProps {
  item: ScoredItem;
  cardType?: 'movie' | 'product' | 'article';
  onSelect?: (item: ScoredItem) => void;
  priority?: boolean;
  className?: string;
}

export function RecCard({
  item,
  cardType = 'movie',
  onSelect,
  priority = false,
  className = '',
}: RecCardProps) {
  const [imageError, setImageError] = useState(false);

  // Dynamically resolve TMDB poster for movie cards when image_url is missing
  const { data: tmdbPosterUrl } = useMoviePoster(
    item.title,
    item.year,
    cardType === 'movie' && !item.image_url
  );
  const activeImageUrl = item.image_url || tmdbPosterUrl;

  const handleClick = () => {
    onSelect?.(item);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect?.(item);
    }
  };

  const matchPercentage = Math.round(item.display_score * 100);

  return (
    <article
      role="button"
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`group flex flex-col justify-between rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-3 transition-all duration-150 cursor-pointer hover:border-[#3E3E3E] hover:bg-[var(--color-elevated)]/50 focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] ${className}`}
    >
      <div className="space-y-3">
        {/* 1. Media / Poster Slot (Ratio 2:3 for movies/products; compact header for articles) */}
        {cardType !== 'article' ? (
          <div className="relative aspect-[2/3] w-full overflow-hidden rounded-[4px] bg-[var(--color-elevated)] border border-[var(--color-border)]">
            {activeImageUrl && !imageError ? (
              <Image
                src={activeImageUrl}
                alt={item.title}
                fill
                priority={priority}
                unoptimized
                sizes="(max-width: 640px) 50vw, (max-width: 1024px) 33vw, 25vw"
                className="object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                onError={() => setImageError(true)}
              />
            ) : (
              <div className="flex h-full w-full flex-col items-center justify-center p-3 text-center text-[var(--color-text-muted)]">
                {cardType === 'movie' ? (
                  <Film className="h-8 w-8 mb-2 opacity-40 text-[var(--color-accent)]" />
                ) : (
                  <ShoppingBag className="h-8 w-8 mb-2 opacity-40 text-[var(--color-accent)]" />
                )}
                <span className="text-[11px] font-medium line-clamp-2 text-[var(--color-text-secondary)]">
                  {item.title}
                </span>
              </div>
            )}

            {/* Score Pill in Top Corner */}
            <div className="absolute top-1.5 right-1.5 flex items-center gap-1 rounded-[3px] bg-[var(--color-bg)]/90 px-1.5 py-0.5 text-[10px] font-bold text-[var(--color-text)] tabular-nums border border-[var(--color-border)] shadow-sm">
              <Star className="h-2.5 w-2.5 fill-[var(--color-accent)] text-[var(--color-accent)]" />
              <span>{matchPercentage}%</span>
            </div>
          </div>
        ) : (
          /* Article Top Slot: Category & Match Percentage */
          <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-2 text-xs">
            <div className="flex items-center gap-1.5 text-[var(--color-text-secondary)]">
              <Newspaper className="h-3.5 w-3.5 text-[var(--color-accent)]" />
              <span className="text-[11px] font-semibold text-[var(--color-text)]">
                {item.categories[0] || 'News'}
              </span>
            </div>
            <div className="flex items-center gap-1 text-[10px] font-bold text-[var(--color-text)] tabular-nums">
              <Star className="h-2.5 w-2.5 fill-[var(--color-accent)] text-[var(--color-accent)]" />
              <span>{matchPercentage}%</span>
            </div>
          </div>
        )}

        {/* 2. Text Content & Hierarchy */}
        <div className="space-y-1.5">
          {/* Title clamped to max 2 lines */}
          <h4 className="font-bold text-xs sm:text-sm text-[var(--color-text)] line-clamp-2 leading-snug group-hover:text-[var(--color-accent-text)] transition-colors">
            {item.title}
          </h4>

          {/* Subtitle / Metadata Line */}
          {cardType === 'movie' && (
            <p className="text-[12px] text-[var(--color-text-secondary)] tabular-nums flex items-center gap-1.5 flex-wrap">
              {item.year && <span>{item.year}</span>}
              {item.year && item.categories.length > 0 && <span>·</span>}
              <span className="truncate">{item.categories.slice(0, 2).join(', ')}</span>
            </p>
          )}

          {cardType === 'product' && (
            <p className="text-[12px] text-[var(--color-text-secondary)] tabular-nums flex items-center gap-1.5 truncate">
              {item.subtitle && <span className="font-medium text-[var(--color-text)]">{item.subtitle}</span>}
              {item.subtitle && item.categories.length > 0 && <span>·</span>}
              <span className="text-[var(--color-text-muted)] truncate">{item.categories.slice(0, 2).join(', ')}</span>
            </p>
          )}

          {cardType === 'article' && item.subtitle && (
            /* Abstract snippet clamped to exactly 3 lines */
            <p className="text-xs text-[var(--color-text-secondary)] line-clamp-3 leading-relaxed">
              {item.subtitle}
            </p>
          )}

          {/* Category Chips */}
          {item.categories.length > 0 && (
            <div className="flex items-center gap-1 pt-0.5 flex-wrap">
              {item.categories.slice(0, 2).map((cat) => (
                <Badge
                  key={cat}
                  variant="outline"
                  className="text-[10px] px-1.5 py-0 bg-[var(--color-elevated)]/40 border-[var(--color-border)] text-[var(--color-text-secondary)]"
                >
                  {cat}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 3. Footer: Attribution Reason */}
      <div className="mt-3 pt-2 border-t border-[var(--color-border)]">
        <ReasonBadge reason={item.reason} />
      </div>
    </article>
  );
}

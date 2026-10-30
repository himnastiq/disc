'use client';

import React, { useState, useRef, useMemo } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import {
  ChevronLeft,
  ChevronRight,
  Star,
  Heart,
  Check,
  Plus,
  Sparkles,
  Film,
  ArrowRight,
} from 'lucide-react';
import { useUserState } from '@/lib/user-state';
import { posterUrl } from '@/lib/tmdb-image';
import type { CarouselMovie } from '@/lib/curated';

export interface MovieCarouselRowProps {
  title: string;
  subtitle?: string;
  href?: string;
  ids?: number[];
  items?: CarouselMovie[];
  onSelectItem?: (item: CarouselMovie) => void;
}

export function MovieCarouselRow({
  title,
  subtitle,
  href,
  ids,
  items,
  onSelectItem,
}: MovieCarouselRowProps) {
  const { state, toggleWatchlist, toggleLiked, getMovieState } = useUserState();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [failedImages, setFailedImages] = useState<Record<string | number, boolean>>({});

  const scroll = (direction: 'left' | 'right') => {
    if (scrollRef.current) {
      const offset =
        direction === 'left'
          ? -scrollRef.current.clientWidth * 0.75
          : scrollRef.current.clientWidth * 0.75;
      if (typeof scrollRef.current.scrollBy === 'function') {
        scrollRef.current.scrollBy({ left: offset, behavior: 'smooth' });
      } else {
        scrollRef.current.scrollLeft += offset;
      }
    }
  };

  // Resolve items from either explicit item list or user interaction IDs
  const resolvedItems: CarouselMovie[] = useMemo(() => {
    if (items) return items;
    if (ids) {
      return ids.map((id) => {
        const entry = state.movies[id];
        return {
          id,
          title: entry?.title || `Movie #${id}`,
          poster: entry?.poster_path || null,
          year: entry?.release_date ? entry.release_date.split('-')[0] : '',
          rating: entry?.vote_average || null,
          genreIds: entry?.genre_ids,
        };
      });
    }
    return [];
  }, [items, ids, state.movies]);

  if (resolvedItems.length === 0) return null;

  return (
    <section aria-label={title} className="mb-8 group/row relative">
      {/* Row Header */}
      <div className="flex items-baseline justify-between gap-2 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-base sm:text-lg font-bold text-[var(--color-text)]">
              {title}
            </h3>
            {href && (
              <Link
                href={href}
                className="text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-accent-text)] inline-flex items-center gap-1 transition-colors"
                aria-label={`View all ${title}`}
              >
                <span>View all</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
              {subtitle}
            </p>
          )}
        </div>
      </div>

      <div className="relative">
        {/* Left Scroll Chevron */}
        <button
          type="button"
          onClick={() => scroll('left')}
          className="absolute -left-3 top-1/2 -translate-y-1/2 z-20 w-8 h-12 bg-[var(--color-bg)] hover:bg-[var(--color-elevated)] border border-[var(--color-border)] rounded-r-[4px] flex items-center justify-center text-[var(--color-text)] opacity-0 group-hover/row:opacity-100 transition-opacity cursor-pointer focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)]"
          aria-label={`Scroll ${title} left`}
        >
          <ChevronLeft className="h-5 w-5" />
        </button>

        {/* Carousel Items Container */}
        <div
          ref={scrollRef}
          role="region"
          aria-label={`${title} carousel`}
          tabIndex={0}
          className="flex gap-3 sm:gap-4 overflow-x-auto scroll-smooth scrollbar-none pb-2 pt-1 -mx-1 px-1 snap-x snap-mandatory focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)]"
        >
          {resolvedItems.map((movie, idx) => {
            const numericId = typeof movie.id === 'number' ? movie.id : parseInt(String(movie.id), 10);
            const ms = !isNaN(numericId) ? getMovieState(numericId) : undefined;
            const poster = posterUrl(movie.poster, 'w342');
            const rating = movie.rating ? movie.rating.toFixed(1) : null;
            const userRating = ms?.rating;
            const hasFailed = failedImages[movie.id];

            const handleCardClick = () => {
              onSelectItem?.(movie);
            };

            const handleKeyDown = (e: React.KeyboardEvent) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onSelectItem?.(movie);
              }
            };

            return (
              <article
                key={movie.id}
                className="w-[calc(50%-6px)] sm:w-[calc(33.333%-8px)] md:w-[calc(25%-12px)] shrink-0 snap-start relative group/card"
              >
                {/* Main Card Button (Accessible clickable region) */}
                <button
                  type="button"
                  onClick={handleCardClick}
                  onKeyDown={handleKeyDown}
                  className="w-full flex flex-col gap-2 text-left outline-none cursor-pointer focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] rounded-[var(--radius-card)]"
                >
                  <div className="relative aspect-[2/3] w-full overflow-hidden rounded-[var(--radius-card)] bg-[var(--color-elevated)] border border-[var(--color-border)] group-hover/card:border-[#3E3E3E] transition-colors">
                    {poster && !hasFailed ? (
                      <Image
                        src={poster}
                        alt=""
                        fill
                        unoptimized
                        sizes="(max-width: 640px) 50vw, (max-width: 768px) 33vw, 25vw"
                        priority={idx < 4}
                        onError={() =>
                          setFailedImages((prev) => ({ ...prev, [movie.id]: true }))
                        }
                        className="object-cover transition-transform duration-200 group-hover/card:scale-[1.02]"
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center h-full p-3 text-center text-[var(--color-text-muted)] bg-[var(--color-surface)]">
                        <Film className="h-8 w-8 mb-2 opacity-40 text-[var(--color-accent)]" />
                        <span className="text-xs font-semibold text-[var(--color-text)] line-clamp-2 w-full">
                          {movie.title}
                        </span>
                        {movie.year && (
                          <span className="text-[10px] text-[var(--color-text-secondary)] mt-1 tabular-nums">
                            {movie.year}
                          </span>
                        )}
                      </div>
                    )}

                    {/* Match Percentage or Rank Badge */}
                    {movie.matchPercentage ? (
                      <span className="absolute top-2 left-2 bg-[var(--color-bg)] text-emerald-400 text-[10px] font-bold px-1.5 py-0.5 rounded-[4px] border border-emerald-500/40 tabular-nums flex items-center gap-1 z-10">
                        <Sparkles className="h-2.5 w-2.5 text-emerald-400" />
                        <span>{movie.matchPercentage}%</span>
                      </span>
                    ) : movie.rank !== undefined ? (
                      <span className="absolute top-2 left-2 bg-[var(--color-bg)] text-[var(--color-text)] text-[11px] font-bold px-1.5 py-0.5 rounded-[4px] border border-[var(--color-border)] tabular-nums z-10">
                        #{movie.rank}
                      </span>
                    ) : null}

                    {/* User Rating Badge */}
                    {userRating && (
                      <span className="absolute top-2 right-2 flex items-center gap-1 bg-[var(--color-bg)] text-xs font-semibold px-1.5 py-0.5 rounded-[4px] text-[var(--color-accent-text)] border border-[var(--color-accent)]/40 tabular-nums z-10">
                        <Star className="h-3 w-3 fill-[var(--color-accent)] text-[var(--color-accent)]" />
                        <span>{userRating}</span>
                      </span>
                    )}

                    {/* Score Rating */}
                    {!userRating && rating && Number(rating) > 0 && (
                      <span className="absolute bottom-2 left-2 flex items-center gap-1 bg-[var(--color-bg)] text-xs font-semibold px-1.5 py-0.5 rounded-[4px] text-[var(--color-text)] border border-[var(--color-border)] tabular-nums z-10">
                        <Star className="h-3 w-3 fill-[var(--color-accent)] text-[var(--color-accent)]" />
                        <span>{rating}</span>
                      </span>
                    )}
                  </div>

                  {/* Card Title & Metadata */}
                  <div className="min-w-0">
                    <h4 className="text-xs sm:text-sm font-bold text-[var(--color-text)] truncate leading-tight group-hover/card:text-[var(--color-accent-text)] transition-colors">
                      {movie.title}
                    </h4>
                    <p className="text-[12px] text-[var(--color-text-secondary)] mt-0.5 truncate tabular-nums">
                      {userRating
                        ? `Rated ${userRating}/10`
                        : movie.reason
                        ? movie.reason
                        : movie.year || 'Popular'}
                    </p>
                  </div>
                </button>

                {/* Quick 1-Tap Overlay Actions (Sibling to main button, not nested) */}
                <div className="absolute top-2 right-2 p-1 opacity-0 group-hover/card:opacity-100 group-focus-within/card:opacity-100 transition-opacity flex items-center gap-1.5 z-20">
                  <button
                    type="button"
                    aria-pressed={Boolean(ms?.inWatchlist)}
                    aria-label={ms?.inWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                    title={ms?.inWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (!isNaN(numericId)) {
                        toggleWatchlist(numericId, {
                          title: movie.title,
                          poster_path: movie.poster,
                          release_date: movie.year ? `${movie.year}-01-01` : '',
                          vote_average: movie.rating ?? undefined,
                          genre_ids: movie.genreIds,
                        });
                      }
                    }}
                    className={`h-7 w-7 rounded-[4px] flex items-center justify-center text-xs transition-colors cursor-pointer border shadow-xs focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] ${
                      ms?.inWatchlist
                        ? 'bg-[var(--color-accent)] text-white border-[var(--color-accent)]'
                        : 'bg-[var(--color-bg)]/95 text-[var(--color-text)] border-[var(--color-border)] hover:bg-[var(--color-elevated)]'
                    }`}
                  >
                    {ms?.inWatchlist ? (
                      <Check className="h-3.5 w-3.5" />
                    ) : (
                      <Plus className="h-3.5 w-3.5" />
                    )}
                  </button>

                  <button
                    type="button"
                    aria-pressed={Boolean(ms?.liked)}
                    aria-label={ms?.liked ? 'Liked' : 'Like'}
                    title={ms?.liked ? 'Liked' : 'Like'}
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (!isNaN(numericId)) {
                        toggleLiked(numericId, {
                          title: movie.title,
                          poster_path: movie.poster,
                          release_date: movie.year ? `${movie.year}-01-01` : '',
                          vote_average: movie.rating ?? undefined,
                          genre_ids: movie.genreIds,
                        });
                      }
                    }}
                    className={`h-7 w-7 rounded-[4px] flex items-center justify-center text-xs transition-colors cursor-pointer border shadow-xs focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] ${
                      ms?.liked
                        ? 'bg-[var(--color-accent)] text-white border-[var(--color-accent)]'
                        : 'bg-[var(--color-bg)]/95 text-[var(--color-text)] border-[var(--color-border)] hover:bg-[var(--color-elevated)]'
                    }`}
                  >
                    <Heart
                      className="h-3.5 w-3.5"
                      fill={ms?.liked ? 'currentColor' : 'none'}
                    />
                  </button>
                </div>
              </article>
            );
          })}
        </div>

        {/* Right Scroll Chevron */}
        <button
          type="button"
          onClick={() => scroll('right')}
          className="absolute -right-3 top-1/2 -translate-y-1/2 z-20 w-8 h-12 bg-[var(--color-bg)] hover:bg-[var(--color-elevated)] border border-[var(--color-border)] rounded-l-[4px] flex items-center justify-center text-[var(--color-text)] opacity-0 group-hover/row:opacity-100 transition-opacity cursor-pointer focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)]"
          aria-label={`Scroll ${title} right`}
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      </div>
    </section>
  );
}

export default MovieCarouselRow;

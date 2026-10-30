'use client';

import React from 'react';
import { Sparkles, Check, RotateCcw } from 'lucide-react';
import { useUserState } from '@/lib/user-state';

const AVAILABLE_GENRES = [
  'Action',
  'Adventure',
  'Animation',
  'Comedy',
  'Crime',
  'Documentary',
  'Drama',
  'Family',
  'Fantasy',
  'Film-Noir',
  'Horror',
  'Musical',
  'Mystery',
  'Romance',
  'Sci-Fi',
  'Thriller',
  'War',
  'Western',
];

export function TasteProfiler() {
  const { state, toggleFavoriteGenre, setFavoriteGenres } = useUserState();
  const selectedCount = state.favoriteGenres.length;
  const isComplete = selectedCount >= 3;

  return (
    <section
      aria-labelledby="taste-profiler-title"
      className="mb-8 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-4 sm:p-5"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-4">
        <div>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[var(--color-accent)]" />
            <h2
              id="taste-profiler-title"
              className="text-sm sm:text-base font-bold text-[var(--color-text)]"
            >
              Taste Profiler
            </h2>
          </div>
          <p className="text-xs text-[var(--color-text-secondary)] mt-0.5">
            {isComplete
              ? `Taste vector calibrated with ${selectedCount} genres. Feeds tailored to your cinematic tone.`
              : `Select 3 or more favorite genres to unlock personalized content-based discovery.`}
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span
            className={`text-xs font-semibold px-2.5 py-1 rounded-[4px] border tabular-nums ${
              isComplete
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-[var(--color-elevated)] border-[var(--color-border)] text-[var(--color-text-muted)]'
            }`}
          >
            {selectedCount} / 3 selected
          </span>
          {selectedCount > 0 && (
            <button
              type="button"
              onClick={() => setFavoriteGenres([])}
              className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] p-1 transition-colors flex items-center gap-1 cursor-pointer focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)]"
              aria-label="Reset genre selections"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      <div
        role="group"
        aria-label="Movie genres"
        className="flex flex-wrap gap-2 pt-1"
      >
        {AVAILABLE_GENRES.map((genre) => {
          const isSelected = state.favoriteGenres.includes(genre);
          return (
            <button
              key={genre}
              type="button"
              aria-pressed={isSelected}
              onClick={() => toggleFavoriteGenre(genre)}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[var(--radius-card)] text-xs font-medium transition-colors cursor-pointer min-h-[36px] focus-visible:outline-2 focus-visible:outline-[var(--color-accent-text)] ${
                isSelected
                  ? 'bg-[var(--color-accent)] text-white border border-[var(--color-accent)] font-semibold'
                  : 'bg-[var(--color-elevated)] text-[var(--color-text-secondary)] border border-[var(--color-border)] hover:bg-[var(--color-elevated)]/80 hover:text-[var(--color-text)]'
              }`}
            >
              {isSelected && <Check className="h-3 w-3" />}
              <span>{genre}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export default TasteProfiler;


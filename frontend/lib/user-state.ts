'use client';

import { useCallback, useSyncExternalStore } from 'react';

export interface UserMovieEntry {
  movieId: number;
  title: string;
  poster_path: string | null;
  release_date?: string;
  vote_average?: number | null;
  rating: number | null;
  liked: boolean;
  inWatchlist: boolean;
  inWatchLater?: boolean;
  watched: boolean;
  watchedAt?: string | null;
  watchProgress?: number;
  genre_ids?: number[];
  addedAt: string;
}

export interface UserState {
  movies: Record<number, UserMovieEntry>;
  favoriteGenres: string[];
}

const STORAGE_KEY = 'discovery_engine_user_state';

const initialUserState: UserState = {
  movies: {},
  favoriteGenres: [],
};

let cachedRaw: string | null = null;
let cachedState: UserState = initialUserState;
const listeners = new Set<() => void>();

function emitChange() {
  for (const listener of listeners) {
    listener();
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function getSnapshot(): UserState {
  if (typeof window === 'undefined') return initialUserState;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw !== cachedRaw) {
      cachedRaw = raw;
      if (raw) {
        const parsed = JSON.parse(raw);
        cachedState = {
          movies: parsed?.movies || {},
          favoriteGenres: Array.isArray(parsed?.favoriteGenres) ? parsed.favoriteGenres : [],
        };
      } else {
        cachedState = initialUserState;
      }
    }
  } catch {
    cachedState = initialUserState;
  }
  return cachedState;
}

function getServerSnapshot(): UserState {
  return initialUserState;
}

function persistState(updater: (prev: UserState) => UserState) {
  const current = getSnapshot();
  const next = updater(current);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {}
  getSnapshot();
  emitChange();
}

export function useUserState() {
  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  const isHydrated = typeof window !== 'undefined';

  const getMovieState = useCallback(
    (movieId: number): UserMovieEntry | undefined => {
      return state.movies[movieId];
    },
    [state.movies]
  );

  const toggleWatchlist = useCallback(
    (
      movieId: number,
      meta?: {
        title?: string;
        poster_path?: string | null;
        release_date?: string;
        vote_average?: number | null;
        genre_ids?: number[];
      }
    ) => {
      persistState((prev) => {
        const existing = prev.movies[movieId];
        const inWatchlist = !existing?.inWatchlist;

        const updatedEntry: UserMovieEntry = {
          movieId,
          title: meta?.title || existing?.title || `Movie #${movieId}`,
          poster_path: meta?.poster_path ?? existing?.poster_path ?? null,
          release_date: meta?.release_date || existing?.release_date || '',
          vote_average: meta?.vote_average ?? existing?.vote_average ?? null,
          rating: existing?.rating ?? null,
          liked: existing?.liked ?? false,
          inWatchlist,
          watched: existing?.watched ?? false,
          watchedAt: existing?.watchedAt ?? null,
          watchProgress: existing?.watchProgress ?? 0,
          genre_ids: meta?.genre_ids || existing?.genre_ids || [],
          addedAt: existing?.addedAt || new Date().toISOString(),
        };

        return {
          ...prev,
          movies: { ...prev.movies, [movieId]: updatedEntry },
        };
      });
    },
    []
  );

  const toggleLiked = useCallback(
    (
      movieId: number,
      meta?: {
        title?: string;
        poster_path?: string | null;
        release_date?: string;
        vote_average?: number | null;
        genre_ids?: number[];
      }
    ) => {
      persistState((prev) => {
        const existing = prev.movies[movieId];
        const liked = !existing?.liked;

        const updatedEntry: UserMovieEntry = {
          movieId,
          title: meta?.title || existing?.title || `Movie #${movieId}`,
          poster_path: meta?.poster_path ?? existing?.poster_path ?? null,
          release_date: meta?.release_date || existing?.release_date || '',
          vote_average: meta?.vote_average ?? existing?.vote_average ?? null,
          rating: existing?.rating ?? null,
          liked,
          inWatchlist: existing?.inWatchlist ?? false,
          watched: existing?.watched ?? false,
          watchedAt: existing?.watchedAt ?? null,
          watchProgress: existing?.watchProgress ?? 0,
          genre_ids: meta?.genre_ids || existing?.genre_ids || [],
          addedAt: existing?.addedAt || new Date().toISOString(),
        };

        return {
          ...prev,
          movies: { ...prev.movies, [movieId]: updatedEntry },
        };
      });
    },
    []
  );

  const setRating = useCallback(
    (
      movieId: number,
      rating: number | null,
      meta?: {
        title?: string;
        poster_path?: string | null;
        release_date?: string;
        vote_average?: number | null;
        genre_ids?: number[];
      }
    ) => {
      persistState((prev) => {
        const existing = prev.movies[movieId];

        const updatedEntry: UserMovieEntry = {
          movieId,
          title: meta?.title || existing?.title || `Movie #${movieId}`,
          poster_path: meta?.poster_path ?? existing?.poster_path ?? null,
          release_date: meta?.release_date || existing?.release_date || '',
          vote_average: meta?.vote_average ?? existing?.vote_average ?? null,
          rating,
          liked: existing?.liked ?? false,
          inWatchlist: existing?.inWatchlist ?? false,
          watched: existing?.watched ?? (rating !== null),
          watchedAt: existing?.watchedAt ?? (rating !== null ? new Date().toISOString() : null),
          watchProgress: existing?.watchProgress ?? 0,
          genre_ids: meta?.genre_ids || existing?.genre_ids || [],
          addedAt: existing?.addedAt || new Date().toISOString(),
        };

        return {
          ...prev,
          movies: { ...prev.movies, [movieId]: updatedEntry },
        };
      });
    },
    []
  );

  const toggleFavoriteGenre = useCallback(
    (genre: string) => {
      persistState((prev) => {
        const exists = prev.favoriteGenres.includes(genre);
        const favoriteGenres = exists
          ? prev.favoriteGenres.filter((g) => g !== genre)
          : [...prev.favoriteGenres, genre];
        return { ...prev, favoriteGenres };
      });
    },
    []
  );

  const setFavoriteGenres = useCallback(
    (genres: string[]) => {
      persistState((prev) => ({
        ...prev,
        favoriteGenres: genres,
      }));
    },
    []
  );

  return {
    state,
    isHydrated,
    getMovieState,
    toggleWatchlist,
    toggleLiked,
    setRating,
    toggleFavoriteGenre,
    setFavoriteGenres,
  };
}

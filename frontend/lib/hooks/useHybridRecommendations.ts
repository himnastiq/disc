'use client';

import { useMemo } from 'react';
import { useRecommendations, usePopular, useSimilar } from '@/lib/api/hooks';
import { useUserState } from '@/lib/user-state';
import type { CarouselMovie } from '@/lib/curated';
import type { ScoredItem } from '@/lib/api/schemas';
import type { RecommendResponse } from '@/lib/api/client';

function scoredItemToCarousel(item: ScoredItem, idx: number): CarouselMovie {
  return {
    id: item.item_id,
    title: item.title,
    poster: item.image_url || null,
    year: item.year || null,
    rating: item.display_score ? Number((item.display_score * 10).toFixed(1)) : null,
    rank: idx + 1,
    matchPercentage: Math.round(item.display_score * 100),
    reason: item.reason?.text,
    categories: item.categories,
  };
}

export function useHybridRecommendations(
  activeUser: string = '1',
  initialRecData?: RecommendResponse | null
) {
  const { state } = useUserState();

  // 1. Fetch SAR recommendations for the active user (disabled if pre-provided)
  const { data: recData, isLoading: isRecLoading } = useRecommendations(
    'movies',
    activeUser,
    18,
    { enabled: !initialRecData }
  );

  const effectiveRecData = initialRecData ?? recData;

  // 2. Fetch popular movies for Trending
  const { data: popData, isLoading: isPopLoading } = usePopular('movies', 18);

  // 3. Find most recent liked / highly rated movie from local state
  const mostRecentInteraction = useMemo(() => {
    const entries = Object.values(state.movies);
    const sorted = entries
      .filter((m) => m.liked || (m.rating !== null && m.rating >= 7))
      .sort((a, b) => new Date(b.addedAt).getTime() - new Date(a.addedAt).getTime());

    return sorted[0] || null;
  }, [state.movies]);

  // 4. Fetch similar movies for "Because You Liked"
  const { data: similarData } = useSimilar(
    'movies',
    mostRecentInteraction ? String(mostRecentInteraction.movieId) : undefined,
    10
  );

  // Format "For You"
  const forYou: CarouselMovie[] = useMemo(() => {
    if (!effectiveRecData?.results) return [];
    return effectiveRecData.results.map((item, idx) => scoredItemToCarousel(item, idx));
  }, [effectiveRecData]);

  // Format "Trending"
  const trending: CarouselMovie[] = useMemo(() => {
    if (!popData?.results) return [];
    return popData.results.map((item, idx) => ({
      id: item.item_id,
      title: item.title,
      poster: item.image_url || null,
      year: item.year || null,
      rating: item.display_score ? Number((item.display_score * 10).toFixed(1)) : null,
      rank: idx + 1,
      matchPercentage: Math.round(item.display_score * 100),
      categories: item.categories,
    }));
  }, [popData]);

  // Format "Because You Liked"
  const becauseYouLiked = useMemo(() => {
    if (!mostRecentInteraction || !similarData?.results || similarData.results.length === 0) {
      return null;
    }

    return {
      sourceMovie: {
        id: mostRecentInteraction.movieId,
        title: mostRecentInteraction.title,
        interaction: mostRecentInteraction.rating !== null ? ('rated' as const) : ('liked' as const),
      },
      recommendations: similarData.results.map((item, idx) => scoredItemToCarousel(item, idx)),
    };
  }, [mostRecentInteraction, similarData]);

  // Format "Top Genre Picks"
  const topGenrePicks = useMemo(() => {
    const favoriteGenre = state.favoriteGenres[0];
    if (!favoriteGenre || (!recData?.results && !popData?.results)) return null;

    const pool = recData?.results || popData?.results || [];
    const matched = pool.filter((item) =>
      item.categories?.some((cat) => cat.toLowerCase() === favoriteGenre.toLowerCase())
    );

    if (matched.length === 0) return null;

    return {
      genreName: favoriteGenre,
      movies: matched.map((item, idx) => scoredItemToCarousel(item, idx)),
    };
  }, [state.favoriteGenres, recData, popData]);

  const source = effectiveRecData?.meta?.model === 'sar' ? 'ml-sar' : 'content-based';

  return {
    forYou,
    trending,
    becauseYouLiked,
    topGenrePicks,
    source,
    isLoading: isRecLoading || isPopLoading,
  };
}

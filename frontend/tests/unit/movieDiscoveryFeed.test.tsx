import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MovieCarouselRow } from '@/components/features/MovieCarouselRow';
import { TasteProfiler } from '@/components/features/TasteProfiler';
import { MovieDiscoveryFeed } from '@/components/features/MovieDiscoveryFeed';
import { apiClient, type RecommendResponse } from '@/lib/api/client';
import profileFixture from '../fixtures/profile_movies_1.json';
import recommendFixture from '../fixtures/recommend_movies_1.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('TasteProfiler Component', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders all 18 genres and toggles genre selections', () => {
    renderWithClient(<TasteProfiler />);

    expect(screen.getByRole('heading', { name: /taste profiler/i })).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 3 selected/i)).toBeInTheDocument();

    const scifiButton = screen.getByRole('button', { name: /sci-fi/i });
    expect(scifiButton).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(scifiButton);
    expect(scifiButton).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(/1 \/ 3 selected/i)).toBeInTheDocument();

    // Toggle 2 more genres to complete
    fireEvent.click(screen.getByRole('button', { name: /action/i }));
    fireEvent.click(screen.getByRole('button', { name: /adventure/i }));
    expect(screen.getByText(/3 \/ 3 selected/i)).toBeInTheDocument();

    // Reset button
    const resetButton = screen.getByRole('button', { name: /reset genre selections/i });
    fireEvent.click(resetButton);
    expect(screen.getByText(/0 \/ 3 selected/i)).toBeInTheDocument();
  });
});

describe('MovieCarouselRow Component', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const mockMovies = [
    {
      id: 385,
      title: 'The Matrix (1999)',
      poster: null,
      year: 1999,
      rating: 8.7,
      rank: 1,
      matchPercentage: 94,
    },
    {
      id: 423,
      title: 'Blade Runner (1982)',
      poster: null,
      year: 1982,
      rating: 8.2,
      rank: 2,
      matchPercentage: 88,
    },
  ];

  it('renders carousel items, badges, and triggers selection', () => {
    const onSelect = vi.fn();
    renderWithClient(
      <MovieCarouselRow
        title="Personalized Recommendations"
        subtitle="Discovery feed"
        items={mockMovies}
        onSelectItem={onSelect}
      />
    );

    expect(screen.getByText('Personalized Recommendations')).toBeInTheDocument();
    expect(screen.getByText('Discovery feed')).toBeInTheDocument();
    expect(screen.getByText('94%')).toBeInTheDocument();

    const matrixCard = screen.getByRole('button', { name: /The Matrix/i });
    fireEvent.click(matrixCard);
    expect(onSelect).toHaveBeenCalledWith(mockMovies[0]);
  });

  it('toggles watchlist and liked states via quick overlay actions', () => {
    renderWithClient(
      <MovieCarouselRow
        title="Personalized Recommendations"
        items={mockMovies}
      />
    );

    const watchlistButton = screen.getAllByRole('button', { name: /add to watchlist/i })[0];
    expect(watchlistButton).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(watchlistButton);
    expect(watchlistButton).toHaveAttribute('aria-pressed', 'true');

    const likeButton = screen.getAllByRole('button', { name: /like/i })[0];
    expect(likeButton).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(likeButton);
    expect(likeButton).toHaveAttribute('aria-pressed', 'true');
  });

  it('scrolls carousel when left and right controls are clicked', () => {
    renderWithClient(
      <MovieCarouselRow
        title="Personalized Recommendations"
        items={mockMovies}
      />
    );

    const leftScroll = screen.getByRole('button', { name: /scroll personalized recommendations left/i });
    const rightScroll = screen.getByRole('button', { name: /scroll personalized recommendations right/i });

    expect(leftScroll).toBeInTheDocument();
    expect(rightScroll).toBeInTheDocument();

    fireEvent.click(rightScroll);
    fireEvent.click(leftScroll);
  });
});

describe('MovieDiscoveryFeed Component', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);
    vi.spyOn(apiClient, 'getRecommendations').mockResolvedValue(recommendFixture as RecommendResponse);
    vi.spyOn(apiClient, 'getPopular').mockResolvedValue(recommendFixture as RecommendResponse);
  });

  it('renders welcome banner, profile, and recommended carousels', async () => {
    renderWithClient(
      <MovieDiscoveryFeed
        user="1"
        k={10}
        onKChange={vi.fn()}
        recData={recommendFixture as RecommendResponse}
      />
    );

    expect(screen.getByText('The Discovery Engine')).toBeInTheDocument();
    expect(screen.getByText('SAR model')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /ai insights/i })).toBeInTheDocument();
    expect(await screen.findByText('User #1')).toBeInTheDocument();
    expect(await screen.findByText('Personalized Recommendations')).toBeInTheDocument();
  });
});


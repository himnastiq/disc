import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { CompareTab, computeOverlap } from '@/components/tabs/CompareTab';
import { apiClient, type RecommendResponse, type UsersResponse } from '@/lib/api/client';
import usersFixture from '../fixtures/users_movies.json';
import recommendFixture from '../fixtures/recommend_movies_1.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('computeOverlap pure function', () => {
  it('correctly calculates overlap, percentage, and Jaccard similarity', () => {
    const listA = [
      { item_id: '1', title: 'A', score: 1, rank: 1 },
      { item_id: '2', title: 'B', score: 0.9, rank: 2 },
      { item_id: '3', title: 'C', score: 0.8, rank: 3 },
    ];
    const listB = [
      { item_id: '2', title: 'B', score: 1, rank: 1 },
      { item_id: '3', title: 'C', score: 0.9, rank: 2 },
      { item_id: '4', title: 'D', score: 0.7, rank: 3 },
    ];

    const result = computeOverlap(listA, listB);
    expect(result.overlapCount).toBe(2);
    // overlap = 2 / 3 = 67%
    expect(result.percentage).toBe(67);
    // union = {1, 2, 3, 4} = 4 items. jaccard = 2/4 = 50%
    expect(result.jaccard).toBe(50);
    expect(result.sharedIds.has('2')).toBe(true);
    expect(result.sharedIds.has('3')).toBe(true);
    expect(result.sharedIds.has('1')).toBe(false);
  });

  it('handles empty lists gracefully', () => {
    const result = computeOverlap([], []);
    expect(result.overlapCount).toBe(0);
    expect(result.percentage).toBe(0);
    expect(result.jaccard).toBe(0);
  });
});

describe('CompareTab (P9.5)', () => {
  const popularFixture: RecommendResponse = {
    content_type: 'movies',
    k: 2,
    mode: 'popularity',
    results: [
      {
        item_id: '385', // Matches The Matrix in recommendFixture
        title: 'The Matrix (1999)',
        categories: ['Action', 'Sci-Fi'],
        score: 0.95,
        display_score: 95,
        meta: {},
      },
      {
        item_id: '999', // Different item
        title: 'Titanic (1997)',
        categories: ['Drama', 'Romance'],
        score: 0.88,
        display_score: 88,
        meta: {},
      },
    ],
    meta: {},
  };

  const user2Fixture: RecommendResponse = {
    content_type: 'movies',
    user_id: '2',
    k: 2,
    mode: 'personalized',
    results: [
      {
        item_id: '385',
        title: 'The Matrix (1999)',
        categories: ['Action', 'Sci-Fi'],
        score: 0.92,
        display_score: 92,
        meta: {},
      },
      {
        item_id: '777',
        title: 'Interstellar (2014)',
        categories: ['Adventure', 'Sci-Fi'],
        score: 0.85,
        display_score: 85,
        meta: {},
      },
    ],
    meta: {},
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getUsers').mockResolvedValue(usersFixture as UsersResponse);
    vi.spyOn(apiClient, 'getPopular').mockResolvedValue(popularFixture);
    vi.spyOn(apiClient, 'getRecommendations').mockImplementation(async (_type, userId) => {
      if (userId === '2') {
        return user2Fixture;
      }
      return recommendFixture as RecommendResponse;
    });
  });

  it('renders Popular vs. Personalized mode with overlap banner and highlighted items', async () => {
    renderWithClient(
      <CompareTab type="movies" user="1" k={10} onKChange={vi.fn()} />
    );

    // Check headings
    expect(await screen.findByRole('heading', { name: /Popular for Everyone/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Personalized for User #1/i })).toBeInTheDocument();

    // Check overlap summary banner (1 shared item: The Matrix)
    expect(screen.getByText(/1 of 10 items overlap/i)).toBeInTheDocument();

    // Badges for shared items
    const inBothBadges = screen.getAllByText('In both lists');
    expect(inBothBadges.length).toBeGreaterThanOrEqual(1);
  });

  it('switches to User vs. User mode and displays secondary user selector', async () => {
    renderWithClient(
      <CompareTab type="movies" user="1" k={10} onKChange={vi.fn()} />
    );

    const userVsUserTab = await screen.findByRole('tab', { name: /User vs. User/i });
    fireEvent.click(userVsUserTab);

    // Check secondary user selector presence
    expect(screen.getByText(/Compare User #1 with:/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /User #2/i })).toBeInTheDocument();
  });

  it('calls onKChange when k selector buttons are clicked', async () => {
    const onKChange = vi.fn();
    renderWithClient(
      <CompareTab type="movies" user="1" k={10} onKChange={onKChange} />
    );

    const k5Button = await screen.findByRole('button', { name: '5' });
    fireEvent.click(k5Button);
    expect(onKChange).toHaveBeenCalledWith(5);
  });

  it('renders error state on API error', async () => {
    vi.spyOn(apiClient, 'getPopular').mockRejectedValue(new Error('Failed to load'));

    renderWithClient(
      <CompareTab type="movies" user="1" k={10} onKChange={vi.fn()} />
    );

    expect(await screen.findByText('Comparison failed')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

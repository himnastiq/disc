import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ColdStartTab } from '@/components/tabs/ColdStartTab';
import { apiClient, type TypesResponse, type SearchResponse, type RecommendResponse } from '@/lib/api/client';
import typesFixture from '../fixtures/types.json';
import recommendFixture from '../fixtures/recommend_movies_1.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('ColdStartTab (P9.6)', () => {
  const searchMock: SearchResponse = {
    content_type: 'movies',
    query: 'matrix',
    total_matches: 2,
    results: [
      {
        item_id: '385',
        title: 'The Matrix (1999)',
        categories: ['Action', 'Sci-Fi'],
        year: 1999,
        popularity_rank: 1,
      },
      {
        item_id: '386',
        title: 'The Matrix Reloaded (2003)',
        categories: ['Action', 'Sci-Fi'],
        year: 2003,
        popularity_rank: 10,
      },
    ],
  };

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getTypes').mockResolvedValue(typesFixture as TypesResponse);
    vi.spyOn(apiClient, 'searchItems').mockResolvedValue(searchMock);
    vi.spyOn(apiClient, 'postColdStart').mockResolvedValue(recommendFixture as RecommendResponse);
  });

  it('renders search input and shows popularity fallback message when history is empty', async () => {
    renderWithClient(
      <ColdStartTab type="movies" k={10} onKChange={vi.fn()} />
    );

    expect(await screen.findByRole('searchbox')).toBeInTheDocument();
    expect(screen.getByText(/0 items selected/i)).toBeInTheDocument();
    expect(screen.getByText(/Serving global popularity fallback/i)).toBeInTheDocument();
  });

  it('searches items, adds item as chip, and prevents duplicate addition', async () => {
    renderWithClient(
      <ColdStartTab type="movies" k={10} onKChange={vi.fn()} />
    );

    const searchInput = await screen.findByRole('searchbox');
    fireEvent.change(searchInput, { target: { value: 'matrix' } });

    // Wait for debounced search results to show up
    const addButton = await screen.findByRole('button', { name: /add the matrix \(1999\)/i }, { timeout: 5000 });
    fireEvent.click(addButton);

    // Assert item is now in selected history chips
    await waitFor(() => {
      expect(screen.getByText(/Selected History \(1 \/ 200\)/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/1 items selected/i)).toBeInTheDocument();

    // The add button should now show "Added" and be disabled
    expect(screen.getByRole('button', { name: /added the matrix \(1999\)/i })).toBeDisabled();
  });

  it('removes a selected item chip and clears all chips', async () => {
    renderWithClient(
      <ColdStartTab type="movies" k={10} onKChange={vi.fn()} />
    );

    const searchInput = await screen.findByRole('searchbox');
    fireEvent.change(searchInput, { target: { value: 'matrix' } });

    const addButton = await screen.findByRole('button', { name: /add the matrix \(1999\)/i }, { timeout: 5000 });
    fireEvent.click(addButton);

    // Wait for chip to appear
    await screen.findByRole('button', { name: /remove the matrix \(1999\)/i });

    // Click Clear All
    const clearButton = screen.getByRole('button', { name: /clear all/i });
    fireEvent.click(clearButton);

    expect(screen.getByText(/Selected History \(0 \/ 200\)/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /clear all/i })).not.toBeInTheDocument();
  });

  it('displays explanation card when type does not support cold start', async () => {
    const customTypes: TypesResponse = {
      types: [
        {
          id: 'custom_type',
          display_name: 'Custom Domain',
          card_type: 'movie',
          supports_cold_start: false,
          user_count: 100,
          item_count: 50,
          interaction_count: 500,
        },
      ],
    };
    vi.spyOn(apiClient, 'getTypes').mockResolvedValue(customTypes);

    renderWithClient(
      <ColdStartTab type="custom_type" k={10} onKChange={vi.fn()} />
    );

    expect(
      await screen.findByRole('heading', { name: /Cold-Start Not Supported for Custom Domain/i })
    ).toBeInTheDocument();
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
  });

  it('calls onKChange when k selector buttons are clicked', async () => {
    const onKChange = vi.fn();
    renderWithClient(
      <ColdStartTab type="movies" k={10} onKChange={onKChange} />
    );

    const k5Button = await screen.findByRole('button', { name: '5' });
    fireEvent.click(k5Button);
    expect(onKChange).toHaveBeenCalledWith(5);
  });
});

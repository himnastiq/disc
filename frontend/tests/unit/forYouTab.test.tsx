import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ForYouTab } from '@/components/tabs/ForYouTab';
import { apiClient, type RecommendResponse } from '@/lib/api/client';
import profileFixture from '../fixtures/profile_movies_1.json';
import recommendFixture from '../fixtures/recommend_movies_1.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('ForYouTab (P9.4)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);
    vi.spyOn(apiClient, 'getRecommendations').mockResolvedValue(recommendFixture as RecommendResponse);
  });

  it('renders profile card and recommendations from fixtures', async () => {
    renderWithClient(
      <ForYouTab type="movies" user="1" k={10} onKChange={vi.fn()} />
    );

    // Profile card presence
    expect(await screen.findByText('User #1')).toBeInTheDocument();

    // Recommendation card presence
    expect(await screen.findByRole('heading', { name: 'The Matrix (1999)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Blade Runner (1982)' })).toBeInTheDocument();
  });

  it('renders k selector and triggers onKChange when options are clicked', async () => {
    const onKChange = vi.fn();
    renderWithClient(
      <ForYouTab type="movies" user="1" k={10} onKChange={onKChange} />
    );

    const k5Button = await screen.findByRole('button', { name: /k=5/i });
    fireEvent.click(k5Button);
    expect(onKChange).toHaveBeenCalledWith(5);

    const k20Button = screen.getByRole('button', { name: /k=20/i });
    fireEvent.click(k20Button);
    expect(onKChange).toHaveBeenCalledWith(20);
  });

  it('triggers onSelectItem when clicking a recommendation card', async () => {
    const onSelectItem = vi.fn();
    renderWithClient(
      <ForYouTab type="movies" user="1" k={10} onKChange={vi.fn()} onSelectItem={onSelectItem} />
    );

    const matrixCards = await screen.findAllByRole('button', {
      name: /the matrix \(1999\)/i,
    });
    fireEvent.click(matrixCards[0]);

    expect(onSelectItem).toHaveBeenCalledWith(
      expect.objectContaining({ item_id: '385', title: 'The Matrix (1999)' })
    );
  });

  it('renders error state on recommendation fetch failure', async () => {
    vi.spyOn(apiClient, 'getRecommendations').mockRejectedValue(new Error('API failure'));

    renderWithClient(
      <ForYouTab type="movies" user="1" k={10} onKChange={vi.fn()} />
    );

    expect(await screen.findByText('Failed to fetch recommendations')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  it('renders AI Insights rectangle for products domain', async () => {
    renderWithClient(
      <ForYouTab type="products" user="B0001" k={10} onKChange={vi.fn()} />
    );

    expect(await screen.findByRole('heading', { name: /ai insights/i })).toBeInTheDocument();
  });
});

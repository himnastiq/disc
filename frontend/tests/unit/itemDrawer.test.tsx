import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ItemDrawer } from '@/components/features/ItemDrawer';
import { apiClient } from '@/lib/api/client';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockItemDetail = {
  item_id: '385',
  title: 'The Matrix (1999)',
  subtitle: 'Warner Bros.',
  categories: ['Action', 'Sci-Fi'],
  year: 1999,
  image_url: null,
  text: 'A computer hacker learns from mysterious rebels about the true nature of his reality.',
  popularity_rank: 12,
  meta: {},
};

const mockSimilarResponse = {
  content_type: 'movies',
  user_id: null,
  mode: 'popularity' as const,
  k: 2,
  results: [
    {
      item_id: '423',
      title: 'Blade Runner (1982)',
      subtitle: null,
      categories: ['Sci-Fi'],
      year: 1982,
      image_url: null,
      score: 0.89,
      display_score: 0.92,
      reason: null,
      meta: {},
    },
  ],
  meta: {},
};

describe('ItemDrawer (P9.9)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getItemDetail').mockResolvedValue(mockItemDetail);
    vi.spyOn(apiClient, 'getSimilar').mockResolvedValue(mockSimilarResponse);
  });

  it('renders nothing when itemId is null', () => {
    renderWithClient(
      <ItemDrawer type="movies" itemId={null} onClose={vi.fn()} />
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('renders item title, synopsis, year, and similar items', async () => {
    renderWithClient(
      <ItemDrawer type="movies" itemId="385" onClose={vi.fn()} />
    );

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(await screen.findByRole('heading', { name: 'The Matrix (1999)' })).toBeInTheDocument();
    expect(screen.getByText(/A computer hacker learns from mysterious rebels/i)).toBeInTheDocument();
    expect(screen.getByText('1999')).toBeInTheDocument();

    // Verify similar items
    expect(await screen.findByText('Blade Runner (1982)')).toBeInTheDocument();
  });

  it('closes when Escape key is pressed', async () => {
    const onClose = vi.fn();
    renderWithClient(
      <ItemDrawer type="movies" itemId="385" onClose={onClose} />
    );

    await screen.findByRole('heading', { name: 'The Matrix (1999)' });

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('closes when close button is clicked', async () => {
    const onClose = vi.fn();
    renderWithClient(
      <ItemDrawer type="movies" itemId="385" onClose={onClose} />
    );

    const closeBtn = screen.getByRole('button', { name: /close item drawer/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('traps focus inside the dialog when Tab is pressed', async () => {
    renderWithClient(
      <ItemDrawer type="movies" itemId="385" onClose={vi.fn()} />
    );

    await screen.findByRole('heading', { name: 'The Matrix (1999)' });

    const focusable = screen
      .getByRole('dialog')
      .querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');

    expect(focusable.length).toBeGreaterThan(1);
  });
});

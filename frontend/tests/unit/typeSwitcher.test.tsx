import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TypeSwitcher } from '@/components/shell/TypeSwitcher';
import { apiClient } from '@/lib/api/client';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('TypeSwitcher (P9.1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders domain options correctly', async () => {
    renderWithClient(<TypeSwitcher currentType="movies" onTypeChange={vi.fn()} />);

    expect(await screen.findByRole('tab', { name: /movies/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /products/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /articles/i })).toBeInTheDocument();
  });

  it('indicates active domain selection with aria-selected', async () => {
    renderWithClient(<TypeSwitcher currentType="movies" onTypeChange={vi.fn()} />);

    const moviesTab = await screen.findByRole('tab', { name: /movies/i });
    expect(moviesTab).toHaveAttribute('aria-selected', 'true');

    const productsTab = screen.getByRole('tab', { name: /products/i });
    expect(productsTab).toHaveAttribute('aria-selected', 'false');
  });

  it('switching domain resets user to that domain first demo user without resetting tab', async () => {
    const onTypeChange = vi.fn();

    vi.spyOn(apiClient, 'getUsers').mockResolvedValueOnce({
      content_type: 'products',
      total: 2,
      users: [
        {
          user_id: 'B0001',
          persona: 'Gamer',
          interaction_count: 50,
          is_demo: true,
          top_categories: ['Games'],
        },
      ],
    });

    renderWithClient(<TypeSwitcher currentType="movies" onTypeChange={onTypeChange} />);

    const productsTab = await screen.findByRole('tab', { name: /products/i });
    await waitFor(() => expect(productsTab).not.toBeDisabled());

    fireEvent.click(productsTab);

    await waitFor(() => {
      expect(onTypeChange).toHaveBeenCalledWith('products', 'B0001');
    });
  });

  it('does nothing when clicking already active domain', async () => {
    const onTypeChange = vi.fn();
    renderWithClient(<TypeSwitcher currentType="movies" onTypeChange={onTypeChange} />);

    const moviesTab = await screen.findByRole('tab', { name: /movies/i });
    await waitFor(() => expect(moviesTab).not.toBeDisabled());
    fireEvent.click(moviesTab);

    expect(onTypeChange).not.toHaveBeenCalled();
  });
});

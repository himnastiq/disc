import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AboutTab } from '@/components/tabs/AboutTab';
import { apiClient } from '@/lib/api/client';
import type { AboutResponse } from '@/lib/api/schemas';
import aboutFixture from '../fixtures/about.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('AboutTab (P9.8)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getAbout').mockResolvedValue(aboutFixture as AboutResponse);
  });

  it('renders derivation statement, dataset citations, and architecture diagram', async () => {
    renderWithClient(<AboutTab />);

    // 1. Title and description from fixture
    expect(await screen.findByText('Discovery Engine')).toBeInTheDocument();
    expect(screen.getByText(/v1.0.0/i)).toBeInTheDocument();
    expect(screen.getByText('Real-time adaptive cross-domain recommendation system.')).toBeInTheDocument();

    // 2. Derivation statement
    expect(screen.getByText(/Recommenders Derivation Statement/i)).toBeInTheDocument();
    expect(screen.getByText(/derived from Microsoft Recommenders/i)).toBeInTheDocument();

    // 3. Architecture diagram
    expect(screen.getByRole('img', { name: /System architecture diagram/i })).toBeInTheDocument();

    // 4. Original vs Derived code table
    expect(screen.getAllByText('backend/discovery/').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('backend/engine/')).toBeInTheDocument();
    expect(screen.getByText('Derived (MIT)')).toBeInTheDocument();
    expect(screen.getAllByText('Original Work').length).toBeGreaterThanOrEqual(1);

    // 5. Citations from fixture
    expect(screen.getByText('MovieLens 1M')).toBeInTheDocument();
    expect(screen.getByText('MIND: Microsoft News Dataset')).toBeInTheDocument();

    // 6. Limitations highlights from D-018
    expect(screen.getByText(/Popularity Bias & Monoculture/i)).toBeInTheDocument();
    expect(screen.getByText(/Cold-Start Collaborative Matrix Sparsity/i)).toBeInTheDocument();
  });

  it('renders error state on API failure', async () => {
    vi.spyOn(apiClient, 'getAbout').mockRejectedValue(new Error('About API error'));

    renderWithClient(<AboutTab />);

    expect(await screen.findByText('About information unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ProfileCard, formatDateUtc } from '@/components/features/ProfileCard';
import { apiClient } from '@/lib/api/client';
import profileFixture from '../fixtures/profile_movies_1.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('ProfileCard (P9.2)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders exact interaction counts and persona from fixture', async () => {
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);

    renderWithClient(<ProfileCard type="movies" userId="1" />);

    expect(await screen.findByText('User #1')).toBeInTheDocument();
    expect(screen.getByText('Sci-Fi Fan (High Activity)')).toBeInTheDocument();

    // Verify exact numerical statistics from fixture
    expect(screen.getByText('53')).toBeInTheDocument(); // interaction_count
    expect(screen.getByText('48')).toBeInTheDocument(); // positive_count
  });

  it('renders exact first and last activity formatted in UTC', async () => {
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);

    renderWithClient(<ProfileCard type="movies" userId="1" />);

    const firstDate = formatDateUtc(profileFixture.first_activity);
    const lastDate = formatDateUtc(profileFixture.last_activity);

    const firstDateElements = await screen.findAllByText(firstDate);
    expect(firstDateElements.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(lastDate)).toBeInTheDocument();
  });

  it('renders horizontal category affinity bars matching fixture percentages', async () => {
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);

    renderWithClient(<ProfileCard type="movies" userId="1" />);

    // Drama (21, 39.6%)
    expect(await screen.findByText('Drama')).toBeInTheDocument();
    expect(screen.getByText('21 items')).toBeInTheDocument();
    expect(screen.getByText('39.6%')).toBeInTheDocument();

    // Sci-Fi (14, 26.4%)
    expect(screen.getByText('Sci-Fi')).toBeInTheDocument();
    expect(screen.getByText('14 items')).toBeInTheDocument();
    expect(screen.getByText('26.4%')).toBeInTheDocument();

    // Animation (10, 18.9%)
    expect(screen.getByText('Animation')).toBeInTheDocument();
    expect(screen.getByText('10 items')).toBeInTheDocument();
    expect(screen.getByText('18.9%')).toBeInTheDocument();

    // Verify progressbar accessibility attributes
    const progressbars = screen.getAllByRole('progressbar');
    expect(progressbars.length).toBe(3);
    expect(progressbars[0]).toHaveAttribute('aria-valuenow', '40'); // 39.6 rounded
  });

  it('renders recent activity list with titles and star ratings', async () => {
    vi.spyOn(apiClient, 'getUserProfile').mockResolvedValue(profileFixture);

    renderWithClient(<ProfileCard type="movies" userId="1" />);

    expect(
      await screen.findByText("One Flew Over the Cuckoo's Nest (1975)")
    ).toBeInTheDocument();
    expect(
      screen.getByText('James and the Giant Peach (1996)')
    ).toBeInTheDocument();

    // Check rating signals
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders error state on API failure with retry button', async () => {
    vi.spyOn(apiClient, 'getUserProfile').mockRejectedValue(new Error('Network error'));

    renderWithClient(<ProfileCard type="movies" userId="999" />);

    expect(await screen.findByText('Could not load profile')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

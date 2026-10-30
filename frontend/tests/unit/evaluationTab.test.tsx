import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvaluationTab, formatMetric } from '@/components/tabs/EvaluationTab';
import { apiClient } from '@/lib/api/client';
import type { MetricsResponse } from '@/lib/api/schemas';
import moviesMetricsFixture from '../fixtures/metrics_movies.json';
import articlesMetricsFixture from '../fixtures/metrics_articles.json';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe('EvaluationTab (P9.7)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getMetrics').mockResolvedValue(moviesMetricsFixture as unknown as MetricsResponse);
  });

  it('renders exact metrics matching metrics.json fixture with 4-decimal precision', async () => {
    renderWithClient(<EvaluationTab type="movies" />);

    // 1. Assert Protocol info from fixture
    expect(await screen.findByText(/1918 users/i)).toBeInTheDocument();
    expect(screen.getByText(/Chronological \(80% train\)/i)).toBeInTheDocument();

    // 2. Assert SAR model numbers @ k=10 from fixture
    // From metrics_movies.json: sar @ 10:
    // precision: 0.04135 -> 0.0414 [0.0381, 0.0447]
    // recall: 0.06451 -> 0.0645 [0.0577, 0.0716]
    // ndcg: 0.05922 -> 0.0592 [0.0541, 0.0644]
    const sar10 = moviesMetricsFixture.models.sar['10'];
    const expectedPrecision = formatMetric(sar10.precision, 4);
    const expectedRecall = formatMetric(sar10.recall, 4);
    const expectedNdcg = formatMetric(sar10.ndcg, 4);

    expect(screen.getByText(expectedPrecision)).toBeInTheDocument();
    expect(screen.getByText(expectedRecall)).toBeInTheDocument();
    expect(screen.getAllByText(expectedNdcg).length).toBeGreaterThanOrEqual(1);

    // 3. Assert Popularity numbers @ k=10 from fixture
    const pop10 = moviesMetricsFixture.models.popularity['10'];
    expect(screen.getAllByText(formatMetric(pop10.recall, 4)).length).toBeGreaterThanOrEqual(1);
  });

  it('updates metrics table when switching k selector', async () => {
    renderWithClient(<EvaluationTab type="movies" />);

    // Switch k to 5
    const k5Button = await screen.findByRole('button', { name: '5' });
    fireEvent.click(k5Button);

    // SAR @ 5: precision = 0.04588 -> 0.0459
    const sar5 = moviesMetricsFixture.models.sar['5'];
    expect(screen.getByText(formatMetric(sar5.precision, 4))).toBeInTheDocument();
  });

  it('renders dual protocol section for articles with impression metrics', async () => {
    vi.spyOn(apiClient, 'getMetrics').mockResolvedValue(articlesMetricsFixture as unknown as MetricsResponse);

    renderWithClient(<EvaluationTab type="articles" />);

    expect(
      await screen.findByText(/Protocol \(a\): Impression Candidate Ranking \(MIND Benchmark\)/i)
    ).toBeInTheDocument();

    // In articles metrics fixture, tfidf_profile impression AUC is 0.5714
    expect(screen.getByText('0.5714')).toBeInTheDocument();
    expect(screen.getByText('[0.5480, 0.5960]')).toBeInTheDocument();
  });

  it('renders beyond-accuracy cards with coverage and novelty', async () => {
    renderWithClient(<EvaluationTab type="movies" />);

    expect(await screen.findByText('Catalog Coverage')).toBeInTheDocument();
    expect(screen.getByText('Novelty')).toBeInTheDocument();
    expect(screen.getByText('Diversity')).toBeInTheDocument();
    expect(screen.getByText('Personalisation')).toBeInTheDocument();

    // SAR @ 10 novelty: 9.12 bits
    expect(screen.getByText('9.12 bits')).toBeInTheDocument();
  });

  it('renders error state on API failure', async () => {
    vi.spyOn(apiClient, 'getMetrics').mockRejectedValue(new Error('Network error'));

    renderWithClient(<EvaluationTab type="movies" />);

    expect(await screen.findByText('Evaluation metrics unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });
});

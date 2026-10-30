import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { RecCard } from '@/components/features/RecCard';
import { ReasonBadge } from '@/components/features/ReasonBadge';
import { ModeBadge } from '@/components/features/ModeBadge';
import type { ScoredItem } from '@/lib/api/schemas';

const mockMovieItem: ScoredItem = {
  item_id: '385',
  title: 'The Matrix (1999)',
  subtitle: 'Warner Bros.',
  categories: ['Action', 'Sci-Fi'],
  year: 1999,
  image_url: null,
  score: 0.567,
  display_score: 0.95,
  reason: {
    kind: 'history_item',
    item_id: '1193',
    text: 'Because you watched One Flew Over the Cuckoo Nest',
    similarity_score: 0.85,
  },
  meta: {},
};

const mockProductItem: ScoredItem = {
  item_id: 'B0001',
  title: 'Logitech G502 Gaming Mouse',
  subtitle: 'Logitech',
  categories: ['Hardware', 'Accessories'],
  year: null,
  image_url: null,
  score: 0.72,
  display_score: 0.88,
  reason: {
    kind: 'history_item',
    text: 'Because you purchased Gaming Keyboards',
  },
  meta: {},
};

const mockArticleItem: ScoredItem = {
  item_id: 'N1002',
  title: 'Breakthrough in Solid State Battery Technology',
  subtitle: 'Researchers develop high-capacity solid state electrolytes that double battery longevity.',
  categories: ['Technology', 'Science'],
  year: null,
  image_url: null,
  score: 0.45,
  display_score: 0.78,
  reason: {
    kind: 'popular',
    text: 'Trending in Technology',
  },
  meta: {},
};

describe('RecCard & Badges (P9.3)', () => {
  it('renders movie variant with title, year, category chips, and reason', () => {
    render(<RecCard item={mockMovieItem} cardType="movie" />);

    expect(screen.getByRole('heading', { name: 'The Matrix (1999)' })).toBeInTheDocument();
    expect(screen.getByText('1999')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText(/Because you watched/i)).toBeInTheDocument();
  });

  it('renders product variant with brand and category chips', () => {
    render(<RecCard item={mockProductItem} cardType="product" />);

    expect(screen.getByRole('heading', { name: 'Logitech G502 Gaming Mouse' })).toBeInTheDocument();
    expect(screen.getByText('Logitech')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByText(/Because you purchased/i)).toBeInTheDocument();
  });

  it('renders article variant with headline, abstract snippet, and category', () => {
    render(<RecCard item={mockArticleItem} cardType="article" />);

    expect(screen.getByRole('heading', { name: 'Breakthrough in Solid State Battery Technology' })).toBeInTheDocument();
    expect(screen.getByText(/Researchers develop high-capacity solid state/i)).toBeInTheDocument();
    expect(screen.getAllByText('Technology').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('78%')).toBeInTheDocument();
  });

  it('triggers onSelect when clicked or activated with Enter key', () => {
    const onSelect = vi.fn();
    render(<RecCard item={mockMovieItem} cardType="movie" onSelect={onSelect} />);

    const card = screen.getByRole('button', { name: /view details for the matrix/i });
    fireEvent.click(card);
    expect(onSelect).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(card, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledTimes(2);
  });

  it('renders ReasonBadge correctly for history and popular kinds', () => {
    const { rerender } = render(
      <ReasonBadge reason={{ kind: 'history_item', text: 'Because you liked Alien' }} />
    );
    expect(screen.getByText('Because you liked Alien')).toBeInTheDocument();

    rerender(<ReasonBadge reason={{ kind: 'popular', text: 'Popular in catalog' }} />);
    expect(screen.getByText('Popular in catalog')).toBeInTheDocument();

    rerender(<ReasonBadge reason={null} />);
    expect(screen.queryByText('Popular in catalog')).not.toBeInTheDocument();
  });

  it('renders ModeBadge for personalized and popularity fallback modes', () => {
    const { rerender } = render(<ModeBadge mode="personalized" />);
    expect(screen.getByText(/Personalized/i)).toBeInTheDocument();

    rerender(<ModeBadge mode="popularity" />);
    expect(screen.getByText(/Popularity Fallback/i)).toBeInTheDocument();
  });
});

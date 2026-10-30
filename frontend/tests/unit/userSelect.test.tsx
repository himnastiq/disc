import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UserSelect } from '@/components/shell/UserSelect';
import { apiClient } from '@/lib/api/client';

function renderWithClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

const mockUsers = {
  content_type: 'movies',
  total: 3,
  users: [
    {
      user_id: '1',
      persona: 'Sci-Fi Fan (Heavy)',
      interaction_count: 214,
      is_demo: true,
      top_categories: ['Sci-Fi', 'Action'],
    },
    {
      user_id: '2',
      persona: 'Classic Drama (Mainstream)',
      interaction_count: 85,
      is_demo: true,
      top_categories: ['Drama', 'Romance'],
    },
    {
      user_id: '105',
      persona: null,
      interaction_count: 12,
      is_demo: false,
      top_categories: ['Comedy'],
    },
  ],
};

describe('UserSelect (P9.1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, 'getUsers').mockResolvedValue(mockUsers);
  });

  it('renders trigger button with current user and persona', async () => {
    renderWithClient(
      <UserSelect currentType="movies" currentUser="1" onUserChange={vi.fn()} />
    );

    const trigger = screen.getByRole('button', { name: /select user persona/i });
    expect(trigger).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText('User #1')).toBeInTheDocument();
      expect(screen.getByText(/Sci-Fi Fan/i)).toBeInTheDocument();
    });
  });

  it('opens dropdown and shows searchable user list with demo badges', async () => {
    renderWithClient(
      <UserSelect currentType="movies" currentUser="1" onUserChange={vi.fn()} />
    );

    const trigger = screen.getByRole('button', { name: /select user persona/i });
    await waitFor(() => expect(trigger).not.toBeDisabled());
    fireEvent.click(trigger);

    expect(screen.getByPlaceholderText(/search user id or persona/i)).toBeInTheDocument();
    expect(screen.getByText(/demo personas/i)).toBeInTheDocument();
    expect(screen.getByText('User #2')).toBeInTheDocument();
    expect(screen.getByText(/Classic Drama/i)).toBeInTheDocument();
  });

  it('filters users by search query', async () => {
    renderWithClient(
      <UserSelect currentType="movies" currentUser="1" onUserChange={vi.fn()} />
    );

    const trigger = screen.getByRole('button', { name: /select user persona/i });
    await waitFor(() => expect(trigger).not.toBeDisabled());
    fireEvent.click(trigger);

    const searchInput = screen.getByPlaceholderText(/search user id or persona/i);
    fireEvent.change(searchInput, { target: { value: 'Drama' } });

    const listbox = screen.getByRole('listbox');
    expect(within(listbox).queryByText(/Sci-Fi Fan/i)).not.toBeInTheDocument();
    expect(within(listbox).getByText(/Classic Drama/i)).toBeInTheDocument();
  });

  it('calls onUserChange when clicking a user option', async () => {
    const onUserChange = vi.fn();
    renderWithClient(
      <UserSelect currentType="movies" currentUser="1" onUserChange={onUserChange} />
    );

    const trigger = screen.getByRole('button', { name: /select user persona/i });
    await waitFor(() => expect(trigger).not.toBeDisabled());
    fireEvent.click(trigger);

    const user2 = screen.getByText('User #2');
    fireEvent.click(user2);

    expect(onUserChange).toHaveBeenCalledWith('2');
    expect(screen.queryByPlaceholderText(/search user id or persona/i)).not.toBeInTheDocument();
  });

  it('supports keyboard navigation and Escape to close', async () => {
    renderWithClient(
      <UserSelect currentType="movies" currentUser="1" onUserChange={vi.fn()} />
    );

    const trigger = screen.getByRole('button', { name: /select user persona/i });
    await waitFor(() => expect(trigger).not.toBeDisabled());
    fireEvent.click(trigger);

    expect(screen.getByPlaceholderText(/search user id or persona/i)).toBeInTheDocument();

    fireEvent.keyDown(trigger, { key: 'Escape' });
    expect(screen.queryByPlaceholderText(/search user id or persona/i)).not.toBeInTheDocument();
  });
});

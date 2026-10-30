'use client';

import React from 'react';
import { Film, ShoppingBag, Newspaper } from 'lucide-react';
import { useTypes } from '@/lib/api/hooks';
import { apiClient } from '@/lib/api/client';
import type { ContentTypeKey } from '@/lib/hooks/useUrlState';

export interface TypeSwitcherProps {
  currentType: ContentTypeKey;
  onTypeChange: (type: ContentTypeKey, defaultUserId?: string) => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  movies: <Film className="h-3.5 w-3.5 mr-1.5 shrink-0" />,
  products: <ShoppingBag className="h-3.5 w-3.5 mr-1.5 shrink-0" />,
  articles: <Newspaper className="h-3.5 w-3.5 mr-1.5 shrink-0" />,
};

export function TypeSwitcher({ currentType, onTypeChange }: TypeSwitcherProps) {
  const { data: typesResponse, isLoading } = useTypes();
  const types = typesResponse?.types || [
    { id: 'movies', display_name: 'Movies' },
    { id: 'products', display_name: 'Products' },
    { id: 'articles', display_name: 'Articles' },
  ];

  const handleSelect = async (typeId: string) => {
    if (typeId === currentType) return;

    try {
      // Fetch users for target type to identify first demo user
      const usersData = await apiClient.getUsers(typeId);
      const firstDemo = usersData.users.find((u) => u.is_demo) || usersData.users[0];
      const targetUserId = firstDemo ? firstDemo.user_id : '1';
      onTypeChange(typeId as ContentTypeKey, targetUserId);
    } catch {
      // Fallback if users request fails
      onTypeChange(typeId as ContentTypeKey, '1');
    }
  };

  return (
    <div
      role="tablist"
      aria-label="Content domain switcher"
      className="inline-flex items-center rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5"
    >
      {types.map((t) => {
        const isActive = currentType === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={isActive}
            disabled={isLoading}
            onClick={() => handleSelect(t.id)}
            className={`inline-flex items-center px-2.5 sm:px-3 py-1 text-xs font-medium rounded-[4px] transition-all cursor-pointer ${
              isActive
                ? 'bg-[var(--color-elevated)] text-[var(--color-text)] font-semibold border-b-2 border-[var(--color-accent)]'
                : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:bg-[var(--color-elevated)]/60'
            }`}
          >
            {typeIcons[t.id] || <Film className="h-3.5 w-3.5 mr-1.5" />}
            <span className="capitalize">{t.display_name}</span>
          </button>
        );
      })}
    </div>
  );
}

'use client';

import React from 'react';
import { Film, ShoppingBag, Newspaper, User, Sparkles } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { ThemeToggle } from '@/components/ui/ThemeToggle';
import type { ContentTypeKey } from '@/lib/hooks/useUrlState';

export interface AppHeaderProps {
  currentType: ContentTypeKey;
  onTypeChange: (type: ContentTypeKey) => void;
  currentUser: string;
  onUserChange: (user: string) => void;
}

export function AppHeader({
  currentType,
  onTypeChange,
  currentUser,
  onUserChange,
}: AppHeaderProps) {
  const typeIcons = {
    movies: <Film className="h-4 w-4 mr-1.5" />,
    products: <ShoppingBag className="h-4 w-4 mr-1.5" />,
    articles: <Newspaper className="h-4 w-4 mr-1.5" />,
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-zinc-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/60 dark:border-zinc-800 dark:bg-zinc-950/95 dark:supports-[backdrop-filter]:bg-zinc-950/60">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 flex items-center justify-center font-bold text-sm">
              <Sparkles className="h-4 w-4" />
            </div>
            <span className="font-bold text-base sm:text-lg tracking-tight">Discovery Engine</span>
          </div>
          <Badge variant="secondary" className="hidden sm:inline-flex text-[10px] py-0 px-1.5">
            v1.0
          </Badge>
        </div>

        {/* Center / Controls: TypeSwitcher & UserSelect placeholders */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Domain Type Switcher */}
          <div className="flex items-center rounded-lg border border-zinc-200 bg-zinc-100/80 p-0.5 dark:border-zinc-800 dark:bg-zinc-900">
            {(['movies', 'products', 'articles'] as ContentTypeKey[]).map((t) => {
              const isActive = currentType === t;
              return (
                <button
                  key={t}
                  onClick={() => onTypeChange(t)}
                  className={`inline-flex items-center px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                    isActive
                      ? 'bg-white text-zinc-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-50'
                      : 'text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100'
                  }`}
                  aria-label={`Switch domain to ${t}`}
                >
                  {typeIcons[t]}
                  <span className="capitalize hidden xs:inline">{t}</span>
                </button>
              );
            })}
          </div>

          {/* User Select Placeholder */}
          <div className="relative">
            <select
              value={currentUser}
              onChange={(e) => onUserChange(e.target.value)}
              className="h-8 rounded-md border border-zinc-200 bg-white pl-7 pr-3 text-xs font-medium text-zinc-900 shadow-sm focus:outline-none focus:ring-1 focus:ring-zinc-950 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100"
              aria-label="Select user persona"
            >
              <option value="1">User #1 (Sci-Fi / Active)</option>
              <option value="2">User #2 (Drama / Balanced)</option>
              <option value="3">User #3 (Casual / Action)</option>
            </select>
            <User className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-zinc-400" />
          </div>

          {/* Theme Toggle */}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}


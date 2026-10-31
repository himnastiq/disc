'use client';

import React from 'react';
import { Sparkles } from 'lucide-react';
import { TypeSwitcher } from './TypeSwitcher';
import { UserSelect } from './UserSelect';
import type { ContentTypeKey } from '@/lib/hooks/useUrlState';

export interface AppHeaderProps {
  currentType: ContentTypeKey;
  onTypeChange: (type: ContentTypeKey, defaultUserId?: string) => void;
  currentUser: string;
  onUserChange: (user: string) => void;
}

export function AppHeader({
  currentType,
  onTypeChange,
  currentUser,
  onUserChange,
}: AppHeaderProps) {
  return (
    <header className="sm:sticky sm:top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-shell mx-auto px-4 sm:px-6 min-h-16 py-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        {/* Product Brand (Left) */}
        <div className="flex items-center gap-2.5 sm:flex-1 sm:justify-start">
          <div className="h-7 w-7 rounded-[4px] bg-[var(--color-accent)] text-white flex items-center justify-center font-bold text-xs shadow-sm shrink-0">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="font-bold text-sm sm:text-base tracking-tight text-[var(--color-text)] whitespace-nowrap">
            Discovery Engine
          </span>
        </div>

        {/* Content Type Switcher: Movies, Products, Articles (Center) */}
        <div className="order-last sm:order-none w-full sm:w-auto flex items-center justify-center shrink-0">
          <TypeSwitcher currentType={currentType} onTypeChange={onTypeChange} />
        </div>

        {/* User Selection Controls (Right) */}
        <div className="flex items-center gap-2 sm:gap-3 sm:flex-1 sm:justify-end">
          <UserSelect
            currentType={currentType}
            currentUser={currentUser}
            onUserChange={onUserChange}
          />
        </div>
      </div>
    </header>
  );
}

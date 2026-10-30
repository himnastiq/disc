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
    <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-[52rem] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
        {/* Product Brand */}
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-[4px] bg-[var(--color-accent)] text-white flex items-center justify-center font-bold text-xs shadow-sm">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="font-bold text-sm sm:text-base tracking-tight text-[var(--color-text)]">
            Discovery Engine
          </span>
        </div>

        {/* Controls: TypeSwitcher & UserSelect */}
        <div className="flex items-center gap-2 sm:gap-3">
          <TypeSwitcher currentType={currentType} onTypeChange={onTypeChange} />
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

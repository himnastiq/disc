'use client';

import React from 'react';
import { Sparkles, GitCompare, Zap, BarChart3, Info } from 'lucide-react';
import type { TabKey } from '@/lib/hooks/useUrlState';

export interface TabNavigationProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabs: { id: TabKey; label: string; icon: React.ReactNode }[] = [
    { id: 'for-you', label: 'For You', icon: <Sparkles className="h-4 w-4" /> },
    { id: 'compare', label: 'Compare', icon: <GitCompare className="h-4 w-4" /> },
    { id: 'cold-start', label: 'Cold Start', icon: <Zap className="h-4 w-4" /> },
    { id: 'evaluation', label: 'Evaluation', icon: <BarChart3 className="h-4 w-4" /> },
    { id: 'about', label: 'About', icon: <Info className="h-4 w-4" /> },
  ];

  return (
    <nav
      aria-label="Main Navigation Tabs"
      className="w-full border-b border-[var(--color-border)] bg-[var(--color-bg)]"
    >
      <div className="max-w-[52rem] mx-auto px-4 sm:px-6">
        <div
          role="tablist"
          className="-mb-px flex space-x-2 sm:space-x-6 overflow-x-auto no-scrollbar"
        >
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                aria-current={isActive ? 'page' : undefined}
                onClick={() => onTabChange(tab.id)}
                className={`relative flex items-center gap-1.5 sm:gap-2 whitespace-nowrap py-3.5 px-2 text-xs font-medium min-h-[48px] transition-all cursor-pointer ${
                  isActive
                    ? 'text-[var(--color-accent-text)] font-semibold'
                    : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)]'
                }`}
              >
                {/* 2px accent indicator line on active tab */}
                {isActive && (
                  <span
                    aria-hidden="true"
                    className="absolute top-0 left-0 right-0 h-[2px] bg-[var(--color-accent)]"
                  />
                )}
                <span className={isActive ? 'text-[var(--color-accent)]' : 'text-[var(--color-text-muted)]'}>
                  {tab.icon}
                </span>
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </nav>
  );
}

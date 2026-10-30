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
    <div className="w-full border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <nav
          className="-mb-px flex space-x-6 sm:space-x-8 overflow-x-auto no-scrollbar"
          aria-label="Tabs"
        >
          {tabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => onTabChange(tab.id)}
                className={`flex items-center gap-2 whitespace-nowrap border-b-2 py-3 px-1 text-xs sm:text-sm font-medium transition-all ${
                  isActive
                    ? 'border-zinc-900 text-zinc-900 dark:border-zinc-50 dark:text-zinc-50 font-semibold'
                    : 'border-transparent text-zinc-500 hover:border-zinc-300 hover:text-zinc-700 dark:text-zinc-400 dark:hover:border-zinc-700 dark:hover:text-zinc-300'
                }`}
                aria-current={isActive ? 'page' : undefined}
              >
                {tab.icon}
                {tab.label}
              </button>
            );
          })}
        </nav>
      </div>
    </div>
  );
}


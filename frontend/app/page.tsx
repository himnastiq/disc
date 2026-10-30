'use client';

import React, { Suspense } from 'react';
import { AppHeader } from '@/components/shell/AppHeader';
import { TabNavigation } from '@/components/shell/TabNavigation';
import { AppFooter } from '@/components/shell/AppFooter';
import { useUrlState } from '@/lib/hooks/useUrlState';
import { ForYouTab } from '@/components/tabs/ForYouTab';
import { CompareTab } from '@/components/tabs/CompareTab';
import { ColdStartTab } from '@/components/tabs/ColdStartTab';
import { EvaluationTab } from '@/components/tabs/EvaluationTab';
import { AboutTab } from '@/components/tabs/AboutTab';
import { ItemDrawer } from '@/components/features/ItemDrawer';
import { Skeleton } from '@/components/ui/Skeleton';

function DashboardContent() {
  const {
    type,
    tab,
    user,
    k,
    item,
    setTab,
    setUser,
    setK,
    setItem,
    switchType,
  } = useUrlState();

  return (
    <div className="flex-1 flex flex-col bg-[var(--color-bg)] text-[var(--color-text)] min-h-screen">
      <AppHeader
        currentType={type}
        onTypeChange={(newType, defaultUser) => switchType(newType, defaultUser)}
        currentUser={user}
        onUserChange={setUser}
      />
      <TabNavigation activeTab={tab} onTabChange={setTab} />

      <main className="flex-1 max-w-[52rem] w-full mx-auto px-4 sm:px-6 py-6">
        {/* Tab 1: For You */}
        {tab === 'for-you' && (
          <ForYouTab
            type={type}
            user={user}
            k={k}
            onKChange={setK}
            onSelectItem={(selected) => setItem(selected.item_id)}
          />
        )}

        {/* Tab 2: Compare */}
        {tab === 'compare' && (
          <CompareTab
            type={type}
            user={user}
            k={k}
            onKChange={setK}
            onSelectItem={(selected) => setItem(selected.item_id)}
          />
        )}

        {/* Tab 3: Cold Start */}
        {tab === 'cold-start' && (
          <ColdStartTab
            type={type}
            k={k}
            onKChange={setK}
            onSelectItem={(selected) => setItem(selected.item_id)}
          />
        )}

        {/* Tab 4: Evaluation */}
        {tab === 'evaluation' && (
          <EvaluationTab type={type} />
        )}

        {/* Tab 5: About */}
        {tab === 'about' && (
          <AboutTab />
        )}
      </main>

      {/* Item Details Drawer (accessible deep-linked dialog) */}
      <ItemDrawer
        type={type}
        itemId={item}
        onClose={() => setItem(null)}
        onSelectItem={(selected) => setItem(selected.item_id)}
      />

      <AppFooter />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex flex-col bg-[var(--color-bg)] text-[var(--color-text)] p-6 space-y-6 max-w-[52rem] mx-auto">
          <Skeleton className="h-16 w-full rounded-[var(--radius-card)] bg-[var(--color-surface)]" />
          <Skeleton className="h-12 w-full rounded-[var(--radius-card)] bg-[var(--color-surface)]" />
          <Skeleton className="h-96 w-full rounded-[var(--radius-card)] bg-[var(--color-surface)]" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}

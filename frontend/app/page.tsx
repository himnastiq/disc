'use client';

import React, { Suspense } from 'react';
import { AlertCircle, Sparkles } from 'lucide-react';
import { AppHeader } from '@/components/shell/AppHeader';
import { TabNavigation } from '@/components/shell/TabNavigation';
import { AppFooter } from '@/components/shell/AppFooter';
import { useUrlState } from '@/lib/hooks/useUrlState';
import { useTypes } from '@/lib/api/hooks';
import { ForYouTab } from '@/components/tabs/ForYouTab';
import { CompareTab } from '@/components/tabs/CompareTab';
import { ColdStartTab } from '@/components/tabs/ColdStartTab';
import { EvaluationTab } from '@/components/tabs/EvaluationTab';
import { ItemDrawer } from '@/components/features/ItemDrawer';
import { Skeleton } from '@/components/ui/Skeleton';
import { Button } from '@/components/ui/Button';

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

  const { isError: isTypesError, refetch: refetchTypes } = useTypes();

  if (isTypesError) {
    return (
      <div className="flex-1 flex flex-col bg-[var(--color-bg)] text-[var(--color-text)] min-h-screen">
        <header className="sticky top-0 z-40 w-full border-b border-[var(--color-border)] bg-[var(--color-bg)]">
          <div className="max-w-[52rem] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="h-7 w-7 rounded-[4px] bg-[var(--color-accent)] text-white flex items-center justify-center font-bold text-xs shadow-sm">
                <Sparkles className="h-4 w-4" />
              </div>
              <span className="font-bold text-sm sm:text-base tracking-tight text-[var(--color-text)]">
                Discovery Engine
              </span>
            </div>
          </div>
        </header>
        <main className="flex-1 max-w-[52rem] w-full mx-auto px-4 sm:px-6 py-12 flex items-center justify-center">
          <div
            role="alert"
            className="rounded-[var(--radius-card)] border border-red-500/30 bg-red-950/20 p-8 max-w-lg w-full text-center space-y-4"
          >
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-500/10 text-red-400">
              <AlertCircle className="h-6 w-6" />
            </div>
            <div className="space-y-2">
              <h2 className="text-lg font-bold text-[var(--color-text)]">
                Recommender Service Unavailable
              </h2>
              <p className="text-sm text-[var(--color-text-secondary)]">
                Could not connect to the Discovery Engine backend API. Please ensure the backend server is running.
              </p>
            </div>
            <Button
              onClick={() => refetchTypes()}
              className="w-full sm:w-auto"
            >
              Try again
            </Button>
          </div>
        </main>
        <AppFooter />
      </div>
    );
  }

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

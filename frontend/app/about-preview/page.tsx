'use client';

import React, { Suspense } from 'react';
import { AppHeader } from '@/components/shell/AppHeader';
import { AboutTab } from '@/components/tabs/AboutTab';
import { useUrlState } from '@/lib/hooks/useUrlState';
import { Skeleton } from '@/components/ui/Skeleton';

function AboutPreviewContent() {
  const { type, user, setUser, switchType } = useUrlState();

  return (
    <div className="flex-1 flex flex-col bg-[var(--color-bg)] text-[var(--color-text)] min-h-screen">
      <AppHeader
        currentType={type}
        onTypeChange={(newType, defaultUser) => switchType(newType, defaultUser)}
        currentUser={user}
        onUserChange={setUser}
      />
      <main className="flex-1 max-w-shell w-full mx-auto px-4 sm:px-6 py-8 lg:py-10">
        <AboutTab />
      </main>
    </div>
  );
}

export default function AboutPreviewPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex flex-col bg-[var(--color-bg)] text-[var(--color-text)] p-6 space-y-6 max-w-shell mx-auto">
          <Skeleton className="h-16 w-full rounded-[var(--radius-card)] bg-[var(--color-surface)]" />
          <Skeleton className="h-96 w-full rounded-[var(--radius-card)] bg-[var(--color-surface)]" />
        </div>
      }
    >
      <AboutPreviewContent />
    </Suspense>
  );
}

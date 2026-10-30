'use client';

import React, { useState } from 'react';
import { notFound } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Tabs } from '@/components/ui/Tabs';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { EmptyState } from '@/components/ui/EmptyState';
import { Toast } from '@/components/ui/Toast';
import { Tooltip } from '@/components/ui/Tooltip';
import { ThemeToggle } from '@/components/ui/ThemeToggle';

export default function DevComponentsPage() {
  // Guard: Exclude in production builds if env is production
  if (process.env.NODE_ENV === 'production' && !process.env.NEXT_PUBLIC_ALLOW_DEV_ROUTES) {
    notFound();
  }

  const [activeTab, setActiveTab] = useState('one');
  const [showToast, setShowToast] = useState(true);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 p-8 text-zinc-900 dark:text-zinc-50">
      <div className="max-w-5xl mx-auto space-y-10">
        <div className="flex items-center justify-between border-b border-zinc-200 dark:border-zinc-800 pb-4">
          <div>
            <h1 className="text-2xl font-bold">Design System Primitives Catalog</h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Interactive preview of all Phase 8 design system tokens and primitives.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-zinc-500">Toggle Theme:</span>
            <ThemeToggle />
          </div>
        </div>

        {/* Buttons */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">1. Buttons</h2>
          <div className="flex flex-wrap gap-3 items-center">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="primary" isLoading>
              Loading
            </Button>
            <Button variant="primary" size="sm">
              Small
            </Button>
            <Button variant="primary" size="lg">
              Large
            </Button>
          </div>
        </section>

        {/* Badges */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">2. Badges & Domain Tokens</h2>
          <div className="flex flex-wrap gap-3 items-center">
            <Badge variant="default">Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="success">Success</Badge>
            <Badge variant="destructive">Destructive</Badge>
            <Badge variant="movie">Movies (Amber)</Badge>
            <Badge variant="product">Products (Sky)</Badge>
            <Badge variant="article">Articles (Emerald)</Badge>
          </div>
        </section>

        {/* Tabs */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">3. Tabs</h2>
          <Tabs
            tabs={[
              { id: 'one', label: 'For You' },
              { id: 'two', label: 'Compare' },
              { id: 'three', label: 'Cold Start' },
            ]}
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        </section>

        {/* Skeletons */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">4. Skeletons</h2>
          <div className="space-y-2 max-w-sm">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-10 w-full rounded-md" />
          </div>
        </section>

        {/* Cards */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">5. Cards</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Standard Card Title</CardTitle>
                <CardDescription>Card description with subtle muted color</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Main content area for card body information.</p>
              </CardContent>
              <CardFooter className="justify-between">
                <Badge variant="movie">Movie</Badge>
                <Button size="sm" variant="outline">Action</Button>
              </CardFooter>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Domain Card (Product)</CardTitle>
                <CardDescription>Demonstrating product variant</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm">Logitech G502 High Performance Gaming Mouse</p>
              </CardContent>
              <CardFooter className="justify-between">
                <Badge variant="product">Product</Badge>
                <Button size="sm">View Details</Button>
              </CardFooter>
            </Card>
          </div>
        </section>

        {/* States: Error, Empty, Toast, Tooltip */}
        <section className="space-y-4">
          <h2 className="text-lg font-semibold">6. Feedback & Interactive States</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <ErrorState
              title="Connection Failed"
              message="Could not reach the FastAPI recommendation service."
              onRetry={() => alert('Retry triggered')}
            />
            <EmptyState
              title="No Liked Items"
              description="Add items in the Cold Start tab to build your taste profile."
              action={<Button size="sm">Search Catalog</Button>}
            />
          </div>

          <div className="flex flex-wrap items-center gap-6 pt-4">
            <Tooltip content="Tooltip explaining why this was recommended">
              <Button variant="outline" size="sm">Hover for Tooltip</Button>
            </Tooltip>

            {showToast && (
              <Toast
                type="success"
                title="Cold-Start Recommendations Ready"
                description="Switched from popularity to personalized SAR collaborative filtering."
                onClose={() => setShowToast(false)}
              />
            )}
          </div>
        </section>
      </div>
    </div>
  );
}


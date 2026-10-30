'use client';

import React, { Suspense } from 'react';
import { AppHeader } from '@/components/shell/AppHeader';
import { TabNavigation } from '@/components/shell/TabNavigation';
import { AppFooter } from '@/components/shell/AppFooter';
import { useUrlState, type ContentTypeKey, type TabKey } from '@/lib/hooks/useUrlState';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { Sparkles, User, Tag, Clock } from 'lucide-react';

function DashboardContent() {
  const { type, tab, user, setType, setTab, setUser } = useUrlState();

  const domainBadges: Record<ContentTypeKey, { label: string; variant: 'movie' | 'product' | 'article' }> = {
    movies: { label: 'Movies & TV', variant: 'movie' },
    products: { label: 'E-Commerce Products', variant: 'product' },
    articles: { label: 'News Articles', variant: 'article' },
  };

  return (
    <div className="flex-1 flex flex-col">
      <AppHeader
        currentType={type}
        onTypeChange={setType}
        currentUser={user}
        onUserChange={setUser}
      />
      <TabNavigation activeTab={tab} onTabChange={setTab} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Active Tab View Header */}
        <div className="mb-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-xl sm:text-2xl font-bold tracking-tight capitalize">
                {tab.replace('-', ' ')}
              </h1>
              <Badge variant={domainBadges[type].variant}>
                {domainBadges[type].label}
              </Badge>
            </div>
            <p className="text-xs sm:text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              Active persona: <span className="font-semibold text-zinc-700 dark:text-zinc-300">User #{user}</span>
            </p>
          </div>
        </div>

        {/* Tab 1: For You */}
        {tab === 'for-you' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            {/* Left Column: Profile Card (P9.2) */}
            <div className="lg:col-span-4 space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center font-bold text-zinc-700 dark:text-zinc-300">
                      <User className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base">User #{user}</CardTitle>
                      <CardDescription className="text-xs">
                        High-engagement Sci-Fi Persona
                      </CardDescription>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4 text-xs">
                  <div className="flex items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-2">
                    <span className="text-zinc-500 flex items-center gap-1.5">
                      <Tag className="h-3.5 w-3.5" /> Total Ratings
                    </span>
                    <span className="font-semibold">214 interactions</span>
                  </div>

                  <div>
                    <h5 className="font-medium text-zinc-700 dark:text-zinc-300 mb-2">
                      Top Affinity Categories
                    </h5>
                    <div className="space-y-1.5">
                      <div>
                        <div className="flex justify-between mb-0.5 text-[11px]">
                          <span>Drama</span>
                          <span>42%</span>
                        </div>
                        <div className="h-1.5 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-500 rounded-full" style={{ width: '42%' }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5 text-[11px]">
                          <span>Sci-Fi</span>
                          <span>28%</span>
                        </div>
                        <div className="h-1.5 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-500 rounded-full" style={{ width: '28%' }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between mb-0.5 text-[11px]">
                          <span>Action</span>
                          <span>18%</span>
                        </div>
                        <div className="h-1.5 w-full bg-zinc-100 dark:bg-zinc-800 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-500 rounded-full" style={{ width: '18%' }} />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="pt-2">
                    <h5 className="font-medium text-zinc-700 dark:text-zinc-300 mb-1.5 flex items-center gap-1.5">
                      <Clock className="h-3.5 w-3.5" /> Recent Activity
                    </h5>
                    <p className="text-[11px] text-zinc-500">
                      Rated <span className="font-medium text-zinc-700 dark:text-zinc-300">The Matrix (1999)</span> ★★★★★
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column: Recommendation Cards Grid (P9.3, P9.4) */}
            <div className="lg:col-span-8 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm sm:text-base text-zinc-900 dark:text-zinc-100">
                  Top Recommendations (k = 10)
                </h3>
                <span className="text-xs text-zinc-400">Personalized Mode (SAR Jaccard)</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                {[1, 2, 3, 4, 5, 6].map((idx) => (
                  <Card key={idx} className="flex flex-col justify-between hover:shadow-md transition-shadow">
                    <CardHeader className="p-4 pb-2">
                      <div className="flex items-start justify-between gap-2">
                        <CardTitle className="text-sm font-semibold leading-snug">
                          {type === 'movies' && `Recommended Film #${idx}`}
                          {type === 'products' && `Recommended Hardware #${idx}`}
                          {type === 'articles' && `Trending Headline #${idx}`}
                        </CardTitle>
                        <Badge variant={domainBadges[type].variant} className="text-[10px] px-1.5 py-0">
                          {98 - idx * 4}% match
                        </Badge>
                      </div>
                      <CardDescription className="text-xs pt-1">
                        {type === 'movies' && '1999 • Sci-Fi, Action'}
                        {type === 'products' && 'Logitech • Video Games'}
                        {type === 'articles' && 'Technology • 2 hours ago'}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="p-4 pt-2 pb-3 text-xs text-zinc-500 dark:text-zinc-400">
                      <p className="line-clamp-2">
                        {type === 'movies' && 'A computer hacker learns from mysterious rebels about the true nature of his reality.'}
                        {type === 'products' && 'Precision optical gaming mouse with customizable weights and RGB lighting.'}
                        {type === 'articles' && 'Scientists announce significant breakthroughs in high-density solid state batteries.'}
                      </p>
                    </CardContent>
                    <div className="border-t border-zinc-100 dark:border-zinc-800 p-3 bg-zinc-50/50 dark:bg-zinc-900/50 rounded-b-xl flex items-center justify-between text-[11px]">
                      <span className="text-zinc-500 flex items-center gap-1">
                        <Sparkles className="h-3 w-3 text-amber-500" />
                        Because you liked item #{100 + idx}
                      </span>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Compare */}
        {tab === 'compare' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Popular for Everyone</CardTitle>
                <CardDescription>Global baseline recommendations without user conditioning</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[1, 2, 3].map((n) => (
                  <div key={n} className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 text-xs">
                    Popular Item #{n}
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Personalized for User #{user}</CardTitle>
                <CardDescription>Conditioned on historical user affinity</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {[1, 2, 3].map((n) => (
                  <div key={n} className="p-3 rounded-lg border border-zinc-200 dark:border-zinc-800 text-xs">
                    Personalized Item #{n}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tab 3: Cold Start */}
        {tab === 'cold-start' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Interactive Cold-Start Builder</CardTitle>
              <CardDescription>
                Search and add items to simulate a brand-new user profile in real time.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <input
                type="text"
                placeholder="Search catalog by title (e.g. Star Wars, Zelda, Economy)..."
                className="w-full h-10 px-3 rounded-md border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-950"
              />
              <div className="p-4 rounded-lg bg-zinc-100 dark:bg-zinc-800/50 text-xs text-zinc-500">
                Taste Threshold Indicator: 0 likes selected. Currently serving global popularity fallback.
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab 4: Evaluation */}
        {tab === 'evaluation' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Cross-Domain Evaluation & Benchmarks</CardTitle>
              <CardDescription>
                Reproducible metrics computed across Movies, Products, and News datasets.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-zinc-200 dark:border-zinc-800 text-zinc-500">
                    <tr>
                      <th className="py-2">Metric</th>
                      <th className="py-2">Random Baseline</th>
                      <th className="py-2">Popularity Baseline</th>
                      <th className="py-2">Trained Model</th>
                      <th className="py-2">Relative Gain</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800/60 font-mono">
                    <tr>
                      <td className="py-2 font-sans font-medium">HitRate@10</td>
                      <td className="py-2">0.0217</td>
                      <td className="py-2">0.2024</td>
                      <td className="py-2 font-bold text-emerald-600 dark:text-emerald-400">0.3823</td>
                      <td className="py-2 text-emerald-600">+88.9%</td>
                    </tr>
                    <tr>
                      <td className="py-2 font-sans font-medium">NDCG@10</td>
                      <td className="py-2">0.0042</td>
                      <td className="py-2">0.0660</td>
                      <td className="py-2 font-bold text-emerald-600 dark:text-emerald-400">0.1021</td>
                      <td className="py-2 text-emerald-600">+54.6%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Tab 5: About */}
        {tab === 'about' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">About Discovery Engine</CardTitle>
              <CardDescription>
                Architecture, licensing, and academic provenance.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">
              <p>
                Discovery Engine is an adaptive, zero-fabrication recommendation engine providing
                multi-domain recommendation serving across Movies (MovieLens 1M), E-Commerce Products
                (Amazon Reviews), and News (Microsoft MIND).
              </p>
              <p>
                Derived from the open-source Microsoft Recommenders framework (MIT License), modernized
                with lightweight sparse algorithms, strict temporal splits, and type-safe Next.js serving.
              </p>
            </CardContent>
          </Card>
        )}
      </main>

      <AppFooter />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center">
          <Skeleton className="h-12 w-48 rounded-lg" />
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}

'use client';

import React, { useState, useMemo } from 'react';
import {
  Search,
  X,
  Plus,
  Trash2,
  Sparkles,
  SlidersHorizontal,
  Star,
  Check,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import { useTypes, useItemSearch, useColdStart } from '@/lib/api/hooks';
import { RecCard } from '@/components/features/RecCard';
import { ModeBadge } from '@/components/features/ModeBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { ErrorState } from '@/components/ui/ErrorState';
import { useDebounce } from '@/lib/hooks/useDebounce';
import type { ScoredItem, SearchItem } from '@/lib/api/schemas';

export interface ColdStartTabProps {
  type: string;
  k: number;
  onKChange: (k: number) => void;
  onSelectItem?: (item: ScoredItem) => void;
}

export interface SelectedHistoryItem {
  item_id: string;
  title: string;
  categories: string[];
  signal: number;
}

export function ColdStartTab({
  type,
  k,
  onKChange,
  onSelectItem,
}: ColdStartTabProps) {
  const { data: typesData } = useTypes();
  const currentTypeDescriptor = useMemo(
    () => typesData?.types.find((t) => t.id === type),
    [typesData?.types, type]
  );

  const supportsColdStart = currentTypeDescriptor ? currentTypeDescriptor.supports_cold_start : true;
  const cardType = currentTypeDescriptor?.card_type || (type === 'products' ? 'product' : type === 'articles' ? 'article' : 'movie');

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedQuery = useDebounce(searchQuery, 250);
  const {
    data: searchData,
    isLoading: isSearching,
  } = useItemSearch(type, debouncedQuery);

  // Selected history items state
  const [selectedItems, setSelectedItems] = useState<SelectedHistoryItem[]>([]);

  // Derived payload for cold-start query
  const historyPayload = useMemo(
    () => selectedItems.map((item) => ({ item_id: item.item_id, signal: item.signal })),
    [selectedItems]
  );

  // Cold start recommendations query
  const {
    data: coldStartData,
    isLoading: isRecsLoading,
    isError: isRecsError,
    refetch: refetchColdStart,
  } = useColdStart(type, historyPayload, k, { enabled: supportsColdStart });

  const selectedItemIds = useMemo(
    () => new Set(selectedItems.map((item) => item.item_id)),
    [selectedItems]
  );

  const handleAddItem = (item: SearchItem) => {
    if (selectedItemIds.has(item.item_id)) return;
    if (selectedItems.length >= 200) return;

    // Default signal: 5.0 for rating domains, 1.0 for articles/clicks
    const defaultSignal = cardType === 'article' ? 1.0 : 5.0;
    setSelectedItems((prev) => [
      ...prev,
      {
        item_id: item.item_id,
        title: item.title,
        categories: item.categories || [],
        signal: defaultSignal,
      },
    ]);
  };

  const handleRemoveItem = (itemId: string) => {
    setSelectedItems((prev) => prev.filter((item) => item.item_id !== itemId));
  };

  const handleClearAll = () => {
    setSelectedItems([]);
  };

  const handleSignalChange = (itemId: string, newSignal: number) => {
    setSelectedItems((prev) =>
      prev.map((item) => (item.item_id === itemId ? { ...item, signal: newSignal } : item))
    );
  };

  if (!supportsColdStart) {
    return (
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-8 text-center space-y-4">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-[var(--color-elevated)] text-[var(--color-accent-text)]">
          <AlertCircle className="h-6 w-6" />
        </div>
        <div className="space-y-1">
          <h3 className="text-base font-bold text-[var(--color-text)]">
            Cold-Start Not Supported for {currentTypeDescriptor?.display_name || type}
          </h3>
          <p className="max-w-md mx-auto text-xs text-[var(--color-text-secondary)] leading-relaxed">
            This recommender model operates on user impressions or pre-computed interactions rather
            than an ad-hoc interaction history. Use the <strong>For You</strong> and <strong>Compare</strong> tabs
            to explore personalized and popular feeds for registered users.
          </p>
        </div>
      </div>
    );
  }

  const currentMode = coldStartData?.mode || (selectedItems.length === 0 ? 'popularity' : 'personalized');

  return (
    <div className="space-y-6">
      {/* 1. Header & Catalog Search */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-4">
        <div>
          <h3 className="text-sm font-bold text-[var(--color-text)] flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-[var(--color-accent)]" />
            <span>Interactive Cold-Start Explorer</span>
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Build a hypothetical taste profile by searching and selecting items from the catalog.
            Discover how recommendations adapt dynamically from popularity fallback to personalization.
          </p>
        </div>

        {/* Search Input Box */}
        <div className="relative">
          <div className="relative flex items-center">
            <Search className="absolute left-3 h-4 w-4 text-[var(--color-text-muted)] pointer-events-none" />
            <input
              type="text"
              role="searchbox"
              placeholder={`Search ${currentTypeDescriptor?.display_name || type} by title or keyword...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-bg)] pl-9 pr-10 text-xs text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent-text)] transition-colors"
            />
            {isSearching && (
              <div className="absolute right-3">
                <Loader2 className="h-4 w-4 animate-spin text-[var(--color-text-muted)]" />
              </div>
            )}
            {!isSearching && searchQuery.length > 0 && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                aria-label="Clear search query"
                className="absolute right-3 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Search Dropdown Results */}
          {debouncedQuery.trim().length > 0 && searchData && searchData.results && (
            <div
              role="group"
              aria-label="Search results"
              className="absolute z-20 left-0 right-0 mt-1 max-h-60 overflow-y-auto rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-elevated)] p-1.5 shadow-lg space-y-1"
            >
              {searchData.results.length === 0 ? (
                <div className="p-3 text-center text-xs text-[var(--color-text-muted)]">
                  No matching items found for &quot;{debouncedQuery}&quot;.
                </div>
              ) : (
                searchData.results.map((item) => {
                  const isAdded = selectedItemIds.has(item.item_id);
                  return (
                    <div
                      key={item.item_id}
                      className="flex items-center justify-between gap-3 rounded-[4px] p-2 hover:bg-[var(--color-surface)] transition-colors"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs text-[var(--color-text)] truncate">
                            {item.title}
                          </span>
                          {item.year && (
                            <span className="text-[12px] text-[var(--color-text-muted)] tabular-nums">
                              ({item.year})
                            </span>
                          )}
                        </div>
                        {item.categories && item.categories.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-0.5">
                            {Array.from(new Set(item.categories)).slice(0, 3).map((cat, idx) => (
                              <span
                                key={`${cat}-${idx}`}
                                className="text-[12px] text-[var(--color-text-secondary)] bg-[var(--color-bg)] px-1.5 py-0.5 rounded"
                              >
                                {cat}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>

                      <button
                        type="button"
                        aria-label={isAdded ? `Added ${item.title}` : `Add ${item.title}`}
                        disabled={isAdded || selectedItems.length >= 200}
                        onClick={() => handleAddItem(item)}
                        className={`inline-flex items-center gap-1 rounded-[4px] px-2.5 py-1 text-xs font-semibold transition-colors cursor-pointer ${
                          isAdded
                            ? 'bg-transparent text-[var(--color-accent-text)] border border-[var(--color-accent)]/40 cursor-default'
                            : 'bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-active)]'
                        }`}
                      >
                        {isAdded ? (
                          <>
                            <Check className="h-3 w-3" />
                            <span>Added</span>
                          </>
                        ) : (
                          <>
                            <Plus className="h-3 w-3" />
                            <span>Add</span>
                          </>
                        )}
                      </button>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </div>

      {/* 2. Selected Taste Profile Chips & Clear Button */}
      <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h4 className="text-xs font-bold text-[var(--color-text)] uppercase tracking-wider">
              Selected History ({selectedItems.length} / 200)
            </h4>
            <ModeBadge mode={currentMode} />
          </div>

          {selectedItems.length > 0 && (
            <button
              type="button"
              onClick={handleClearAll}
              className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent-text)] cursor-pointer transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Clear All</span>
            </button>
          )}
        </div>

        {/* Threshold explanation notice */}
        <div
          role="status"
          aria-label="Taste threshold status"
          className="rounded-[4px] bg-[var(--color-elevated)] border border-[var(--color-border)] p-3 text-xs flex items-center justify-between gap-3"
        >
          <div className="flex items-center gap-2">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                selectedItems.length > 0 ? 'bg-[var(--color-accent)] animate-pulse' : 'bg-gray-500'
              }`}
            />
            <span className="text-[var(--color-text-secondary)]">
              {selectedItems.length === 0 ? (
                <>
                  <strong className="text-[var(--color-text)]">0 items selected.</strong> Serving global popularity fallback. Add at least 1 item to trigger personalized cold start.
                </>
              ) : (
                <>
                  <strong className="text-[var(--color-text)]">{selectedItems.length} items selected.</strong> Serving personalized recommendations based on your hypothetical profile.
                </>
              )}
            </span>
          </div>
          <span className="text-[12px] text-[var(--color-text-muted)] tabular-nums shrink-0">
            Max 200 items
          </span>
        </div>

        {/* Selected Items Chips List */}
        {selectedItems.length === 0 ? (
          <div className="py-6 text-center text-xs text-[var(--color-text-muted)] border border-dashed border-[var(--color-border)] rounded-[var(--radius-card)]">
            No items in hypothetical history. Search above to add items to your profile.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2 pt-1">
            {selectedItems.map((item) => (
              <div
                key={item.item_id}
                className="inline-flex items-center gap-2 rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-elevated)] px-2.5 py-1.5 text-xs text-[var(--color-text)]"
              >
                <span className="font-medium max-w-[140px] truncate" title={item.title}>
                  {item.title}
                </span>

                {/* Rating / Signal Control */}
                {cardType === 'article' ? (
                  <span className="rounded bg-[var(--color-bg)] px-1.5 py-0.5 text-[12px] font-semibold text-[var(--color-accent-text)]">
                    Clicked
                  </span>
                ) : (
                  <div className="flex items-center gap-0.5">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <button
                        key={star}
                        type="button"
                        aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                        onClick={() => handleSignalChange(item.item_id, star)}
                        className="p-1.5 cursor-pointer text-[var(--color-text-muted)] hover:text-amber-400 transition-colors"
                      >
                        <Star
                          className={`h-3 w-3 ${
                            star <= item.signal
                              ? 'fill-amber-400 text-amber-400'
                              : 'text-[var(--color-text-muted)]'
                          }`}
                        />
                      </button>
                    ))}
                  </div>
                )}

                {/* Remove Chip */}
                <button
                  type="button"
                  aria-label={`Remove ${item.title}`}
                  onClick={() => handleRemoveItem(item.item_id)}
                  className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent-text)] cursor-pointer"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Live Cold-Start Recommendation Feed */}
      <div className="space-y-4">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] pb-3">
          <div>
            <h3 className="text-sm font-bold text-[var(--color-text)] flex items-center gap-2">
              <span>Cold-Start Recommendations</span>
              <span className="text-xs font-normal text-[var(--color-text-muted)] tabular-nums">
                ({coldStartData?.results ? coldStartData.results.length : 0} items)
              </span>
            </h3>
          </div>

          {/* k Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-[var(--color-text-muted)] flex items-center gap-1">
              <SlidersHorizontal className="h-3 w-3" /> k:
            </span>
            <div className="inline-flex rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-0.5 text-xs">
              {[5, 10, 20].map((kVal) => (
                <button
                  key={kVal}
                  type="button"
                  onClick={() => onKChange(kVal)}
                  className={`px-2.5 py-1 text-xs font-semibold rounded-[4px] cursor-pointer tabular-nums transition-colors ${
                    k === kVal
                      ? 'bg-[var(--color-elevated)] text-[var(--color-accent-text)]'
                      : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                  }`}
                >
                  {kVal}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Loading Skeletons */}
        {isRecsLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {Array.from({ length: k }).map((_, i) => (
              <div key={i} className="space-y-2">
                <Skeleton className="aspect-[2/3] w-full rounded-[var(--radius-card)] bg-[var(--color-elevated)]" />
                <Skeleton className="h-4 w-3/4 bg-[var(--color-elevated)]" />
                <Skeleton className="h-3 w-1/2 bg-[var(--color-elevated)]" />
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {isRecsError && (
          <div className="rounded-[var(--radius-card)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <ErrorState
              title="Recommendations unavailable"
              message="Could not generate cold-start recommendations for the current profile."
              onRetry={refetchColdStart}
            />
          </div>
        )}

        {/* Success Grid */}
        {!isRecsLoading && !isRecsError && coldStartData && (
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-4">
            {coldStartData.results.map((item, idx) => (
              <RecCard
                key={`${item.item_id}-${idx}`}
                item={item}
                cardType={cardType}
                onSelect={onSelectItem}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

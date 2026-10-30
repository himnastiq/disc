import { describe, it, expect } from 'vitest';
import {
  normalizeTab,
  normalizeType,
  DEFAULT_TAB,
  DEFAULT_TYPE,
} from '@/lib/hooks/useUrlState';

describe('URL State Parameter Normalization & Fallbacks (P8.5)', () => {
  it('preserves valid tabs unchanged', () => {
    expect(normalizeTab('for-you')).toBe('for-you');
    expect(normalizeTab('compare')).toBe('compare');
    expect(normalizeTab('cold-start')).toBe('cold-start');
    expect(normalizeTab('evaluation')).toBe('evaluation');
  });

  it('falls back to default tab for invalid or missing values', () => {
    expect(normalizeTab('invalid-tab')).toBe(DEFAULT_TAB);
    expect(normalizeTab('about')).toBe(DEFAULT_TAB);
    expect(normalizeTab('')).toBe(DEFAULT_TAB);
    expect(normalizeTab(null)).toBe(DEFAULT_TAB);
    expect(normalizeTab(undefined)).toBe(DEFAULT_TAB);
  });

  it('preserves valid content types unchanged', () => {
    expect(normalizeType('movies')).toBe('movies');
    expect(normalizeType('products')).toBe('products');
    expect(normalizeType('articles')).toBe('articles');
  });

  it('falls back to default type for invalid or missing values', () => {
    expect(normalizeType('unknown-domain')).toBe(DEFAULT_TYPE);
    expect(normalizeType('')).toBe(DEFAULT_TYPE);
    expect(normalizeType(null)).toBe(DEFAULT_TYPE);
    expect(normalizeType(undefined)).toBe(DEFAULT_TYPE);
  });
});


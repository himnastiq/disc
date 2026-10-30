import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export function normalizeMovieTitle(rawTitle: string): { title: string; year?: number } {
  let title = rawTitle.trim();
  let year: number | undefined;

  const yearMatch = title.match(/\((\d{4})\)$/);
  if (yearMatch) {
    year = parseInt(yearMatch[1], 10);
    title = title.replace(/\s*\(\d{4}\)$/, '').trim();
  }

  if (title.endsWith(', The')) {
    title = 'The ' + title.slice(0, -5);
  } else if (title.endsWith(', A')) {
    title = 'A ' + title.slice(0, -3);
  } else if (title.endsWith(', An')) {
    title = 'An ' + title.slice(0, -4);
  }

  return { title, year };
}

// In-memory cache + persistent disk cache
const CACHE_FILE = path.join(process.cwd(), '.cache', 'tmdb_posters.json');
let memoryCache: Record<string, string | null> | null = null;

function getCache(): Record<string, string | null> {
  if (memoryCache !== null) return memoryCache;
  try {
    if (fs.existsSync(CACHE_FILE)) {
      memoryCache = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf-8'));
      return memoryCache!;
    }
  } catch {
    // ignore
  }
  memoryCache = {};
  return memoryCache;
}

function setCache(key: string, value: string | null) {
  const cache = getCache();
  cache[key] = value;
  try {
    const dir = path.dirname(CACHE_FILE);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    fs.writeFileSync(CACHE_FILE, JSON.stringify(cache, null, 2), 'utf-8');
  } catch {
    // non-fatal
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const rawTitle = searchParams.get('title') || '';
  const rawYear = searchParams.get('year');

  if (!rawTitle) {
    return NextResponse.json({ poster_url: null, error: 'Missing title' }, { status: 400 });
  }

  const apiKey = process.env.TMDB_API_KEY;
  if (!apiKey) {
    return NextResponse.json({ poster_url: null, configured: false });
  }

  const { title: cleanTitle, year: extractedYear } = normalizeMovieTitle(rawTitle);
  const year = rawYear ? parseInt(rawYear, 10) : extractedYear;

  const cacheKey = `${cleanTitle.toLowerCase()}_${year || ''}`;
  const cache = getCache();
  if (cacheKey in cache) {
    return NextResponse.json({ poster_url: cache[cacheKey], cached: true, configured: true });
  }

  try {
    const tmdbUrl = new URL('https://api.themoviedb.org/3/search/movie');
    tmdbUrl.searchParams.set('api_key', apiKey);
    tmdbUrl.searchParams.set('query', cleanTitle);
    if (year) {
      tmdbUrl.searchParams.set('year', String(year));
    }
    tmdbUrl.searchParams.set('include_adult', 'false');

    const res = await fetch(tmdbUrl.toString());

    if (!res.ok) {
      return NextResponse.json({
        poster_url: null,
        configured: true,
        error: `TMDB returned status ${res.status}`,
      });
    }

    const data = await res.json();
    const posterPath = data.results?.[0]?.poster_path;
    const posterUrl = posterPath ? `https://image.tmdb.org/t/p/w500${posterPath}` : null;

    setCache(cacheKey, posterUrl);

    return NextResponse.json({ poster_url: posterUrl, cached: false, configured: true });
  } catch (err: unknown) {
    return NextResponse.json({ poster_url: null, configured: true, error: String(err) });
  }
}

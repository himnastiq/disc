export function posterUrl(
  path: string | null | undefined,
  size: 'w185' | 'w342' | 'w500' | 'original' = 'w342'
): string | null {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  return `https://image.tmdb.org/t/p/${size}${cleanPath}`;
}


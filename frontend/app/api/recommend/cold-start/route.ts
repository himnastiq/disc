import { proxyToBackend } from '@/lib/server/proxy';

export async function POST(request: Request) {
  try {
    const body = await request.text();
    return proxyToBackend('/v1/recommend/cold-start', {
      method: 'POST',
      body,
    });
  } catch {
    return proxyToBackend('/v1/recommend/cold-start', {
      method: 'POST',
      body: '{}',
    });
  }
}


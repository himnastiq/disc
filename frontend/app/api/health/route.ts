import { proxyToBackend } from '@/lib/server/proxy';

export async function GET() {
  return proxyToBackend('/v1/health');
}


import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  const backendPath = `/v1/types/${encodeURIComponent(type)}/search${query ? `?${query}` : ''}`;
  return proxyToBackend(backendPath);
}


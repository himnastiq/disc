import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string; itemId: string }> }
) {
  const { type, itemId } = await params;
  const backendPath = `/v1/items/${encodeURIComponent(itemId)}?type=${encodeURIComponent(type)}`;
  return proxyToBackend(backendPath);
}


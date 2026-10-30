import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string; itemId: string }> }
) {
  const { type, itemId } = await params;
  const backendPath = `/v1/types/${encodeURIComponent(type)}/items/${encodeURIComponent(itemId)}`;
  return proxyToBackend(backendPath);
}


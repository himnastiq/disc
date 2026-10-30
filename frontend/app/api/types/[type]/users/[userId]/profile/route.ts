import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string; userId: string }> }
) {
  const { type, userId } = await params;
  const backendPath = `/v1/types/${encodeURIComponent(type)}/users/${encodeURIComponent(userId)}/profile`;
  return proxyToBackend(backendPath);
}


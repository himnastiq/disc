import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string; userId: string }> }
) {
  const { type, userId } = await params;
  const backendPath = `/v1/users/${encodeURIComponent(userId)}/profile?type=${encodeURIComponent(type)}`;
  return proxyToBackend(backendPath);
}


import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  const backendPath = `/v1/types/${encodeURIComponent(type)}/metrics`;
  return proxyToBackend(backendPath);
}


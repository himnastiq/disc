import { proxyToBackend } from '@/lib/server/proxy';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  const { searchParams } = new URL(request.url);
  searchParams.set('type', type);
  const backendPath = `/v1/similar?${searchParams.toString()}`;
  return proxyToBackend(backendPath);
}


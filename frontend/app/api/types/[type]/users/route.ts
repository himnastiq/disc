import { proxyToBackend } from '@/lib/server/proxy';
import { isValidTypeId, badRequest } from '@/lib/server/validate';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  if (!isValidTypeId(type)) return badRequest('Invalid content type.');
  const { searchParams } = new URL(request.url);
  const query = searchParams.toString();
  const backendPath = `/v1/types/${encodeURIComponent(type)}/users${query ? `?${query}` : ''}`;
  return proxyToBackend(backendPath);
}


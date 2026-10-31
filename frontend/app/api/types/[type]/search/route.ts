import { proxyToBackend } from '@/lib/server/proxy';
import { isValidTypeId, badRequest, boundedIntParam } from '@/lib/server/validate';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  if (!isValidTypeId(type)) return badRequest('Invalid content type.');
  const { searchParams } = new URL(request.url);
  const kError = boundedIntParam(searchParams, 'limit', 1, 100);
  if (kError) return badRequest(kError);
  searchParams.set('type', type);
  const backendPath = `/v1/items/search?${searchParams.toString()}`;
  return proxyToBackend(backendPath);
}


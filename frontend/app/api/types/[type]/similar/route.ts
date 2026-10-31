import { proxyToBackend } from '@/lib/server/proxy';
import { isValidTypeId, badRequest, boundedIntParam } from '@/lib/server/validate';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  const { type } = await params;
  if (!isValidTypeId(type)) return badRequest('Invalid content type.');
  const { searchParams } = new URL(request.url);
  const kError = boundedIntParam(searchParams, 'k', 1, 50);
  if (kError) return badRequest(kError);
  searchParams.set('type', type);
  const backendPath = `/v1/similar?${searchParams.toString()}`;
  return proxyToBackend(backendPath);
}


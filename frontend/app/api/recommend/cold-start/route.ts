import { proxyToBackend } from '@/lib/server/proxy';
import { ColdStartRequestSchema } from '@/lib/api/schemas';
import { badRequest } from '@/lib/server/validate';

export async function POST(request: Request) {
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return badRequest('Request body must be valid JSON.');
  }
  const parsed = ColdStartRequestSchema.safeParse(payload);
  if (!parsed.success) return badRequest('Invalid cold-start request.');
  return proxyToBackend('/v1/recommend/cold-start', {
    method: 'POST',
    body: JSON.stringify(parsed.data),
  });
}


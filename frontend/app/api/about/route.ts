import { connection } from 'next/server';
import { proxyToBackend } from '@/lib/server/proxy';

export async function GET() {
  await connection();
  return proxyToBackend('/v1/about');
}


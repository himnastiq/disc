import { NextResponse } from 'next/server';

const API_BASE_URL = process.env.API_BASE_URL || 'http://127.0.0.1:8000';
const API_KEY = process.env.API_KEY || process.env.RECOMMENDER_API_KEY || '';
const DEFAULT_TIMEOUT_MS = 10000;

export interface ProxyOptions {
  method?: string;
  headers?: Record<string, string>;
  body?: string;
  timeoutMs?: number;
}

export async function proxyToBackend(
  backendPath: string,
  options: ProxyOptions = {}
): Promise<NextResponse> {
  const url = `${API_BASE_URL}${backendPath.startsWith('/') ? '' : '/'}${backendPath}`;
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (API_KEY) {
    headers['x-api-key'] = API_KEY;
  }

  try {
    const res = await fetch(url, {
      method: options.method || 'GET',
      headers,
      body: options.body,
      signal: AbortSignal.timeout(timeoutMs),
      cache: 'no-store',
    });

    const contentType = res.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }

    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { 'Content-Type': contentType || 'text/plain' },
    });
  } catch (err: unknown) {
    const isTimeout =
      err instanceof Error && (err.name === 'TimeoutError' || err.name === 'AbortError');
    const statusCode = isTimeout ? 504 : 502;
    const errorCode = isTimeout ? 'GATEWAY_TIMEOUT' : 'BAD_GATEWAY';
    const message = isTimeout
      ? `Backend request timed out after ${timeoutMs}ms: ${backendPath}`
      : `Failed to connect to backend recommender service at ${API_BASE_URL}`;

    return NextResponse.json(
      {
        error: {
          code: errorCode,
          message,
          details: err instanceof Error ? err.message : String(err),
        },
      },
      { status: statusCode }
    );
  }
}


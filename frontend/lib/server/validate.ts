import { NextResponse } from 'next/server';

const TYPE_ID_PATTERN = /^[a-z0-9_-]{1,32}$/i;

export function isValidTypeId(value: string): boolean {
  return TYPE_ID_PATTERN.test(value);
}

export function badRequest(message: string): NextResponse {
  return NextResponse.json({ error: { code: 'BAD_REQUEST', message } }, { status: 400 });
}

/** Returns an error message when the param is present but invalid; null when absent or valid. */
export function boundedIntParam(
  searchParams: URLSearchParams,
  name: string,
  min: number,
  max: number
): string | null {
  const raw = searchParams.get(name);
  if (raw === null) return null;
  if (!/^[0-9]+$/.test(raw)) return name + ' must be a whole number.';
  const value = Number(raw);
  if (value < min || value > max) return name + ' must be between ' + min + ' and ' + max + '.';
  return null;
}


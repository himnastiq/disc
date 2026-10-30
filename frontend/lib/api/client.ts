import { z } from 'zod';
import {
  ErrorResponseSchema,
  TypesResponseSchema,
  UsersResponseSchema,
  UserProfileResponseSchema,
  RecommendResponseSchema,
  ItemDetailSchema,
  SearchResponseSchema,
  MetricsResponseSchema,
  AboutResponseSchema,
  type ColdStartRequest,
} from './schemas';
export type {
  TypesResponse,
  UsersResponse,
  UserProfileResponse,
  RecommendResponse,
  ItemDetail,
  SearchResponse,
  MetricsResponse,
  AboutResponse,
  ColdStartRequest,
} from './schemas';

export class ApiError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public code: string = 'API_ERROR',
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(
  schema: z.ZodSchema<T>,
  path: string,
  init?: RequestInit
): Promise<T> {
  const url = path.startsWith('/api') ? path : `/api${path.startsWith('/') ? '' : '/'}${path}`;

  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err: unknown) {
    throw new ApiError(
      err instanceof Error ? err.message : 'Network request failed',
      0,
      'NETWORK_FAILURE',
      err
    );
  }

  let data: unknown;
  try {
    data = await res.json();
  } catch (err: unknown) {
    throw new ApiError(
      `Unexpected response from server: malformed JSON response from ${path}`,
      res.status || 502,
      'INVALID_JSON',
      err
    );
  }

  if (!res.ok) {
    const errorParsed = ErrorResponseSchema.safeParse(data);
    if (errorParsed.success) {
      throw new ApiError(
        errorParsed.data.error.message,
        res.status,
        errorParsed.data.error.code,
        errorParsed.data.error.details
      );
    }
    throw new ApiError(
      `API request failed with status ${res.status}`,
      res.status,
      'HTTP_ERROR',
      data
    );
  }

  const result = schema.safeParse(data);
  if (!result.success) {
    console.error(`[Zod ValidationError] Payload from ${path} did not match schema:`, result.error);
    throw new ApiError(
      `Unexpected response from server: ${result.error.issues[0]?.message || 'schema validation failed'}`,
      res.status,
      'SCHEMA_VALIDATION_ERROR',
      result.error.format()
    );
  }

  return result.data;
}

// ---------------------------------------------------------------------------
// Convenience client methods
// ---------------------------------------------------------------------------

export const apiClient = {
  getTypes: () => apiFetch(TypesResponseSchema, '/api/types'),

  getUsers: (type: string, query?: string) => {
    const q = query ? `?query=${encodeURIComponent(query)}` : '';
    return apiFetch(UsersResponseSchema, `/api/types/${encodeURIComponent(type)}/users${q}`);
  },

  getUserProfile: (type: string, userId: string) =>
    apiFetch(
      UserProfileResponseSchema,
      `/api/types/${encodeURIComponent(type)}/users/${encodeURIComponent(userId)}/profile`
    ),

  getRecommendations: (type: string, userId?: string, k: number = 10) => {
    const params = new URLSearchParams();
    if (userId) params.set('user_id', userId);
    params.set('k', String(k));
    return apiFetch(
      RecommendResponseSchema,
      `/api/types/${encodeURIComponent(type)}/recommend?${params.toString()}`
    );
  },

  getPopular: (type: string, k: number = 10) =>
    apiFetch(
      RecommendResponseSchema,
      `/api/types/${encodeURIComponent(type)}/popular?k=${k}`
    ),

  getSimilar: (type: string, itemId: string, k: number = 10) =>
    apiFetch(
      RecommendResponseSchema,
      `/api/types/${encodeURIComponent(type)}/similar?item_id=${encodeURIComponent(itemId)}&k=${k}`
    ),

  getItemDetail: (type: string, itemId: string) =>
    apiFetch(
      ItemDetailSchema,
      `/api/types/${encodeURIComponent(type)}/items/${encodeURIComponent(itemId)}`
    ),

  searchItems: (type: string, query: string, limit: number = 20) =>
    apiFetch(
      SearchResponseSchema,
      `/api/types/${encodeURIComponent(type)}/search?q=${encodeURIComponent(query)}&limit=${limit}`
    ),

  postColdStart: (request: ColdStartRequest) =>
    apiFetch(RecommendResponseSchema, '/api/recommend/cold-start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    }),

  getMetrics: (type: string) =>
    apiFetch(
      MetricsResponseSchema,
      `/api/types/${encodeURIComponent(type)}/metrics`
    ),

  getAbout: () => apiFetch(AboutResponseSchema, '/api/about'),
};

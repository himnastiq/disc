import { describe, it, expect } from 'vitest';
import {
  TypesResponseSchema,
  UsersResponseSchema,
  UserProfileResponseSchema,
  RecommendResponseSchema,
  AboutResponseSchema,
  ErrorResponseSchema,
} from '@/lib/api/schemas';
import typesFixture from '../fixtures/types.json';
import usersMoviesFixture from '../fixtures/users_movies.json';
import profileMovies1Fixture from '../fixtures/profile_movies_1.json';
import recommendMovies1Fixture from '../fixtures/recommend_movies_1.json';
import aboutFixture from '../fixtures/about.json';

describe('Zod Schema Runtime Validation (P8.3)', () => {
  it('validates TypesResponse schema against recorded backend fixture', () => {
    const result = TypesResponseSchema.safeParse(typesFixture);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.types.length).toBe(3);
      expect(result.data.types[0].id).toBe('movies');
      expect(result.data.types[0].card_type).toBe('movie');
    }
  });

  it('validates UsersResponse schema against recorded backend fixture', () => {
    const result = UsersResponseSchema.safeParse(usersMoviesFixture);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.users.length).toBe(3);
      expect(result.data.users[0].user_id).toBe('1');
    }
  });

  it('validates UserProfileResponse schema against recorded backend fixture', () => {
    const result = UserProfileResponseSchema.safeParse(profileMovies1Fixture);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.user_id).toBe('1');
      expect(result.data.top_categories.length).toBeGreaterThan(0);
    }
  });

  it('validates RecommendResponse schema against recorded backend fixture', () => {
    const result = RecommendResponseSchema.safeParse(recommendMovies1Fixture);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.mode).toBe('personalized');
      expect(result.data.results.length).toBe(2);
      expect(result.data.results[0].reason?.kind).toBe('history_item');
    }
  });

  it('validates AboutResponse schema against recorded backend fixture', () => {
    const result = AboutResponseSchema.safeParse(aboutFixture);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.title).toBe('Discovery Engine');
      expect(result.data.attributions.length).toBeGreaterThan(0);
    }
  });

  it('gracefully fails on malformed API payloads without crashing (P8.3 Acceptance)', () => {
    const malformedPayload = {
      types: [
        {
          id: 'movies',
          // missing display_name, card_type, supports_cold_start
        },
      ],
    };
    const result = TypesResponseSchema.safeParse(malformedPayload);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.length).toBeGreaterThan(0);
    }
  });

  it('parses standardized ErrorResponse schema properly', () => {
    const errorPayload = {
      error: {
        code: 'USER_NOT_FOUND',
        message: 'User 99999 was not found in catalog',
      },
    };
    const result = ErrorResponseSchema.safeParse(errorPayload);
    expect(result.success).toBe(true);
    if (result.success) {
      expect(result.data.error.code).toBe('USER_NOT_FOUND');
    }
  });
});


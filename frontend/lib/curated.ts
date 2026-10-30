export interface CarouselMovie {
  id: number | string;
  title: string;
  poster: string | null;
  year?: string | number | null;
  rating?: number | null;
  rank?: number;
  matchPercentage?: number;
  reason?: string | null;
  genreIds?: number[];
  categories?: string[];
}

export const CRITICALLY_ACCLAIMED_MOVIES: CarouselMovie[] = [
  {
    id: 858,
    title: 'The Godfather (1972)',
    poster: 'https://image.tmdb.org/t/p/w342/3bhkrj58Vtu7enYsRolD1fZdja1.jpg',
    year: 1972,
    rating: 9.2,
    rank: 1,
    reason: 'Universal acclaim · Top 10 AFI Masterwork',
    categories: ['Crime', 'Drama'],
  },
  {
    id: 318,
    title: 'The Shawshank Redemption (1994)',
    poster: 'https://image.tmdb.org/t/p/w342/9cqNxx0GxF0bflZmeSMuL5tnGzr.jpg',
    year: 1994,
    rating: 9.3,
    rank: 2,
    reason: '#1 Rated on IMDb Top 250',
    categories: ['Drama'],
  },
  {
    id: 296,
    title: 'Pulp Fiction (1994)',
    poster: 'https://image.tmdb.org/t/p/w342/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg',
    year: 1994,
    rating: 8.9,
    rank: 3,
    reason: 'Palme d\'Or Winner · Iconic Postmodern Cinema',
    categories: ['Crime', 'Drama'],
  },
  {
    id: 527,
    title: 'Schindler\'s List (1993)',
    poster: 'https://image.tmdb.org/t/p/w342/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg',
    year: 1993,
    rating: 9.0,
    rank: 4,
    reason: '7 Academy Awards including Best Picture',
    categories: ['Drama', 'History'],
  },
  {
    id: 50,
    title: 'The Usual Suspects (1995)',
    poster: 'https://image.tmdb.org/t/p/w342/bUPmtQzrRhzqYySeiMpv7GurGLm.jpg',
    year: 1995,
    rating: 8.5,
    rank: 5,
    reason: 'Oscar Winner for Best Original Screenplay',
    categories: ['Crime', 'Mystery', 'Thriller'],
  },
  {
    id: 260,
    title: 'Star Wars: Episode IV - A New Hope (1977)',
    poster: 'https://image.tmdb.org/t/p/w342/6FfCtAuVAW8XJjZ7eWeLibRLWTw.jpg',
    year: 1977,
    rating: 8.6,
    rank: 6,
    reason: 'Landmark Sci-Fi Cultural Phenomenon',
    categories: ['Action', 'Adventure', 'Sci-Fi'],
  },
  {
    id: 593,
    title: 'The Silence of the Lambs (1991)',
    poster: 'https://image.tmdb.org/t/p/w342/uS9m8OBk1A8eM9I042bx8XXpqAq.jpg',
    year: 1991,
    rating: 8.6,
    rank: 7,
    reason: 'Big Five Academy Award Winner',
    categories: ['Crime', 'Drama', 'Thriller'],
  },
  {
    id: 1198,
    title: 'Raiders of the Lost Ark (1981)',
    poster: 'https://image.tmdb.org/t/p/w342/ceG9VzoRAVGwivFU40um3br6Df.jpg',
    year: 1981,
    rating: 8.4,
    rank: 8,
    reason: 'Definitive Action-Adventure Masterclass',
    categories: ['Action', 'Adventure'],
  },
];

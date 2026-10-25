"""Discovery Engine dataset adapters package."""

from engine.adapters.amazon import AmazonProductsAdapter
from engine.adapters.movielens import MovieLensAdapter
from engine.adapters.toy import ToyAdapter

__all__ = ["AmazonProductsAdapter", "MovieLensAdapter", "ToyAdapter"]

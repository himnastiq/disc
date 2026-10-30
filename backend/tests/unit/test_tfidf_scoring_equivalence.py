"""The vectorised TF-IDF scoring must return exactly what the old per-item loop returned."""

from __future__ import annotations

import math
from types import SimpleNamespace

import numpy as np
from scipy import sparse

from engine.models.tfidf import TfidfProfileModel, _pad_with_popular

N_ITEMS = 400
N_TERMS = 60


class _FakeVectorizer:
    """Counts how often the (expensive) vocabulary array is requested."""

    def __init__(self, names: list[str]) -> None:
        self._names = np.array(names, dtype=object)
        self.calls = 0

    def get_feature_names_out(self) -> np.ndarray:
        self.calls += 1
        return self._names


def _make_model(seed: int, fresh: set[str] | None) -> TfidfProfileModel:
    """Build a model by hand (no training) that contains deliberate score ties."""
    rng = np.random.default_rng(seed)
    dense = rng.random((N_ITEMS, N_TERMS)) * (rng.random((N_ITEMS, N_TERMS)) < 0.05)
    dense[100:110] = dense[0]  # identical rows give identical scores (ties)
    dense[200:205] = 0.0  # all-zero rows score 0 and must never be recommended
    ids = [f"N{n:05d}" for n in rng.permutation(N_ITEMS)]  # id order differs from row order

    model = TfidfProfileModel.__new__(TfidfProfileModel)
    model.tfidf_matrix = sparse.csr_matrix(dense)
    model.item_ids = ids
    model.item2index = {item_id: idx for idx, item_id in enumerate(ids)}
    model.index2item = dict(enumerate(ids))
    model.catalogue = set(ids)
    model.item_counts = {item_id: idx % 7 for idx, item_id in enumerate(ids)}
    model.sorted_popular = sorted(ids, key=lambda x: (-model.item_counts[x], x))
    model.fresh_candidates = None
    model.window_item_counts = {}
    model.sorted_window_popular = []
    model._score_cache = None
    model._feature_names_cache = None
    model.vectorizer = _FakeVectorizer([f"term{t}" for t in range(N_TERMS)])
    model.spec = SimpleNamespace(serving=SimpleNamespace(explanation_min_threshold=0.2))
    model.item_titles = {}
    model._is_fitted = True
    if fresh is not None:
        model.set_fresh_candidates(fresh)
    return model


def _reference(
    model: TfidfProfileModel, profile: sparse.csr_matrix, k: int, exclusions: set[str]
) -> list[tuple[str, float]]:
    """The original implementation: dense scores, a Python loop, then a full sort."""
    assert model.tfidf_matrix is not None
    scores_arr = np.asarray(model.tfidf_matrix.dot(profile.T).toarray()).flatten()
    candidates: list[tuple[float, str]] = []
    for idx, score_val in enumerate(scores_arr):
        item_id = model.index2item[idx]
        if model.fresh_candidates is not None and item_id not in model.fresh_candidates:
            continue
        if item_id in exclusions:
            continue
        s = float(score_val)
        if np.isfinite(s) and s > 0.0:
            candidates.append((s, item_id))
    candidates.sort(key=lambda x: (-x[0], x[1]))
    if len(candidates) < k:
        selected_ids = {c[1] for c in candidates}
        pop_recs = model.popular(k=k - len(candidates), exclude_ids=exclusions.union(selected_ids))
        candidates = _pad_with_popular(candidates, pop_recs)
    return [(item_id, float(score)) for score, item_id in candidates[:k]]


def _random_profile(rng: np.random.Generator) -> sparse.csr_matrix:
    vec = rng.random(N_TERMS) * (rng.random(N_TERMS) < 0.2)
    vec[0] = 1.0  # never an empty profile
    return sparse.csr_matrix(vec.reshape(1, -1))


def _assert_same(model: TfidfProfileModel, profile: sparse.csr_matrix, k: int, excl: set[str]):
    expected = _reference(model, profile, k, excl)
    got = model._score_candidates(profile, k=k, exclusions=excl)
    assert [r.item_id for r in got] == [item_id for item_id, _ in expected]
    assert [r.rank for r in got] == list(range(1, len(expected) + 1))
    for result, (_, score) in zip(got, expected, strict=True):
        assert math.isclose(result.score, score, rel_tol=1e-12, abs_tol=1e-15)


def test_vectorised_scoring_matches_the_original_loop() -> None:
    for seed in range(6):
        rng = np.random.default_rng(1000 + seed)
        ids = [f"N{n:05d}" for n in range(N_ITEMS)]
        pools: list[set[str] | None] = [None, set(rng.choice(ids, 60, replace=False).tolist())]
        for fresh in pools:
            model = _make_model(seed, fresh)
            for k in (1, 5, 10, 50, 500):
                profile = _random_profile(rng)
                excl = set(rng.choice(model.item_ids, 30, replace=False).tolist())
                _assert_same(model, profile, k, excl)
                _assert_same(model, profile, k, set())


def test_cache_follows_changes_of_the_candidate_pool() -> None:
    rng = np.random.default_rng(7)
    model = _make_model(3, {f"N{n:05d}" for n in range(50)})
    profile = _random_profile(rng)
    _assert_same(model, profile, 10, set())
    model.set_fresh_candidates({f"N{n:05d}" for n in range(200, 330)})
    _assert_same(model, profile, 10, set())
    model.fresh_candidates = None
    _assert_same(model, profile, 10, set())


def test_pads_with_popular_when_few_candidates_match() -> None:
    model = _make_model(5, None)
    only_term = np.zeros((1, N_TERMS))
    only_term[0, 59] = 1.0  # a term that very few items contain
    profile = sparse.csr_matrix(only_term)
    _assert_same(model, profile, 50, set())


def test_non_positive_k_returns_nothing() -> None:
    model = _make_model(1, None)
    assert model._score_candidates(_random_profile(np.random.default_rng(1)), 0, set()) == []


def _reference_best(
    model: TfidfProfileModel, rec_id: str, history_pairs: list[tuple[str, float]]
) -> tuple[str | None, float, float]:
    """The original explain() loop: one row slice and one sparse product per history item."""
    assert model.tfidf_matrix is not None
    rec_vec = model.tfidf_matrix[model.item2index[rec_id], :]
    best_h: str | None = None
    best_contrib = -1.0
    total_contrib = 0.0
    for h_id, sig in history_pairs:
        if h_id not in model.item2index:
            continue
        h_vec = model.tfidf_matrix[model.item2index[h_id], :]
        sim = float(h_vec.dot(rec_vec.T).toarray()[0, 0])
        contrib = max(0.0, sim * float(sig))
        total_contrib += contrib
        if contrib > best_contrib:
            best_contrib = contrib
            best_h = h_id
    return best_h, best_contrib, total_contrib


def test_explain_matches_the_original_loop_and_reads_the_vocabulary_once() -> None:
    rng = np.random.default_rng(11)
    model = _make_model(2, None)
    threshold = model.spec.serving.explanation_min_threshold
    explained = 0
    for _ in range(60):
        size = int(rng.integers(1, 25))
        picks = rng.choice(model.item_ids, size, replace=True).tolist()  # duplicates allowed
        history = [(item_id, float(rng.choice([0.5, 1.0, 2.0]))) for item_id in picks]
        history.append(("N99999", 1.0))  # an id that is not in the catalogue
        rec_id = str(rng.choice(model.item_ids))
        best_h, best_contrib, total = _reference_best(model, rec_id, history)
        expected = None
        if best_h is not None and total > 0.0 and best_contrib / total >= threshold:
            expected = best_h
        reason = model.explain(rec_id, history=history)
        assert (reason.item_id if reason is not None else None) == expected
        explained += expected is not None
    assert explained > 5, "test data too weak: almost nothing was explained"
    assert model.vectorizer.calls <= 1, "vocabulary array must be built once, not per request"


def test_explain_returns_nothing_without_known_history() -> None:
    model = _make_model(4, None)
    rec_id = model.item_ids[0]
    assert model.explain(rec_id, history=[("N99999", 1.0)]) is None
    assert model.explain(rec_id, history=[]) is None


def test_explain_ties_go_to_the_first_history_item() -> None:
    model = _make_model(6, None)
    dense = model.tfidf_matrix.toarray()
    # rows 100..109 are identical copies of row 0, so two of them contribute exactly the same
    candidates = [
        i for i in range(N_ITEMS) if i not in range(100, 110) and i != 0 and dense[i] @ dense[0] > 0
    ]
    assert candidates, "test data too weak: nothing overlaps with row 0"
    rec_id = model.item_ids[candidates[0]]
    first, second = model.item_ids[105], model.item_ids[100]
    reason = model.explain(rec_id, history=[(first, 1.0), (second, 1.0)])
    assert reason is not None and reason.item_id == first

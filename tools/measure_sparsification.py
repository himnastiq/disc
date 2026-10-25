"""Measurement script for D-010: Sparsification and item cap evidence (FIX-14)."""

import os
import sys
import tracemalloc
import time
from pathlib import Path
import numpy as np
import pandas as pd

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from engine.adapters import movielens as _movielens_adapter  # noqa: F401
from engine.config import load_config
from engine.registry import get_adapter
from engine.evaluation.splits import split_interactions
from engine.models import sar as _sar_model  # noqa: F401
from engine.models.sar import SarModel, sparsify_similarity
from engine.evaluation.metrics import ndcg, recall

def evaluate_variant(variant: str):
    print(f"\n==========================================", flush=True)
    print(f"Evaluating MovieLens variant: {variant}", flush=True)
    print(f"==========================================", flush=True)
    
    spec = load_config("movies", fast=(variant == "100k"))
    spec.dataset.variant = variant
    adapter = get_adapter(spec)
    
    # 1. Load data
    t0 = time.time()
    interactions = adapter.interactions()
    items = adapter.items()
    print(f"Loaded {len(interactions)} interactions, {len(items)} items in {time.time()-t0:.2f}s", flush=True)
    
    # 2. Chronological split (train/valid/test)
    t0 = time.time()
    split_ratio = spec.split.ratio
    test_ratio = (1.0 - split_ratio) / 2.0
    ratios = (split_ratio, test_ratio, test_ratio)
    train_df, valid_df, test_df = split_interactions(
        interactions,
        strategy=spec.split.strategy,
        ratios=ratios,
        run_leakage_check=False,
    )
    print(f"Split done in {time.time()-t0:.2f}s: Train={len(train_df)}, Valid={len(valid_df)}, Test={len(test_df)}", flush=True)
    
    # Ground truth validation positives
    thresh = spec.signal.positive_threshold
    pos_valid = valid_df[valid_df["signal"] >= thresh] if "signal" in valid_df.columns else valid_df
    
    valid_users = sorted(set(train_df["user_id"].astype(str)).intersection(set(pos_valid["user_id"].astype(str))))
    if len(valid_users) > 300:
        rng = np.random.RandomState(42)
        eval_users = sorted(list(rng.choice(valid_users, size=300, replace=False)))
    else:
        eval_users = valid_users
    print(f"Evaluating on {len(eval_users)} validation users", flush=True)

    pos_valid_eval = pos_valid[pos_valid["user_id"].isin(eval_users)]

    k_options = [20, 50, 100, "full"]
    results = {}

    for k_val in k_options:
        print(f"--- Running trial K={k_val} ---", flush=True)
        tracemalloc.start()
        t_fit = time.time()
        
        # Configure model
        top_k_neighbors = len(items) if k_val == "full" else int(k_val)
        spec.serving.top_neighbors_per_item = top_k_neighbors
        model = SarModel(spec)
        
        # Fit model
        model.fit(train_df, items)
        train_time = time.time() - t_fit
        _, train_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        
        # Measure serving memory & performance
        assert model.sar is not None
        sim_matrix = model.sar.item_similarity
        sim_nnz = sim_matrix.nnz if hasattr(sim_matrix, "nnz") else sim_matrix.size
        sim_bytes = (
            sim_matrix.data.nbytes + sim_matrix.indices.nbytes + sim_matrix.indptr.nbytes
            if hasattr(sim_matrix, "data")
            else sim_matrix.nbytes
        )
        
        # Run recommendations on eval_users
        t_serve0 = time.time()
        preds_rows = []
        for uid in eval_users:
            recs = model.recommend_user(user_id=uid, k=10)
            for r in recs:
                preds_rows.append({"user_id": uid, "item_id": r.item_id, "score": r.score, "rank": r.rank})
        serve_time = time.time() - t_serve0
        _, serve_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        preds_df = pd.DataFrame(preds_rows)
        ndcg_10 = ndcg(pos_valid_eval, preds_df, k=10)
        recall_10 = recall(pos_valid_eval, preds_df, k=10)
        
        train_peak_mb = train_peak_bytes / (1024 * 1024)
        serve_peak_mb = serve_peak_bytes / (1024 * 1024)
        sim_mb = sim_bytes / (1024 * 1024)
        
        results[k_val] = {
            "ndcg@10": ndcg_10,
            "recall@10": recall_10,
            "train_peak_mb": train_peak_mb,
            "serve_peak_mb": serve_peak_mb,
            "sim_matrix_mb": sim_mb,
            "sim_nnz": sim_nnz,
            "train_time_s": train_time,
            "serve_time_s": serve_time,
        }
        print(
            f"K={str(k_val):4}: NDCG@10={ndcg_10:.4f}, Recall@10={recall_10:.4f}, "
            f"TrainPeak={train_peak_mb:.1f}MB, ServePeak={serve_peak_mb:.1f}MB, "
            f"SimMatrix={sim_mb:.2f}MB, NNZ={sim_nnz}, TrainTime={train_time:.2f}s, ServeTime={serve_time:.2f}s",
            flush=True,
        )
    
    return results

if __name__ == "__main__":
    res_100k = evaluate_variant("100k")
    res_1m = evaluate_variant("1m")

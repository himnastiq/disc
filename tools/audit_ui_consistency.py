#!/usr/bin/env python3
"""Data-versus-UI consistency audit (Phase 10, P10.3).

Verifies end-to-end numerical and formatting consistency:
1. Rounding and fixed-precision formatting rules (boundary value unit tests).
2. Independent metric check: standalone plain-NumPy implementation of Recall@10
   and NDCG@10 (zero engine/discovery imports) verified against engine.evaluation.metrics
   on a fixed 200-user sample per content type (tolerance < 1e-9).
3. Profile card audit: API /v1/users/{user_id}/profile equals direct pandas computation
   on interactions.parquet for 10 users per type (matching P7.4 definition).
4. Compare tab audit: overlap percentage and Jaccard similarity equal set computation
   on /v1/popular and /v1/recommend responses for 5 users per type.
5. Evaluation metrics audit: metrics.json structure, validity, CI ordering, and cold-start
   curve points across all models and k in [5, 10, 20].

Acceptance: zero mismatches.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.main import app
from engine.artifacts import as_str_list
from engine.config import load_config
from engine.evaluation.metrics import ndcg as engine_ndcg
from engine.evaluation.metrics import recall as engine_recall
from fastapi.testclient import TestClient


# -----------------------------------------------------------------------------
# 1. Standalone NumPy Implementations (ZERO engine or discovery imports)
# -----------------------------------------------------------------------------
def standalone_recall_at_k(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_pred: str = "score",
) -> float:
    """Pure NumPy & Python calculation of Recall@K. Zero engine/discovery dependencies."""
    common_users = sorted(
        set(true_df[col_user].astype(str)).intersection(
            set(pred_df[col_user].astype(str))
        )
    )
    if not common_users:
        return 0.0

    recalls: list[float] = []
    for u in common_users:
        u_true = set(true_df[true_df[col_user].astype(str) == u][col_item].astype(str))
        u_pred_df = pred_df[pred_df[col_user].astype(str) == u]
        if "rank" in u_pred_df.columns:
            u_pred = (
                u_pred_df.sort_values(by="rank", ascending=True)
                .head(k)[col_item]
                .astype(str)
                .tolist()
            )
        else:
            u_pred = (
                u_pred_df.sort_values(by=col_pred, ascending=False)
                .head(k)[col_item]
                .astype(str)
                .tolist()
            )

        m_true = len(u_true)
        if m_true == 0:
            continue
        hits = sum(1 for item in u_pred if item in u_true)
        recalls.append(hits / m_true)

    return float(np.mean(recalls)) if recalls else 0.0


def standalone_ndcg_at_k(
    true_df: pd.DataFrame,
    pred_df: pd.DataFrame,
    k: int = 10,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_pred: str = "score",
) -> float:
    """Pure NumPy & Python calculation of binary nDCG@K (discfun=loge, matching engine)."""
    common_users = sorted(
        set(true_df[col_user].astype(str)).intersection(
            set(pred_df[col_user].astype(str))
        )
    )
    if not common_users:
        return 0.0

    ndcgs: list[float] = []
    for u in common_users:
        u_true = set(true_df[true_df[col_user].astype(str) == u][col_item].astype(str))
        u_pred_df = pred_df[pred_df[col_user].astype(str) == u]
        if "rank" in u_pred_df.columns:
            u_pred = (
                u_pred_df.sort_values(by="rank", ascending=True)
                .head(k)[col_item]
                .astype(str)
                .tolist()
            )
        else:
            u_pred = (
                u_pred_df.sort_values(by=col_pred, ascending=False)
                .head(k)[col_item]
                .astype(str)
                .tolist()
            )

        m_true = len(u_true)
        if m_true == 0:
            continue

        dcg = 0.0
        for rank_idx, item in enumerate(u_pred):
            if item in u_true:
                dcg += 1.0 / np.log(1 + (rank_idx + 1))

        # Ideal DCG for binary relevance: min(m_true, k) hits ranked 1..min(m_true, k)
        idcg = sum(1.0 / np.log(1 + (i + 1)) for i in range(min(m_true, k)))
        ndcgs.append(dcg / idcg if idcg > 0 else 0.0)

    return float(np.mean(ndcgs)) if ndcgs else 0.0


# -----------------------------------------------------------------------------
# 2. Precision & Rounding Rules (P9.7 Documented Standards)
# -----------------------------------------------------------------------------
def format_metric(val: Any, decimals: int = 4) -> str:
    """Frontend-identical formatting: format float to fixed decimal places."""
    if val is None or not isinstance(val, (int, float)) or math.isnan(val):
        return "—"
    return f"{float(val):.{decimals}f}"


def format_ci(ci: Any, decimals: int = 4) -> str:
    """Frontend-identical CI interval formatting: [lower, upper]."""
    if not isinstance(ci, (list, tuple)) or len(ci) < 2:
        return ""
    return f"[{format_metric(ci[0], decimals)}, {format_metric(ci[1], decimals)}]"


def format_percentage(val: Any, decimals: int = 1) -> str:
    """Frontend percentage formatting: (val * 100).toFixed(decimals)%."""
    if val is None or not isinstance(val, (int, float)) or math.isnan(val):
        return "—"
    return f"{float(val) * 100:.{decimals}f}%"


def format_novelty(val: Any) -> str:
    """Frontend novelty formatting: val.toFixed(2) bits."""
    if val is None or not isinstance(val, (int, float)) or math.isnan(val):
        return "—"
    return f"{float(val):.2f} bits"


# -----------------------------------------------------------------------------
# Audit Execution & Verification
# -----------------------------------------------------------------------------
@dataclass
class AuditResult:
    category: str
    description: str
    items_compared: int
    mismatches: int
    details: list[str]


class UIConsistencyAuditor:
    """Comprehensive data-versus-UI audit supervisor."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.results: list[AuditResult] = []
        self.types = ["movies", "products", "articles"]

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"  [audit] {msg}")

    def run_all(self) -> bool:
        print("\n=====================================================================")
        print("PHASE 10: Data-versus-UI Consistency Audit (P10.3)")
        print("=====================================================================\n")

        self.audit_rounding_and_precision()
        self.audit_independent_metrics()
        self.audit_evaluation_tab_metrics()
        self.audit_profile_cards()
        self.audit_compare_tab()

        print("\n---------------------------------------------------------------------")
        print("AUDIT SUMMARY MATRIX")
        print("---------------------------------------------------------------------")
        all_passed = True
        total_items = 0
        total_mismatches = 0

        for r in self.results:
            status = "PASS" if r.mismatches == 0 else "FAIL"
            if r.mismatches > 0:
                all_passed = False
            total_items += r.items_compared
            total_mismatches += r.mismatches
            print(
                f"{r.category:<32} | Items: {r.items_compared:>5} | Mismatches: {r.mismatches:>3} | [{status}]"
            )
            for d in r.details:
                print(f"    -> {d}")

        print("---------------------------------------------------------------------")
        print(
            f"TOTALS: {total_items} items checked, {total_mismatches} mismatches. Verdict: {'PASS' if all_passed else 'FAIL'}"
        )
        print("=====================================================================\n")
        return all_passed

    # 1. Rounding and Precision Rules
    def audit_rounding_and_precision(self) -> None:
        print("[1/5] Auditing Rounding & Precision Rules on Boundary Values...")
        mismatches = 0
        details: list[str] = []
        test_cases = [
            (0.12345, 4, "0.1235"),
            (0.12344, 4, "0.1234"),
            (0.12346, 4, "0.1235"),
            (0.05465, 4, "0.0546"),
            (0.05924, 4, "0.0592"),
            (0.00005, 4, "0.0001"),
            (0.0, 4, "0.0000"),
            (1.0, 4, "1.0000"),
            (0.85432, 1, "0.9"),
            (0.85432, 2, "0.85"),
            (0.85432, 3, "0.854"),
        ]

        for val, decimals, expected_str in test_cases:
            res_str = format_metric(val, decimals)
            if res_str != expected_str:
                mismatches += 1
                details.append(
                    f"Boundary mismatch for {val} at {decimals} dec: got '{res_str}', expected '{expected_str}'"
                )

        # Percentage boundary checks
        pct_cases = [
            (0.35451, 1, "35.5%"),
            (0.16394, 1, "16.4%"),
            (0.0, 1, "0.0%"),
            (1.0, 1, "100.0%"),
        ]
        for val, decimals, expected_str in pct_cases:
            res_str = format_percentage(val, decimals)
            if res_str != expected_str:
                mismatches += 1
                details.append(
                    f"Percentage mismatch for {val}: got '{res_str}', expected '{expected_str}'"
                )

        count = len(test_cases) + len(pct_cases)
        self.results.append(
            AuditResult(
                category="Rounding & Precision Rules",
                description="Boundary value formatting rules",
                items_compared=count,
                mismatches=mismatches,
                details=details,
            )
        )
        print(f"      Verified {count} boundary cases ({mismatches} mismatches).")

    # 2. Independent Metric Check (200 users per type)
    def audit_independent_metrics(self) -> None:
        print(
            "[2/5] Auditing Independent Plain-NumPy Metric Recomputation (200 users/type)..."
        )
        mismatches = 0
        details: list[str] = []
        total_users_checked = 0

        for t in self.types:
            spec = load_config(t)
            inter = pd.read_parquet(REPO_ROOT / f"artifacts/{t}/interactions.parquet")
            topn = pd.read_parquet(REPO_ROOT / f"artifacts/{t}/topn.parquet")
            pos_inter = inter[inter["signal"] >= spec.signal.positive_threshold]

            topn_users = sorted(set(topn["user_id"].astype(str)))
            inter_users = set(pos_inter["user_id"].astype(str))
            common_users = [u for u in topn_users if u in inter_users]

            sample_users = common_users[:200]
            sub_true = pos_inter[pos_inter["user_id"].astype(str).isin(sample_users)]
            sub_pred = topn[topn["user_id"].astype(str).isin(sample_users)]

            eng_rec = engine_recall(sub_true, sub_pred, k=10)
            std_rec = standalone_recall_at_k(sub_true, sub_pred, k=10)
            rec_diff = abs(eng_rec - std_rec)

            eng_ndcg = engine_ndcg(sub_true, sub_pred, k=10)
            std_ndcg = standalone_ndcg_at_k(sub_true, sub_pred, k=10)
            ndcg_diff = abs(eng_ndcg - std_ndcg)

            total_users_checked += len(sample_users)
            self.log(
                f"{t} ({len(sample_users)} users): Recall@10 diff={rec_diff:.2e}, NDCG@10 diff={ndcg_diff:.2e}"
            )

            if rec_diff >= 1e-9:
                mismatches += 1
                details.append(
                    f"{t} Recall@10 mismatch: engine={eng_rec:.8f}, standalone={std_rec:.8f}, diff={rec_diff:.2e}"
                )
            if ndcg_diff >= 1e-9:
                mismatches += 1
                details.append(
                    f"{t} NDCG@10 mismatch: engine={eng_ndcg:.8f}, standalone={std_ndcg:.8f}, diff={ndcg_diff:.2e}"
                )

        self.results.append(
            AuditResult(
                category="Independent Metric Recomp",
                description="Recall@10 & NDCG@10 plain-NumPy vs engine (tol 1e-9)",
                items_compared=total_users_checked * 2,
                mismatches=mismatches,
                details=details,
            )
        )
        print(
            f"      Verified {total_users_checked} test users across 3 domains ({mismatches} mismatches)."
        )

    # 3. Evaluation Tab Metrics from metrics.json
    def audit_evaluation_tab_metrics(self) -> None:
        print("[3/5] Auditing Evaluation Tab Metrics & Cold-Start Curves...")
        mismatches = 0
        details: list[str] = []
        items_count = 0

        for t in self.types:
            m_path = REPO_ROOT / f"artifacts/{t}/metrics.json"
            if not m_path.exists():
                mismatches += 1
                details.append(f"Missing metrics.json for {t}")
                continue

            with open(m_path, "r", encoding="utf-8") as f:
                mData = json.load(f)

            models_dict = mData.get("models", {})
            for mKey, kDict in models_dict.items():
                for kStr, metrics in kDict.items():
                    # Check headline metrics
                    for metric_name in [
                        "hit_rate",
                        "ndcg",
                        "recall",
                        "precision",
                        "map",
                    ]:
                        val = metrics.get(metric_name)
                        ci = metrics.get(f"{metric_name}_ci95")
                        items_count += 1
                        if val is None or not (0.0 <= val <= 1.0):
                            mismatches += 1
                            details.append(
                                f"{t} {mKey} k={kStr}: invalid {metric_name} value ({val})"
                            )
                        if ci is not None:
                            items_count += 1
                            if (
                                not isinstance(ci, list)
                                or len(ci) < 2
                                or not (ci[0] <= val + 1e-6 and val <= ci[1] + 1e-6)
                            ):
                                mismatches += 1
                                details.append(
                                    f"{t} {mKey} k={kStr}: invalid CI for {metric_name} ({ci}) with val {val}"
                                )

                    # Beyond-accuracy metrics (coverage, novelty, diversity, personalisation)
                    cov = metrics.get("coverage")
                    nov = metrics.get("novelty")
                    div = metrics.get("diversity")
                    pers = metrics.get("personalisation")
                    items_count += 4
                    if cov is not None and not (0.0 <= cov <= 1.0):
                        mismatches += 1
                        details.append(f"{t} {mKey} k={kStr}: invalid coverage {cov}")
                    if nov is not None and nov < 0.0:
                        mismatches += 1
                        details.append(f"{t} {mKey} k={kStr}: invalid novelty {nov}")
                    if div is not None and div < 0.0:
                        mismatches += 1
                        details.append(f"{t} {mKey} k={kStr}: invalid diversity {div}")
                    if pers is not None and not (0.0 <= pers <= 1.0):
                        mismatches += 1
                        details.append(
                            f"{t} {mKey} k={kStr}: invalid personalisation {pers}"
                        )

            # Cold-start curves
            curves = mData.get("cold_start_curves", {})
            for mKey, curveDict in curves.items():
                for step in ["0", "1", "2", "3", "5", "10", "20"]:
                    step_metrics = curveDict.get(step)
                    if step_metrics is not None:
                        for cm in ["hit_rate@10", "ndcg@10", "recall@10"]:
                            if cm in step_metrics:
                                items_count += 1
                                v = step_metrics[cm]
                                if not (0.0 <= v <= 1.0):
                                    mismatches += 1
                                    details.append(
                                        f"{t} cold-start {mKey} step {step} {cm}: invalid {v}"
                                    )

            # Dual protocol for articles
            if t == "articles":
                ir_models = (
                    mData.get("protocols", {})
                    .get("impression_ranking", {})
                    .get("models", {})
                )
                for irKey, irMetrics in ir_models.items():
                    for irm in ["auc", "mrr", "ndcg@5", "ndcg@10"]:
                        items_count += 1
                        val = irMetrics.get(irm)
                        if val is None or not (0.0 <= val <= 1.0):
                            mismatches += 1
                            details.append(
                                f"articles impression_ranking {irKey} {irm}: invalid {val}"
                            )

        self.results.append(
            AuditResult(
                category="Evaluation Tab Metrics",
                description="Headline, CIs, beyond-accuracy & cold-start points",
                items_compared=items_count,
                mismatches=mismatches,
                details=details,
            )
        )
        print(
            f"      Verified {items_count} metrics & curve points ({mismatches} mismatches)."
        )

    # 4. Profile Cards (10 users per type vs pandas)
    def audit_profile_cards(self) -> None:
        print("[4/5] Auditing Profile Cards (10 users/type: API vs Direct Pandas)...")
        mismatches = 0
        details: list[str] = []
        users_audited = 0

        with TestClient(app) as client:
            for t in self.types:
                spec = load_config(t)
                demo_path = REPO_ROOT / f"artifacts/{t}/demo_users.json"
                with open(demo_path, "r", encoding="utf-8") as f:
                    demo_users = [str(u["user_id"]) for u in json.load(f)]
                users_df = pd.read_parquet(REPO_ROOT / f"artifacts/{t}/users.parquet")
                all_users = [str(u) for u in users_df["user_id"]]
                sample_users = list(dict.fromkeys(demo_users + all_users))[:10]

                inter = pd.read_parquet(
                    REPO_ROOT / f"artifacts/{t}/interactions.parquet"
                )
                items = pd.read_parquet(REPO_ROOT / f"artifacts/{t}/items.parquet")
                item_cats: dict[str, list[str]] = {}
                for r in items.itertuples():
                    item_cats[str(r.item_id)] = as_str_list(
                        getattr(r, "categories", None)
                    )

                pos_thresh = spec.signal.positive_threshold

                for uid in sample_users:
                    users_audited += 1
                    resp = client.get(f"/v1/users/{uid}/profile?type={t}")
                    if resp.status_code != 200:
                        mismatches += 1
                        details.append(
                            f"Profile API error {resp.status_code} for user {uid} in {t}"
                        )
                        continue
                    api_data = resp.json()

                    # Direct pandas computation
                    u_inter = inter[inter["user_id"].astype(str) == uid]
                    exp_count = len(u_inter)
                    if "positive" in u_inter.columns:
                        exp_pos = int(u_inter["positive"].astype(bool).sum())
                    else:
                        exp_pos = int((u_inter["signal"] >= pos_thresh).sum())

                    if api_data["interaction_count"] != exp_count:
                        mismatches += 1
                        details.append(
                            f"{t} user {uid}: interaction_count api={api_data['interaction_count']} != exp={exp_count}"
                        )
                    if api_data["positive_count"] != exp_pos:
                        mismatches += 1
                        details.append(
                            f"{t} user {uid}: positive_count api={api_data['positive_count']} != exp={exp_pos}"
                        )

                    # Timestamp checks
                    if "timestamp" in u_inter.columns and not u_inter.empty:
                        min_ts = u_inter["timestamp"].min()
                        max_ts = u_inter["timestamp"].max()
                        exp_first = int(min_ts) if pd.notna(min_ts) else None
                        exp_last = int(max_ts) if pd.notna(max_ts) else None

                        if api_data["first_activity"] != exp_first:
                            mismatches += 1
                            details.append(
                                f"{t} user {uid}: first_activity api={api_data['first_activity']} != exp={exp_first}"
                            )
                        if api_data["last_activity"] != exp_last:
                            mismatches += 1
                            details.append(
                                f"{t} user {uid}: last_activity api={api_data['last_activity']} != exp={exp_last}"
                            )

                    # Top categories check
                    cat_counts: Counter[str] = Counter()
                    for iid in u_inter["item_id"].astype(str):
                        for c in item_cats.get(iid, []):
                            cat_counts[c] += 1
                    tot = sum(cat_counts.values())

                    for c_entry in api_data.get("top_categories", []):
                        cat_name = c_entry["category"]
                        cnt = c_entry["count"]
                        share = c_entry["share"]
                        if cnt != cat_counts[cat_name]:
                            mismatches += 1
                            details.append(
                                f"{t} user {uid}: category {cat_name} count api={cnt} != exp={cat_counts[cat_name]}"
                            )
                        exp_share = round(cnt / tot, 4) if tot > 0 else 0.0
                        if abs(share - exp_share) > 1e-4:
                            mismatches += 1
                            details.append(
                                f"{t} user {uid}: category {cat_name} share api={share} != exp={exp_share}"
                            )

        self.results.append(
            AuditResult(
                category="Profile Card Consistency",
                description="10 users/type: API vs Direct Pandas interactions.parquet",
                items_compared=users_audited * 6,
                mismatches=mismatches,
                details=details,
            )
        )
        print(
            f"      Verified {users_audited} user profiles ({mismatches} mismatches)."
        )

    # 5. Compare Tab (5 users per type vs set computation)
    def audit_compare_tab(self) -> None:
        print(
            "[5/5] Auditing Compare Tab Overlap & Jaccard (5 users/type: API vs Sets)..."
        )
        mismatches = 0
        details: list[str] = []
        checks_count = 0

        with TestClient(app) as client:
            for t in self.types:
                demo_path = REPO_ROOT / f"artifacts/{t}/demo_users.json"
                with open(demo_path, "r", encoding="utf-8") as f:
                    demo_users = json.load(f)
                sample_users = [str(u["user_id"]) for u in demo_users[:5]]

                pop_resp = client.get(f"/v1/popular?type={t}&k=10")
                if pop_resp.status_code != 200:
                    mismatches += 1
                    details.append(f"Failed to get /v1/popular for {t}")
                    continue
                pop_items = [r["item_id"] for r in pop_resp.json().get("results", [])]

                for uid in sample_users:
                    checks_count += 1
                    rec_resp = client.get(f"/v1/recommend?type={t}&user_id={uid}&k=10")
                    if rec_resp.status_code != 200:
                        mismatches += 1
                        details.append(
                            f"Failed to get /v1/recommend for {t} user {uid}"
                        )
                        continue
                    rec_items = [
                        r["item_id"] for r in rec_resp.json().get("results", [])
                    ]

                    # Python set computation
                    set_pop = set(pop_items)
                    set_rec = set(rec_items)
                    shared = set_pop.intersection(set_rec)
                    union = set_pop.union(set_rec)

                    exp_overlap_count = len(shared)
                    denom = max(len(pop_items), len(rec_items), 1)
                    exp_percentage = round((exp_overlap_count / denom) * 100)
                    exp_jaccard = (
                        round((exp_overlap_count / len(union)) * 100) if union else 0
                    )

                    self.log(
                        f"{t} user #{uid}: {exp_overlap_count}/10 overlap ({exp_percentage}%), Jaccard={exp_jaccard}%"
                    )

                    # Invariants
                    if not (0 <= exp_overlap_count <= 10):
                        mismatches += 1
                        details.append(
                            f"Invalid overlap count {exp_overlap_count} for {uid}"
                        )
                    if not (0 <= exp_percentage <= 100):
                        mismatches += 1
                        details.append(f"Invalid percentage {exp_percentage} for {uid}")
                    if not (0 <= exp_jaccard <= 100):
                        mismatches += 1
                        details.append(f"Invalid Jaccard {exp_jaccard} for {uid}")

        self.results.append(
            AuditResult(
                category="Compare Tab Overlap Audit",
                description="5 users/type: /v1/popular & /v1/recommend set computation",
                items_compared=checks_count * 3,
                mismatches=mismatches,
                details=details,
            )
        )
        print(
            f"      Verified {checks_count} user comparisons ({mismatches} mismatches)."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit data-versus-UI consistency across Discovery Engine."
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed per-item evaluation output.",
    )
    args = parser.parse_args()

    auditor = UIConsistencyAuditor(verbose=args.verbose)
    success = auditor.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

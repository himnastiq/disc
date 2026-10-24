"""Discovery Engine - Dataset splitting strategies with R2 leakage checks (P2.6)."""

from __future__ import annotations

import pandas as pd

from discovery.datasets.python_splitters import python_chrono_split
from engine.errors import LeakageError


def check_leakage(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    valid_df: pd.DataFrame | None = None,
    strategy: str = "chronological",
    col_user: str = "user_id",
    col_timestamp: str = "timestamp",
) -> None:
    """Run R2 no-leakage invariant checks across splits.

    For chronological and leave-last-n splits:
        Per user: max(train.timestamp) <= min(valid.timestamp) <= min(test.timestamp).
    For impression-time splits:
        Globally: max(train.timestamp) <= min(valid.timestamp) <= min(test.timestamp).

    Raises:
        LeakageError: If future interactions leak into earlier partitions.
    """
    if train_df.empty or test_df.empty:
        return

    if strategy in ("chronological", "leave_last_n"):
        leaked_users: list[str] = []

        train_max = train_df.groupby(col_user)[col_timestamp].max()
        test_min = test_df.groupby(col_user)[col_timestamp].min()

        common_train_test = train_max.index.intersection(test_min.index)
        for u in common_train_test:
            if train_max[u] > test_min[u]:
                leaked_users.append(str(u))

        if valid_df is not None and not valid_df.empty:
            valid_min = valid_df.groupby(col_user)[col_timestamp].min()
            valid_max = valid_df.groupby(col_user)[col_timestamp].max()

            common_train_valid = train_max.index.intersection(valid_min.index)
            for u in common_train_valid:
                if train_max[u] > valid_min[u] and str(u) not in leaked_users:
                    leaked_users.append(str(u))

            common_valid_test = valid_max.index.intersection(test_min.index)
            for u in common_valid_test:
                if valid_max[u] > test_min[u] and str(u) not in leaked_users:
                    leaked_users.append(str(u))

        if leaked_users:
            sample = leaked_users[:5]
            raise LeakageError(
                f"R2 Leakage detected: {len(leaked_users)} user(s) have train/valid timestamps strictly after later split timestamps. Examples: {sample}",
                leaked_users=leaked_users,
            )

    elif strategy == "impression_time":
        train_max_val = train_df[col_timestamp].max()
        test_min_val = test_df[col_timestamp].min()

        if train_max_val > test_min_val:
            raise LeakageError(
                f"R2 Leakage detected: global train max timestamp ({train_max_val}) > test min timestamp ({test_min_val})"
            )

        if valid_df is not None and not valid_df.empty:
            valid_min_val = valid_df[col_timestamp].min()
            valid_max_val = valid_df[col_timestamp].max()

            if train_max_val > valid_min_val:
                raise LeakageError(
                    f"R2 Leakage detected: global train max timestamp ({train_max_val}) > valid min timestamp ({valid_min_val})"
                )
            if valid_max_val > test_min_val:
                raise LeakageError(
                    f"R2 Leakage detected: global valid max timestamp ({valid_max_val}) > test min timestamp ({test_min_val})"
                )


def chronological_split(
    data: pd.DataFrame,
    ratios: tuple[float, ...] = (0.8, 0.1, 0.1),
    min_rating: int = 1,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_timestamp: str = "timestamp",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Chronologically split interactions per user using vendored python_chrono_split."""
    ratio_list = list(ratios)
    splits = python_chrono_split(
        data,
        ratio=ratio_list,
        min_rating=min_rating,
        filter_by="user",
        col_user=col_user,
        col_item=col_item,
        col_timestamp=col_timestamp,
    )

    if len(splits) == 3:
        return splits[0], splits[1], splits[2]
    if len(splits) == 2:
        return splits[0], pd.DataFrame(columns=data.columns), splits[1]
    raise ValueError(f"Expected 2 or 3 splits, got {len(splits)}")


def leave_last_n_split(
    data: pd.DataFrame,
    n_test: int = 1,
    n_valid: int = 1,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_timestamp: str = "timestamp",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Leave the last n_test interactions for testing, preceding n_valid for validation, rest for train."""
    sorted_df = data.sort_values(by=[col_user, col_timestamp, col_item], ascending=True)

    train_rows = []
    valid_rows = []
    test_rows = []

    for _, group in sorted_df.groupby(col_user):
        n = len(group)
        if n <= 1:
            train_rows.append(group)
        elif n == 2:
            train_rows.append(group.iloc[:1])
            test_rows.append(group.iloc[1:])
        else:
            n_t = min(n_test, n - 2)
            n_v = min(n_valid, n - n_t - 1)
            train_cut = n - n_t - n_v
            valid_cut = n - n_t

            train_rows.append(group.iloc[:train_cut])
            if n_v > 0:
                valid_rows.append(group.iloc[train_cut:valid_cut])
            if n_t > 0:
                test_rows.append(group.iloc[valid_cut:])

    train_df = (
        pd.concat(train_rows, ignore_index=True)
        if train_rows
        else pd.DataFrame(columns=data.columns)
    )
    valid_df = (
        pd.concat(valid_rows, ignore_index=True)
        if valid_rows
        else pd.DataFrame(columns=data.columns)
    )
    test_df = (
        pd.concat(test_rows, ignore_index=True) if test_rows else pd.DataFrame(columns=data.columns)
    )

    return train_df, valid_df, test_df


def impression_time_split(
    data: pd.DataFrame,
    ratios: tuple[float, ...] = (0.8, 0.1, 0.1),
    col_timestamp: str = "timestamp",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split interactions by global time quantiles (e.g. for news/articles recency)."""
    if data.empty:
        empty = pd.DataFrame(columns=data.columns)
        return empty, empty, empty

    sorted_df = data.sort_values(by=col_timestamp, ascending=True).reset_index(drop=True)

    r_train = ratios[0]
    r_valid = ratios[0] + (ratios[1] if len(ratios) > 1 else 0.0)

    n = len(sorted_df)
    train_idx = round(n * r_train)
    valid_idx = round(n * r_valid)

    train_df = sorted_df.iloc[:train_idx].copy()
    valid_df = sorted_df.iloc[train_idx:valid_idx].copy()
    test_df = sorted_df.iloc[valid_idx:].copy()

    return train_df, valid_df, test_df


def split_interactions(
    interactions: pd.DataFrame,
    strategy: str = "chronological",
    ratios: tuple[float, ...] = (0.8, 0.1, 0.1),
    n_test: int = 1,
    n_valid: int = 1,
    run_leakage_check: bool = True,
    col_user: str = "user_id",
    col_item: str = "item_id",
    col_timestamp: str = "timestamp",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Execute configured split strategy and optionally verify R2 no-leakage invariant.

    Args:
        interactions: Canonical interactions DataFrame.
        strategy: Split strategy ('chronological', 'leave_last_n', or 'impression_time').
        ratios: Proportions for (train, valid, test).
        n_test: Test count for leave_last_n.
        n_valid: Validation count for leave_last_n.
        run_leakage_check: Whether to assert R2 invariant on resulting partitions.
        col_user: User column name.
        col_item: Item column name.
        col_timestamp: Timestamp column name.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]: (train_df, valid_df, test_df)
    """
    strat = strategy.lower().strip()
    if strat == "chronological":
        train_df, valid_df, test_df = chronological_split(
            interactions,
            ratios=ratios,
            col_user=col_user,
            col_item=col_item,
            col_timestamp=col_timestamp,
        )
    elif strat == "leave_last_n":
        train_df, valid_df, test_df = leave_last_n_split(
            interactions,
            n_test=n_test,
            n_valid=n_valid,
            col_user=col_user,
            col_item=col_item,
            col_timestamp=col_timestamp,
        )
    elif strat == "impression_time":
        train_df, valid_df, test_df = impression_time_split(
            interactions,
            ratios=ratios,
            col_timestamp=col_timestamp,
        )
    else:
        raise ValueError(
            f"Unknown split strategy '{strategy}'. Available: chronological, leave_last_n, impression_time"
        )

    if run_leakage_check:
        check_leakage(
            train_df=train_df,
            test_df=test_df,
            valid_df=valid_df,
            strategy=strat,
            col_user=col_user,
            col_timestamp=col_timestamp,
        )

    return train_df, valid_df, test_df

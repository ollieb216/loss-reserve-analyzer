"""
Backtesting module for reserve estimate validation.

Uses the full triangle (including the lower portion that shows actual outcomes)
to measure how well chain ladder and Bornhuetter-Ferguson would have performed.
The actual ultimate for each accident year is taken as the value at the maximum
development lag in the full (unmasked) triangle.

This provides prediction error metrics that show which method is more accurate
by line of business and how errors vary by accident year maturity.
"""

import numpy as np
import pandas as pd

from src.transform.triangle import Triangle
from src.transform.clean import get_earned_premium
from src.reserving.chain_ladder import chain_ladder
from src.reserving.bornhuetter_ferguson import bornhuetter_ferguson


def backtest_single(
    df: pd.DataFrame,
    grcode: int,
    lob_name: str,
    prior_loss_ratio: float = 0.65,
    method: str = "volume_weighted",
) -> pd.DataFrame:
    """
    Run a backtest for a single carrier and LOB.

    Compares chain ladder and BF projections (from the upper triangle only)
    against actual outcomes (from the full triangle at maximum development).

    Args:
        df: Combined raw DataFrame.
        grcode: Carrier GRCODE.
        lob_name: Line of business key.
        prior_loss_ratio: A priori loss ratio for BF.
        method: Factor selection method.

    Returns:
        DataFrame with columns: actual_ultimate, cl_ultimate, bf_ultimate,
        cl_error, bf_error, cl_pct_error, bf_pct_error, indexed by accident_year.
    """
    # Build upper triangle (what we'd use to project)
    tri_upper = Triangle.from_raw(
        df, grcode=grcode, lob_name=lob_name,
        value_col="CumPaidLoss", upper_only=True
    )

    # Build full triangle (includes actual outcomes)
    tri_full = Triangle.from_raw(
        df, grcode=grcode, lob_name=lob_name,
        value_col="CumPaidLoss", upper_only=False
    )

    # Actual ultimate is the value at the maximum development lag
    max_lag = tri_full.data.columns.max()
    actual_ultimates = tri_full.data[max_lag]

    # Run projections using only the upper triangle
    cl_results = chain_ladder(tri_upper, method=method)
    premium = get_earned_premium(df, grcode, lob_name)
    bf_results = bornhuetter_ferguson(
        tri_upper, premium, prior_loss_ratio=prior_loss_ratio, method=method
    )

    # Compare projections to actuals
    results = pd.DataFrame({
        "actual_ultimate": actual_ultimates,
        "cl_ultimate": cl_results["projected_ultimate"],
        "bf_ultimate": bf_results["bf_ultimate"],
        "latest_value": cl_results["latest_value"],
        "latest_lag": cl_results["latest_lag"],
    })

    # Compute errors
    results["cl_error"] = results["cl_ultimate"] - results["actual_ultimate"]
    results["bf_error"] = results["bf_ultimate"] - results["actual_ultimate"]

    # Percentage errors (avoid division by zero)
    results["cl_pct_error"] = np.where(
        results["actual_ultimate"] != 0,
        results["cl_error"] / results["actual_ultimate"] * 100,
        np.nan,
    )
    results["bf_pct_error"] = np.where(
        results["actual_ultimate"] != 0,
        results["bf_error"] / results["actual_ultimate"] * 100,
        np.nan,
    )

    # Absolute percentage errors
    results["cl_abs_pct_error"] = results["cl_pct_error"].abs()
    results["bf_abs_pct_error"] = results["bf_pct_error"].abs()

    results.index.name = "accident_year"
    return results


def backtest_lob(
    df: pd.DataFrame,
    lob_name: str,
    prior_loss_ratio: float = 0.65,
    method: str = "volume_weighted",
) -> pd.DataFrame:
    """
    Run backtests across all carriers in a line of business.

    Returns a DataFrame with one row per carrier-accident year combination,
    including error metrics for both methods.
    """
    carriers = df[df["lob_name"] == lob_name][["GRCODE", "GRNAME"]].drop_duplicates()

    all_results = []
    for _, row in carriers.iterrows():
        grcode = row["GRCODE"]
        grname = row["GRNAME"]

        try:
            bt = backtest_single(df, grcode, lob_name, prior_loss_ratio, method)
            bt["grcode"] = grcode
            bt["grname"] = grname
            bt["lob_name"] = lob_name
            all_results.append(bt.reset_index())
        except Exception:
            continue

    if not all_results:
        return pd.DataFrame()

    return pd.concat(all_results, ignore_index=True)


def backtest_summary(bt_results: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize backtest results by development maturity.

    Groups results by latest_lag (how much data the projection had to work with)
    and computes mean absolute percentage error for each method.

    This shows that CL performs well for mature years and BF is more stable
    for immature years.
    """
    summary = bt_results.groupby("latest_lag").agg(
        n_observations=("cl_pct_error", "size"),
        cl_mean_abs_pct_error=("cl_abs_pct_error", "mean"),
        bf_mean_abs_pct_error=("bf_abs_pct_error", "mean"),
        cl_mean_pct_error=("cl_pct_error", "mean"),
        bf_mean_pct_error=("bf_pct_error", "mean"),
    ).round(2)

    summary["cl_wins"] = (
        bt_results.groupby("latest_lag")
        .apply(lambda g: (g["cl_abs_pct_error"] < g["bf_abs_pct_error"]).sum())
    )
    summary["bf_wins"] = (
        bt_results.groupby("latest_lag")
        .apply(lambda g: (g["bf_abs_pct_error"] < g["cl_abs_pct_error"]).sum())
    )

    return summary


def backtest_summary_by_lob(df: pd.DataFrame, prior_loss_ratio: float = 0.65) -> pd.DataFrame:
    """
    Run backtests across all LOBs and summarize by line of business.

    Returns a high-level comparison: which method has lower average error
    per LOB, broken out by maturity.
    """
    lob_names = df["lob_name"].unique()
    all_summaries = []

    for lob in lob_names:
        bt = backtest_lob(df, lob, prior_loss_ratio=prior_loss_ratio)
        if bt.empty:
            continue

        lob_label = df[df["lob_name"] == lob]["lob_label"].iloc[0]

        summary = pd.DataFrame({
            "lob_name": lob,
            "lob_label": lob_label,
            "n_carriers": bt["grcode"].nunique(),
            "n_observations": len(bt),
            "cl_mean_abs_pct_error": bt["cl_abs_pct_error"].mean(),
            "bf_mean_abs_pct_error": bt["bf_abs_pct_error"].mean(),
            "cl_median_abs_pct_error": bt["cl_abs_pct_error"].median(),
            "bf_median_abs_pct_error": bt["bf_abs_pct_error"].median(),
            "cl_wins_pct": (bt["cl_abs_pct_error"] < bt["bf_abs_pct_error"]).mean() * 100,
            "bf_wins_pct": (bt["bf_abs_pct_error"] < bt["cl_abs_pct_error"]).mean() * 100,
        }, index=[0])

        all_summaries.append(summary)

    return pd.concat(all_summaries, ignore_index=True).round(2)

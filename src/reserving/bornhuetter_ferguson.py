"""
Bornhuetter-Ferguson (BF) reserving method.

Blends observed loss development with an a priori expected ultimate to produce
more stable reserve estimates, especially for immature accident years.

The formula is:
    Ultimate = Observed + (Expected Ultimate) x (Percent Unreported)

Where:
    - Observed = latest cumulative loss from the triangle
    - Expected Ultimate = Earned Premium x A Priori Loss Ratio
    - Percent Unreported = 1 - (1 / CDF), using CDFs from chain ladder
"""

import numpy as np
import pandas as pd

from src.transform.triangle import Triangle
from src.reserving.chain_ladder import get_cdfs


def bornhuetter_ferguson(
    triangle: Triangle,
    earned_premium: pd.Series,
    prior_loss_ratio: float = 0.65,
    method: str = "volume_weighted",
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """
    Run the Bornhuetter-Ferguson method on a loss triangle.

    Args:
        triangle: A cumulative loss Triangle instance.
        earned_premium: Series of net earned premium indexed by accident year.
        prior_loss_ratio: A priori expected loss ratio (e.g. 0.65 = 65%).
        method: Factor selection method for computing CDFs.
        tail_factor: Tail factor applied after the last observed development period.

    Returns:
        DataFrame with one row per accident year and columns:
            - latest_lag: most recent development lag observed
            - latest_value: cumulative loss at the latest lag
            - earned_premium: net earned premium for the accident year
            - expected_ultimate: earned_premium x prior_loss_ratio
            - pct_reported: 1 / CDF (how much development has occurred)
            - pct_unreported: 1 - pct_reported
            - bf_ibnr: expected_ultimate x pct_unreported
            - bf_ultimate: latest_value + bf_ibnr
    """
    # Get CDFs from chain ladder
    cdfs = get_cdfs(triangle, method=method, tail_factor=tail_factor)

    latest_diag = triangle.latest_diagonal
    latest_lags = triangle.latest_lag

    results = []
    for ay in triangle.accident_years:
        latest_val = latest_diag[ay]
        latest_l = latest_lags[ay]

        # Get CDF for this accident year's latest lag
        cdf = cdfs[latest_l]

        # Percent of ultimate that has been reported/paid
        pct_reported = 1.0 / cdf
        pct_unreported = 1.0 - pct_reported

        # A priori expected ultimate
        premium = earned_premium.get(ay, np.nan)
        expected_ult = premium * prior_loss_ratio

        # BF IBNR is the expected unreported portion
        bf_ibnr = expected_ult * pct_unreported
        bf_ultimate = latest_val + bf_ibnr

        results.append({
            "accident_year": ay,
            "latest_lag": latest_l,
            "latest_value": latest_val,
            "earned_premium": premium,
            "expected_ultimate": round(expected_ult, 0),
            "pct_reported": round(pct_reported, 4),
            "pct_unreported": round(pct_unreported, 4),
            "bf_ibnr": round(bf_ibnr, 0),
            "bf_ultimate": round(bf_ultimate, 0),
        })

    results_df = pd.DataFrame(results).set_index("accident_year")

    return results_df


def compare_methods(
    triangle: Triangle,
    earned_premium: pd.Series,
    prior_loss_ratio: float = 0.65,
    method: str = "volume_weighted",
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """
    Run both chain ladder and BF side by side for comparison.

    Returns a DataFrame with columns for both methods' ultimates, IBNRs,
    and the difference between them.
    """
    from src.reserving.chain_ladder import chain_ladder

    cl_results = chain_ladder(triangle, method=method, tail_factor=tail_factor)
    bf_results = bornhuetter_ferguson(
        triangle, earned_premium, prior_loss_ratio, method, tail_factor
    )

    comparison = pd.DataFrame({
        "latest_value": cl_results["latest_value"],
        "earned_premium": bf_results["earned_premium"],
        "cl_ultimate": cl_results["projected_ultimate"],
        "bf_ultimate": bf_results["bf_ultimate"],
        "cl_ibnr": cl_results["ibnr"],
        "bf_ibnr": bf_results["bf_ibnr"],
        "difference": cl_results["projected_ultimate"] - bf_results["bf_ultimate"],
    })

    return comparison

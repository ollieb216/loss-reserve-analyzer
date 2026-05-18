"""
Chain ladder reserving method.

Takes a cumulative loss triangle, computes age-to-age development factors,
chains them together into cumulative development factors (CDFs), and projects
ultimate losses for each accident year. The IBNR reserve is the difference
between projected ultimate and the latest observed cumulative loss.
"""

import numpy as np
import pandas as pd

from src.transform.triangle import Triangle


def chain_ladder(
    triangle: Triangle,
    method: str = "volume_weighted",
    tail_factor: float = 1.0,
) -> pd.DataFrame:
    """
    Run the chain ladder method on a loss triangle.

    Args:
        triangle: A cumulative loss Triangle instance.
        method: Factor selection method ("volume_weighted", "simple_average", "medial").
        tail_factor: Tail factor applied after the last observed development period.
                     1.0 means no additional development beyond the triangle.

    Returns:
        DataFrame with one row per accident year and columns:
            - latest_lag: most recent development lag observed
            - latest_value: cumulative loss at the latest lag
            - cdf_to_ultimate: cumulative development factor from latest lag to ultimate
            - projected_ultimate: estimated total losses when fully developed
            - ibnr: projected_ultimate minus latest_value
    """
    # Get selected age-to-age factors
    selected = triangle.select_factors(method)

    # Build cumulative development factors (CDFs)
    # The CDF for each lag is the product of all remaining age-to-age factors
    # from that lag to ultimate, including the tail factor
    ata_values = selected.values
    n_factors = len(ata_values)

    cdfs = np.ones(n_factors + 1)
    # Work backwards: CDF at the last lag is just the tail factor
    cdfs[-1] = tail_factor
    for i in range(n_factors - 1, -1, -1):
        cdfs[i] = ata_values[i] * cdfs[i + 1]

    # Map each development lag to its CDF
    lags = triangle.development_lags
    cdf_by_lag = {}
    for i, lag in enumerate(lags):
        if i < len(cdfs):
            cdf_by_lag[lag] = cdfs[i]
        else:
            cdf_by_lag[lag] = tail_factor

    # Project ultimates
    latest_diag = triangle.latest_diagonal
    latest_lags = triangle.latest_lag

    results = []
    for ay in triangle.accident_years:
        latest_val = latest_diag[ay]
        latest_l = latest_lags[ay]

        # Find the CDF from the latest observed lag to ultimate
        lag_idx = lags.index(latest_l)
        cdf = cdfs[lag_idx] if lag_idx < len(cdfs) else tail_factor

        projected_ult = latest_val * cdf
        ibnr = projected_ult - latest_val

        results.append({
            "accident_year": ay,
            "latest_lag": latest_l,
            "latest_value": latest_val,
            "cdf_to_ultimate": round(cdf, 6),
            "projected_ultimate": round(projected_ult, 0),
            "ibnr": round(ibnr, 0),
        })

    results_df = pd.DataFrame(results).set_index("accident_year")

    return results_df


def get_cdfs(
    triangle: Triangle,
    method: str = "volume_weighted",
    tail_factor: float = 1.0,
) -> pd.Series:
    """
    Compute cumulative development factors for each lag.

    This is useful for the BF method, which needs the CDFs to compute
    the percent reported/unreported.

    Returns:
        Series indexed by development lag with CDF values.
    """
    selected = triangle.select_factors(method)
    ata_values = selected.values
    lags = triangle.development_lags

    cdfs = np.ones(len(lags))
    cdfs[-1] = tail_factor
    for i in range(len(ata_values) - 1, -1, -1):
        cdfs[i] = ata_values[i] * cdfs[i + 1]

    return pd.Series(cdfs, index=lags, name="cdf_to_ultimate")

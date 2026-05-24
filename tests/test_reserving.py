"""
Unit tests for the loss reserve analyzer.

Tests the Triangle class, chain ladder, Bornhuetter-Ferguson, and backtesting
using a small hand-calculated triangle where expected results are known.
"""

import numpy as np
import pandas as pd
import pytest

from src.transform.triangle import Triangle, _mask_lower_triangle
from src.reserving.chain_ladder import chain_ladder, get_cdfs
from src.reserving.bornhuetter_ferguson import bornhuetter_ferguson, compare_methods


# ---------------------------------------------------------------------------
# Test fixtures: a small 4x4 triangle with known values
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_raw_df():
    """
    Create a small raw DataFrame that mimics the CAS format.

    4 accident years (2004-2007), 4 development lags.
    Full triangle values (including lower):
        AY/Lag   1     2     3     4
        2004   100   200   250   270
        2005   150   300   375   405
        2006   200   400   500   540
        2007   250   500   625   675

    Upper triangle (as of year-end 2007):
        AY/Lag   1     2     3     4
        2004   100   200   250   270
        2005   150   300   375   NaN
        2006   200   400   NaN   NaN
        2007   250   NaN   NaN   NaN
    """
    rows = []
    full = {
        2004: {1: 100, 2: 200, 3: 250, 4: 270},
        2005: {1: 150, 2: 300, 3: 375, 4: 405},
        2006: {1: 200, 2: 400, 3: 500, 4: 540},
        2007: {1: 250, 2: 500, 3: 625, 4: 675},
    }
    for ay, lags in full.items():
        for lag, val in lags.items():
            rows.append({
                "GRCODE": 999,
                "GRNAME": "Test Carrier",
                "AccidentYear": ay,
                "DevelopmentYear": ay + lag - 1,
                "DevelopmentLag": lag,
                "CumPaidLoss": val,
                "IncurredLosses": val,
                "BulkLoss": 0,
                "EarnedPremDIR": 500,
                "EarnedPremCeded": 100,
                "EarnedPremNet": 400,
                "Single": 1,
                "PostedReserves2007": 100.0,
                "lob_name": "test",
                "lob_label": "Test Line",
            })
    return pd.DataFrame(rows)


@pytest.fixture
def upper_triangle(sample_raw_df):
    """Build an upper-only triangle from the sample data."""
    return Triangle.from_raw(sample_raw_df, grcode=999, lob_name="test", upper_only=True)


@pytest.fixture
def full_triangle(sample_raw_df):
    """Build a full triangle from the sample data."""
    return Triangle.from_raw(sample_raw_df, grcode=999, lob_name="test", upper_only=False)


# ---------------------------------------------------------------------------
# Triangle class tests
# ---------------------------------------------------------------------------

class TestTriangle:
    def test_from_raw_shape(self, upper_triangle):
        assert upper_triangle.data.shape == (4, 4)

    def test_from_raw_carrier_name(self, upper_triangle):
        assert upper_triangle.carrier_name == "Test Carrier"

    def test_from_raw_lob(self, upper_triangle):
        assert upper_triangle.lob == "Test Line"

    def test_is_cumulative(self, upper_triangle):
        assert upper_triangle.is_cumulative is True

    def test_upper_triangle_masking(self, upper_triangle):
        """2007 should only have lag 1 observed."""
        data = upper_triangle.data
        assert data.loc[2007, 1] == 250
        assert pd.isna(data.loc[2007, 2])
        assert pd.isna(data.loc[2007, 3])
        assert pd.isna(data.loc[2007, 4])

    def test_upper_triangle_2006(self, upper_triangle):
        """2006 should have lags 1-2 observed."""
        data = upper_triangle.data
        assert data.loc[2006, 1] == 200
        assert data.loc[2006, 2] == 400
        assert pd.isna(data.loc[2006, 3])

    def test_full_triangle_no_nans(self, full_triangle):
        """Full triangle should have no NaN values."""
        assert full_triangle.data.isna().sum().sum() == 0

    def test_accident_years(self, upper_triangle):
        assert upper_triangle.accident_years == [2004, 2005, 2006, 2007]

    def test_development_lags(self, upper_triangle):
        assert upper_triangle.development_lags == [1, 2, 3, 4]

    def test_latest_diagonal(self, upper_triangle):
        diag = upper_triangle.latest_diagonal
        assert diag[2004] == 270
        assert diag[2005] == 375
        assert diag[2006] == 400
        assert diag[2007] == 250

    def test_latest_lag(self, upper_triangle):
        lags = upper_triangle.latest_lag
        assert lags[2004] == 4
        assert lags[2005] == 3
        assert lags[2006] == 2
        assert lags[2007] == 1

    def test_to_incremental(self, upper_triangle):
        inc = upper_triangle.to_incremental()
        assert inc.is_cumulative is False
        assert inc.data.loc[2004, 1] == 100
        assert inc.data.loc[2004, 2] == 100
        assert inc.data.loc[2004, 3] == 50

    def test_to_cumulative_roundtrip(self, upper_triangle):
        """Converting to incremental and back should give the same triangle."""
        inc = upper_triangle.to_incremental()
        cum = inc.to_cumulative()
        pd.testing.assert_frame_equal(
            cum.data.dropna(axis=1, how="all"),
            upper_triangle.data.dropna(axis=1, how="all"),
            check_dtype=False,
        )

    def test_age_to_age_factors(self, upper_triangle):
        ata = upper_triangle.age_to_age_factors()
        assert abs(ata.loc[2004, "1-2"] - 2.0) < 0.01
        assert abs(ata.loc[2005, "1-2"] - 2.0) < 0.01
        assert abs(ata.loc[2006, "1-2"] - 2.0) < 0.01

    def test_select_factors_volume_weighted(self, upper_triangle):
        factors = upper_triangle.select_factors("volume_weighted")
        assert abs(factors["1-2"] - 2.0) < 0.01
        assert abs(factors["2-3"] - 1.25) < 0.01
        assert abs(factors["3-4"] - 1.08) < 0.01


# ---------------------------------------------------------------------------
# Chain ladder tests
# ---------------------------------------------------------------------------

class TestChainLadder:
    def test_chain_ladder_mature_year(self, upper_triangle):
        """AY 2004 is fully developed, IBNR should be 0."""
        results = chain_ladder(upper_triangle)
        assert results.loc[2004, "ibnr"] == 0

    def test_chain_ladder_cdf(self, upper_triangle):
        """CDF from lag 1 to ultimate = 2.0 * 1.25 * 1.08 = 2.7"""
        cdfs = get_cdfs(upper_triangle)
        expected_cdf_lag1 = 2.0 * 1.25 * 1.08
        assert abs(cdfs[1] - expected_cdf_lag1) < 0.01

    def test_chain_ladder_projection_2007(self, upper_triangle):
        """AY 2007: 250 * 2.7 = 675"""
        results = chain_ladder(upper_triangle)
        assert abs(results.loc[2007, "projected_ultimate"] - 675) < 1

    def test_chain_ladder_projection_2006(self, upper_triangle):
        """AY 2006: 400 * 1.25 * 1.08 = 540"""
        results = chain_ladder(upper_triangle)
        assert abs(results.loc[2006, "projected_ultimate"] - 540) < 1

    def test_chain_ladder_ibnr_2007(self, upper_triangle):
        """IBNR for 2007 = 675 - 250 = 425"""
        results = chain_ladder(upper_triangle)
        assert abs(results.loc[2007, "ibnr"] - 425) < 1

    def test_tail_factor(self, upper_triangle):
        """Tail factor of 1.05 should increase all projections by 5%."""
        results_no_tail = chain_ladder(upper_triangle, tail_factor=1.0)
        results_tail = chain_ladder(upper_triangle, tail_factor=1.05)
        assert results_tail.loc[2007, "projected_ultimate"] > results_no_tail.loc[2007, "projected_ultimate"]


# ---------------------------------------------------------------------------
# Bornhuetter-Ferguson tests
# ---------------------------------------------------------------------------

class TestBornhuetterFerguson:
    def test_bf_mature_year(self, upper_triangle):
        """AY 2004 is fully developed, BF IBNR should be ~0."""
        premium = pd.Series({2004: 400, 2005: 400, 2006: 400, 2007: 400})
        results = bornhuetter_ferguson(upper_triangle, premium, prior_loss_ratio=0.65)
        assert abs(results.loc[2004, "bf_ibnr"]) < 1

    def test_bf_uses_prior(self, upper_triangle):
        """Different prior loss ratios should produce different BF results."""
        premium = pd.Series({2004: 400, 2005: 400, 2006: 400, 2007: 400})
        bf_low = bornhuetter_ferguson(upper_triangle, premium, prior_loss_ratio=0.50)
        bf_high = bornhuetter_ferguson(upper_triangle, premium, prior_loss_ratio=0.90)
        assert bf_high.loc[2007, "bf_ibnr"] > bf_low.loc[2007, "bf_ibnr"]

    def test_bf_formula(self, upper_triangle):
        """
        Manual check for AY 2007:
        CDF from lag 1 = 2.7, pct_reported = 1/2.7 = 0.3704
        pct_unreported = 0.6296, expected_ultimate = 400 * 0.65 = 260
        bf_ibnr = 260 * 0.6296 = 163.7, bf_ultimate = 250 + 163.7 = 413.7
        """
        premium = pd.Series({2004: 400, 2005: 400, 2006: 400, 2007: 400})
        results = bornhuetter_ferguson(upper_triangle, premium, prior_loss_ratio=0.65)
        assert abs(results.loc[2007, "bf_ultimate"] - 413.7) < 2

    def test_compare_methods(self, upper_triangle):
        """compare_methods should return both CL and BF results."""
        premium = pd.Series({2004: 400, 2005: 400, 2006: 400, 2007: 400})
        comp = compare_methods(upper_triangle, premium)
        assert "cl_ultimate" in comp.columns
        assert "bf_ultimate" in comp.columns
        assert "difference" in comp.columns
        assert len(comp) == 4


# ---------------------------------------------------------------------------
# Mask lower triangle tests
# ---------------------------------------------------------------------------

class TestMaskLowerTriangle:
    def test_mask_preserves_diagonal(self):
        df = pd.DataFrame(
            [[10, 20, 30], [40, 50, 60], [70, 80, 90]],
            index=[2005, 2006, 2007],
            columns=[1, 2, 3],
        )
        masked = _mask_lower_triangle(df)
        assert masked.loc[2005, 3] == 30
        assert masked.loc[2006, 2] == 50
        assert masked.loc[2007, 1] == 70

    def test_mask_hides_future(self):
        df = pd.DataFrame(
            [[10, 20, 30], [40, 50, 60], [70, 80, 90]],
            index=[2005, 2006, 2007],
            columns=[1, 2, 3],
        )
        masked = _mask_lower_triangle(df)
        assert pd.isna(masked.loc[2006, 3])
        assert pd.isna(masked.loc[2007, 2])
        assert pd.isna(masked.loc[2007, 3])

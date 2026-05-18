"""
Triangle class for actuarial loss development analysis.

Wraps a pandas DataFrame in triangle shape (accident years as rows,
development lags as columns) and provides methods for cumulative/incremental
conversion, age-to-age factor computation, and upper/full triangle handling.
"""

import numpy as np
import pandas as pd


class Triangle:
    """
    A loss development triangle.

    The underlying data is a DataFrame where:
        - Index = accident years (e.g. 1998, 1999, ..., 2007)
        - Columns = development lags (e.g. 1, 2, ..., 10)
        - Values = loss amounts (cumulative or incremental)

    Attributes:
        data: The triangle DataFrame.
        is_cumulative: Whether the values represent cumulative losses.
        carrier_name: Name of the insurance carrier.
        lob: Line of business label.
        value_type: What the values represent (e.g. "CumPaidLoss", "IncurredLosses").
    """

    def __init__(
        self,
        data: pd.DataFrame,
        is_cumulative: bool = True,
        carrier_name: str = "",
        lob: str = "",
        value_type: str = "",
    ):
        self.data = data.copy()
        self.is_cumulative = is_cumulative
        self.carrier_name = carrier_name
        self.lob = lob
        self.value_type = value_type

    @classmethod
    def from_raw(
        cls,
        df: pd.DataFrame,
        grcode: int,
        lob_name: str,
        value_col: str = "CumPaidLoss",
        upper_only: bool = True,
    ) -> "Triangle":
        """
        Build a Triangle from the combined raw dataset.

        Filters to a specific carrier and line of business, pivots from
        long format to triangle shape, and optionally masks the lower triangle.

        Args:
            df: Combined raw DataFrame (output of ingestion).
            grcode: GRCODE of the carrier to extract.
            lob_name: Line of business key (e.g. "pp_auto").
            value_col: Column to use as triangle values.
                       "CumPaidLoss" or "IncurredLosses" are most common.
            upper_only: If True, mask the lower triangle with NaN.
                        Set False to keep the full triangle for backtesting.

        Returns:
            A Triangle instance.
        """
        # Filter to carrier and LOB
        mask = df["GRCODE"] == grcode
        if "lob_name" in df.columns:
            mask = mask & (df["lob_name"] == lob_name)

        subset = df.loc[mask].copy()

        if subset.empty:
            raise ValueError(
                f"No data found for GRCODE={grcode}, lob_name={lob_name}"
            )

        carrier_name = subset["GRNAME"].iloc[0]
        lob_label = subset["lob_label"].iloc[0] if "lob_label" in subset.columns else lob_name

        # Pivot from long to triangle shape
        triangle = subset.pivot(
            index="AccidentYear",
            columns="DevelopmentLag",
            values=value_col,
        )
        triangle = triangle.sort_index(axis=0).sort_index(axis=1)

        if upper_only:
            triangle = _mask_lower_triangle(triangle)

        is_cumulative = value_col in ("CumPaidLoss", "IncurredLosses")

        return cls(
            data=triangle,
            is_cumulative=is_cumulative,
            carrier_name=carrier_name,
            lob=lob_label,
            value_type=value_col,
        )

    def to_cumulative(self) -> "Triangle":
        """
        Convert incremental triangle to cumulative by summing across columns.

        Returns a new Triangle instance. If already cumulative, returns a copy.
        """
        if self.is_cumulative:
            return Triangle(
                data=self.data,
                is_cumulative=True,
                carrier_name=self.carrier_name,
                lob=self.lob,
                value_type=self.value_type,
            )

        cumulative = self.data.cumsum(axis=1)

        return Triangle(
            data=cumulative,
            is_cumulative=True,
            carrier_name=self.carrier_name,
            lob=self.lob,
            value_type=self.value_type,
        )

    def to_incremental(self) -> "Triangle":
        """
        Convert cumulative triangle to incremental by differencing columns.

        Returns a new Triangle instance. If already incremental, returns a copy.
        """
        if not self.is_cumulative:
            return Triangle(
                data=self.data,
                is_cumulative=False,
                carrier_name=self.carrier_name,
                lob=self.lob,
                value_type=self.value_type,
            )

        incremental = self.data.copy()
        cols = incremental.columns.tolist()

        # Difference each column from the previous one, right to left
        for i in range(len(cols) - 1, 0, -1):
            incremental[cols[i]] = incremental[cols[i]] - incremental[cols[i - 1]]

        return Triangle(
            data=incremental,
            is_cumulative=False,
            carrier_name=self.carrier_name,
            lob=self.lob,
            value_type=self.value_type,
        )

    def age_to_age_factors(self) -> pd.DataFrame:
        """
        Compute age-to-age (link ratio) factors from the triangle.

        For each pair of adjacent development periods, computes the ratio
        of cumulative losses at period n+1 to period n. Only uses the
        upper triangle (non-NaN values).

        Returns:
            DataFrame with one row per accident year and one column per
            development period pair (e.g. "1-2", "2-3", ..., "9-10").
        """
        if not self.is_cumulative:
            tri = self.to_cumulative().data
        else:
            tri = self.data

        cols = tri.columns.tolist()
        factors = pd.DataFrame(index=tri.index)

        for i in range(len(cols) - 1):
            col_current = cols[i]
            col_next = cols[i + 1]
            label = f"{col_current}-{col_next}"

            # Only compute where both values exist and current is nonzero
            valid = tri[col_current].notna() & tri[col_next].notna() & (tri[col_current] != 0)
            factors[label] = np.where(valid, tri[col_next] / tri[col_current], np.nan)

        return factors

    def select_factors(self, method: str = "volume_weighted") -> pd.Series:
        """
        Select development factors using the specified method.

        Args:
            method: One of "volume_weighted", "simple_average", or "medial".
                - volume_weighted: sum of numerators / sum of denominators
                - simple_average: mean of individual factors
                - medial: average after excluding highest and lowest

        Returns:
            Series of selected factors indexed by period pair labels.
        """
        if not self.is_cumulative:
            tri = self.to_cumulative().data
        else:
            tri = self.data

        cols = tri.columns.tolist()
        selected = {}

        for i in range(len(cols) - 1):
            col_current = cols[i]
            col_next = cols[i + 1]
            label = f"{col_current}-{col_next}"

            valid = tri[col_current].notna() & tri[col_next].notna() & (tri[col_current] != 0)
            current_vals = tri.loc[valid, col_current]
            next_vals = tri.loc[valid, col_next]

            if len(current_vals) == 0:
                selected[label] = np.nan
                continue

            if method == "volume_weighted":
                selected[label] = next_vals.sum() / current_vals.sum()

            elif method == "simple_average":
                individual_factors = next_vals / current_vals
                selected[label] = individual_factors.mean()

            elif method == "medial":
                individual_factors = next_vals / current_vals
                if len(individual_factors) <= 2:
                    selected[label] = individual_factors.mean()
                else:
                    trimmed = individual_factors.sort_values().iloc[1:-1]
                    selected[label] = trimmed.mean()

            else:
                raise ValueError(f"Unknown method: {method}")

        return pd.Series(selected, name=f"selected_factors_{method}")

    @property
    def accident_years(self) -> list:
        """List of accident years in the triangle."""
        return self.data.index.tolist()

    @property
    def development_lags(self) -> list:
        """List of development lags in the triangle."""
        return self.data.columns.tolist()

    @property
    def latest_diagonal(self) -> pd.Series:
        """
        Extract the latest diagonal of the triangle.

        This is the most recent observed cumulative loss for each accident year,
        which is the starting point for projecting ultimates.
        """
        if not self.is_cumulative:
            tri = self.to_cumulative().data
        else:
            tri = self.data

        diagonal = {}
        for ay in tri.index:
            row = tri.loc[ay].dropna()
            if len(row) > 0:
                diagonal[ay] = row.iloc[-1]
            else:
                diagonal[ay] = np.nan

        return pd.Series(diagonal, name="latest_diagonal")

    @property
    def latest_lag(self) -> pd.Series:
        """
        The most recent development lag observed for each accident year.
        """
        lags = {}
        for ay in self.data.index:
            row = self.data.loc[ay].dropna()
            if len(row) > 0:
                lags[ay] = row.index[-1]
            else:
                lags[ay] = np.nan

        return pd.Series(lags, name="latest_lag")

    def __repr__(self) -> str:
        return (
            f"Triangle(carrier='{self.carrier_name}', lob='{self.lob}', "
            f"value='{self.value_type}', "
            f"shape={self.data.shape}, cumulative={self.is_cumulative})"
        )

    def __str__(self) -> str:
        header = repr(self)
        return f"{header}\n{self.data.to_string()}"


def _mask_lower_triangle(triangle: pd.DataFrame) -> pd.DataFrame:
    """
    Mask the lower-right portion of the triangle with NaN.

    In a 10x10 triangle with accident years 1998-2007, the upper triangle
    represents data that would have been observable as of year-end 2007.
    Accident year 2007 has only lag 1 observed, 2006 has lags 1-2, etc.
    """
    masked = triangle.copy()
    max_ay = masked.index.max()

    for ay in masked.index:
        max_observable_lag = max_ay - ay + 1
        for lag in masked.columns:
            if lag > max_observable_lag:
                masked.loc[ay, lag] = np.nan

    return masked

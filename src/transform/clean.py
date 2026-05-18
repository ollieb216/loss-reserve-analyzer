"""
Data cleaning and loading utilities for triangle construction.

Provides helper functions for loading the processed Parquet dataset,
listing available carriers and lines of business, and filtering data.
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_combined(path: str = "data/processed/combined_schedule_p.parquet") -> pd.DataFrame:
    """
    Load the combined Schedule P dataset from Parquet.

    Args:
        path: Path to the Parquet file produced by the ingestion step.

    Returns:
        Combined DataFrame with all carriers and lines of business.
    """
    filepath = Path(path)
    if not filepath.exists():
        raise FileNotFoundError(
            f"Combined data not found at {filepath}. Run the ingestion step first: "
            f"python -m src.ingestion.ingest"
        )

    df = pd.read_parquet(filepath)
    logger.info(f"Loaded {len(df):,} rows from {filepath}")
    return df


def list_carriers(df: pd.DataFrame, lob_name: str = None) -> pd.DataFrame:
    """
    List available carriers, optionally filtered by line of business.

    Returns a DataFrame with GRCODE, GRNAME, and row count.
    """
    if lob_name:
        df = df[df["lob_name"] == lob_name]

    carriers = (
        df.groupby(["GRCODE", "GRNAME"])
        .size()
        .reset_index(name="rows")
        .sort_values("GRCODE")
    )
    return carriers


def list_lobs(df: pd.DataFrame) -> pd.DataFrame:
    """
    List available lines of business with carrier counts.
    """
    lobs = (
        df.groupby(["lob_name", "lob_label"])
        .agg(carriers=("GRCODE", "nunique"), rows=("GRCODE", "size"))
        .reset_index()
    )
    return lobs


def get_earned_premium(
    df: pd.DataFrame, grcode: int, lob_name: str
) -> pd.Series:
    """
    Extract net earned premium by accident year for a carrier and LOB.

    Used as input for the Bornhuetter-Ferguson method. Returns one value
    per accident year (premium is constant across development lags).

    Returns:
        Series indexed by AccidentYear with EarnedPremNet values.
    """
    mask = (df["GRCODE"] == grcode)
    if "lob_name" in df.columns:
        mask = mask & (df["lob_name"] == lob_name)

    subset = df.loc[mask]

    # Premium is the same for all development lags within an accident year,
    # so just take the first value per AY
    premium = (
        subset.groupby("AccidentYear")["EarnedPremNet"]
        .first()
        .sort_index()
    )

    return premium


def get_posted_reserves(
    df: pd.DataFrame, grcode: int, lob_name: str
) -> float:
    """
    Get the posted reserves as of 2007 for a carrier and LOB.

    This is the actual reserve the carrier posted, useful as a
    benchmark to compare against model estimates.
    """
    mask = (df["GRCODE"] == grcode)
    if "lob_name" in df.columns:
        mask = mask & (df["lob_name"] == lob_name)

    subset = df.loc[mask]
    posted = subset["PostedReserves2007"].iloc[0]
    return posted

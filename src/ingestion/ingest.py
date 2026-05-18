"""
Ingestion module for CAS Loss Reserve Database.

Loads Schedule P loss triangle CSVs from the CAS (Casualty Actuarial Society),
validates schema consistency, and produces a single combined DataFrame with
a line_of_business column appended.
"""

import logging
from pathlib import Path

import pandas as pd
import yaml

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = [
    "GRCODE",
    "GRNAME",
    "AccidentYear",
    "DevelopmentYear",
    "DevelopmentLag",
    "IncurredLosses",
    "CumPaidLoss",
    "BulkLoss",
    "EarnedPremDIR",
    "EarnedPremCeded",
    "EarnedPremNet",
    "Single",
    "PostedReserves2007",
]

EXPECTED_DTYPES = {
    "GRCODE": "int64",
    "GRNAME": "object",
    "AccidentYear": "int64",
    "DevelopmentYear": "int64",
    "DevelopmentLag": "int64",
    "IncurredLosses": "int64",
    "CumPaidLoss": "int64",
    "BulkLoss": "int64",
    "EarnedPremDIR": "int64",
    "EarnedPremCeded": "int64",
    "EarnedPremNet": "int64",
    "Single": "int64",
    "PostedReserves2007": "float64",
}


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load pipeline configuration from YAML file."""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def validate_schema(df: pd.DataFrame, filename: str) -> None:
    """
    Validate that a DataFrame matches the expected CAS Schedule P schema.

    Checks column names are present and that core numeric columns have no nulls.
    Raises ValueError if validation fails.
    """
    missing_cols = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing_cols:
        raise ValueError(f"{filename}: missing columns {missing_cols}")

    extra_cols = set(df.columns) - set(EXPECTED_COLUMNS)
    if extra_cols:
        logger.warning(f"{filename}: unexpected extra columns {extra_cols}")

    # Check for nulls in core loss columns
    core_cols = ["GRCODE", "AccidentYear", "DevelopmentLag", "IncurredLosses", "CumPaidLoss"]
    for col in core_cols:
        null_count = df[col].isna().sum()
        if null_count > 0:
            raise ValueError(f"{filename}: {null_count} null values in {col}")

    # Validate accident year and development lag ranges
    ay_range = df["AccidentYear"].unique()
    dl_range = df["DevelopmentLag"].unique()
    if len(ay_range) == 0 or len(dl_range) == 0:
        raise ValueError(f"{filename}: empty accident year or development lag range")

    logger.info(
        f"{filename}: validated OK - {len(df)} rows, "
        f"{df['GRCODE'].nunique()} carriers, "
        f"AY {ay_range.min()}-{ay_range.max()}, "
        f"DL {dl_range.min()}-{dl_range.max()}"
    )


def load_single_lob(filepath: Path, lob_name: str, lob_label: str) -> pd.DataFrame:
    """
    Load a single line-of-business CSV and append LOB identifiers.

    Args:
        filepath: Path to the CSV file.
        lob_name: Short LOB key (e.g. "pp_auto").
        lob_label: Display label (e.g. "Private Passenger Auto").

    Returns:
        DataFrame with lob_name and lob_label columns appended.
    """
    df = pd.read_csv(filepath)

    # Strip whitespace from column names (common CSV issue)
    df.columns = df.columns.str.strip()

    validate_schema(df, filepath.name)

    df["lob_name"] = lob_name
    df["lob_label"] = lob_label

    return df


def ingest_all(config_path: str = "config/config.yaml") -> pd.DataFrame:
    """
    Load and combine all lines of business defined in the config.

    Returns a single DataFrame with all LOBs stacked, validated, and labeled.
    """
    config = load_config(config_path)
    raw_dir = Path(config["data"]["raw_dir"])

    frames = []
    for lob in config["data"]["lines_of_business"]:
        filepath = raw_dir / lob["file"]

        if not filepath.exists():
            logger.warning(f"File not found, skipping: {filepath}")
            continue

        df = load_single_lob(filepath, lob["name"], lob["label"])
        frames.append(df)
        logger.info(f"Loaded {lob['label']}: {len(df):,} rows, {df['GRCODE'].nunique()} carriers")

    if not frames:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(
        f"Combined dataset: {len(combined):,} rows, "
        f"{combined['GRCODE'].nunique()} unique carriers, "
        f"{combined['lob_name'].nunique()} lines of business"
    )

    return combined


def save_combined(df: pd.DataFrame, config_path: str = "config/config.yaml") -> Path:
    """Save the combined DataFrame as a Parquet file."""
    config = load_config(config_path)
    output_dir = Path(config["data"]["processed_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "combined_schedule_p.parquet"
    df.to_parquet(output_path, index=False)
    logger.info(f"Saved combined data to {output_path}")

    return output_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    combined = ingest_all()
    output_path = save_combined(combined)

    print(f"\nIngestion complete:")
    print(f"  Total rows: {len(combined):,}")
    print(f"  Carriers: {combined['GRCODE'].nunique()}")
    print(f"  Lines of business: {combined['lob_name'].nunique()}")
    print(f"  Accident years: {combined['AccidentYear'].min()}-{combined['AccidentYear'].max()}")
    print(f"  Output: {output_path}")

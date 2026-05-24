"""Data cleaning and loading utilities."""

import logging
from pathlib import Path
import pandas as pd
import yaml

logger = logging.getLogger(__name__)


def load_from_csvs(config_path="config/config.yaml"):
    """Load all LOBs directly from CSVs and return combined DataFrame."""
    with open(config_path) as f:
        config = yaml.safe_load(f)
    raw_dir = Path(config["data"]["raw_dir"])
    frames = []
    for lob in config["data"]["lines_of_business"]:
        fp = raw_dir / lob["file"]
        if not fp.exists():
            logger.warning(f"File not found: {fp}")
            continue
        d = pd.read_csv(fp)
        d.columns = d.columns.str.strip()
        d["lob_name"] = lob["name"]
        d["lob_label"] = lob["label"]
        frames.append(d)
    if not frames:
        raise FileNotFoundError(f"No CSV files found in {raw_dir}")
    return pd.concat(frames, ignore_index=True)


def load_combined(path="data/processed/combined_schedule_p.parquet"):
    """Load combined dataset from Parquet, fall back to CSVs."""
    filepath = Path(path)
    if filepath.exists():
        try:
            return pd.read_parquet(filepath)
        except ImportError:
            pass
    return load_from_csvs()


def list_carriers(df, lob_name=None):
    if lob_name:
        df = df[df["lob_name"] == lob_name]
    return df.groupby(["GRCODE", "GRNAME"]).size().reset_index(name="rows").sort_values("GRCODE")


def list_lobs(df):
    return df.groupby(["lob_name", "lob_label"]).agg(
        carriers=("GRCODE", "nunique"), rows=("GRCODE", "size")
    ).reset_index()


def get_earned_premium(df, grcode, lob_name):
    mask = (df["GRCODE"] == grcode)
    if "lob_name" in df.columns:
        mask = mask & (df["lob_name"] == lob_name)
    return df.loc[mask].groupby("AccidentYear")["EarnedPremNet"].first().sort_index()


def get_posted_reserves(df, grcode, lob_name):
    mask = (df["GRCODE"] == grcode)
    if "lob_name" in df.columns:
        mask = mask & (df["lob_name"] == lob_name)
    return df.loc[mask]["PostedReserves2007"].iloc[0]

"""
Export pipeline results as JSON for the static dashboard.

Runs chain ladder and BF for every carrier-LOB combination and writes
JSON files to docs/data/ for the frontend to consume.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from src.transform.clean import load_combined, list_carriers, list_lobs, get_earned_premium
from src.transform.triangle import Triangle
from src.reserving.chain_ladder import chain_ladder, get_cdfs
from src.reserving.bornhuetter_ferguson import bornhuetter_ferguson, compare_methods

logger = logging.getLogger(__name__)


def export_all(output_dir: str = "docs/data", prior_loss_ratio: float = 0.65):
    """Export reserve results for all carrier-LOB combos as JSON."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    df = load_combined()
    lobs = list_lobs(df)

    # Build the index: all available carrier-LOB combos
    index = []
    all_results = []
    errors = []

    for _, lob_row in lobs.iterrows():
        lob_name = lob_row["lob_name"]
        lob_label = lob_row["lob_label"]
        carriers = list_carriers(df, lob_name=lob_name)

        for _, carrier_row in carriers.iterrows():
            grcode = int(carrier_row["GRCODE"])
            grname = carrier_row["GRNAME"]

            try:
                # Build triangle
                tri = Triangle.from_raw(df, grcode=grcode, lob_name=lob_name, value_col="CumPaidLoss")
                premium = get_earned_premium(df, grcode, lob_name)

                # Run both methods
                cl = chain_ladder(tri)
                bf = bornhuetter_ferguson(tri, premium, prior_loss_ratio=prior_loss_ratio)
                comp = compare_methods(tri, premium, prior_loss_ratio=prior_loss_ratio)

                # Get triangle data for heatmap
                tri_data = tri.data.copy()
                tri_data.index.name = "AccidentYear"
                tri_data = tri_data.reset_index()
                tri_data.columns = tri_data.columns.astype(str)

                # Get development factors
                ata = tri.age_to_age_factors()
                ata.index = ata.index.astype(str)
                selected = tri.select_factors("volume_weighted")

                # Get CDFs
                cdfs = get_cdfs(tri)

                # Build result object
                result = {
                    "grcode": grcode,
                    "grname": grname,
                    "lob_name": lob_name,
                    "lob_label": lob_label,
                    "triangle": _df_to_dict(tri_data),
                    "ata_factors": _df_to_dict(ata),
                    "selected_factors": {k: (None if np.isnan(v) else round(v, 4)) for k, v in selected.to_dict().items()},
                    "cdfs": {str(k): (None if np.isnan(v) else round(v, 4)) for k, v in cdfs.to_dict().items()},
                    "comparison": _df_to_dict(comp.reset_index()),
                    "totals": {
                        "cl_ibnr": float(comp["cl_ibnr"].sum()),
                        "bf_ibnr": float(comp["bf_ibnr"].sum()),
                        "cl_ultimate": float(comp["cl_ultimate"].sum()),
                        "bf_ultimate": float(comp["bf_ultimate"].sum()),
                        "latest_total": float(comp["latest_value"].sum()),
                    },
                }

                all_results.append(result)
                index.append({
                    "grcode": grcode,
                    "grname": grname,
                    "lob_name": lob_name,
                    "lob_label": lob_label,
                    "cl_ibnr": float(comp["cl_ibnr"].sum()),
                    "bf_ibnr": float(comp["bf_ibnr"].sum()),
                })

            except Exception as e:
                errors.append({"grcode": grcode, "grname": grname, "lob_name": lob_name, "error": str(e)})
                logger.warning(f"Error processing GRCODE={grcode} {lob_name}: {e}")

    # Write individual results as one big JSON (dashboard will filter client-side)
    with open(output_path / "results.json", "w") as f:
        json.dump(all_results, f, cls=NumpyEncoder)

    # Write the index (lightweight, for populating dropdowns)
    with open(output_path / "index.json", "w") as f:
        json.dump(index, f, cls=NumpyEncoder)

    logger.info(f"Exported {len(all_results)} carrier-LOB results to {output_path}")
    if errors:
        logger.warning(f"{len(errors)} errors encountered")

    print(f"\nExport complete:")
    print(f"  Carrier-LOB combos: {len(all_results)}")
    print(f"  Errors: {len(errors)}")
    print(f"  Output: {output_path}")


def _df_to_dict(df):
    """Convert DataFrame to list-of-dicts, handling NaN for JSON."""
    return json.loads(df.to_json(orient="records"))


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types and NaN."""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if np.isnan(obj):
                return None
            return float(obj)
        if isinstance(obj, np.ndarray):
            return [None if isinstance(v, float) and np.isnan(v) else v for v in obj.tolist()]
        return super().default(obj)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
    export_all()

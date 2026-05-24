# Loss Reserve Analyzer

End-to-end actuarial data pipeline that ingests NAIC Schedule P loss triangles, runs chain ladder and Bornhuetter-Ferguson reserving methods, and visualizes reserve estimates across 6 P&C lines of business.

## Overview

This project demonstrates both actuarial knowledge and data engineering skills by building a Python pipeline that:

1. Ingests publicly available Schedule P loss triangle data from the CAS Loss Reserve Database
2. Cleans and structures the data into loss development triangles across multiple carriers and lines of business
3. Runs chain ladder and Bornhuetter-Ferguson reserving methods programmatically
4. Outputs reserve estimates with an interactive dashboard showing loss development patterns

## Data Source

The data comes from the [CAS Loss Reserve Database](https://www.casact.org/publications-research/research/research-resources/loss-reserving-data-pulled-naic-schedule-p), which contains Schedule P loss triangles for U.S. property-casualty insurers. The dataset covers:

- 374 unique insurance carriers
- 6 lines of business (Private Passenger Auto, Commercial Auto, Workers Compensation, Medical Malpractice, Other Liability, Product Liability)
- Accident years 1998-2007 with 10 years of development

## Setup

```bash
git clone https://github.com/ollieb216/loss-reserve-analyzer.git
cd loss-reserve-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Download the 6 CSV files from the CAS link above and place them in `data/raw/`.

## Usage

```bash
# Run the ingestion pipeline
python -m src.ingestion.ingest

# Test the reserving methods
python3 -c "
from src.transform.triangle import Triangle
from src.transform.clean import load_combined, get_earned_premium
from src.reserving.bornhuetter_ferguson import compare_methods

df = load_combined()
tri = Triangle.from_raw(df, grcode=43, lob_name='pp_auto', value_col='CumPaidLoss')
premium = get_earned_premium(df, 43, 'pp_auto')
print(compare_methods(tri, premium).to_string())
"
```

## Project Structure

```
loss-reserve-analyzer/
├── config/
│   └── config.yaml              # Pipeline configuration (LOB mappings, method params)
├── data/
│   ├── raw/                     # Downloaded CAS CSVs (not tracked in Git)
│   └── processed/               # Cleaned Parquet files (not tracked in Git)
├── src/
│   ├── ingestion/
│   │   └── ingest.py            # Data loading, schema validation, Parquet export
│   ├── transform/
│   │   ├── triangle.py          # Triangle class (pivot, cumulative/incremental, factors)
│   │   └── clean.py             # Data loading helpers, carrier/LOB lookups
│   ├── reserving/
│   │   ├── chain_ladder.py      # Chain ladder method
│   │   └── bornhuetter_ferguson.py  # BF method and CL vs BF comparison
│   └── dashboard/               # Shiny app (planned)
├── docs/                        # Static dashboard for GitHub Pages (planned)
├── tests/
├── .gitignore
├── pyproject.toml
└── README.md
```

## Methods

**Chain Ladder**: Computes age-to-age development factors from historical loss triangles, chains them into cumulative development factors, and projects ultimate losses by multiplying the latest observed value by the CDF. Best suited for mature accident years with stable development patterns.

**Bornhuetter-Ferguson**: Blends observed loss development with an a priori expected ultimate (earned premium x expected loss ratio). More stable for immature accident years where chain ladder projections can be volatile. The formula is: Ultimate = Observed + (Expected Ultimate x Percent Unreported).

## Tech Stack

Python, Pandas, NumPy, PyArrow, Plotly, PyYAML

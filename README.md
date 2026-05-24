# Loss Reserve Analyzer

A Python pipeline that ingests NAIC Schedule P loss triangle data, applies chain ladder and Bornhuetter-Ferguson reserving methods across 772 carrier-LOB combinations, validates projections against actual outcomes through backtesting, and serves results through an interactive dashboard.

**Live dashboard:** [ollieb216.github.io/loss-reserve-analyzer](https://ollieb216.github.io/loss-reserve-analyzer/)

## What this project does

Insurance companies need to estimate how much they will ultimately pay on claims that have already occurred but are not fully settled. These estimates, called loss reserves, are the largest liability on a property-casualty insurer's balance sheet.

This project builds a complete reserving pipeline:

1. **Ingests** the CAS Loss Reserve Database (derived from NAIC Schedule P filings) covering 374 insurance carriers across 6 lines of business
2. **Structures** raw tabular data into loss development triangles, the standard actuarial data format
3. **Projects** ultimate losses using two industry-standard methods: chain ladder (development-based) and Bornhuetter-Ferguson (prior-weighted)
4. **Backtests** both methods against actual outcomes to measure prediction accuracy across lines of business and maturity levels
5. **Visualizes** results through a static dashboard with interactive carrier and LOB selection

## Data

The CAS Loss Reserve Database contains Schedule P loss triangles for U.S. property-casualty insurers. Each triangle has 10 accident years (1998-2007) with 10 years of development. Both the upper triangle (observable in real time) and the lower triangle (actual outcomes) are included, enabling retrospective validation.

Six lines of business are covered:

| Line of business | Carriers | Tail length |
|---|---|---|
| Private Passenger Auto | 143 | Short |
| Commercial Auto | 157 | Short |
| Workers Compensation | 132 | Long |
| Medical Malpractice | 34 | Long |
| Other Liability | 236 | Long |
| Product Liability | 70 | Long |

Download the CSVs from the [CAS website](https://www.casact.org/publications-research/research/research-resources/loss-reserving-data-pulled-naic-schedule-p) and place them in `data/raw/`.

## Methods

**Chain ladder** computes age-to-age development factors from historical data, chains them into cumulative development factors, and multiplies the latest observed loss by the appropriate CDF to project ultimate losses. The method assumes future development will follow historical patterns.

**Bornhuetter-Ferguson** blends observed development with an a priori expected ultimate (earned premium times an expected loss ratio). For immature accident years where observed data is volatile, BF gives more weight to the prior expectation. For mature years, it converges to the observed data. The formula is: Ultimate = Observed + (Expected Ultimate) x (Percent Unreported).

**Backtesting** uses only the upper triangle to make projections, then compares against actual outcomes in the lower triangle. This measures prediction error by method, line of business, and accident year maturity.

## Project structure

```
loss-reserve-analyzer/
├── config/config.yaml           # Pipeline configuration
├── data/
│   ├── raw/                     # CAS CSVs (gitignored)
│   └── processed/               # Parquet output (gitignored)
├── src/
│   ├── ingestion/ingest.py      # Data loading and schema validation
│   ├── transform/
│   │   ├── triangle.py          # Triangle class (pivot, factors, conversions)
│   │   └── clean.py             # Data loading and filtering utilities
│   ├── reserving/
│   │   ├── chain_ladder.py      # Chain ladder implementation
│   │   ├── bornhuetter_ferguson.py  # BF implementation with method comparison
│   │   └── backtest.py          # Backtesting against actual outcomes
│   └── dashboard/
│       └── export.py            # JSON export for static dashboard
├── docs/                        # Static dashboard (GitHub Pages)
│   ├── index.html
│   └── data/                    # Pre-computed JSON results
└── tests/
    └── test_reserving.py        # Unit tests with hand-calculated triangles
```

## Setup

```bash
git clone https://github.com/ollieb216/loss-reserve-analyzer.git
cd loss-reserve-analyzer
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Download the 6 CAS CSV files into `data/raw/`, then run the pipeline:

```bash
# Ingest and validate raw data
python -m src.ingestion.ingest

# Export results for dashboard
python -m src.dashboard.export

# Run tests
pytest tests/

# Preview dashboard locally
cd docs && python -m http.server 8000
```

## Key findings from backtesting

Backtesting across 772 carrier-LOB combinations revealed:

- For **mature accident years** (7+ years of development), both methods produce nearly identical results with errors under 1.5%
- For **immature accident years** (1-2 years of development), chain ladder errors average 12-18% while BF errors depend heavily on the a priori loss ratio assumption
- **Short-tailed lines** (auto) show lower prediction errors overall because claims settle faster
- **Long-tailed lines** (med mal, other liability) have higher variance and are more sensitive to method selection
- The 65% a priori loss ratio works reasonably for auto but is too aggressive for some specialty lines, demonstrating that BF performance is driven by the quality of the prior assumption

## Tech stack

Python, Pandas, NumPy, PyArrow, Plotly.js, HTML/CSS/JS, GitHub Pages

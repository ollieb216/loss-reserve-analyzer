# Loss Reserve Analyzer

Actuarial loss reserving pipeline using NAIC Schedule P triangle data from the CAS Loss Reserve Database. Implements chain ladder and Bornhuetter-Ferguson methods across 6 lines of business and 700+ insurance carriers.

## Setup

```bash
pip install -e ".[dev]"
```

## Data

Download the CAS Loss Reserve Database CSVs from:
https://www.casact.org/publications-research/research/research-resources/loss-reserving-data-pulled-naic-schedule-p

Place all 6 CSV files in `data/raw/`.

## Usage

```bash
# Run ingestion pipeline
python -m src.ingestion.ingest
```

## Project Structure

```
loss-reserve-analyzer/
├── config/config.yaml        # Pipeline configuration
├── data/
│   ├── raw/                  # Downloaded CAS CSVs
│   └── processed/            # Cleaned Parquet files
├── src/
│   ├── ingestion/ingest.py   # Data loading and validation
│   ├── transform/            # Triangle class and pivot logic
│   ├── reserving/            # Chain ladder and BF methods
│   └── dashboard/            # Python Shiny app
├── tests/
└── notebooks/
```

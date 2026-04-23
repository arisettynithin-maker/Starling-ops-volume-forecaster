# Starling Ops Volume Forecaster

## What I Built and Why

Starling's operations team handles a high and growing volume of inbound contacts — account queries, payment disputes, fraud reports, complaints. The challenge isn't just dealing with today's volume, it's knowing *next month's* volume well enough to have the right headcount in place. Traditional approaches (look at last year, add X%) miss the structural trend — neobank contact volumes don't behave like high-street bank volumes, and macro shocks (think the 2022 cost-of-living squeeze) create demand surges that a naive seasonal model won't catch. This project builds a forward-looking demand signal from three public data sources — FCA complaints, Google Trends, and ONS macro indicators — and runs a Prophet time-series model to generate a 12-month forecast with confidence intervals. The Streamlit app makes the output navigable without needing to run any code.

## Data Sources

- **FCA Complaints Data** — half-year firm-level complaints published by the FCA. Filtered to the neobank segment and distributed monthly.
- **Google Trends (via pytrends)** — UK search volume for "Starling Bank" and "neobank help", used as a leading indicator that arrives before the 6-month FCA publication lag.
- **ONS API** — UK unemployment rate (series LF24) and consumer confidence index, as macro context variables.

## What I Found

Complaint volumes follow a clear January spike — consistently 15–20% above the annual average — almost certainly driven by post-holiday payment disputes and customers reviewing their finances at the start of the year. Any headcount plan that doesn't account for this will be caught short in Q1.

Search volume for "Starling Bank" tracks complaint trends with roughly a 4–6 week lead. This isn't surprising — customers search before they call or complain — but it means Google Trends is usable as a near-term demand signal in months where the FCA data isn't published yet.

The 2022 cost-of-living period shows a notable demand spike that macro indicators (falling consumer confidence, persistent inflation) would have flagged 6–8 weeks in advance if anyone had been watching them. This suggests there's a real forecasting benefit to layering macro signals into the model rather than treating them as background noise.

Neobank complaint growth has been running at roughly 15–20% YoY through the analysis period — not a quality signal per se (growing customer bases generate more contacts), but it means headcount needs to compound at a similar rate just to keep pace, before any service improvement initiatives.

## How to Run

```bash
# clone and install
git clone https://github.com/nithin-arisetty/starling-ops-volume-forecaster.git
cd starling-ops-volume-forecaster
pip install -r requirements.txt

# generate the processed data (runs FCA + Google Trends + ONS ingestion)
python data/ingest.py

# run the analysis notebook
jupyter notebook notebooks/starling_volume_analysis.ipynb

# launch the Streamlit app
streamlit run app/streamlit_app.py
```

The app works with demo data even before running `ingest.py` — useful for a quick look.

## SQL Queries

Ten SQLite-compatible queries in `sql/`, covering YoY trend analysis, rolling averages, seasonal indexing, anomaly detection, and capacity gap modelling. See [sql/README_sql.md](sql/README_sql.md) for the full index.

## Live Demo

[Streamlit Cloud URL — add after deploying]

## Repository

[github.com/arisettynithin-maker/Starling-ops-volume-forecaster](https://github.com/arisettynithin-maker/Starling-ops-volume-forecaster)

---

*Nithin Arisetty, 2024*

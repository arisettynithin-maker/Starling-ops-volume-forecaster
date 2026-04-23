# Deployment Instructions

## Local Setup

```bash
git clone https://github.com/nithin-arisetty/starling-ops-volume-forecaster.git
cd starling-ops-volume-forecaster
pip install -r requirements.txt

# Step 1: generate the data
python data/ingest.py

# Step 2: run the analysis notebook (optional — generates prophet_forecast.csv)
jupyter notebook notebooks/starling_volume_analysis.ipynb

# Step 3: launch the app
streamlit run app/streamlit_app.py
```

The app loads demo data automatically if `data/processed/combined_demand_signals.csv` doesn't exist yet, so you can view it before running the ingest.

## Streamlit Cloud Deployment

1. Push the repo to GitHub (public or private with Streamlit Cloud connected)
2. Go to [share.streamlit.io](https://share.streamlit.io) and click "New app"
3. Set:
   - Repository: `nithin-arisetty/starling-ops-volume-forecaster`
   - Branch: `main`
   - Main file path: `app/streamlit_app.py`
4. Click "Deploy"

Note: the live Streamlit Cloud deployment will use demo/synthetic data since the FCA/ONS ingestion runs locally. To deploy with real data, commit `data/processed/combined_demand_signals.csv` and `data/processed/prophet_forecast.csv` to the repo.

## SQLite Queries

```bash
# create the database and run any query
sqlite3 starling_ops.db < sql/schema.sql
# load data from Python (see the notebook, section 2 — uses pandas to_sql)
sqlite3 starling_ops.db < sql/01_complaint_volume_trend_yoy.sql
```

## Dependencies

- Python 3.10+
- Prophet requires a C compiler — on Mac: `xcode-select --install`
- On Linux: `apt-get install build-essential`

*Nithin Arisetty, 2024*

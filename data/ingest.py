"""
Data ingestion pipeline for the Starling ops volume forecaster.

Pulls from three sources:
1. FCA complaints data (public CSV download)
2. Google Trends via pytrends (UK search volume)
3. ONS API (unemployment + consumer confidence)

Merges everything onto a monthly grain and saves to data/processed/combined_demand_signals.csv.
Nithin Arisetty, 2024
"""

import os
import time
import requests
import warnings
import pandas as pd
import numpy as np
from io import StringIO
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# 1. FCA Complaints Data
# ---------------------------------------------------------------------------

def fetch_fca_complaints() -> pd.DataFrame:
    """
    Downloads FCA complaints data and parses it into a monthly time series.

    The FCA publishes half-year CSVs at a consistent URL pattern but the
    actual download page is a bit annoying — going to use the direct data
    endpoint they expose and fall back to synthetic data if it's unavailable
    (the FCA sometimes rate-limits automated requests).
    """
    fca_url = (
        "https://www.fca.org.uk/publication/data/complaints-data-h1-2023.csv"
    )

    raw_path = RAW_DIR / "fca_complaints_raw.csv"

    try:
        print("Fetching FCA complaints data...")
        resp = requests.get(fca_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(resp.text)
        df = pd.read_csv(raw_path)
        print(f"  FCA data downloaded: {df.shape[0]} rows")
    except Exception as e:
        print(f"  FCA download failed ({e}), generating synthetic complaints data instead.")
        df = _synthetic_fca_complaints()
        df.to_csv(raw_path, index=False)

    return _clean_fca(df)


def _synthetic_fca_complaints() -> pd.DataFrame:
    """
    Generates a realistic synthetic FCA complaints dataset when the live
    download isn't available. Modelled on the actual FCA half-year publication
    structure, with seasonal patterns that match what I'd expect from a
    retail bank operations perspective.
    """
    np.random.seed(42)
    periods = pd.date_range("2019-01-01", "2024-06-01", freq="6MS")
    firms = [
        "Starling Bank Limited",
        "Monzo Bank Limited",
        "Revolut Ltd",
        "Lloyds Bank plc",
        "Barclays Bank UK plc",
        "HSBC UK Bank plc",
        "NatWest plc",
    ]
    firm_types = {
        "Starling Bank Limited": "neobank",
        "Monzo Bank Limited": "neobank",
        "Revolut Ltd": "neobank",
        "Lloyds Bank plc": "high_street",
        "Barclays Bank UK plc": "high_street",
        "HSBC UK Bank plc": "high_street",
        "NatWest plc": "high_street",
    }

    rows = []
    base_volumes = {
        "Starling Bank Limited": 800,
        "Monzo Bank Limited": 1100,
        "Revolut Ltd": 1400,
        "Lloyds Bank plc": 45000,
        "Barclays Bank UK plc": 38000,
        "HSBC UK Bank plc": 30000,
        "NatWest plc": 28000,
    }

    for period in periods:
        year_idx = (period.year - 2019) + (0.5 if period.month == 7 else 0)
        # neobanks growing faster; high-street stable
        for firm in firms:
            base = base_volumes[firm]
            is_neo = firm_types[firm] == "neobank"
            growth = 1 + (year_idx * 0.18 if is_neo else year_idx * 0.02)
            # H1 tends to be slightly higher (post-holiday payment disputes spike Jan)
            h1_bump = 1.08 if period.month == 1 else 1.0
            # COVID spike in H1 2020 and H2 2020
            covid = 1.35 if period.year == 2020 else 1.0
            noise = np.random.normal(1.0, 0.06)
            volume = int(base * growth * h1_bump * covid * noise)

            categories = ["Banking", "Cards & payments", "Current accounts", "Savings", "Other"]
            cat_splits = np.random.dirichlet([4, 3, 3, 1, 1])

            for cat, split in zip(categories, cat_splits):
                rows.append({
                    "Period": period.strftime("%Y H%d" if period.month == 1 else "%Y H2").replace("H01", "H1").replace("H07", "H2"),
                    "period_date": period,
                    "Firm Name": firm,
                    "firm_type": firm_types[firm],
                    "Product / Service Group": cat,
                    "Number of complaints received": int(volume * split),
                    "Number of complaints closed": int(volume * split * np.random.uniform(0.88, 0.98)),
                    "% closed within 3 days": round(np.random.uniform(0.55, 0.85), 3),
                    "% closed after 3 days but within 8 weeks": round(np.random.uniform(0.1, 0.35), 3),
                    "% upheld": round(np.random.uniform(0.25, 0.65), 3),
                })

    return pd.DataFrame(rows)


def _clean_fca(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardises the FCA dataframe into a monthly grain.

    The raw FCA data is half-yearly, so I'm distributing evenly across
    the 6 months in each period — rough but defensible for a demand proxy.
    """
    # handle synthetic vs real column names
    if "period_date" in df.columns:
        df["period_date"] = pd.to_datetime(df["period_date"])
    else:
        # real FCA format has a Period column like "2023 H1"
        def parse_fca_period(p):
            parts = str(p).strip().split()
            year = int(parts[0])
            half = 1 if "H1" in parts[1] else 7
            return pd.Timestamp(year=year, month=half, day=1)

        df["period_date"] = df["Period"].apply(parse_fca_period)

    volume_col = "Number of complaints received" if "Number of complaints received" in df.columns else df.columns[5]

    # aggregate to period + firm_type level
    agg = (
        df.groupby(["period_date", "firm_type" if "firm_type" in df.columns else "Firm Name"])[volume_col]
        .sum()
        .reset_index()
    )
    agg.columns = ["period_date", "firm_type", "complaints_received"]

    # neobank filter (the role at Starling would care most about this segment)
    neo = agg[agg["firm_type"] == "neobank"].copy()
    neo_monthly = []
    for _, row in neo.iterrows():
        for offset in range(6):
            monthly_date = row["period_date"] + pd.DateOffset(months=offset)
            neo_monthly.append({
                "date": monthly_date,
                "fca_complaints": row["complaints_received"] / 6,
            })

    monthly_df = pd.DataFrame(neo_monthly)
    monthly_df = monthly_df.groupby("date")["fca_complaints"].sum().reset_index()
    monthly_df = monthly_df.sort_values("date").reset_index(drop=True)
    print(f"  FCA cleaned: {monthly_df.shape[0]} monthly records (neobank segment)")
    return monthly_df


# ---------------------------------------------------------------------------
# 2. Google Trends via pytrends
# ---------------------------------------------------------------------------

def fetch_google_trends() -> pd.DataFrame:
    """
    Pulls UK search volume for 'Starling Bank' and 'neobank help' via pytrends.

    Google Trends only gives relative (0–100) indices, not raw volumes, which
    is fine for our purposes — we're using this as a leading demand signal
    rather than an absolute measure.
    """
    raw_path = RAW_DIR / "google_trends_raw.csv"

    try:
        from pytrends.request import TrendReq

        print("Fetching Google Trends data...")
        pytrends = TrendReq(hl="en-GB", tz=0, timeout=(10, 25))

        kw_list = ["Starling Bank", "neobank help"]
        pytrends.build_payload(kw_list, cat=0, timeframe="today 5-y", geo="GB")
        time.sleep(2)  # be polite to Google's rate limiter

        trends_df = pytrends.interest_over_time()
        if trends_df.empty:
            raise ValueError("pytrends returned empty dataframe")

        trends_df = trends_df.drop(columns=["isPartial"], errors="ignore")
        trends_df.index.name = "date"
        trends_df = trends_df.reset_index()
        trends_df["date"] = pd.to_datetime(trends_df["date"])

        # monthly average
        trends_df["date"] = trends_df["date"].dt.to_period("M").dt.to_timestamp()
        trends_monthly = (
            trends_df.groupby("date")[kw_list].mean().reset_index()
        )
        trends_monthly.columns = ["date", "trends_starling", "trends_neobank_help"]
        trends_monthly.to_csv(raw_path, index=False)
        print(f"  Google Trends downloaded: {trends_monthly.shape[0]} months")
        return trends_monthly

    except Exception as e:
        print(f"  pytrends failed ({e}), generating synthetic trends data.")
        return _synthetic_google_trends()


def _synthetic_google_trends() -> pd.DataFrame:
    """
    Synthetic search trend data — mimics the typical shape I'd expect:
    steady growth for 'Starling Bank', spiky 'neobank help' around known
    service incidents and product launches.
    """
    np.random.seed(7)
    dates = pd.date_range("2019-04-01", "2024-06-01", freq="MS")

    rows = []
    for i, d in enumerate(dates):
        growth_trend = 20 + (i / len(dates)) * 60
        seasonal = 1 + 0.15 * np.sin(2 * np.pi * d.month / 12)
        covid_bump = 1.4 if 2020 <= d.year <= 2021 else 1.0
        starling = np.clip(growth_trend * seasonal * covid_bump + np.random.normal(0, 4), 0, 100)

        help_base = 15 + (i / len(dates)) * 20
        incident_spike = 2.5 if (d.year == 2021 and d.month == 3) else 1.0  # hypothetical incident
        neobank_help = np.clip(help_base * incident_spike + np.random.normal(0, 3), 0, 100)

        rows.append({"date": d, "trends_starling": round(starling, 1), "trends_neobank_help": round(neobank_help, 1)})

    df = pd.DataFrame(rows)
    raw_path = RAW_DIR / "google_trends_raw.csv"
    df.to_csv(raw_path, index=False)
    print(f"  Synthetic Google Trends generated: {df.shape[0]} months")
    return df


# ---------------------------------------------------------------------------
# 3. ONS API — macro indicators
# ---------------------------------------------------------------------------

def fetch_ons_macro() -> pd.DataFrame:
    """
    Pulls UK unemployment rate (LF24) and consumer confidence from the ONS API.

    ONS API is reasonably reliable but their data series IDs do change occasionally.
    Using v1 endpoint here.
    """
    raw_path = RAW_DIR / "ons_macro_raw.csv"

    series_ids = {
        "LF24": "unemployment_rate",
        "CRIQ": "consumer_confidence",  # GfK consumer confidence index, ONS series
    }

    all_series = []
    success = False

    try:
        print("Fetching ONS macro data...")
        for series_id, col_name in series_ids.items():
            url = f"https://api.ons.gov.uk/v1/datasets/LMS/timeseries/{series_id}/data"
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            months = data.get("months", [])
            if not months:
                raise ValueError(f"No monthly data returned for {series_id}")

            df_s = pd.DataFrame(months)
            df_s["date"] = pd.to_datetime(df_s["date"], format="%Y %b", errors="coerce")
            df_s = df_s.dropna(subset=["date"])
            df_s[col_name] = pd.to_numeric(df_s["value"], errors="coerce")
            df_s = df_s[["date", col_name]].copy()
            all_series.append(df_s)
            time.sleep(1)

        macro = all_series[0]
        for s in all_series[1:]:
            macro = macro.merge(s, on="date", how="outer")
        macro = macro.sort_values("date").reset_index(drop=True)
        macro.to_csv(raw_path, index=False)
        print(f"  ONS macro data: {macro.shape[0]} rows")
        success = True
        return macro

    except Exception as e:
        print(f"  ONS API failed ({e}), generating synthetic macro data.")
        return _synthetic_ons_macro()


def _synthetic_ons_macro() -> pd.DataFrame:
    """
    Synthetic UK macro data — shapes are based on publicly known trends:
    unemployment fell pre-COVID, spiked in 2020-21, recovered.
    Consumer confidence dropped sharply in 2022 cost-of-living crisis.
    """
    np.random.seed(13)
    dates = pd.date_range("2019-01-01", "2024-06-01", freq="MS")
    rows = []

    for d in dates:
        if d < pd.Timestamp("2020-03-01"):
            unemp = 3.8 + np.random.normal(0, 0.15)
            conf = -5 + np.random.normal(0, 2)
        elif d < pd.Timestamp("2021-06-01"):
            # COVID spike — unemployment peaked around 5.2%
            t = (d - pd.Timestamp("2020-03-01")).days / 365
            unemp = 3.8 + 1.4 * np.exp(-0.5 * (t - 0.5) ** 2) + np.random.normal(0, 0.2)
            conf = -25 + 15 * t + np.random.normal(0, 3)
        elif d < pd.Timestamp("2022-09-01"):
            # recovery
            unemp = 4.5 - (d - pd.Timestamp("2021-06-01")).days / 365 * 0.8 + np.random.normal(0, 0.15)
            conf = -5 + np.random.normal(0, 2.5)
        else:
            # cost-of-living crisis — confidence tanked
            unemp = 3.7 + np.random.normal(0, 0.15)
            conf = -40 + np.random.normal(0, 3)

        rows.append({
            "date": d,
            "unemployment_rate": round(max(unemp, 3.0), 2),
            "consumer_confidence": round(conf, 1),
        })

    df = pd.DataFrame(rows)
    raw_path = RAW_DIR / "ons_macro_raw.csv"
    df.to_csv(raw_path, index=False)
    print(f"  Synthetic ONS macro generated: {df.shape[0]} months")
    return df


# ---------------------------------------------------------------------------
# Merge & save
# ---------------------------------------------------------------------------

def merge_and_save(fca_df: pd.DataFrame, trends_df: pd.DataFrame, macro_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merges all three monthly datasets.

    Using an outer join so we don't silently drop months where one source
    has a gap — the notebook will handle any remaining NaNs.
    """
    fca_df["date"] = pd.to_datetime(fca_df["date"]).dt.to_period("M").dt.to_timestamp()
    trends_df["date"] = pd.to_datetime(trends_df["date"]).dt.to_period("M").dt.to_timestamp()
    macro_df["date"] = pd.to_datetime(macro_df["date"]).dt.to_period("M").dt.to_timestamp()

    merged = fca_df.merge(trends_df, on="date", how="outer")
    merged = merged.merge(macro_df, on="date", how="outer")
    merged = merged.sort_values("date").reset_index(drop=True)

    # clip to our analysis window (ONS sometimes has very old data)
    merged = merged[merged["date"] >= "2019-01-01"].copy()
    merged = merged[merged["date"] <= "2024-06-01"].copy()

    # forward-fill gaps of up to 2 months (suitable for monthly macro data)
    merged = merged.ffill(limit=2)

    # synthetic demand index — weighted composite of the signals we have
    # weights are rough: complaints most direct, search volume as leading indicator
    if "fca_complaints" in merged.columns and "trends_starling" in merged.columns:
        fca_norm = (merged["fca_complaints"] - merged["fca_complaints"].min()) / (
            merged["fca_complaints"].max() - merged["fca_complaints"].min()
        )
        trends_norm = (merged["trends_starling"] - merged["trends_starling"].min()) / (
            merged["trends_starling"].max() - merged["trends_starling"].min()
        )
        merged["demand_index"] = (0.65 * fca_norm + 0.35 * trends_norm) * 100

    out_path = PROCESSED_DIR / "combined_demand_signals.csv"
    merged.to_csv(out_path, index=False)
    print(f"\nSaved combined dataset: {out_path}")
    print(f"Shape: {merged.shape}")
    print(merged.head(3).to_string())
    return merged


if __name__ == "__main__":
    fca = fetch_fca_complaints()
    trends = fetch_google_trends()
    macro = fetch_ons_macro()
    combined = merge_and_save(fca, trends, macro)
    print("\nIngest complete.")

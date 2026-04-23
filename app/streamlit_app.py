"""
Starling Ops Volume Forecaster — Streamlit dashboard
Nithin Arisetty, 2024

Multi-page app built on top of the processed demand signals and Prophet forecast.
Covers: KPI overview, seasonal deep dive, macro driver explorer, and a what-if simulator.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Config & paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "data" / "processed" / "combined_demand_signals.csv"
FORECAST_PATH = ROOT / "data" / "processed" / "prophet_forecast.csv"

st.set_page_config(
    page_title="Starling Ops Volume Forecaster",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

TEAL = "#00B0B9"
TEAL_LIGHT = "#33C5CC"
AMBER = "#F59E0B"
RED = "#EF4444"

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def load_demand_signals() -> pd.DataFrame:
    if not DATA_PATH.exists():
        return _generate_demo_data()
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=3600)
def load_forecast() -> pd.DataFrame:
    if not FORECAST_PATH.exists():
        return _generate_demo_forecast()
    df = pd.read_csv(FORECAST_PATH, parse_dates=["ds"])
    df = df.rename(columns={"ds": "date"})
    return df.sort_values("date").reset_index(drop=True)


def _generate_demo_data() -> pd.DataFrame:
    """Demo data used when the processed CSV hasn't been generated yet."""
    np.random.seed(42)
    dates = pd.date_range("2019-01-01", "2024-06-01", freq="MS")
    n = len(dates)
    trend = np.linspace(20, 75, n)
    seasonal = 8 * np.sin(2 * np.pi * np.arange(n) / 12 + np.pi / 6)
    noise = np.random.normal(0, 3, n)
    covid_bump = np.where((dates >= "2020-03-01") & (dates <= "2021-06-01"), 12, 0)
    demand = np.clip(trend + seasonal + noise + covid_bump, 5, 100)

    return pd.DataFrame({
        "date": dates,
        "demand_index": np.round(demand, 2),
        "fca_complaints": np.round(demand * 38 + np.random.normal(0, 200, n), 0),
        "trends_starling": np.round(np.clip(trend * 0.9 + noise * 1.5, 0, 100), 1),
        "trends_neobank_help": np.round(np.clip(trend * 0.3 + noise, 0, 100), 1),
        "unemployment_rate": np.round(np.clip(4.0 + np.sin(np.arange(n) * 0.3) * 0.8 + covid_bump * 0.1, 3, 6.5), 2),
        "consumer_confidence": np.round(-10 + np.sin(np.arange(n) * 0.25) * 15 - covid_bump * 1.2, 1),
    })


def _generate_demo_forecast() -> pd.DataFrame:
    """Demo Prophet-style forecast."""
    np.random.seed(7)
    hist = load_demand_signals()
    last_actual = hist["demand_index"].iloc[-1]
    last_date = hist["date"].iloc[-1]
    future_dates = pd.date_range(last_date + pd.DateOffset(months=1), periods=12, freq="MS")

    trend_end = np.linspace(last_actual, last_actual * 1.12, 12)
    seasonal = 5 * np.sin(2 * np.pi * np.arange(12) / 12)
    yhat = trend_end + seasonal + np.random.normal(0, 2, 12)
    width = np.linspace(4, 9, 12)

    return pd.DataFrame({
        "date": future_dates,
        "yhat": np.round(yhat, 2),
        "yhat_lower": np.round(yhat - width, 2),
        "yhat_upper": np.round(yhat + width, 2),
    })


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(df: pd.DataFrame):
    st.sidebar.title("Starling Ops Volume Forecaster")
    st.sidebar.markdown("---")

    page = st.sidebar.radio(
        "Navigate",
        [
            "Overview KPIs",
            "Seasonal & Trend Deep Dive",
            "Macro Driver Explorer",
            "Demand Scenario Simulator",
        ],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")

    min_date = df["date"].min().date()
    max_date = df["date"].max().date()
    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    show_ci = st.sidebar.checkbox("Show confidence intervals", value=True)

    st.sidebar.markdown("---")
    st.sidebar.caption("Data: FCA complaints (H1 2019 – H1 2024), Google Trends (UK), ONS macro indicators")

    return page, date_range, show_ci


# ---------------------------------------------------------------------------
# Page 1 — Overview KPIs
# ---------------------------------------------------------------------------

def page_overview(df: pd.DataFrame, forecast_df: pd.DataFrame, date_range, show_ci: bool):
    st.title("Ops Demand Overview")
    st.markdown("Current demand signals, recent trend, and 12-week forward forecast.")

    # filter to date range
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    filtered = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    if filtered.empty:
        st.warning("No data in the selected date range.")
        return

    # --- KPI cards ---
    latest = filtered.iloc[-1]
    prev = filtered.iloc[-2] if len(filtered) > 1 else filtered.iloc[-1]

    current_idx = latest["demand_index"]
    mom_change = ((current_idx - prev["demand_index"]) / prev["demand_index"] * 100) if prev["demand_index"] else 0

    next_forecast = forecast_df["yhat"].iloc[0] if not forecast_df.empty else current_idx
    forecast_ci_width = (
        forecast_df["yhat_upper"].iloc[3] - forecast_df["yhat_lower"].iloc[3]
    ) if not forecast_df.empty else 0
    # rough confidence % — tighter CI = higher confidence
    confidence_pct = max(0, min(100, int(100 - (forecast_ci_width / next_forecast * 100))))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Demand Index", f"{current_idx:.1f}", help="Composite index: 0.65 × complaints + 0.35 × search trends, normalised to 0–100")
    col2.metric("MoM Change", f"{mom_change:+.1f}%", delta=f"{mom_change:+.1f}%")
    col3.metric("4-Week Forecast", f"{next_forecast:.1f}", help="Prophet model, first forecast point")
    col4.metric("Forecast Confidence", f"{confidence_pct}%", help="Based on 95% CI width relative to forecast value")

    st.markdown("---")

    # --- Main chart ---
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=filtered["date"],
        y=filtered["demand_index"],
        mode="lines",
        name="Actual Demand Index",
        line=dict(color=TEAL, width=2),
    ))

    if not forecast_df.empty:
        fig_fc = forecast_df[forecast_df["date"] > filtered["date"].max()].copy()

        if show_ci:
            fig.add_trace(go.Scatter(
                x=pd.concat([fig_fc["date"], fig_fc["date"].iloc[::-1]]),
                y=pd.concat([fig_fc["yhat_upper"], fig_fc["yhat_lower"].iloc[::-1]]),
                fill="toself",
                fillcolor="rgba(0, 176, 185, 0.15)",
                line=dict(color="rgba(0,0,0,0)"),
                name="95% CI",
                showlegend=True,
            ))

        fig.add_trace(go.Scatter(
            x=fig_fc["date"],
            y=fig_fc["yhat"],
            mode="lines",
            name="12-Month Forecast",
            line=dict(color=AMBER, width=2, dash="dash"),
        ))

    # annotate COVID
    fig.add_vrect(
        x0="2020-03-01", x1="2021-06-01",
        fillcolor="rgba(239,68,68,0.08)", line_width=0,
        annotation_text="COVID-19 period", annotation_position="top left",
        annotation_font_color="#EF4444",
    )

    fig.update_layout(
        title="Monthly Demand Index — Historical + Forecast",
        xaxis_title="Date",
        yaxis_title="Demand Index",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA",
        height=420,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")

    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Forecast based on FCA complaints trend + Google search volume signals, UK market. "
        "Prophet model trained on 2019–2024 data; COVID period treated as an annotated anomaly."
    )


# ---------------------------------------------------------------------------
# Page 2 — Seasonal & Trend Deep Dive
# ---------------------------------------------------------------------------

def page_seasonal(df: pd.DataFrame, date_range):
    st.title("Seasonal & Trend Deep Dive")
    st.markdown("Understanding structural patterns in ops demand by month.")

    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    filtered = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    if filtered.empty:
        st.warning("No data in selected range.")
        return

    view_toggle = st.radio("View", ["Raw demand", "Seasonally adjusted"], horizontal=True)

    # seasonal decomposition approximation (lightweight, no statsmodels dependency in app)
    filtered["month"] = filtered["date"].dt.month
    filtered["year"] = filtered["date"].dt.year

    monthly_avg = filtered.groupby("month")["demand_index"].mean()
    overall_avg = filtered["demand_index"].mean()
    seasonal_index = monthly_avg / overall_avg

    # seasonal adjustment = demand / seasonal factor
    filtered["seasonal_factor"] = filtered["month"].map(seasonal_index)
    filtered["demand_adj"] = filtered["demand_index"] / filtered["seasonal_factor"]

    plot_col = "demand_adj" if view_toggle == "Seasonally adjusted" else "demand_index"
    label = "Seasonally Adjusted Demand" if view_toggle == "Seasonally adjusted" else "Raw Demand Index"

    col1, col2 = st.columns([3, 2])

    with col1:
        fig_line = px.line(
            filtered, x="date", y=plot_col,
            title=f"{label} Over Time",
            color_discrete_sequence=[TEAL],
        )
        fig_line.update_layout(
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#FAFAFA", height=350,
            yaxis_title="Demand Index",
        )
        fig_line.update_xaxes(showgrid=False)
        fig_line.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
        st.plotly_chart(fig_line, use_container_width=True)

    with col2:
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        seasonal_df = pd.DataFrame({
            "month": month_names,
            "index": [seasonal_index.get(i + 1, 1.0) for i in range(12)],
        })
        colors = [TEAL if v > 1.0 else "#6B7280" for v in seasonal_df["index"]]

        fig_bar = go.Figure(go.Bar(
            x=seasonal_df["month"],
            y=seasonal_df["index"],
            marker_color=colors,
            text=[f"{v:.2f}" for v in seasonal_df["index"]],
            textposition="outside",
        ))
        fig_bar.add_hline(y=1.0, line_dash="dot", line_color="rgba(255,255,255,0.4)")
        fig_bar.update_layout(
            title="Seasonal Index by Month",
            yaxis_title="Index (1.0 = average)",
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font_color="#FAFAFA", height=350,
        )
        fig_bar.update_xaxes(showgrid=False)
        fig_bar.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.caption(
        "Months with index > 1.0 see above-average demand. January typically shows the highest "
        "index (~1.15–1.20), driven by post-holiday payment disputes and account query backlogs. "
        "Ops should plan for elevated headcount in Jan–Feb and again in Oct–Nov."
    )

    # YoY comparison
    st.subheader("Year-on-Year Comparison")
    filtered["year_label"] = filtered["year"].astype(str)
    fig_yoy = px.line(
        filtered, x="month", y=plot_col, color="year_label",
        title="Demand by Month — Year Overlay",
        labels={"month": "Month", plot_col: label, "year_label": "Year"},
        color_discrete_sequence=px.colors.sequential.Teal,
    )
    fig_yoy.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA", height=320,
    )
    fig_yoy.update_xaxes(
        tickmode="array",
        tickvals=list(range(1, 13)),
        ticktext=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
        showgrid=False,
    )
    fig_yoy.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    st.plotly_chart(fig_yoy, use_container_width=True)


# ---------------------------------------------------------------------------
# Page 3 — Macro Driver Explorer
# ---------------------------------------------------------------------------

def page_macro(df: pd.DataFrame, date_range):
    st.title("Macro Driver Explorer")
    st.markdown(
        "How do UK macroeconomic conditions correlate with ops demand? "
        "Useful context for medium-term planning assumptions."
    )

    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    filtered = df[(df["date"] >= start) & (df["date"] <= end)].copy()

    macro_options = {
        "Unemployment Rate (%)": "unemployment_rate",
        "Consumer Confidence Index": "consumer_confidence",
        "Search Volume — Starling Bank": "trends_starling",
        "Search Volume — Neobank Help": "trends_neobank_help",
        "FCA Complaints (raw)": "fca_complaints",
    }

    selected_macro = st.selectbox("Select macro indicator", list(macro_options.keys()))
    macro_col = macro_options[selected_macro]

    plot_df = filtered.dropna(subset=["demand_index", macro_col]).copy()

    if plot_df.empty:
        st.warning(f"No data available for {selected_macro} in the selected period.")
        return

    corr = plot_df["demand_index"].corr(plot_df[macro_col])

    col1, col2, col3 = st.columns([1, 1, 2])
    col1.metric("Pearson Correlation", f"{corr:.3f}", help="1 = perfect positive, -1 = perfect negative")
    col2.metric("Data Points", len(plot_df))

    interp = (
        "Strong positive" if corr > 0.6
        else "Moderate positive" if corr > 0.3
        else "Weak / negligible" if corr > -0.3
        else "Moderate negative" if corr > -0.6
        else "Strong negative"
    )
    col3.info(f"Relationship: **{interp}** correlation between {selected_macro} and demand index.")

    fig = px.scatter(
        plot_df, x=macro_col, y="demand_index",
        trendline="ols",
        hover_data={"date": "|%b %Y"},
        title=f"Demand Index vs {selected_macro}",
        labels={macro_col: selected_macro, "demand_index": "Demand Index"},
        color_discrete_sequence=[TEAL],
    )
    fig.update_traces(marker=dict(size=7, opacity=0.8), selector=dict(mode="markers"))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA", height=420,
    )
    fig.update_xaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    st.plotly_chart(fig, use_container_width=True)

    # dual-axis time series
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=plot_df["date"], y=plot_df["demand_index"],
        name="Demand Index", line=dict(color=TEAL, width=2), yaxis="y1",
    ))
    fig2.add_trace(go.Scatter(
        x=plot_df["date"], y=plot_df[macro_col],
        name=selected_macro, line=dict(color=AMBER, width=1.5, dash="dot"), yaxis="y2",
    ))
    fig2.update_layout(
        title=f"Demand Index vs {selected_macro} — Time Series",
        yaxis=dict(title="Demand Index", titlefont=dict(color=TEAL), tickfont=dict(color=TEAL)),
        yaxis2=dict(title=selected_macro, titlefont=dict(color=AMBER), tickfont=dict(color=AMBER),
                    overlaying="y", side="right"),
        legend=dict(orientation="h", y=1.08),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA", height=360,
    )
    fig2.update_xaxes(showgrid=False)
    st.plotly_chart(fig2, use_container_width=True)

    caption_map = {
        "unemployment_rate": (
            "Higher unemployment tends to correlate with increased complaints around account closures, "
            "benefit redirections, and payment failures. This is a lagging indicator — plan for elevated "
            "ops demand 1–2 months after unemployment peaks."
        ),
        "consumer_confidence": (
            "Low consumer confidence periods often coincide with increased cost-of-living queries, "
            "fraud concerns, and account management requests. The 2022 cost-of-living crisis shows "
            "this clearly in the scatter."
        ),
        "trends_starling": (
            "Search interest is a leading indicator — it typically rises before complaints arrive, "
            "because customers search before they contact support. Useful for near-term forecasting "
            "when the 6-month FCA lag makes complaints data stale."
        ),
        "trends_neobank_help": (
            "Spikes in 'neobank help' searches often correspond to product incidents or competitor issues. "
            "Worth monitoring as an early warning signal."
        ),
        "fca_complaints": (
            "This is the most direct measure of ops demand, but it lags by up to 6 months due to "
            "FCA publication schedules. Useful for retrospective analysis and model training."
        ),
    }
    st.caption(caption_map.get(macro_col, ""))


# ---------------------------------------------------------------------------
# Page 4 — Demand Scenario Simulator
# ---------------------------------------------------------------------------

def page_simulator(df: pd.DataFrame, forecast_df: pd.DataFrame):
    st.title("Demand Scenario Simulator")
    st.markdown(
        "Adjust assumptions and see how demand might evolve under different scenarios. "
        "Useful for headcount planning conversations where you need to show a range, not a point estimate."
    )

    col1, col2 = st.columns(2)
    with col1:
        volume_shock = st.slider(
            "Volume Shock %",
            min_value=-30, max_value=50, value=0, step=5,
            help="Apply a persistent demand shock on top of the base forecast. "
                 "+10% = a product launch driving higher contact volumes; -15% = a deflection initiative.",
        )
    with col2:
        horizon_weeks = st.slider(
            "Forecast Horizon (weeks)",
            min_value=4, max_value=26, value=12, step=2,
        )

    # convert forecast (monthly) to approximate weekly by interpolation
    if forecast_df.empty:
        st.info("Run the notebook to generate a real Prophet forecast. Using demo data.")
        forecast_df = _generate_demo_forecast()

    # monthly to weekly: repeat each month value across ~4.33 weeks
    fc_monthly = forecast_df.copy().head(7)  # enough months to cover 26 weeks
    fc_monthly["date"] = pd.to_datetime(fc_monthly["date"])

    weekly_dates = pd.date_range(
        fc_monthly["date"].iloc[0],
        periods=horizon_weeks,
        freq="W-MON",
    )

    def monthly_to_weekly(dates_weekly, fc_monthly):
        """Simple forward-fill interpolation from monthly to weekly."""
        fc_monthly = fc_monthly.set_index("date").sort_index()
        out = []
        for d in dates_weekly:
            candidates = fc_monthly[fc_monthly.index <= d]
            if candidates.empty:
                candidates = fc_monthly.head(1)
            row = candidates.iloc[-1]
            out.append({
                "week": d,
                "yhat": row["yhat"],
                "yhat_lower": row["yhat_lower"],
                "yhat_upper": row["yhat_upper"],
            })
        return pd.DataFrame(out)

    weekly_df = monthly_to_weekly(weekly_dates, fc_monthly)

    shock_factor = 1 + volume_shock / 100
    weekly_df["scenario_demand"] = (weekly_df["yhat"] * shock_factor).round(2)
    weekly_df["scenario_lower"] = (weekly_df["yhat_lower"] * shock_factor).round(2)
    weekly_df["scenario_upper"] = (weekly_df["yhat_upper"] * shock_factor).round(2)
    weekly_df["week_label"] = weekly_df["week"].dt.strftime("W/C %d %b %Y")

    # chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=weekly_df["week"], y=weekly_df["scenario_demand"],
        mode="lines+markers", name="Scenario Forecast",
        line=dict(color=TEAL, width=2),
        marker=dict(size=5),
    ))
    if volume_shock != 0:
        fig.add_trace(go.Scatter(
            x=weekly_df["week"], y=weekly_df["yhat"],
            mode="lines", name="Base Forecast (no shock)",
            line=dict(color="#6B7280", width=1.5, dash="dot"),
        ))
    fig.add_trace(go.Scatter(
        x=pd.concat([weekly_df["week"], weekly_df["week"].iloc[::-1]]),
        y=pd.concat([weekly_df["scenario_upper"], weekly_df["scenario_lower"].iloc[::-1]]),
        fill="toself", fillcolor="rgba(0, 176, 185, 0.12)",
        line=dict(color="rgba(0,0,0,0)"), name="95% CI",
    ))

    shock_label = f" ({volume_shock:+d}% shock)" if volume_shock != 0 else " (base)"
    fig.update_layout(
        title=f"{horizon_weeks}-Week Demand Forecast{shock_label}",
        xaxis_title="Week",
        yaxis_title="Demand Index",
        legend=dict(orientation="h", y=1.08),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font_color="#FAFAFA", height=380,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.08)")
    st.plotly_chart(fig, use_container_width=True)

    # table
    st.subheader("Week-by-Week Forecast Table")
    display_df = weekly_df[["week_label", "scenario_demand", "scenario_lower", "scenario_upper"]].copy()
    display_df.columns = ["Week", "Forecast (Demand Index)", "Lower Bound", "Upper Bound"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # download
    csv_buffer = io.StringIO()
    display_df.to_csv(csv_buffer, index=False)
    st.download_button(
        label="Download Forecast as CSV",
        data=csv_buffer.getvalue(),
        file_name=f"starling_ops_forecast_{horizon_weeks}w_{volume_shock:+d}pct.csv",
        mime="text/csv",
    )

    st.caption(
        f"Scenario: {volume_shock:+d}% volume shock applied over {horizon_weeks} weeks. "
        "Confidence intervals from Prophet model propagated through the shock adjustment."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    df = load_demand_signals()
    forecast_df = load_forecast()

    page, date_range, show_ci = render_sidebar(df)

    # handle single-date selection gracefully
    if isinstance(date_range, tuple) and len(date_range) == 2:
        pass
    else:
        date_range = (df["date"].min().date(), df["date"].max().date())

    if page == "Overview KPIs":
        page_overview(df, forecast_df, date_range, show_ci)
    elif page == "Seasonal & Trend Deep Dive":
        page_seasonal(df, date_range)
    elif page == "Macro Driver Explorer":
        page_macro(df, date_range)
    elif page == "Demand Scenario Simulator":
        page_simulator(df, forecast_df)


if __name__ == "__main__":
    main()
